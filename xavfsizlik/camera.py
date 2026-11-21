"""Kamera qatlami: OpenCV → fswebcam → demo (simulyatsiya) tartibida ishlaydi."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from .config import Config

try:  # ixtiyoriy
    import cv2  # type: ignore
except Exception:  # pragma: no cover - muhitga bog'liq
    cv2 = None

try:  # rasmlarni vaqt tamg'asi bilan bezash uchun
    from PIL import Image, ImageDraw, ImageFont  # type: ignore
except Exception:  # pragma: no cover
    Image = ImageDraw = ImageFont = None


class CameraError(RuntimeError):
    pass


class Camera:
    """Rasmga olish uchun yagona interfeys."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._cap = None
        self._demo_files: list[Path] = []
        self._demo_cursor = 0
        self._burst_source: Path | None = None
        self._burst_index = 0
        self.probe_info: dict = {}

    # ------------------------------------------------------------------ info
    @property
    def backend(self) -> str:
        if self.cfg.simulate:
            return "simulate"
        if cv2 is not None:
            return "opencv"
        if shutil.which("fswebcam"):
            return "fswebcam"
        return "yo'q"

    def probe(self) -> dict:
        """Haqiqiy qurilma javob beradimi? Natija `probe_info` da ham saqlanadi."""
        if self.cfg.simulate:
            self.probe_info = {"ok": True, "backend": "simulate", "note": "demo rejim"}
            return self.probe_info
        if cv2 is not None:
            cap = cv2.VideoCapture(self.cfg.camera_index)
            opened = cap.isOpened()
            frame_ok = False
            if opened:
                for _ in range(10):
                    ok, frame = cap.read()
                    if ok and frame is not None:
                        frame_ok = True
                        break
            cap.release()
            if frame_ok:
                self.probe_info = {"ok": True, "backend": "opencv"}
            elif opened:
                self.probe_info = {
                    "ok": False, "backend": "opencv",
                    "note": f"/dev/video{self.cfg.camera_index} ochildi, lekin kadr kelmadi "
                            f"(kamera band yoki haydovchi muammosi)",
                }
            else:
                self.probe_info = {
                    "ok": False, "backend": "opencv",
                    "note": f"/dev/video{self.cfg.camera_index} topilmadi yoki ochilmadi",
                }
            return self.probe_info
        if shutil.which("fswebcam"):
            return {"ok": True, "backend": "fswebcam"}
        return {"ok": False, "backend": "yo'q", "note": "kamera kutubxonasi o'rnatilmagan"}

    def describe(self) -> dict:
        return {
            "backend": self.backend,
            "camera_index": self.cfg.camera_index,
            "resolution": f"{self.cfg.capture_width}x{self.cfg.capture_height}",
            "simulate": self.cfg.simulate,
            "probe": self.probe_info,
        }

    # ------------------------------------------------------------- open/close
    def _open(self):
        if self.cfg.simulate or cv2 is None:
            return None
        if self._cap is not None:
            return self._cap
        cap = cv2.VideoCapture(self.cfg.camera_index)
        if not cap.isOpened():
            cap.release()
            return None
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg.capture_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg.capture_height)
        for _ in range(max(0, self.cfg.warmup_frames)):
            cap.read()
        self._cap = cap
        return cap

    def close(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            finally:
                self._cap = None

    # --------------------------------------------------------------- helpers
    def _demo_pool(self) -> list[Path]:
        if not self._demo_files:
            folder = self.cfg.demo_path
            if folder.is_dir():
                self._demo_files = sorted(
                    p for p in folder.iterdir()
                    if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
                )
        return self._demo_files

    def _add_watermark(self, path: Path, label: str) -> None:
        """Rasmning pastki o'ng burchagiga vaqt tamg'asini yozish."""
        if Image is None or ImageDraw is None:
            return
        try:
            with Image.open(path) as img:
                img = img.convert("RGB")
                draw = ImageDraw.Draw(img)
                try:
                    font = ImageFont.truetype("DejaVuSans.ttf", max(16, img.width // 48))
                except Exception:
                    font = ImageFont.load_default()
                pad = 10
                bbox = draw.textbbox((0, 0), label, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                x = img.width - tw - pad * 2
                y = img.height - th - pad * 2
                draw.rectangle([x, y, img.width, img.height], fill=(0, 0, 0))
                draw.text((x + pad, y + pad // 2), label, fill=(255, 255, 255), font=font)
                img.save(path, "JPEG", quality=88)
        except Exception:
            pass  # tamg'a qo'shilmagani uchun rasm yo'qolmasin

    # -------------------------------------------------------------- capture
    def capture(self, target_dir: Path, *, event_ts: datetime, tag: str = "intruder") -> list[dict]:
        """Bir voqea uchun `burst_count` ta rasm oladi va metadata qaytaradi."""
        target_dir.mkdir(parents=True, exist_ok=True)
        made: list[dict] = []
        backend = self.backend
        # demo rejimda bitta sahna tanlanadi — kadrlar ketma-ket "burst"ga o'xshasin
        self._burst_source = self._pick_demo_source() if self.cfg.simulate else None
        self._burst_index = 0
        self.probe_info: dict = {}

        for i in range(max(1, self.cfg.burst_count)):
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
            filename = f"{tag}_{stamp}_{i + 1}.jpg"
            path = target_dir / filename

            ok = self._capture_frame(path)
            if not ok:
                continue

            label = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._add_watermark(path, label)
            made.append({
                "file": filename,
                "taken_at": datetime.now().isoformat(timespec="seconds"),
                "event_at": event_ts.isoformat(timespec="seconds"),
                "backend": backend,
                "size_bytes": path.stat().st_size,
            })

            if i + 1 < self.cfg.burst_count and self.cfg.burst_delay:
                import time
                time.sleep(self.cfg.burst_delay)

        if not made:
            hint = ""
            if cv2 is not None and not self.cfg.simulate:
                hint = (f" · video{self.cfg.camera_index} ochilmadi yoki kadr bermadi."
                        " Kamerani boshqa dastur (Zoom/Meet/Chrome) band qilgan bo'lishi mumkin.")
            raise CameraError("Rasm olishning iloji bo'lmadi." + hint)
        return made

    def _pick_demo_source(self) -> Path | None:
        pool = self._demo_pool()
        if not pool:
            return None
        src = pool[self._demo_cursor % len(pool)]
        self._demo_cursor += 1
        return src

    def _demo_variant(self, src: Path, path: Path, index: int) -> bool:
        """Bir xil sahnadan yengil farqli kadr: mayda zoom + yorqinlik jitteri."""
        try:
            import random
            if Image is not None:
                with Image.open(src) as img:
                    img = img.convert("RGB")
                    w, h = img.size
                    zoom = 1.0 + 0.012 * index + random.uniform(-0.004, 0.004)
                    cw, ch = int(w / zoom), int(h / zoom)
                    left = (w - cw) // 2 + random.randint(-6, 6)
                    top = (h - ch) // 2 + random.randint(-6, 6)
                    left = max(0, min(w - cw, left))
                    top = max(0, min(h - ch, top))
                    crop = img.crop((left, top, left + cw, top + ch)).resize((w, h))
                    factor = 1.0 + random.uniform(-0.03, 0.03)
                    crop = crop.point(lambda v: max(0, min(255, int(v * factor))))
                    crop.save(path, "JPEG", quality=88)
                    return True
            shutil.copyfile(src, path)
            return True
        except Exception:
            return False

    def _capture_frame(self, path: Path) -> bool:
        # 1) OpenCV
        cap = self._open()
        if cap is not None:
            for _ in range(3):  # bir necha urinish: ba'zi kameralar birinchi kadrni bermaydi
                ok, frame = cap.read()
                if ok and frame is not None:
                    try:
                        cv2.imwrite(str(path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                        return path.exists()
                    except Exception:
                        break
            self.close()

        # 2) fswebcam
        if not self.cfg.simulate and shutil.which("fswebcam"):
            try:
                with tempfile.TemporaryDirectory() as td:
                    tmp = Path(td) / "shot.jpg"
                    cmd = [
                        "fswebcam", "-q", "-d", f"/dev/video{self.cfg.camera_index}",
                        "-r", f"{self.cfg.capture_width}x{self.cfg.capture_height}",
                        "--no-banner", str(tmp),
                    ]
                    proc = subprocess.run(cmd, capture_output=True, timeout=15)
                    if proc.returncode == 0 and tmp.exists():
                        shutil.copyfile(tmp, path)
                        return True
            except Exception:
                pass

        # 3) Demo (faqat simulyatsiya rejimida)
        if not self.cfg.simulate:
            return False
        src = getattr(self, "_burst_source", None) or self._pick_demo_source()
        if src is None:
            return False
        index = getattr(self, "_burst_index", 0)
        self._burst_index = index + 1
        return self._demo_variant(src, path, index)

    # ------------------------------------------------------------------ test
    def selftest(self) -> dict:
        """Sozlamani tekshirish: bitta sinov kadri olib, darhol o'chiradi."""
        target = self.cfg.snapshots_path / ".selftest"
        try:
            shots = self.capture(target, event_ts=datetime.now(), tag="selftest")
            for s in shots:
                (target / s["file"]).unlink(missing_ok=True)
            return {"ok": True, "backend": self.backend, "shots": len(shots)}
        except CameraError as exc:
            return {"ok": False, "backend": self.backend, "error": str(exc)}


class EventCamera(Camera):
    """Kamera qurilmasini voqealar orasida ochiq ushlab turadigan variant.

    Ba'zi noutbuklarda kamera sovuq holda ochilishi 1–2 soniya oladi;
    shu sababli qurilma doimo tayyor turadi.
    """

    def warm(self) -> bool:
        return self._open() is not None
