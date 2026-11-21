"""Parol urinishlarini kuzatish va voqealarga birlashtirish.

Ikki yo'l ishlaydi:
1. `watch_files()` — tizim jurnallari (auth.log, journal) yangi yozuvlarini o'qiydi.
2. `report_attempt()` — PAM yoki boshqa joydan to'g'ridan-to'g'ri xabar berilganda.
"""

from __future__ import annotations

import re
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Callable

from .config import Config

# syslog: "Nov 21 03:14:07 host sshd[123]: Failed password for root from 10.0.0.5 ..."
SYSLOG_RE = re.compile(r"^(?P<ts>[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+\S+\s+(?P<rest>.*)$")
ISO_RE = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)\S*\s+(?P<rest>.*)$")
# "for ali", "for invalid user hacker", "user=ali", "for user nilufar"
USER_RE = re.compile(
    r"(?:for (?:invalid[ ]+)?user\s+|for\s+|user[= ]\s*)(?P<user>[A-Za-z0-9_.\-\\$]+)",
    re.I,
)
# "FAILED su for root by guest" → birinchi ism (root) yoki "by" dan keyingisi
SU_BY_RE = re.compile(r"\bby\s+(?P<by>[A-Za-z0-9_.\-]+)", re.I)
SOURCE_RE = re.compile(r"from\s+(?P<src>[0-9a-fA-F:.]+)", re.I)


def default_log_candidates() -> list[Path]:
    return [
        Path("/var/lib/pc-xafsizlik/attempts.log"),
        Path("/var/log/auth.log"),
        Path("/var/log/secure"),
    ]


def parse_line(line: str) -> dict | None:
    line = line.rstrip("\n")
    if not line.strip():
        return None
    ts = None
    rest = line
    m = ISO_RE.match(line)
    if m:
        rest = m.group("rest")
        try:
            ts = datetime.fromisoformat(m.group("ts"))
        except ValueError:
            ts = None
    else:
        m = SYSLOG_RE.match(line)
        if m:
            rest = m.group("rest")
            try:
                ts = datetime.strptime(
                    f"{datetime.now().year} {m.group('ts')}", "%Y %b %d %H:%M:%S"
                )
            except ValueError:
                ts = None
    user = None
    source = None
    # "FAILED su for root by guest" → parolni kiritgan odam = guest
    bm = SU_BY_RE.search(rest)
    um = USER_RE.search(rest)
    if bm and "failed su" in rest.lower():
        user = bm.group("by")
    elif um:
        user = um.group("user")
    else:
        lm = re.search(r"logname=(?P<n>[A-Za-z0-9_.\-]+)", rest)
        if lm:
            user = lm.group("n")
    sm = SOURCE_RE.search(rest)
    if sm:
        source = sm.group("src")
    return {"ts": ts, "raw": line.strip(), "user": user, "source": source}


class AttemptWatcher:
    """Xato parol urinishlarini yig'adi va chegaradan oshsa callback chaqiradi."""

    def __init__(self, cfg: Config, on_event: Callable[[dict], None]):
        self.cfg = cfg
        self.on_event = on_event
        self._lock = threading.Lock()
        self._attempts: deque[dict] = deque(maxlen=500)
        self._last_event: float = 0.0
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._offsets: dict[Path, int] = {}
        self._grep_support: bool | None = None
        self.stats = {"seen": 0, "events": 0, "started_at": None, "sources": []}

    # ------------------------------------------------------------------ API
    def report_attempt(self, *, user: str = "noma'lum", source: str = "lokal", raw: str = "",
                       ts: datetime | None = None, kind: str = "password") -> dict | None:
        """Bitta xato urinish qayd etiladi. Chegara oshsa voqea qaytadi."""
        now = ts or datetime.now()
        item = {
            "at": now, "user": user or "noma'lum", "source": source or "lokal",
            "raw": raw, "kind": kind,
        }
        with self._lock:
            self.stats["seen"] += 1
            self._attempts.append(item)
            window_start = now.timestamp() - max(1, self.cfg.window_seconds)
            recent = [a for a in self._attempts if a["at"].timestamp() >= window_start]
            enough = len(recent) >= max(1, self.cfg.threshold)
            cooled = (now.timestamp() - self._last_event) >= self.cfg.cooldown_seconds
            if not (enough and cooled):
                return None
            self._last_event = now.timestamp()
            self.stats["events"] += 1
            event = {
                "detected_at": now.isoformat(timespec="seconds"),
                "attempts": len(recent),
                "window_seconds": self.cfg.window_seconds,
                "users": sorted({a["user"] for a in recent})[:8],
                "sources": sorted({a["source"] for a in recent if a["source"]})[:8],
                "first_attempt": recent[0]["at"].isoformat(timespec="seconds"),
                "last_attempt": recent[-1]["at"].isoformat(timespec="seconds"),
                "samples": [a["raw"] for a in recent if a["raw"]][-5:],
            }
        self.on_event(event)
        return event

    def recent(self, limit: int = 20) -> list[dict]:
        with self._lock:
            items = list(self._attempts)[-limit:]
        return [
            {**a, "at": a["at"].isoformat(timespec="seconds")}
            for a in reversed(items)
        ]

    def snapshot_stats(self) -> dict:
        with self._lock:
            return dict(self.stats)

    # --------------------------------------------------------------- watcher
    def _matches(self, line: str) -> bool:
        low = line.lower()
        return any(k.lower() in low for k in self.cfg.auth_log_keywords)

    def _log_paths(self) -> list[Path]:
        if self.cfg.log_files:
            return [Path(p) for p in self.cfg.log_files]
        paths = [p for p in default_log_candidates() if p.exists()]
        extra = getattr(self.cfg, "extra_log_file", "")
        if extra:
            ep = Path(extra)
            if ep.exists() and ep not in paths:
                paths.append(ep)
        return paths

    def _read_new(self, path: Path) -> list[str]:
        try:
            size = path.stat().st_size
        except OSError:
            return []
        offset = self._offsets.get(path, 0)
        if size < offset:  # log rotatsiya bo'lgan
            offset = 0
        if size == offset:
            return []
        try:
            with path.open("r", errors="replace") as fh:
                fh.seek(offset)
                chunk = fh.read(512 * 1024)
                self._offsets[path] = fh.tell()
        except OSError:
            return []
        return chunk.splitlines()

    def _poll_file(self, path: Path) -> None:
        for line in self._read_new(path):
            if not self._matches(line):
                continue
            parsed = parse_line(line)
            if not parsed:
                continue
            self.report_attempt(
                user=parsed["user"] or "noma'lum",
                source=parsed["source"] or str(path),
                raw=parsed["raw"],
                ts=parsed["ts"],
            )

    def _loop_files(self, paths: list[Path]) -> None:
        while not self._stop.is_set():
            for p in paths:
                self._poll_file(p)
            self._stop.wait(1.0)

    def _supports_grep(self) -> bool:
        """journalctl -g ni qo'llab-quvvatlaydimi (systemd >= 237)."""
        if self._grep_support is not None:
            return self._grep_support
        import subprocess
        try:
            out = subprocess.run(["journalctl", "--help"], capture_output=True,
                                 text=True, timeout=5).stdout
            self._grep_support = "--grep" in out or " -g " in out
        except (OSError, subprocess.SubprocessError):
            self._grep_support = False
        return self._grep_support

    def _loop_journal(self) -> None:
        """`journalctl -f` orqali tizim jurnalini kuzatish (asosiy manba)."""
        import subprocess
        base = ["journalctl", "-f", "-n", "0", "-o", "short-iso"]
        if self._supports_grep():
            pattern = "|".join(
                k.replace("(", r"\(").replace(")", r"\)").replace("|", r"\|")
                for k in self.cfg.auth_log_keywords
            )
            base += ["-g", pattern]

        while not self._stop.is_set():
            try:
                proc = subprocess.Popen(
                    base,
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                    bufsize=1,
                )
            except (FileNotFoundError, PermissionError):
                return
            try:
                assert proc.stdout is not None
                for line in proc.stdout:
                    if self._stop.is_set():
                        break
                    if self._matches(line):
                        parsed = parse_line(line)
                        if parsed:
                            self.report_attempt(
                                user=parsed["user"] or "noma'lum",
                                source=parsed["source"] or "journal",
                                raw=parsed["raw"],
                                ts=parsed["ts"],
                            )
            except (OSError, ValueError):
                pass
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
            self._stop.wait(5.0)

    def start(self) -> dict:
        self._stop.clear()
        self.stats["started_at"] = datetime.now().isoformat(timespec="seconds")

        # --- Windows: Security Event Log (4625) -----------------------
        from .windows_log import IS_WINDOWS, poll_loop  # mahalliy import
        if IS_WINDOWS:
            t = threading.Thread(
                target=poll_loop,
                args=(lambda row: self.report_attempt(
                    user=row["user"], source=row["source"], raw=row["raw"], ts=row["ts"],
                ), 8.0, self._stop.is_set),
                daemon=True, name="win-eventlog",
            )
            t.start()
            self._threads.append(t)
            self.stats["sources"] = ["Windows Security (4625)"]
            return {"watching": self.stats["sources"]}

        # --- Linux: journal (asosiy) + spool fayl ---------------------
        sources: list[str] = []
        import shutil as _sh
        has_journal = _sh.which("journalctl") is not None

        file_paths: list[Path] = []
        if not has_journal:
            # journal yo'q tizimlarda to'g'ridan-to'g'ri log fayllar
            file_paths = [p for p in (Path("/var/log/auth.log"), Path("/var/log/secure"),
                                      Path("/var/log/syslog")) if p.exists()]
            if self.cfg.log_files:
                file_paths = [Path(p) for p in self.cfg.log_files]
        elif self.cfg.log_files:
            file_paths = [Path(p) for p in self.cfg.log_files]

        # PAM/lock-screen urinishlari uchun spool fayl (har doim kuzatiladi)
        extra = getattr(self.cfg, "extra_log_file", "")
        if extra:
            ep = Path(extra)
            try:
                ep.parent.mkdir(parents=True, exist_ok=True)
                ep.touch(exist_ok=True)
            except OSError:
                pass  # root bo'lmasa yaratilmaydi — muhim emas
            if ep.exists() and ep not in file_paths:
                file_paths.append(ep)

        if has_journal:
            t = threading.Thread(target=self._loop_journal, daemon=True, name="log-journal")
            t.start()
            self._threads.append(t)
            sources.append("journalctl")

        if file_paths:
            for p in file_paths:
                try:
                    self._offsets[p] = p.stat().st_size
                except OSError:
                    self._offsets[p] = 0
            t = threading.Thread(target=self._loop_files, args=(file_paths,), daemon=True,
                                 name="log-files")
            t.start()
            self._threads.append(t)
            sources.extend(str(p) for p in file_paths)

        self.stats["sources"] = sources or ["hech qanday manba topilmadi"]
        return {"watching": self.stats["sources"]}

    def stop(self) -> None:
        self._stop.set()
        for t in self._threads:
            t.join(timeout=2)
        self._threads.clear()
        self.stats["started_at"] = None


def simulate_attempts(watcher: AttemptWatcher, count: int = 4, user: str = "user") -> list[dict]:
    """Demo uchun: ketma-ket xato urinishlar. Voqea(lar) qaytariladi."""
    fired = []
    for i in range(count):
        ev = watcher.report_attempt(
            user=user, source="192.168.1.15",
            raw=f"Failed password for {user} from 192.168.1.15 port 51{100 + i} ssh2",
            kind="password",
        )
        if ev:
            fired.append(ev)
        time.sleep(0.05)
    return fired
