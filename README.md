# 🛡 PC Xavfsizlik — noutbuk qo'riqchisi

Noutbukingizga **kimdir parolni xato kiritsa** (yoki login qilishga urinsa), dastur
**jimgina veb-kameradan rasm oladi** va barcha voqealarni bitta dashboardda saqlaydi.

Hech narsa internetga yuborilmaydi — barcha rasmlar va jurnal faqat shu kompyuterda qoladi.

---

## Nima qiladi

| Qism | Vazifasi |
|---|---|
| **Kuzatuvchi** | Linux: `auth.log` / `journalctl`; Windows: Security Event Log (`4625`) |
| **Kamera** | OpenCV → `fswebcam` → demo tartibida; voqeada 3 ta kadr oladi |
| **Saqlash** | `snapshots/` papkasida rasmlar + `events.jsonl` jurnal |
| **Dashboard** | Qo'riqlashni yoqish/o'chirish, voqealar galereyasi, demo, tozalash |

**Chegara:** 120 soniya ichida **3 ta** xato urinish → voqea → kamera ishga tushadi.
Voqeadan keyin 30 soniya "sovish" — rasmga olish takrorlanib ketmaydi.

---

## 🚀 Noutbukka o'rnatish (tavsiya etiladi)

**Batafsil qo'llanma: [ORNATISH.md](ORNATISH.md)**

### Linux — bitta buyruq
```bash
git clone https://github.com/NomerBozori/pc-xafsizlik.git
cd pc-xafsizlik
sudo ./install.sh
```
→ `/opt/pc-xafsizlik` ga o'rnatiladi, **systemd xizmati** yaratiladi
(kompyuter yonganda avtomatik ishga tushadi), kamera va jurnal tekshiriladi.

### Windows — bitta fayl
`install-windows.bat` → **o'ng tugma → "Run as administrator"**
→ `C:\ProgramData\PCXavfsizlik` ga o'rnatiladi, **boot vazifasi** yaratiladi.

### Tekshirish
```bash
sudo /opt/pc-xafsizlik/.venv/bin/python /opt/pc-xafsizlik/app.py --doctor
```
```
Kamera:            ✅ opencv · sinov kadri olindi
Jurnal:            ✅ journalctl (auth.log)
Tizim xizmati:     ✅ active / enabled
End-to-end sinov:  ✅ voqea yaratildi, 3 ta rasm
```

### Sinash — haqiqiy parol urinishi
```bash
sudo -k                  # parolni "unutish"
sudo ls                  # noto'g'ri parol kiriting, 3 marta
```
Bir necha soniyada dashboard'da voqea + kamera rasmi paydo bo'ladi.

**Boshqarish:**
```bash
sudo systemctl status pc-xafsizlik      # holat
sudo systemctl restart pc-xafsizlik     # qayta yoqish
sudo journalctl -u pc-xafsizlik -f      # jonli log
```
Dashboard: **http://127.0.0.1:8000**

### Oddiy ishga tushirish (o'rnatmasdan)
```bash
./run.sh              # Linux / macOS
run.bat               # Windows
```
> Kamera topilmasa dastur **demo rejimiga** o'tadi va namunali rasmlar bilan ishlaydi.

---

## Sozlash

`config.json` yaratish:
```bash
python app.py --init-config
```

Asosiy maydonlar:

```json
{
  "threshold": 3,            // nechta xato urinish voqea hisoblanadi
  "window_seconds": 120,     // qaysi vaqt oynasida sanaladi
  "cooldown_seconds": 30,    // voqeadan keyingi "sovish"
  "burst_count": 3,          // bitta voqeada nechta rasm
  "burst_delay": 0.8,        // rasmlar orasidagi pauza
  "capture_width": 1280,
  "capture_height": 720,
  "retention_days": 30,      // shu kundan eski rasmlar tozalanadi
  "simulate": false          // true = demo rasmlar (kamera yo'q)
}
```

Muhit o'zgaruvchilari (config.json ustidan yozadi):

```bash
PCX_THRESHOLD=5 PCX_SIMULATE=1 PCX_PORT=9000 python app.py --arm
```

| O'zgaruvchi | Ma'nosi |
|---|---|
| `PCX_SIMULATE=1` | demo rejim (generatsiya qilingan rasmlar) |
| `PCX_THRESHOLD`, `PCX_WINDOW`, `PCX_COOLDOWN` | chegara sozlamalari |
| `PCX_CAMERA_INDEX` | qaysi kamera (`/dev/video0` → 0) |
| `PCX_LOG_FILES` | log fayllari ro'yxati (`:` bilan ajratilgan) |
| `PCX_PORT`, `PCX_HOST` | veb-server manzili |

---

## Windows'da parol urinishlarini ushlash

Windows'da `auth.log` yo'q, shuning uchun dastur **Security Event Log**'dagi
`4625` (muvaffaqiyatsiz kirish) yozuvlarini o'qiydi.

Kerak: **Administrator huquqida** ishga tushirish (aks holda Security jurnalini o'qib bo'lmaydi):

```bat
:: Administrator sifatida
run.bat
```

Agar ekran qulfini ochishda xato parol kiritilsa — `4625` yoziladi va ~8 soniya
ichida kamera ishga tushadi.

---

## Linux'da sinash (kamera bo'lmasa ham)

```bash
# 1-terminal: demo rejimda ishga tushirish
PCX_SIMULATE=1 python app.py --arm

# 2-terminal: 3 ta soxta xato urinish
curl -X POST localhost:8000/api/simulate -H 'Content-Type: application/json' -d '{"count":4}'
```

Dashboard'da voqea va rasmlar paydo bo'ladi.

Haqiqiy logni sinash — `auth.log`ga o'xshash yozuv qo'shib:
```bash
echo "Nov 21 03:14:07 host sshd[1]: Failed password for root from 10.0.0.5 port 555 ssh2" | sudo tee -a /var/log/auth.log
```

---

## Buyruqlar qatorasi (API)

| Metod | Yo'l | Vazifasi |
|---|---|---|
| GET | `/api/status` | holat, statistika, oxirgi urinishlar |
| GET | `/api/events` | voqealar ro'yxati |
| POST | `/api/arm` · `/api/disarm` | qo'riqlashni yoqish / to'xtatish |
| POST | `/api/test` | darhol sinov rasmi |
| POST | `/api/selftest` | kamerani tekshirish |
| POST | `/api/simulate` | soxta urinishlar (`count`, `user`) |
| POST | `/api/purge` | eski rasmlarni o'chirish |
| DELETE | `/api/events` | barchasini o'chirish |

Misol — tashqi skriptdan xato urinish haqida xabar berish (PAM hook va h.k.):
```bash
curl -X POST localhost:8000/api/simulate -d '{"count":1,"user":"ali"}'
```

---

## Testlar

```bash
python tests/test_core.py      # yoki: python -m pytest tests -q
```

---

## ⚠ Huquqiy eslatma

Bu vosita **faqat o'zingizga tegishli qurilmada**, o'z mol-mulkingizni himoya qilish uchun.
Boshqa odamni uning xabarisiz rasmga olish ko'p mamlakatlarda **qonunga xilof**.
Oilaviy/ish joyidagi qurilmalarda foydalanuvchilarni oldindan xabardor qiling —
aks holda bu maxfiylik qonunchiligini buzishi mumkin.

Dastur hech qanday ma'lumotni tashqariga yubormaydi.
