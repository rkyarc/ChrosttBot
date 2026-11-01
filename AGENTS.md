# Aturan Project Chrostt Bot

Bot Telegram Python (pyTelegramBotAPI) dengan fitur AI assistant, downloader,
stiker, saham, berita, dan panel admin. Dokumen ini adalah konteks kerja untuk
kontributor dan agen otomatis.

## Branch

- `dev/ilham` — branch kerja aktif milik Ilham (RusdiEneri). Semua perubahan kode
  masuk ke sini dulu.
- `dev/ricky` — branch kerja milik rkyarc (author repo). Perubahan dari sisi Ricky
  masuk ke sini, lalu di-merge lewat Pull Request.
- `staging` — hasil merge dari `dev/ilham` / `dev/ricky` untuk uji sebelum rilis.
- `main` — **JANGAN DISENTUH.** Branch ini adalah titik awal perombakan pertama dan
  dipertahankan sebagai arsip/referensi. Jangan checkout, commit, merge, rebase,
  reset, push, atau mengubah `main` maupun `origin/main` kecuali diminta eksplisit
  oleh pemilik repo.

## Alur Kerja

- Ilham: `dev/ilham` → push → merge ke `staging`. Berhenti di staging.
- Ricky: `dev/ricky` → Pull Request → merge ke `main`.
- Jangan merge `main` ke branch kerja tanpa diminta.

## Struktur

```
config.py              # env & konstanta (satu-satunya sumber konfigurasi)
main.py                # bootstrap: logging, daftar perintah, polling loop
bot/
  __init__.py          # instance TeleBot (tg_bot)
  admin.py             # parsing ADMIN_IDS, cek akses, data pengguna
  ai_prompt.py         # system prompt user & admin
  keyboards.py         # semua inline keyboard
  play_mode.py         # siklus mode tunggu judul /play
  riwayat.py           # penyimpanan riwayat AI (SQLite)
  sessions.py          # cache per chat dengan TTL
  telegram_io.py       # operasi Telegram yang tahan error
  utils.py             # format, escape HTML, potong pesan
  decorators.py        # aman_handler
  handlers/            # interaksi Telegram per fitur
  services/            # integrasi eksternal (AI, downloader, data)
```

## Standar Kode

- Python 3.10+, tanpa dependency baru kecuali benar-benar perlu. Cek dulu apa yang
  sudah ada di `pyproject.toml`/`requirements.txt`.
- Ikuti gaya file di sekitarnya: nama fungsi & variabel bahasa Indonesia, docstring
  singkat yang menjelaskan *kenapa*, bukan mengulang kode.
- Jangan menambah komentar dekoratif. Komentar hanya untuk keputusan tidak jelas
  atau jebakan (mis. kuirk API, urutan handler).
- Semua teks yang dikirim ke pengguna memakai `parse_mode="HTML"` dan melewati
  `escape_html()` untuk data eksternal.
- Handler yang menyentuh jaringan wajib menangani exception dan memberi pesan yang
  bisa ditindaklanjuti; traceback penuh hanya ke log.
- Jangan pernah mencatat atau mengirim token, API key, atau isi `.env`.
- Batasi input pengguna (panjang teks, jumlah hasil, jeda antar request).

## Konvensi Fitur

- **Mode percakapan** (AI, /play) disimpan di `SessionStore` dengan TTL, bukan
  variabel global yang tumbuh tanpa batas.
- **Prompt interaktif** memakai ForceReply dan wajib dihapus saat mode berakhir,
  supaya kolom balas tidak menggantung di chat.
- **Data yang harus bertahan** setelah restart masuk SQLite (`bot/riwayat.py`),
  bukan file JSON ad-hoc.
- **Akses admin** dicek dari `from_user.id` (bukan `chat.id`). Panel admin berisi
  data sensitif sehingga hanya boleh dibuka di chat pribadi.
- **Akses lebih dalam untuk admin** tidak boleh membuka jalur eksekusi: tidak ada
  shell, tulis/hapus file, ubah konfigurasi, atau broadcast otomatis dari AI.

## Verifikasi Sebelum Selesai

Jalankan minimal:

```bash
poetry run ruff check bot main.py config.py --select F,E9
poetry run python -m compileall -q bot main.py
```

Untuk perubahan alur handler, tambahkan uji manual dengan stub `send_message` /
`delete_message` (tanpa jaringan) yang mencakup: jalur sukses, pembatalan, dan
penolakan akses. Jangan mengklaim fitur berfungsi tanpa bukti dari perintah yang
benar-benar dijalankan.

## Catatan

- `dev/ilham` dan `staging` berada di atas `origin/main` (perbaikan bug, Chrostt AI,
  panel admin, riwayat SQLite), sedangkan `dev/ricky` masih di `b4ea2a1`.
- `data/` berisi database riwayat dan sudah di-`.gitignore`; jangan commit isinya.
