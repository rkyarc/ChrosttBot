# Chrostt Bot

Chrostt Bot adalah bot Telegram berbasis Python dengan dua fitur utama: cek saham Indonesia lewat Yahoo Finance dan hapus background foto lewat remove.bg.

## Struktur Folder

```text
ChrosttBot/
├── main.py
├── config.py
├── .env.example
├── bot/
│   ├── __init__.py
│   ├── keyboards.py
│   ├── utils.py
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── background.py
│   │   ├── menu.py
│   │   └── saham.py
│   └── services/
│       ├── __init__.py
│       ├── removebg.py
│       └── saham.py
└── .env
```

## Fungsi Tiap File

- `config.py` memuat variabel environment dari `.env` dan menghentikan startup jika token belum diisi.
- `.env.example` adalah template isi environment yang bisa kamu salin menjadi `.env`.
- `bot/__init__.py` membuat instance `bot`.
- `bot/keyboards.py` menyimpan semua inline keyboard.
- `bot/utils.py` berisi helper umum, seperti format rupiah.
- `bot/services/saham.py` berisi akses data saham, validasi kode emiten, dan format kode emiten.
- `bot/services/removebg.py` menangani request ke API remove.bg.
- `bot/handlers/menu.py` menangani menu utama dan info bot.
- `bot/handlers/saham.py` menangani menu saham, cek IHSG, dan pencarian emiten.
- `bot/handlers/background.py` menangani kirim foto dan proses hapus background.
- `main.py` hanya menjalankan bot dan memuat semua handler agar registrasi fungsi terjadi otomatis.

## Setup

1. Salin `.env.example` menjadi `.env` di root project.
2. Isi minimal:

```env
TELEGRAM_TOKEN=isi_token_bot_kamu
REMOVE_BG_API_KEY=isi_api_key_removebg_kamu
```

3. Install dependency.

```bash
poetry install
```

4. Jalankan bot.

```bash
poetry run python main.py
```

## Catatan

- File `.env` sudah diabaikan lewat `.gitignore`.
- Kode saham Indonesia biasanya ditulis tanpa `.JK` saat input, misalnya `BBCA`.
- IHSG diambil melalui kode `^JKSE`.
- Jika kamu baru pertama kali menjalankan project, pastikan dependency sudah terpasang lewat `poetry install`.
