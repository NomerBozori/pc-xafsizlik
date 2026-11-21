"""Asosiy mantiq uchun testlar: python -m pytest tests -q  (yoki python tests/test_core.py)"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from xavfsizlik.camera import Camera  # noqa: E402
from xavfsizlik.config import Config  # noqa: E402
from xavfsizlik.monitor import Monitor  # noqa: E402
from xavfsizlik.storage import EventStore  # noqa: E402
from xavfsizlik.watcher import AttemptWatcher, parse_line, simulate_attempts  # noqa: E402


def make_cfg(tmp: Path) -> Config:
    return Config(
        threshold=3, window_seconds=60, cooldown_seconds=60,
        snapshot_dir=str(tmp / "snaps"),
        demo_dir=str(Path(__file__).resolve().parent.parent / "demo_assets"),
        simulate=True, burst_count=2, burst_delay=0.0,
    )


def test_parse_syslog_line():
    row = parse_line("Nov 21 03:14:07 laptop sshd[812]: Failed password for root from 10.0.0.5 port 55123 ssh2")
    assert row is not None
    assert row["user"] == "root"
    assert row["source"] == "10.0.0.5"
    assert row["ts"] is not None


def test_parse_iso_line():
    row = parse_line("2026-11-21T03:14:07+05:00 laptop sudo: pam_unix(sudo:auth): authentication failure; logname=u")
    assert row is not None
    assert row["ts"].year == 2026


def test_threshold_fires_once():
    with tempfile.TemporaryDirectory() as td:
        cfg = make_cfg(Path(td))
        fired = []
        w = AttemptWatcher(cfg, fired.append)
        for i in range(2):
            assert w.report_attempt(user="ali", source="10.0.0.9", raw=f"try{i}") is None
        ev = w.report_attempt(user="ali", source="10.0.0.9", raw="try2")
        assert ev is not None and ev["attempts"] >= 3
        assert w.report_attempt(user="ali", source="10.0.0.9", raw="try3") is None  # cooldown ichida
        assert w.snapshot_stats()["seen"] == 4


def test_full_pipeline_writes_photos():
    with tempfile.TemporaryDirectory() as td:
        cfg = make_cfg(Path(td))
        m = Monitor(cfg)
        simulate_attempts(m.watcher, count=4)
        rows = m.store.all()
        assert len(rows) == 1
        event = rows[0]
        assert len(event["photos"]) == 2
        for p in event["photos"]:
            assert (m.store.base / p["file"]).is_file()
        assert m.store.get(event["id"])["id"] == event["id"]


def test_photo_path_is_sandboxed():
    with tempfile.TemporaryDirectory() as td:
        store = EventStore(make_cfg(Path(td)))
        assert store.photo_path("../../etc/passwd") is None
        assert store.photo_path("yo'q.jpg") is None


def test_camera_without_demo_returns_false():
    with tempfile.TemporaryDirectory() as td:
        cfg = make_cfg(Path(td))
        cfg.simulate = False
        cfg.demo_dir = str(Path(td) / "bo'sh")
        cam = Camera(cfg)
        assert cam._capture_frame(Path(td) / "x.jpg") is False


def test_store_clear():
    with tempfile.TemporaryDirectory() as td:
        cfg = make_cfg(Path(td))
        m = Monitor(cfg)
        simulate_attempts(m.watcher, count=4)
        assert m.store.all()
        removed = m.store.clear()
        assert removed == 2
        assert m.store.all() == []


def test_status_shape():
    with tempfile.TemporaryDirectory() as td:
        m = Monitor(make_cfg(Path(td)))
        s = m.status()
        for key in ("armed", "camera", "stats", "threshold", "counters"):
            assert key in s




def test_live_log_file_triggers_capture():
    """Haqiqiy log faylga yozilgan xato urinishlar voqeani ishga tushirishi kerak."""
    import time
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        log = tmp / "auth.log"
        log.write_text("", encoding="utf-8")
        cfg = make_cfg(tmp)
        cfg.log_files = [str(log)]
        cfg.simulate = True
        cfg.burst_count = 2
        cfg.burst_delay = 0.0
        m = Monitor(cfg)
        m.arm()
        try:
            time.sleep(0.3)  # watcher boshlanishini kutish
            for i in range(cfg.threshold):
                with log.open("a", encoding="utf-8") as fh:
                    fh.write(f"Nov 21 03:14:0{i} laptop gdm-password]: "
                             f"gkr-pam: authentication failure for user ali\n")
                time.sleep(0.15)
            deadline = time.time() + 8
            while time.time() < deadline and not m.store.all():
                time.sleep(0.2)
            rows = m.store.all()
            assert rows, "log yozuvi voqeani ishga tushirmadi"
            assert rows[0]["photos"], "rasm olinmadi"
            assert "ali" in rows[0]["users"]
        finally:
            m.disarm()


def test_journal_line_formats():
    """turli jurnal formatlarini tanish."""
    cases = [
        ("2026-11-21T08:00:00+0500 host gdm-password]: gkr-pam: authentication failure for user nilufar", "nilufar"),
        ("Nov 21 08:00:00 host sudo: pam_unix(sudo:auth): authentication failure; logname=ali", "ali"),
        ("2026-11-21T08:00:00+0500 host sshd[9]: Failed password for invalid user hacker from 1.2.3.4 port 5 ssh2", "hacker"),
        ("2026-11-21T08:00:00+0500 host su: FAILED su for root by guest", None),
    ]
    for line, expected in cases:
        parsed = parse_line(line)
        assert parsed is not None, line
        if expected:
            assert parsed["user"] == expected, f"{line} → {parsed['user']}"

if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"✓ {name}")
            except AssertionError as exc:
                failures += 1
                print(f"✗ {name}: {exc}")
    raise SystemExit(1 if failures else 0)
