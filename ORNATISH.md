# 📦 Noutbukka o'rnatish qo'llanmasi

Bu qo'llanma **haqiqiy kompyuteringizda** ishlatish uchun. Dashboard'ni ko'rish shart emas —
dastur fonda tizim xizmati sifatida ishlaydi va kompyuter har yonganda o'zi ishga tushadi.

---

## 1️⃣ Avval: qaysi operatsion tizim?

Terminal / buyruq qatorini oching va kerakli bo'limni bajaring.

---

## 🐧 Linux (Ubuntu, Debian, Mint, Kali...)

### 1-qadam — fayllarni olish

```bash
git clone https://github.com/NomerBozori/pc-xafsizlik.git
cd pc-xafsizlik
```

### 2-qadam — o'rnatish (bitta buyruq)

```bash
sudo ./install.sh
```

Skript hammasini qiladi:
- `/opt/pc-xafsizlik` ga ko'chiradi
- Python kutubxonalarini o'rnatadi (flask, pillow, opencv)
- **systemd xizmati** yaratadi — kompyuter yonganda avtomatik ishga tushadi
- kamerani va jurnalni tekshiradi (`--doctor`)

### 3-qadam — tekshirish

```bash
sudo systemctl status pc-xafsizlik     # ishlayaptimi
sudo journalctl -u pc-xafsizlik -f     # jonli jurnal
```

Brauzerda: **http://127.0.0.1:8000** → "Qo'riqlashni yoqish" bosilgan bo'ladi.

### 4-qadam — sinash (haqiqiy!)

Yangi terminalda **noto'g'ri parol bilan sudo** kiriting:

```bash
sudo -k          # avvalgi parolni unutish
sudo ls          # noto'g'ri parol kiriting (2-3 marta)
```

Bir necha soniyadan keyin dashboard'da voqea va **kamera rasmi** paydo bo'ladi.
Telefoningizdan ham ko'rish uchun: `PCX_HOST=0.0.0.0` (pastda).

### Foydali buyruqlar

| Amal | Buyruq |
|---|---|
| Holat | `sudo systemctl status pc-xafsizlik` |
| To'xtatish | `sudo systemctl stop pc-xafsizlik` |
| Qayta yoqish | `sudo systemctl restart pc-xafsizlik` |
| Jurnal | `sudo journalctl -u pc-xafsizlik -f` |
| Sozlash | `sudo nano /opt/pc-xafsizlik/config.json` |
| Rasmlar | `ls /opt/pc-xafsizlik/snapshots/` |
| Diagnostika | `sudo /opt/pc-xafsizlik/.venv/bin/python /opt/pc-xafsizlik/app.py --doctor` |
| O'chirish | `sudo ./install.sh --uninstall` |

---

## 🪟 Windows 10 / 11

### 1-qadam — Python

[python.org](https://python.org) dan Python 3.10+ o'rnating.
O'rnatishda **"Add Python to PATH"** ni albatta belgilang.

### 2-qadam — fayllarni olish

GitHub'dan ZIP yuklab oling yoki:
```bat
git clone https://github.com/NomerBozori/pc-xafsizlik.git
```

### 3-qadam — o'rnatish

`install-windows.bat` fayliga **o'ng tugma → "Run as administrator"**.

Skript:
- `C:\ProgramData\PCXavfsizlik` ga o'rnatadi
- kutubxonalarni o'rnatadi (opencv bilan)
- **boot vazifasi** yaratadi (SYSTEM huquqida, har yonganda ishga tushadi)
- diagnostika o'tkazadi

### 4-qadam — sinash

Ekran qulflang (`Win + L`), **noto'g'ri parol** kiriting 3 marta.
~10 soniyada kamera rasm oladi.

> ⚠️ Windows'da Security jurnalidan o'qish uchun **Administrator** huquqi shart —
> `install-windows.bat` buni o'zi ta'minlaydi (SYSTEM sifatida ishlaydi).

**Windows'da muammo bo'lsa:**
```bat
schtasks /query /tn PCXavfsizlik          :: vazifa bormi
schtasks /end /tn PCXavfsizlik            :: to'xtatish
schtasks /run /tn PCXavfsizlik            :: qayta ishga tushirish
```

---

## 📱 Telefon/planshet orqali ko'rish (ixtiyoriy)

Standart holatda dashboard faqat shu kompyuterda ochiladi (xavfsizlik uchun).
Uy Wi-Fi tarmog'idagi telefondan ko'rish uchun:

**Linux:**
```bash
sudo systemctl edit pc-xafsizlik
# [Service] bo'limiga qo'shing:
# Environment=PCX_HOST=0.0.0.0
sudo systemctl restart pc-xafsizlik
```
So'ng kompyuterning IP manzilini toping: `ip a` → `http://192.168.x.x:8000`

**Windows:** `config.json` ga `"host": "0.0.0.0"` qo'shilmaydi — vazifani tahrirlang:
```bat
schtasks /change /tn PCXavfsizlik /tr "C:\ProgramData\PCXavfsizlik\.venv\Scripts\pythonw.exe C:\ProgramData\PCXavfsizlik\app.py --arm --host 0.0.0.0"
```

⚠️ Faqat ishonchli uy tarmog'ida qiling. Internetga ochmang!

---

## ⚙️ Sozlamalar (`config.json`)

```json
{
  "threshold": 3,          // 3 ta xato urinish → voqea
  "window_seconds": 120,   // shu vaqt ichida sanaladi
  "cooldown_seconds": 30,  // voqeadan keyin sovish (takror rasmlar bo'lmasin)
  "burst_count": 3,        // voqeada nechta rasm
  "burst_delay": 0.8,      // rasmlar orasidagi pauza (soniya)
  "capture_width": 1280,
  "capture_height": 720,
  "camera_index": 0,       // /dev/video0 → 0 ; ikkinchi kamera → 1
  "retention_days": 30,    // eski rasmlar avto-o'chiriladi
  "simulate": false        // TRUE qilmang — demo rasmlar ishlatiladi!
}
```

### Kamerani sozlash

```bash
# qaysi kameralar bor
ls /dev/video*
v4l2-ctl --list-devices        # sudo apt install v4l-utils

# kamera ishlayaptimi
sudo /opt/pc-xafsizlik/.venv/bin/python /opt/pc-xafsizlik/app.py --doctor
```

Agar rasm qora chiqsa — `capture_width/height` ni kamaytiring (640x480) yoki
`warmup_frames` ni oshiring (12).

---

## ✅ O'rnatilganini qanday bilaman?

```bash
sudo /opt/pc-xafsizlik/.venv/bin/python /opt/pc-xafsizlik/app.py --doctor
```

Ko'rinishi kerak:
```
Tizim:
  ✅ Linux ... · Python 3.x
Kamera:
  ✅ aniqlandi: opencv
  ✅ sinov kadri olindi (3 ta)
Jurnal manbalari:
  ✅ journalctl: bor
Tizim xizmati:
  ✅ pc-xafsizlik: active / enabled
End-to-end sinov:
  ✅ voqea yaratildi, 3 ta rasm saqlandi
```

---

## ❗ Muammolarni bartaraf etish

| Muammo | Yechim |
|---|---|
| `kamera topilmadi` | `sudo apt install python3-opencv` yoki `sudo apt install fswebcam` |
| `auth.log o'qish taqiqlangan` | Xizmat root sifatida ishlashi kerak: `sudo systemctl status pc-xafsizlik` |
| Rasm qora | `capture_width/height` = 640x480, `warmup_frames` = 12 |
| Voqea yaratilmayapti | `threshold` ni 2 ga tushiring; `sudo journalctl -f` da `authentication failure` bormi? |
| Windows'da ishlamayapti | Administrator sifatida o'rnatilganini tekshiring: `schtasks /query /tn PCXavfsizlik` |
| Kamera boshqa dasturda band | Zoom/Teams/Chrome'ni yoping |
| `Port 8000 band` | `PCX_PORT=8080` yoki `--port 8080` |

Log:
```bash
sudo journalctl -u pc-xafsizlik -n 100 --no-pager
```

---

## 🔐 Maxfiylik

- Barcha rasmlar faqat **shu kompyuterda** — hech qanday tarmoq, hech qanday "bulut".
- Dashboard standart holatda `127.0.0.1` (faqat lokal) da tinglaydi.
- Rasmlar `snapshots/` papkasida, `chmod 700` bilan saqlanadi.
- 30 kundan keyin avtomatik o'chiriladi (`retention_days`).

---

## ⚠️ Huquqiy eslatma

Bu dastur **o'zingizga tegishli** qurilmada o'z xavfsizligingiz uchun. Boshqa odamni
xabarisiz rasmga olish ko'p mamlakatlarda qonunga xilof. Uyda yoki ish joyida
qurilmadan foydalanuvchilarni oldindan xabardor qiling.
