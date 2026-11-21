"""Monitor — kuzatuvchi, kamera va saqlashni bog'laydigan markaz."""

from __future__ import annotations

import threading
from datetime import datetime

from .camera import Camera, CameraError
from .config import Config
from .storage import EventStore
from .watcher import AttemptWatcher


class Monitor:
    """Qo'riqchi: xato urinishlar → voqea → rasm → jurnal."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.store = EventStore(cfg)
        self.camera = Camera(cfg)
        self.watcher = AttemptWatcher(cfg, self.handle_event)
        self.armed = False
        self._capture_lock = threading.Lock()
        self._busy = False
        self.last_error: str | None = None
        self.counters = {"events": 0, "photos": 0}

    # ------------------------------------------------------------------ mode
    def arm(self) -> dict:
        if self.armed:
            return self.status()
        info = self.watcher.start()
        self.armed = True
        return {**self.status(), "watching": info["watching"]}

    def disarm(self) -> dict:
        self.watcher.stop()
        self.camera.close()
        self.armed = False
        return self.status()

    # ---------------------------------------------------------- event handle
    def handle_event(self, event: dict) -> None:
        """Watcher chaqiradi. Rasmga olish alohida oqimda — kuzatuv to'xtamasin."""
        if self._busy:
            return
        self._busy = True
        try:
            shots: list[dict] = []
            error = None
            try:
                shots = self.camera.capture(
                    self.store.base,
                    event_ts=datetime.now(),
                    tag="urinish",
                )
            except CameraError as exc:
                error = str(exc)
            record = self.store.add(event, shots, error=error)
            self.counters["events"] += 1
            self.counters["photos"] += len(shots)
            self.last_error = error
        except Exception as exc:  # hech qachon kuzatuvni to'xtatmaymiz
            self.last_error = f"Voqeani yozishda xato: {exc}"
        finally:
            self._busy = False

    def trigger_test(self) -> dict:
        """Qo'lda sinov: hozir rasmga oladi (chegaradan qat'i nazar)."""
        with self._capture_lock:
            shots = self.camera.capture(self.store.base, event_ts=datetime.now(), tag="sinov")
            event = {
                "detected_at": datetime.now().isoformat(timespec="seconds"),
                "attempts": 0,
                "users": ["sinov"],
                "sources": ["qo'lda"],
                "samples": ["Qo'lda ishga tushirilgan sinov"],
            }
            record = self.store.add(event, shots)
            self.counters["photos"] += len(shots)
        return record

    # ----------------------------------------------------------------- status
    def status(self) -> dict:
        stats = self.watcher.snapshot_stats()
        return {
            "armed": self.armed,
            "camera": self.camera.describe(),
            "stats": stats,
            "threshold": self.cfg.threshold,
            "window_seconds": self.cfg.window_seconds,
            "cooldown_seconds": self.cfg.cooldown_seconds,
            "retention_days": self.cfg.retention_days,
            "counters": dict(self.counters),
            "last_error": self.last_error,
            "recent_attempts": self.watcher.recent(8),
            "snapshot_dir": str(self.store.base),
            "now": datetime.now().isoformat(timespec="seconds"),
        }
