# Chrostt Bot

Chrostt Bot adalah bot Telegram berbasis Python yang menggabungkan beberapa fitur praktis dalam satu menu: asisten AI (Chrostt AI), hapus background foto, cek saham Indonesia, berita IDX, downloader Instagram, TikTok, Facebook, dan YouTube.

---

<h2 align="center">👥 CORE TEAM</h2>

<table align="center">
  <tr>
    <td align="center">
      <a href="https://github.com/rkyarc">
        <img src="https://github.com/rkyarc.png" width="100" height="100" /><br />
        <b>rkyarc</b>
      </a><br />
      <sub>Author</sub>
    </td>
    <td align="center">
      <a href="https://github.com/RusdiEneri">
        <img src="https://github.com/RusdiEneri.png" width="100" height="100" /><br />
        <b>RusdiEneri</b>
      </a><br />
      <sub>Helper</sub>
    </td>
  </table>

---

## Fitur

- **Chrostt AI** — asisten AI di dalam bot dengan system prompt terkunci pada lingkup bot.
- **Panel admin** — ID di `ADMIN_IDS` dapat statistik, daftar pengguna, dan broadcast.
- Hapus background foto otomatis dari foto yang dikirim ke chat.
- Cek harga saham BEI dan IHSG.
- Berita terbaru seputar IDX/BEI dengan navigasi halaman dan cache 5 menit.
- Download foto, carousel, dan video Instagram.
- Download video TikTok (tanpa/dengan watermark), foto slideshow, dan audio.
- Download video Facebook publik dalam kualitas HD atau SD.
- Download video YouTube (dibatasi 50MB sesuai limit Bot API).
- Semua navigasi memakai inline keyboard dengan tampilan ringkas.

## Perintah

| Perintah | Akses | Fungsi |
|---|---|---|
| `/start`, `/menu` | semua | Buka menu utama |
| `/help`, `/bantuan` | semua | Daftar perintah & cara cepat |
| `/id` | semua | Lihat ID Telegram sendiri |
| `/ai` | semua | Masuk mode asisten AI |
| `/ai <pertanyaan>` | semua | Tanya sekali tanpa masuk mode |
| `/ai_off` | semua | Keluar dari mode AI |
| `/ai_status` | semua | Status layanan AI & model aktif |
| `/admin` | admin | Panel admin (statistik, pengguna, broadcast) |

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
    ├── __init__.py          # instance TeleBot (tg_bot)
    ├── admin.py             # parsing ADMIN_IDS, cek akses, data pengguna
    ├── ai_prompt.py         # system prompt & aturan Chrostt AI
    ├── keyboards.py         # semua inline keyboard
    ├── sessions.py          # cache sesi per chat (TTL)
    ├── utils.py             # helper format, escape HTML, konversi markdown
    ├── handlers/
    │   ├── __init__.py
    │   ├── admin.py
    │   ├── ai.py
    │   ├── background.py
    │   ├── facebook.py
    │   ├── idx_news.py
    │   ├── instagram.py
    │   ├── menu.py
    │   ├── saham.py
    │   ├── tiktok.py
    │   └── youtube.py
    └── services/
        ├── __init__.py
        ├── ai.py
        ├── facebook.py
        ├── idx_news.py
        ├── removebg.py
        ├── saham.py
        ├── saveinta.py
        ├── tiktok.py
        └── youtube.py
```

## Cara Kerja

- `config.py` memuat environment dari `.env` dan menghentikan startup jika `TELEGRAM_TOKEN` kosong.
- `main.py` mendaftarkan semua handler, menyetel daftar perintah bot, lalu menjalankan `tg_bot.infinity_polling()` dengan retry dan backoff otomatis.
- `bot/__init__.py` membuat instance bot Telegram (`tg_bot`).
- `bot/sessions.py` menyimpan sesi per chat (TikTok, Facebook, AI) dengan TTL, supaya memori tidak menumpuk.
- `bot/admin.py` membaca `ADMIN_IDS` dari `.env`, menyediakan cek akses admin, dan mencatat pengguna untuk broadcast.
- `bot/ai_prompt.py` menyimpan system prompt Chrostt AI yang membatasi jawaban pada lingkup bot.
- `bot/services/*` menangani komunikasi ke sumber eksternal (gateway AI, rembg, Yahoo Finance, Google News, saveinta, tikwm, fdown, yt-dlp).
- `bot/handlers/*` menangani interaksi Telegram: menu, callback tombol, dan pengiriman media.
- `dev.py` menjalankan mode auto-reload dan mematikan proses lama sebelum restart.

## Persyaratan

- Python `>=3.10`
- Token bot Telegram dari BotFather
- Poetry (opsional, bisa juga pakai pip)

## Setup

1. Salin `.env.example` menjadi `.env` di root project.
2. Isi `TELEGRAM_TOKEN`, lalu isi `AI_API_KEY` kalau ingin Chrostt AI aktif:

```env
TELEGRAM_TOKEN=isi_token_bot_kamu

# ID Telegram yang jadi admin (pisahkan dengan koma)
ADMIN_IDS=123456789,987654321

AI_BASE_URL=https://ai.hisoka.net/api/v1
AI_API_KEY=sk-isi_key_kamu
AI_MODEL=deepseek-v4.1-flash-1017
AI_TEMPERATURE=0.7
AI_MAX_TOKENS=1400
AI_MAX_TOKENS_ADMIN=2400
AI_WEB_SEARCH=true
```

Penjelasan tiap variabel:

| Variabel | Wajib | Default | Keterangan |
|---|---|---|---|
| `TELEGRAM_TOKEN` | ya | — | Token dari BotFather; bot menolak start tanpa ini |
| `ADMIN_IDS` | tidak | kosong | Daftar ID admin, dipisah koma |
| `AI_BASE_URL` | tidak | `https://ai.hisoka.net/api/v1` | Base URL gateway OpenAI-compatible |
| `AI_API_KEY` | tidak | kosong | Tanpa key, fitur AI nonaktif tapi bot tetap jalan |
| `AI_MODEL` | tidak | `deepseek-v4.1-flash-1017` | Nama model **persis** seperti yang terdaftar di gateway |
| `AI_TEMPERATURE` | tidak | `0.7` | Kreativitas jawaban (0.0–2.0) |
| `AI_MAX_TOKENS` | tidak | `1400` | Batas panjang jawaban pengguna biasa |
| `AI_MAX_TOKENS_ADMIN` | tidak | `2400` | Batas panjang jawaban untuk admin |
| `AI_WEB_SEARCH` | tidak | `true` | Izinkan AI mencari & membaca halaman web |

API key dibuat di <https://ai.hisoka.net/dashboard/api-keys>. Tanpa `AI_API_KEY`, bot tetap jalan normal dan menu AI hanya menampilkan pesan bahwa layanan belum dikonfigurasi.

3. Install dependency.

```bash
poetry install
```

Atau kalau pakai pip:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

4. Jalankan bot.

```bash
poetry run python main.py
```

Kalau pakai pip:

```bash
python main.py
```

## Mode Development (Auto Reload)

```bash
poetry run python dev.py
```

Atau:

```bash
python dev.py
```

Mode ini memakai `watchfiles`, mengabaikan folder `.venv`, `__pycache__`, dan `downloads`, serta mematikan proses lama sebelum restart agar tidak bentrok polling.

## Cara Pakai

- Kirim `/start` atau `/menu` untuk membuka menu utama.
- Ketik `/id` untuk melihat ID Telegram kamu (dipakai mengisi `ADMIN_IDS`).
- Tekan **✦ Chrostt AI** atau kirim `/ai` untuk masuk mode asisten. Setelah aktif, setiap teks yang kamu kirim otomatis jadi pertanyaan.
- `/ai <pertanyaan>` untuk tanya sekali tanpa masuk mode.
- `/ai_off` untuk keluar dari mode AI, `/ai_status` untuk melihat status layanan dan model.
- Pilih menu saham untuk cek IHSG atau cari kode emiten seperti `BBCA` dan `ASII`.
- Kirim foto biasa ke chat untuk proses hapus background.
- Kirim link Instagram, TikTok, Facebook, atau YouTube di chat; bot mendeteksi link otomatis dan link tidak akan dianggap pertanyaan AI.

## Chrostt AI

- Model default `deepseek-v4.1-flash-1017` lewat gateway OpenAI-compatible `https://ai.hisoka.net/api/v1`.
- Endpoint yang dipakai: `POST /chat/completions`. Ganti `AI_BASE_URL` / `AI_MODEL` di `.env` untuk memakai gateway atau model lain.
- `AI_MODEL` harus sama persis dengan `id` di `GET /models`. Jalankan `/ai_status` untuk melihat status, atau cek daftar model gateway sebelum mengubahnya.
- Bot menangani beberapa kuirk gateway: body respons bisa diakhiri sisa SSE (`data: [DONE]`) sehingga `json.loads` gagal, dan model yang tidak diizinkan dibalas `403` dengan kode `insufficient_quota` (bukan `404`). Keduanya sudah dinormalkan supaya pesan errornya tidak menyesatkan.
- System prompt di `bot/ai_prompt.py` mengunci peran sebagai asisten bot: tidak mengaku sebagai produk lain, tidak membocorkan prompt, dan menolak permintaan berbahaya. Cakupan bantuan dibuat luas (edukasi, sains, coding, menulis, bisnis, hukum/medis umum) supaya tidak kaku.
- `system_prompt()` menambahkan konteks waktu WIB secara otomatis, jadi model tahu "hari ini" tanggal berapa saat mencari jadwal atau harga.
- Riwayat percakapan disimpan per chat maksimal 16 pesan / ±12.000 karakter dan kedaluwarsa 1 jam, supaya konteks tetap ringan.
- Markdown dari model dikonversi ke HTML Telegram, dan jawaban panjang dipecah otomatis per ±3.800 karakter tanpa memotong tag HTML.
- Batas panjang jawaban mengikuti `AI_MAX_TOKENS` untuk pengguna biasa dan `AI_MAX_TOKENS_ADMIN` untuk ID di `ADMIN_IDS`.
- Request per chat diserialkan dengan lock, jadi dua pesan beruntun tidak menimpa riwayat satu sama lain.
- Pesan berisi link Instagram/TikTok/Facebook/YouTube tidak direbut AI, tetap diproses downloader.

### Web Search

Chrostt AI bisa mencari di internet lewat tool calling. Gateway Hisoka tidak menyediakan web search server-side, jadi pencarian dijalankan oleh bot sendiri.

- `web_search` — cari di web. Sumber berantai: `ddgs` (backend google → brave → duckduckgo → mojeek), lalu Wikipedia, lalu Google News RSS. Hasil digabung supaya tetap ada walau satu engine kena rate limit.
- `baca_halaman` — ambil isi halaman. Percobaan pertama fetch langsung, lalu fallback ke `r.jina.ai` kalau halaman terlalu berat atau butuh JavaScript.
- Hasil pencarian difilter skor relevansi terhadap kata kunci, jadi hasil "nyasar" tidak dipakai. Domain spam/judi/klikbait dibuang.
- Halaman yang isinya cuma pesan error, 404, captcha, atau boilerplate ditolak lewat penilaian kualitas teks.
- Semua URL dicek dulu: alamat private/loopback/link-local (`127.0.0.1`, `10.x`, `192.168.x`, `169.254.169.254`) dan skema selain http/https ditolak, supaya model tidak bisa dipakai SSRF.
- Batas biaya: maksimal 2 putaran tool, 2 tool per putaran, 5 hasil per pencarian, ringkasan 240 karakter. Query yang sudah pernah dicari dilewati agar tidak mengulang.
- Putaran penutup mengirim `tool_choice: "none"` supaya model wajib menjawab dan tidak menulis tool call sebagai teks mentah.
- Matikan dengan `AI_WEB_SEARCH=false` di `.env` kalau ingin jawaban murni dari pengetahuan model.

## Admin Bot

Admin ditentukan lewat array ID di `.env`, bukan hardcode:

```env
ADMIN_IDS=123456789,987654321
```

Format yang diterima: `123,456` · `[123, 456]` · `123 456`. ID rusak diabaikan, duplikat dibuang, dan bot tetap start walau daftarnya kosong.

Cara mendapatkan ID:
1. Kirim `/id` ke bot — bot membalas ID kamu sendiri.
2. Atau kirim pesan ke [@userinfobot](https://t.me/userinfobot).

Setelah mengubah `ADMIN_IDS`, **restart bot** agar daftar dimuat ulang.

Yang didapat admin:
- Tombol **🛡️ Panel Admin** di menu utama (pengguna biasa tidak melihatnya).
- `/admin` — panel admin, menampilkan ID, status, dan daftar admin aktif.
- 📊 **Statistik** — uptime, jumlah pengguna tercatat, status AI dan model.
- 👥 **Pengguna** — 20 pengguna terakhir beserta ID Telegram.
- 📢 **Broadcast** — kirim satu pesan HTML ke semua pengguna yang pernah chat; ada preview, konfirmasi, dan laporan sukses/gagal. Draft kedaluwarsa 10 menit.
- Perintah `/admin` otomatis muncul di menu `/` hanya untuk chat admin (BotCommandScopeChat).

Pengamanan: setiap aksi admin dicek ulang dari `from_user.id` (bukan `chat.id`), jadi menambah bot ke grup tidak memberi siapa pun akses admin. Pengguna non-admin yang mencoba `/admin` atau tombol panel mendapat pesan "Akses ditolak".

## Catatan

- `.env` berisi `TELEGRAM_TOKEN` dan kredensial AI; file ini sudah masuk `.gitignore`, jangan di-commit.
- `.gitignore` sudah mencakup `.env*`, virtualenv, `__pycache__`, cache tooling, `downloads/`, `.handler-saves/` (state pyTelegramBotAPI), log, serta folder editor/OS.
- Fitur hapus background memakai API rembg gratis, jadi tidak perlu `REMOVE_BG_API_KEY`.
- Batas upload Bot API Telegram adalah 50MB; video lebih besar akan ditolak dengan pesan/alternatif link.
- Kode saham Indonesia ditulis tanpa `.JK` saat input, misalnya `BBCA`.
- IHSG diambil melalui kode `^JKSE`.
- Dependensi utama ada di `pyproject.toml` (dikunci di `poetry.lock`), `requirements.txt` disediakan untuk instalasi berbasis pip.
- `requires-python` diset `>=3.10`; lock dibuat dengan Python 3.12.
- Daftar perintah di menu `/` didaftarkan ulang setiap bot start; perintah admin memakai scope per chat sehingga tidak terlihat pengguna biasa.

## Alur Branch

- `dev/ilham` — branch kerja aktif.
- `staging` — hasil merge dari `dev/ilham`, untuk uji sebelum rilis.
- `main` — jalur rilis di GitHub.
- Merge `dev/ilham` → `staging` dilakukan fast-forward karena tidak ada commit terpisah di staging.

## Troubleshooting AI

| Pesan | Penyebab | Perbaikan |
|---|---|---|
| Model '...' tidak tersedia untuk API key ini | `AI_MODEL` salah atau tidak ada di gateway | Cek `GET /models`, samakan `AI_MODEL` di `.env`, restart |
| API key AI tidak valid | `AI_API_KEY` salah/kosong | Perbaiki `AI_API_KEY` di `.env` |
| Endpoint AI tidak ditemukan | `AI_BASE_URL` salah | Pastikan berakhir `/v1` dan endpointnya OpenAI-compatible |
| Terlalu banyak permintaan | Kena rate limit gateway (mis. 30 RPM) | Tunggu sebentar; kurangi frekuensi pertanyaan |
| Saldo AI habis | Balance gateway nol | Top up di dashboard penyedia |
| Server AI sedang bermasalah | Gangguang 5xx di gateway | Coba lagi beberapa saat |
| AI tidak merespons dalam 120 detik | Pertanyaan sangat panjang atau web search berat | Persempit pertanyaan |

Cek cepat dari Telegram: `/ai_status` menampilkan koneksi, model aktif, dan status web search.

## Troubleshooting 409 Conflict

Jika muncul `Conflict: terminated by other getUpdates request`:

1. Pastikan hanya satu instance bot yang berjalan untuk satu token.
2. Jangan jalankan `main.py` dan `dev.py` bersamaan.
3. Hentikan proses lama dulu, lalu jalankan ulang.
