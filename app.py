#!/usr/bin/env python3
"""PC Xavfsizlik — parol urinishlarini kamera bilan qayd etuvchi veb-dashboard.

Ishga tushirish:
    .venv/bin/python app.py

Brauzerda: http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from flask import (
    Flask, abort, jsonify, render_template, request, send_from_directory,
)

from xavfsizlik.camera import CameraError
from xavfsizlik.config import load_config, write_default_config
from xavfsizlik.monitor import Monitor
from xavfsizlik.watcher import parse_line, simulate_attempts

BASE_DIR = Path(__file__).resolve().parent


def create_app(cfg) -> Flask:
    app = Flask(__name__, template_folder=str(BASE_DIR / "templates"),
                static_folder=str(BASE_DIR / "static"))
    app.config["JSON_AS_ASCII"] = False
    monitor = Monitor(cfg)
    app.extensions["monitor"] = monitor

    # ------------------------------------------------------------------ pages
    @app.get("/")
    def index():
        return render_template("index.html", cfg=cfg)

    # -------------------------------------------------------------------- api
    @app.get("/api/status")
    def api_status():
        return jsonify(monitor.status())

    @app.get("/api/events")
    def api_events():
        limit = min(int(request.args.get("limit", 100)), 500)
        rows = monitor.store.all(limit=limit)
        return jsonify({"count": len(rows), "events": rows})

    @app.post("/api/arm")
    def api_arm():
        if not monitor.armed:
            info = monitor.watcher.start()
            monitor.armed = True
            return jsonify({"ok": True, "armed": True, "watching": info["watching"]})
        return jsonify({"ok": True, "armed": True})

    @app.post("/api/disarm")
    def api_disarm():
        monitor.disarm()
        return jsonify({"ok": True, "armed": False})

    @app.post("/api/test")
    def api_test():
        try:
            record = monitor.trigger_test()
        except CameraError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 503
        return jsonify({"ok": True, "event": record, "status": monitor.status()})

    @app.post("/api/selftest")
    def api_selftest():
        return jsonify(monitor.camera.selftest())

    @app.post("/api/simulate")
    def api_simulate():
        """Demo: soxta parol urinishlari. Chegaradan oshsa rasm olinadi."""
        body = request.get_json(silent=True) or {}
        count = int(body.get("count", max(cfg.threshold, 4)))
        user = str(body.get("user") or "user")
        fired = simulate_attempts(monitor.watcher, count=count, user=user)
        return jsonify({"ok": True, "attempts": count, "events": fired,
                        "status": monitor.status()})

    @app.delete("/api/events")
    def api_clear():
        removed = monitor.store.clear()
        monitor.counters.update({"events": 0, "photos": 0})
        return jsonify({"ok": True, "removed_photos": removed})

    @app.post("/api/report")
    def api_report():
        """Tashqi vosita (PAM hook, skript) xato urinish haqida xabar beradi.

        JSON: {"user": "ali", "source": "login-ekran", "raw": "..."}
        Yoki text/plain: bitta qator.
        """
        body = request.get_json(silent=True)
        if isinstance(body, dict):
            user = str(body.get("user") or "noma'lum")
            source = str(body.get("source") or "lokal")
            raw = str(body.get("raw") or "")
        else:
            line = (request.get_data(as_text=True) or "").strip()
            parsed = parse_line(line) if line else None
            user = (parsed or {}).get("user") or "noma'lum"
            source = (parsed or {}).get("source") or "lokal"
            raw = line
        event = monitor.watcher.report_attempt(user=user, source=source, raw=raw)
        return jsonify({"ok": True, "event_fired": event is not None})

    # Mahalliy (loopback) manzilgina — tashqi tarmoqdan yopiq
    @app.before_request
    def local_only():
        if request.remote_addr not in {"127.0.0.1", "::1", None}:
            return jsonify({"error": "faqat lokal manzildan"}), 403
        return None

    @app.post("/api/purge")
    def api_purge():
        return jsonify({"ok": True, "removed": monitor.store.purge_old()})

    @app.get("/api/events/<event_id>/photos/<filename>")
    def api_photo(event_id: str, filename: str):
        record = monitor.store.get(event_id)
        if not record or not any(p["file"] == filename for p in record.get("photos", [])):
            abort(404)
        return send_from_directory(monitor.store.base, filename, mimetype="image/jpeg")

    # ------------------------------------------------------------------ misc
    @app.after_request
    def no_cache(resp):
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    return app


def parse_args():
    p = argparse.ArgumentParser(description="PC Xavfsizlik dashboard")
    p.add_argument("--host", default=os.environ.get("PCX_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("PCX_PORT", "8000")))
    p.add_argument("--debug", action="store_true")
    p.add_argument("--arm", action="store_true", help="ishga tushganda darhol qo'riqlashni yoqish")
    p.add_argument("--init-config", action="store_true", help="config.json namunasi yaratish")
    p.add_argument("--doctor", action="store_true", help="o'rnatishni tekshirish (diagnostika)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.init_config:
        path = write_default_config()
        print(f"Namuna sozlama yozildi: {path}")
        return

    cfg = load_config()
    if args.doctor:
        from xavfsizlik.doctor import run_doctor
        raise SystemExit(run_doctor(cfg))

    if cfg.simulate is False:
        # kamera mavjudligini "yumshoq" tekshirish
        from xavfsizlik.camera import Camera
        backend = Camera(cfg).backend
        if backend == "simulate":
            print("⚠  Kamera topilmadi — demo (simulyatsiya) rejimida ishlaymiz.")
            print("   Haqiqiy kamera uchun: sudo apt install python3-opencv yoki fswebcam")
    else:
        print("ℹ  PCX_SIMULATE=1 — demo rasmlar ishlatiladi.")

    app = create_app(cfg)
    monitor = app.extensions["monitor"]
    if args.arm:
        monitor.arm()

    print(f"\n  PC Xavfsizlik → http://127.0.0.1:{args.port}\n")
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
