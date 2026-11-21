#!/usr/bin/env bash
# PC Xavfsizlik — oson ishga tushirish (Linux / macOS)
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
. .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# Kamera uchun (agar o'rnatilmagan bo'lsa) — ixtiyoriy
if ! python -c "import cv2" 2>/dev/null; then
  echo "ℹ  OpenCV topilmadi. Kamera uchun: pip install opencv-python"
fi

echo "→ Dashboard: http://127.0.0.1:${PCX_PORT:-8000}"
python app.py --arm "$@"
