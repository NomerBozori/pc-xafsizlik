#!/usr/bin/env bash
# ============================================================================
# PC Xavfsizlik — Linux uchun to'liq o'rnatuvchi
#
#   sudo ./install.sh              # o'rnatish + tizim xizmatini yoqish
#   sudo ./install.sh --no-service # faqat o'rnatish (xizmatsiz)
#   sudo ./install.sh --uninstall  # butunlay olib tashlash
# ============================================================================
set -euo pipefail

APP_NAME="pc-xavfsizlik"
# Standart: /opt/pc-xafsizlik. Boshqa joy: sudo PCX_INSTALL_DIR=/srv/pcx ./install.sh
INSTALL_DIR="${PCX_INSTALL_DIR:-/opt/pc-xafsizlik}"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_SRC="$SRC_DIR/deploy/pc-xavfsizlik.service"
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}!${NC} $*"; }
die()  { echo -e "${RED}✗${NC} $*" >&2; exit 1; }

# ------------------------------------------------------------------ uninstall
if [[ "${1:-}" == "--uninstall" ]]; then
  [[ $EUID -eq 0 ]] || die "sudo bilan ishga tushiring."
  echo "→ Xizmat to'xtatilmoqda..."
  systemctl disable --now "$APP_NAME" 2>/dev/null || true
  rm -f "/etc/systemd/system/$APP_NAME.service"
  systemctl daemon-reload 2>/dev/null || true
  # Rasmlarni saqlab qolamiz
  if [[ -d "$INSTALL_DIR/snapshots" ]] && compgen -G "$INSTALL_DIR/snapshots/*.jpg" > /dev/null; then
    BACKUP="/root/pc-xavfsizlik-snapshots-$(date +%Y%m%d-%H%M%S)"
    cp -r "$INSTALL_DIR/snapshots" "$BACKUP"
    ok "Rasmlar saqlandi: $BACKUP"
  fi
  rm -rf "$INSTALL_DIR"
  ok "O'chirildi. (Rasmlar zaxirasi yuqorida ko'rsatilgan joyda.)"
  exit 0
fi

# ------------------------------------------------------------------- checks
[[ $EUID -eq 0 ]] || die "Bu skript root huquqi talab qiladi. Iltimos:
   sudo ./install.sh"
command -v python3 >/dev/null || die "python3 topilmadi. O'rnating: sudo apt install python3 python3-venv python3-pip"
python3 -c 'import venv' 2>/dev/null || die "python3-venv yo'q. O'rnating: sudo apt install python3-venv"

OS="$(uname -s)"
echo "→ O'rnatilmoqda: $SRC_DIR  →  $INSTALL_DIR  ($OS)"

# --------------------------------------------------------------- copy files
mkdir -p "$INSTALL_DIR"
for item in app.py requirements.txt README.md ORNATISH.md templates static xavfsizlik demo_assets; do
  [[ -e "$SRC_DIR/$item" ]] && cp -r "$SRC_DIR/$item" "$INSTALL_DIR/"
done
mkdir -p "$INSTALL_DIR/deploy"
[[ -f "$SERVICE_SRC" ]] && cp "$SERVICE_SRC" "$INSTALL_DIR/deploy/"
ok "Fayllar ko'chirildi"

# ------------------------------------------------------------------ venv/pip
if [[ ! -d "$INSTALL_DIR/.venv" ]]; then
  python3 -m venv "$INSTALL_DIR/.venv"
fi
"$INSTALL_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"
ok "Python kutubxonalari o'rnatildi (flask, pillow)"

# ------------------------------------------------------------------- camera
CAMERA_OK=0
if "$INSTALL_DIR/.venv/bin/python" -c "import cv2" 2>/dev/null; then
  CAMERA_OK=1
else
  echo "→ Kamera kutubxonasi (opencv-python-headless) o'rnatilmoqda..."
  if "$INSTALL_DIR/.venv/bin/pip" install --quiet opencv-python-headless 2>/dev/null; then
    CAMERA_OK=1
    ok "OpenCV o'rnatildi"
  else
    warn "OpenCV o'rnatilmadi (internet yoki wheel muammosi). fswebcam sinab ko'riladi."
  fi
fi

if [[ $CAMERA_OK -eq 0 ]]; then
  if command -v fswebcam >/dev/null; then
    ok "fswebcam topildi — kamera shu orqali ishlaydi"
  else
    warn "Kamera kutubxonasi yo'q. O'rnatish uchun:"
    echo "     sudo apt install fswebcam        # yoki"
    echo "     sudo $INSTALL_DIR/.venv/bin/pip install opencv-python-headless"
  fi
fi

# kamera qurilmasini tekshirish
if [[ -e /dev/video0 ]]; then
  ok "Kamera qurilmasi topildi: /dev/video0"
else
  warn "/dev/video0 topilmadi — noutbuk kamerasini tekshiring (ba'zilarda /dev/video1)"
fi

# ------------------------------------------------------------------ config
if [[ ! -f "$INSTALL_DIR/config.json" ]]; then
  "$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/app.py" --init-config >/dev/null
  ok "config.json yaratildi: $INSTALL_DIR/config.json"
fi

# ----------------------------------------------------------------- service
if [[ "${1:-}" != "--no-service" ]]; then
  if command -v systemctl >/dev/null; then
    if [[ ! -f "$SERVICE_SRC" ]]; then
      die "Xizmat fayli topilmadi: $SERVICE_SRC"
    fi
    # Xizmat faylidagi yo'lni haqiqiy o'rnatish papkasiga moslashtiramiz
    sed "s#/opt/pc-xafsizlik#$INSTALL_DIR#g" "$SERVICE_SRC" \
      > "/etc/systemd/system/$APP_NAME.service"
    systemctl daemon-reload
    systemctl enable --now "$APP_NAME"
    sleep 2
    if systemctl is-active --quiet "$APP_NAME"; then
      ok "Tizim xizmati ishga tushdi va har boot'da avtomatik yonadi"
    else
      warn "Xizmat ko'tarilmadi. Jurnal: sudo journalctl -u $APP_NAME -n 50"
    fi
  else
    warn "systemctl yo'q — xizmat o'rnatilmadi, qo'lda: python3 app.py --arm"
  fi
fi

# -------------------------------------------------------------------- test
echo
echo "→ Diagnostika ishga tushirilmoqda..."
"$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/app.py" --doctor || true

echo
echo "=============================================================="
ok "O'rnatish tugadi!"
echo "  Dashboard:   http://127.0.0.1:8000"
echo "  Holat:       sudo systemctl status $APP_NAME"
echo "  Jurnal:      sudo journalctl -u $APP_NAME -f"
echo "  Rasmlar:     $INSTALL_DIR/snapshots/"
echo "  Sozlama:     sudo nano $INSTALL_DIR/config.json"
echo "  O'chirish:   sudo ./install.sh --uninstall"
echo "=============================================================="
