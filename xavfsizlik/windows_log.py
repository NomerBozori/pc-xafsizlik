"""Windows: kirish/parol hodisalarini Windows Event Log'dan o'qish.

Windows'da Linux'dagi auth.log yo'q. Unga o'xshash ma'lumot quyidagi
jurnallarda bo'ladi:

  4625  — "An account failed to log on"  (parol xato yoki login rad etildi)
  4624  — muvaffaqiyatli kirish (bizni qiziqtirmaydi, lekin log uchun)
  4800/4801 — ekran qulflandi/ochildi

Bu modul faqat Windows'da ishlaydi. `win32evtlog` (pywin32) bo'lmasa,
`wevtutil` orqali jurnal o'qiladi.
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime
from typing import Callable

IS_WINDOWS = sys.platform.startswith("win")

# "TargetUserName:      admin" kabi qatorlardan foydalanuvchini ajratish
_XML_DATA_RE = re.compile(
    r'<Data Name="(?P<name>TargetUserName|IpAddress|WorkstationName)">(?P<val>[^<]*)</Data>',
    re.I,
)


def read_failed_logons(max_records: int = 20) -> list[dict]:
    """Windows Security jurnalidan oxirgi 4625 yozuvlarini o'qish.

    Eslatma: Security jurnalini o'qish uchun Administrator huquqi kerak.
    """
    if not IS_WINDOWS:
        return []
    cmd = [
        "wevtutil", "qe", "Security",
        "/q:*[System[(EventID=4625)]]",
        f"/c:{max_records}", "/rd:true", "/f:xml",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError):
        return []
    if proc.returncode != 0:
        return []

    out: list[dict] = []
    for block in proc.stdout.split("<Event ")[1:]:
        data = {m.group("name").lower(): m.group("val")
                for m in _XML_DATA_RE.finditer(block)}
        ts_m = re.search(r"<TimeCreated SystemTime='([^']+)'", block)
        ts = None
        if ts_m:
            try:
                ts = datetime.fromisoformat(ts_m.group(1).replace("Z", "+00:00"))
            except ValueError:
                ts = None
        out.append({
            "user": data.get("targetusername") or "noma'lum",
            "source": data.get("ipaddress") or data.get("workstationname") or "lokal",
            "ts": ts,
            "raw": f"Windows 4625: foydalanuvchi={data.get('targetusername', '?')} "
                   f"manba={data.get('ipaddress') or data.get('workstationname') or 'lokal'}",
        })
    return out


def poll_loop(on_attempt: Callable[[dict], None], interval: float = 10.0,
              stop: Callable[[], bool] = lambda: False) -> None:
    """Yangi 4625 yozuvlarini kuzatib, `on_attempt`ni chaqirib turadi."""
    import time
    seen: set[str] = set()
    # boshlanishida mavjudlarini "ko'rilgan" deb belgilaymiz
    for row in read_failed_logons(max_records=50):
        seen.add(row["raw"])
    while not stop():
        for row in read_failed_logons(max_records=20):
            key = row["raw"]
            if key in seen:
                continue
            seen.add(key)
            on_attempt(row)
        time.sleep(interval)
