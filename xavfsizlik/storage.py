"""Voqealarni saqlash: JSONL jurnal + rasmlar papkasi + tozalash."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path

from .config import Config


class EventStore:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.base = cfg.snapshots_path
        self.base.mkdir(parents=True, exist_ok=True)
        self.journal = self.base / "events.jsonl"
        self._lock = threading.Lock()

    # ----------------------------------------------------------------- write
    def add(self, event: dict, shots: list[dict], error: str | None = None) -> dict:
        record = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "detected_at": event.get("detected_at") or datetime.now().isoformat(timespec="seconds"),
            "attempts": event.get("attempts", 0),
            "window_seconds": event.get("window_seconds"),
            "users": event.get("users", []),
            "sources": event.get("sources", []),
            "first_attempt": event.get("first_attempt"),
            "last_attempt": event.get("last_attempt"),
            "samples": event.get("samples", []),
            "photos": shots,
            "error": error,
        }
        line = json.dumps(record, ensure_ascii=False)
        with self._lock:
            with self.journal.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        return record

    # ------------------------------------------------------------------ read
    def all(self, limit: int = 200) -> list[dict]:
        if not self.journal.exists():
            return []
        rows: list[dict] = []
        with self._lock:
            with self.journal.open("r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        rows.reverse()  # eng yangi birinchi
        return rows[:limit]

    def get(self, event_id: str) -> dict | None:
        for row in self.all(limit=10_000):
            if row.get("id") == event_id:
                return row
        return None

    def photo_path(self, filename: str) -> Path | None:
        """Xavfsiz yo'l: faqat snapshots papkasi ichidagi fayllar."""
        if not filename or "/" in filename or "\\" in filename or ".." in filename:
            return None
        path = self.base / filename
        return path if path.is_file() else None

    def clear(self) -> int:
        removed = 0
        for f in self.base.glob("*.jpg"):
            try:
                f.unlink()
                removed += 1
            except OSError:
                pass
        with self._lock:
            if self.journal.exists():
                self.journal.unlink()
        return removed

    # ------------------------------------------------------------- retention
    def purge_old(self) -> int:
        days = max(1, int(self.cfg.retention_days))
        cutoff = datetime.now() - timedelta(days=days)
        removed = 0
        for f in self.base.glob("*.jpg"):
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                if mtime < cutoff:
                    f.unlink()
                    removed += 1
            except OSError:
                pass
        # jurnalni ham qayta yozamiz
        if self.journal.exists():
            keep, changed = [], False
            for row in self.all(limit=10_000):
                try:
                    ts = datetime.fromisoformat(row.get("detected_at", ""))
                except ValueError:
                    keep.append(row)
                    continue
                if ts >= cutoff:
                    keep.append(row)
                else:
                    changed = True
            if changed:
                with self._lock:
                    with self.journal.open("w", encoding="utf-8") as fh:
                        for row in reversed(keep):
                            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return removed
