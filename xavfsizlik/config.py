"""Sozlamalar — fayl, muhit o'zgaruvchilari va standart qiymatlar."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_NAME = "config.json"

DEFAULTS = {
    # Kamera
    "camera_index": 0,
    "capture_width": 1280,
    "capture_height": 720,
    "warmup_frames": 6,          # kamera "isishi" uchun tashlab yuboriladigan kadrlar
    "burst_count": 3,            # bitta voqeada nechta rasm
    "burst_delay": 0.8,          # rasmlar orasidagi soniya
    # Kuzatish
    "threshold": 3,              # nechta xato urinish "voqea" hisoblanadi
    "window_seconds": 120,       # shu vaqt ichidagi urinishlar bir voqeaga birlashadi
    "cooldown_seconds": 30,      # voqeadan keyin qayta rasmga olmaslik
    # Log manbalari (Linux). Bo'sh ro'yxat = avtomatik aniqlash.
    "log_files": [],
    "auth_log_keywords": [
        "Failed password",
        "authentication failure",
        "pam_unix(",
        "login failure",
        "Invalid user",
        "FAILED LOGIN",
    ],
    # Xatti-harakat
    "snapshot_dir": "snapshots",
    "retention_days": 30,
    "simulate": False,           # kamera yo'q muhitda demo rasmlar ishlatiladi
    "demo_dir": "demo_assets",
}

ENV_MAP = {
    "PCX_CAMERA_INDEX": ("camera_index", int),
    "PCX_THRESHOLD": ("threshold", int),
    "PCX_WINDOW": ("window_seconds", int),
    "PCX_COOLDOWN": ("cooldown_seconds", int),
    "PCX_SIMULATE": ("simulate", lambda v: v.strip().lower() in {"1", "true", "yes", "ha"}),
    "PCX_SNAPSHOT_DIR": ("snapshot_dir", str),
    "PCX_DEMO_DIR": ("demo_dir", str),
    "PCX_LOG_FILES": ("log_files", lambda v: [p.strip() for p in v.split(os.pathsep) if p.strip()]),
}


@dataclass
class Config:
    camera_index: int = DEFAULTS["camera_index"]
    capture_width: int = DEFAULTS["capture_width"]
    capture_height: int = DEFAULTS["capture_height"]
    warmup_frames: int = DEFAULTS["warmup_frames"]
    burst_count: int = DEFAULTS["burst_count"]
    burst_delay: float = DEFAULTS["burst_delay"]
    threshold: int = DEFAULTS["threshold"]
    window_seconds: int = DEFAULTS["window_seconds"]
    cooldown_seconds: int = DEFAULTS["cooldown_seconds"]
    log_files: list[str] = field(default_factory=list)
    auth_log_keywords: list[str] = field(default_factory=lambda: list(DEFAULTS["auth_log_keywords"]))
    snapshot_dir: str = DEFAULTS["snapshot_dir"]
    retention_days: int = DEFAULTS["retention_days"]
    simulate: bool = DEFAULTS["simulate"]
    demo_dir: str = DEFAULTS["demo_dir"]

    def resolve(self, p: str) -> Path:
        path = Path(p)
        return path if path.is_absolute() else ROOT / path

    @property
    def snapshots_path(self) -> Path:
        return self.resolve(self.snapshot_dir)

    @property
    def demo_path(self) -> Path:
        return self.resolve(self.demo_dir)

    def to_dict(self) -> dict:
        return asdict(self)


def load_config(path: Path | None = None) -> Config:
    """config.json → muhit o'zgaruvchilari ustunlik qiladi."""
    data = dict(DEFAULTS)
    cfg_path = path or ROOT / CONFIG_NAME
    if cfg_path.exists():
        try:
            data.update(json.loads(cfg_path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"config.json buzilgan: {exc}") from exc

    for env_key, (field_name, caster) in ENV_MAP.items():
        raw = os.environ.get(env_key)
        if raw is not None and raw != "":
            try:
                data[field_name] = caster(raw)
            except ValueError:
                raise SystemExit(f"{env_key} qiymati noto'g'ri: {raw!r}")

    allowed = set(Config.__dataclass_fields__)
    unknown = set(data) - allowed
    for key in unknown:
        data.pop(key)

    return Config(**{k: v for k, v in data.items() if k in allowed})


def write_default_config(target: Path | None = None) -> Path:
    target = target or ROOT / CONFIG_NAME
    if not target.exists():
        target.write_text(json.dumps(DEFAULTS, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target
