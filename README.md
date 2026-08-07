# Chrostt Bot

Chrostt Bot adalah bot Telegram berbasis Python yang menggabungkan beberapa fitur praktis dalam satu menu: hapus background foto, cek saham Indonesia lewat Yahoo Finance, download Instagram via SaveInta, dan download video TikTok lewat tikwm.

## Fitur

- Hapus background foto secara otomatis dari gambar yang dikirim ke chat.
- Cek harga saham BEI dan IHSG secara real-time.
- Download foto, carousel, dan video Instagram.
- Download video TikTok, video dengan watermark, foto/slideshow, dan audio jika tersedia.
- Navigasi menu dibuat dengan inline keyboard agar alurnya cepat dan sederhana.

## Struktur Project

```text
ChrosttBot/
├── .env.example
├── config.py
├── dev.py
├── main.py
├── pyproject.toml
├── README.md
├── requirements.txt
└── bot/
	├── __init__.py
	├── keyboards.py
	├── utils.py
	├── handlers/
	│   ├── __init__.py
	│   ├── background.py
	│   ├── instagram.py
	│   ├── menu.py
	│   ├── saham.py
	│   └── tiktok.py
	└── services/
		├── __init__.py
		├── removebg.py
		├── saveinta.py
		├── saham.py
		└── tiktok.py
```

## Cara Kerja

- `config.py` memuat environment dari `.env` dan akan menghentikan startup jika `TELEGRAM_TOKEN` belum diisi.
- `main.py` mengimpor semua handler lalu menjalankan `tg_bot.infinity_polling()` dengan retry otomatis jika polling terputus.
- `bot/__init__.py` membuat instance bot Telegram.
- `bot/keyboards.py` menyimpan semua inline keyboard untuk menu utama, saham, background, Instagram, dan TikTok.
- `bot/utils.py` berisi helper umum, termasuk format angka rupiah.
- `bot/services/saham.py` menangani pengambilan data saham dan validasi kode emiten.
- `bot/services/removebg.py` mengirim gambar ke API rembg untuk menghapus background.
- `bot/services/saveinta.py` menangani scrape dan parsing media Instagram dari SaveInta.
- `bot/services/tiktok.py` mengekstrak data TikTok dari tikwm dan mengunduh media yang dipilih.
- `bot/handlers/menu.py` menangani menu utama, info bot, dan akses cepat ke fitur lain.
- `bot/handlers/saham.py` menangani menu saham, cek IHSG, dan pencarian emiten manual.
- `bot/handlers/background.py` memproses foto yang dikirim pengguna untuk hapus background.
- `bot/handlers/instagram.py` menangkap link Instagram dan mengirim media hasil ekstraksi langsung ke chat.
- `bot/handlers/tiktok.py` menangkap link TikTok, menampilkan detail media, lalu mengirim file sesuai pilihan tombol.
- `dev.py` menjalankan mode auto-reload saat pengembangan dan menghentikan proses lama sebelum restart.

## Persyaratan

- Python `>=3.14`
- Poetry
- Token bot Telegram dari BotFather

## Setup

1. Salin `.env.example` menjadi `.env` di root project.
2. Isi minimal:

```env
TELEGRAM_TOKEN=isi_token_bot_kamu
```

3. Install dependency.

```bash
poetry install
```

4. Jalankan bot.

```bash
poetry run python main.py
```

## Mode Development (Auto Reload)

Kalau ingin bot restart otomatis saat file Python berubah:

```bash
poetry run python dev.py
```

Mode ini memakai `watchfiles` dan sudah mencoba mematikan proses bot lama secara otomatis agar tidak bentrok polling.

## Cara Pakai

- Kirim `/start` atau `/menu` untuk membuka menu utama.
- Pilih menu saham untuk cek IHSG atau cari kode emiten seperti `BBCA` dan `ASII`.
- Kirim foto biasa ke chat untuk proses hapus background.
- Kirim link Instagram untuk memproses postingan, reel, carousel, atau story publik.
- Kirim link TikTok untuk memunculkan pilihan download media.

## Catatan

- `.env.example` hanya berisi `TELEGRAM_TOKEN`.
- Fitur hapus background memakai API rembg gratis, jadi tidak perlu `REMOVE_BG_API_KEY`.
- Dependency utama dikelola dari `pyproject.toml` dan dikunci di `poetry.lock`.
- `requirements.txt` disediakan untuk instalasi berbasis pip dan sudah diselaraskan dengan dependency utama project.
- Kode saham Indonesia biasanya ditulis tanpa `.JK` saat input, misalnya `BBCA`.
- IHSG diambil melalui kode `^JKSE`.
- TikTok link yang didukung biasanya berasal dari `tiktok.com`, `vt.tiktok.com`, atau `vm.tiktok.com`.
- Instagram link yang didukung biasanya berasal dari `instagram.com` atau `instagr.am`.
- Story Instagram yang berisi campuran foto dan video akan diurutkan sesuai kartu sumber, sementara kartu audio-only diabaikan.
- Bot akan mencoba lanjut polling otomatis jika instance Telegram sempat konflik atau terputus.

## Troubleshooting 409 Conflict

Jika muncul pesan `Conflict: terminated by other getUpdates request`:

1. Pastikan hanya satu instance bot yang berjalan untuk satu token.
2. Jangan jalankan `main.py` dan `dev.py` bersamaan.
3. Jika baru pindah dari mode manual ke mode dev, hentikan proses lama dulu lalu jalankan ulang `poetry run python dev.py`.
