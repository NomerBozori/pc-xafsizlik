"""Diagnostika: o'rnatishdan keyin hamma narsa ishlayaptimi-yo'qmi tekshirish.

    python app.py --doctor

Natija: ✅ / ⚠️ / ❌ bilan ro'yxat va oxirida haqiqiy sinov kadri.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .config import Config


def _ok(msg: str) -> str:
    return f"  ✅ {msg}"


def _warn(msg: str) -> str:
    return f"  ⚠️  {msg}"


def _bad(msg: str) -> str:
    return f"  ❌ {msg}"


def _service_state() -> tuple[bool, str]:
    if not shutil.which("systemctl"):
        return False, "systemctl yo'q"
    try:
        active = subprocess.run(["systemctl", "is-active", "pc-xavfsizlik"],
                                capture_output=True, text=True, timeout=5).stdout.strip()
        enabled = subprocess.run(["systemctl", "is-enabled", "pc-xavfsizlik"],
                                 capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return False, "systemctl javob bermadi"
    return active == "active", f"{active or 'noma’lum'} / {enabled or 'noma’lum'}"


def run_doctor(cfg: Config) -> int:
    problems = 0
    print("\n=== PC Xavfsizlik — diagnostika ===\n")

    # ---------------------------------------------------------------- tizim
    print("Tizim:")
    print(_ok(f"{platform.system()} {platform.release()} · Python {platform.python_version()}"))
    if os.name != "nt" and os.geteuid() != 0:
        print(_warn("root emas — /var/log/auth.log o'qilmasligi mumkin (sudo bilan ishga tushiring)"))

    # --------------------------------------------------------------- kamera
    print("\nKamera:")
    try:
        from .camera import Camera
        cam = Camera(cfg)
        backend = cam.backend
        probe = cam.probe()
        if cfg.simulate:
            print(_warn("simulyatsiya rejimi (PCX_SIMULATE=1) — demo rasmlar ishlatiladi"))
        elif probe.get("ok"):
            print(_ok(f"kamera javob berdi: {probe.get('backend')}"))
        elif backend == "yo'q":
            print(_bad("kamera kutubxonasi topilmadi"))
            print("     O'rnatish: sudo apt install python3-opencv   yoki")
            print("                sudo apt install fswebcam")
            problems += 1
        else:
            print(_bad(f"kamera mavjud, lekin javob bermayapti: {probe.get('note')}"))
            print("     • Kamerani boshqa dasturlar (Zoom, Meet, Chrome) yopib qo'ying")
            print("     • Boshqa qurilma indeksini sinab ko'ring: config.json → camera_index: 1")
            problems += 1

        if probe.get("ok"):
            result = cam.selftest()
            if result.get("ok"):
                print(_ok(f"sinov kadri olindi ({result['shots']} ta)"))
            else:
                print(_bad(f"sinov kadri olinmadi: {result.get('error')}"))
                problems += 1
        print(f"     qurilma: video{cfg.camera_index} · {cfg.capture_width}x{cfg.capture_height}")
    except Exception as exc:  # noqa: BLE001
        print(_bad(f"kamera tekshiruvida xato: {exc}"))
        problems += 1

    # ---------------------------------------------------------------- jurnal
    print("\nJurnal manbalari:")
    if os.name == "nt":
        try:
            from .windows_log import read_failed_logons
            rows = read_failed_logons(max_records=3)
            print(_ok(f"Windows Security Event Log o'qildi ({len(rows)} ta oxirgi 4625)"))
        except Exception as exc:  # noqa: BLE001
            print(_bad(f"Event Log o'qilmadi: {exc}"))
            print("     Administrator sifatida ishga tushiring.")
            problems += 1
    else:
        candidates = [Path("/var/log/auth.log"), Path("/var/log/secure"), Path("/var/log/syslog")]
        found = []
        for path in candidates:
            if path.exists():
                readable = os.access(path, os.R_OK)
                found.append(path)
                print((_ok if readable else _bad)(f"{path} {'o‘qiladi' if readable else 'o‘qish taqiqlangan'}"))
                if not readable:
                    problems += 1
        if not found:
            print(_warn("auth.log topilmadi — journalctl ishlatiladi"))
        has_journal = shutil.which("journalctl") is not None
        print((_ok if has_journal else _warn)(f"journalctl: {'bor' if has_journal else 'yo‘q'}"))
        if has_journal:
            try:
                help_txt = subprocess.run(["journalctl", "--help"], capture_output=True,
                                          text=True, timeout=5).stdout
                supports_g = "--grep" in help_txt or " -g " in help_txt
                print((_ok if supports_g else _warn)(
                    "journalctl filtri (-g) " + ("qo'llab-quvvatlanadi" if supports_g else "yo'q — barcha yozuvlar o'qiladi")))
            except (OSError, subprocess.SubprocessError):
                pass

    # ---------------------------------------------------------------- xizmat
    print("\nTizim xizmati:")
    if os.name == "nt":
        try:
            out = subprocess.run(["schtasks", "/query", "/tn", "PCXavfsizlik"],
                                 capture_output=True, text=True, timeout=10).stdout
            if "PCXavfsizlik" in out:
                print(_ok("vazifa ro'yxatdan o'tgan (schtasks: PCXavfsizlik)"))
            else:
                print(_warn("vazifa topilmadi — install-windows.bat ni Administrator sifatida ishga tushiring"))
        except (OSError, subprocess.SubprocessError):
            print(_warn("schtasks tekshirilmadi"))
    else:
        active, detail = _service_state()
        print((_ok if active else _warn)(f"pc-xavfsizlik: {detail}"))
        if not active:
            print("     Yoqish: sudo systemctl enable --now pc-xavfsizlik")

    # ----------------------------------------------------------- sozlamalar
    print("\nSozlamalar:")
    print(_ok(f"chegara: {cfg.threshold} urinish / {cfg.window_seconds} s · sovish {cfg.cooldown_seconds} s"))
    print(_ok(f"saqlash: {cfg.snapshots_path} ({cfg.retention_days} kun)"))

    # --------------------------------------------------- end-to-end sinov
    print("\nEnd-to-end sinov (3 ta soxta urinish):")
    try:
        from .monitor import Monitor
        from .watcher import simulate_attempts
        mon = Monitor(cfg)
        before = len(mon.store.all())
        simulate_attempts(mon.watcher, count=max(3, cfg.threshold), user="__doctor__")
        after = mon.store.all()
        if len(after) > before:
            rec = after[0]
            photos = rec.get("photos", [])
            if photos:
                print(_ok(f"voqea yaratildi, {len(photos)} ta rasm saqlandi"))
                for p in photos:
                    print(f"     {mon.store.base / p['file']}")
            else:
                print(_bad(f"voqea yaratildi, lekin rasm olinmadi: {rec.get('error')}"))
                problems += 1
        else:
            print(_bad("voqea yaratilmadi — threshold sozlamasini tekshiring"))
            problems += 1
    except Exception as exc:  # noqa: BLE001
        print(_bad(f"sinovda xato: {exc}"))
        problems += 1

    # --------------------------------------------------------------- yakun
    print("\n" + "=" * 44)
    if problems == 0:
        print("✅ Hammasi tayyor. Dashboard: http://127.0.0.1:8000\n")
    else:
        print(f"⚠️  {problems} ta muammo topildi — yuqoridagi maslahatlarga qarang.\n")
    return 0 if problems == 0 else 1
