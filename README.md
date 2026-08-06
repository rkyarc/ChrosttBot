# Chrostt Bot

Chrostt Bot adalah bot Telegram berbasis Python yang menyediakan beberapa layanan sederhana, seperti pengecekan harga saham Indonesia melalui Yahoo Finance dan menu untuk fitur hapus background foto. Bot ini dibangun menggunakan library `pyTelegramBotAPI`.

## Fitur

- 🤖 Menu utama dengan tombol inline
- 📈 Cek data saham Indonesia
  - Cek IHSG
  - Cari emiten berdasarkan kode saham BEI
- 📊 Menampilkan harga terakhir saham
- ✂️ Menu hapus background foto (dalam pengembangan / siap dikembangkan)
- ℹ️ Informasi bot

## Teknologi yang Digunakan

- Python
- pyTelegramBotAPI
- yfinance
- requests
- python-dotenv

## Struktur Proyek

```text
nama-folder/
├── bot.py
├── .env
├── requirements.txt
└── README.md
```

## Persyaratan

Sebelum menjalankan bot, pastikan kamu sudah memiliki:

- Python 3.9 atau lebih baru
- Token bot Telegram dari [@BotFather](https://t.me/BotFather)
- API key Remove.bg jika ingin menggunakan fitur hapus background

## Instalasi

1. Clone atau unduh project ini.

```bash
git clone https://github.com/rkyarc/ChrosttBot
cd ChrosttBot
```

2. Buat virtual environment.

```bash
python -m venv venv
```

3. Aktifkan virtual environment.

Windows:

```bash
venv\Scripts\activate
```

Linux / macOS:

```bash
source venv/bin/activate
```

4. Install semua package yang dibutuhkan.

Jika file dependency kamu bernama `requirements.txt`:

```bash
pip install -r requirements.txt
```

Jika file dependency kamu bernama `requirement.txt`:

```bash
pip install -r requirement.txt
```

Atau install manual:

```bash
pip install pyTelegramBotAPI requests python-dotenv yfinance
```

## Konfigurasi Environment

Buat file `.env` di folder utama project, lalu isi dengan token dan API key milik kamu.

```env
TELEGRAM_TOKEN=token_telegram_kamu
REMOVE_BG_API_KEY=api_key_remove_bg_kamu
```

Contoh:

```env
TELEGRAM_TOKEN=123456789:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
REMOVE_BG_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
```

### Cara Mendapatkan Token Telegram Bot

1. Buka Telegram.
2. Cari [@BotFather](https://t.me/BotFather).
3. Gunakan perintah `/newbot`.
4. Ikuti proses pembuatan bot.
5. Salin token yang diberikan oleh BotFather.
6. Tempel token tersebut ke file `.env`.

### Cara Mendapatkan Remove.bg API Key

1. Kunjungi [https://www.remove.bg/api](https://www.remove.bg/api).
2. Daftar atau login.
3. Ambil API key dari dashboard.
4. Tempel API key tersebut ke file `.env`.

## Cara Menjalankan Bot

Jalankan script bot menggunakan Python.

```bash
python bot.py
```

Jika muncul pesan seperti ini:

```text
[SYSTEM] Super App Bot sedang berjalan. Silakan buka Telegram Anda!
```

Berarti bot berhasil dijalankan.

Setelah itu, buka bot Telegram kamu dan kirim perintah:

```text
/start
```

atau

```text
/menu
```

## Penggunaan

### Cek IHSG

1. Kirim `/start` atau `/menu`.
2. Pilih menu **📈 Cek Saham**.
3. Pilih tombol **📊 IHSG**.
4. Bot akan menampilkan data IHSG terbaru.

### Cari Saham

1. Kirim `/start` atau `/menu`.
2. Pilih menu **📈 Cek Saham**.
3. Pilih tombol **🔍 Cari Emiten Manual**.
4. Masukkan kode saham tanpa akhiran `.JK`.

Contoh:

```text
BBCA
```

atau

```text
ASII
```

atau

```text
GOTO
```

Bot akan otomatis menambahkan `.JK` di belakang kode untuk mencari data saham di Bursa Efek Indonesia melalui Yahoo Finance.

## Contoh Kode Saham

| Saham | Input di Bot |
|---|---|
| Bank Central Asia | BBCA |
| Astra International | ASII |
| GoTo Gojek Tokopedia | GOTO |
| Bank Rakyat Indonesia | BBRI |
| Bank Mandiri | BMRI |

## Catatan

- Kode saham Indonesia di Yahoo Finance biasanya memiliki akhiran `.JK`, contohnya `BBCA.JK`.
- Bot ini otomatis menambahkan `.JK` saat pengguna mencari saham berdasarkan kode 4 huruf.
- Data harga diambil dari `yfinance`, sehingga ketersediaan data dapat bergantung pada layanan Yahoo Finance.
- Fitur hapus background memerlukan API key Remove.bg dan dapat dikembangkan lebih lanjut pada bagian handler foto.

## Troubleshooting

### 1. `ModuleNotFoundError: No module named 'telebot'`

Artinya paket `pyTelegramBotAPI` belum ter-install. Jalankan:

```bash
pip install pyTelegramBotAPI
```

atau:

```bash
pip install -r requirements.txt
```

---

### 2. `ModuleNotFoundError: No module named 'dotenv'`

Install paket `python-dotenv`:

```bash
pip install python-dotenv
```

---

### 3. Bot tidak merespons

Beberapa hal yang bisa dicek:

- Pastikan `TELEGRAM_TOKEN` di `.env` sudah benar.
- Pastikan token tidak memiliki spasi berlebih.
- Pastikan script bot sedang berjalan.
- Pastikan tidak ada bot lain yang berjalan dengan token yang sama.

---

### 4. `.env` tidak terbaca

Pastikan file `.env` berada di folder yang sama dengan file bot.

Contoh:

```text
folder-bot/
├── bot.py
└── .env
```

---

### 5. Gagal mengambil data saham

Kemungkinan penyebabnya:

- Kode saham salah.
- Kode saham tidak terdaftar di BEI.
- Yahoo Finance sedang gangguan atau rate limit.
- Koneksi internet bermasalah.

Coba ulangi dengan kode saham yang benar, misalnya:

```text
BBCA
```

## Lisensi

Project ini dapat digunakan dan dikembangkan sesuai kebutuhan.

## Kredit

Bot ini dibuat menggunakan:

- [pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI)
- [yfinance](https://github.com/ranaroussi/yfinance)
- [requests](https://requests.readthedocs.io/)
- [python-dotenv](https://github.com/theskumar/python-dotenv)