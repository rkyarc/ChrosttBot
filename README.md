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
- **AI bisa menjalankan fitur** — "hapus background foto ini", "buatkan stiker", "putarkan lagu lofi", "BBCA berapa?", "berita IDX" langsung dieksekusi lewat tool, bukan cuma dijelaskan.
- **Panel admin** — ID di `ADMIN_IDS` dapat statistik, daftar pengguna, dan broadcast.
- Hapus background foto otomatis dari foto yang dikirim ke chat.
- Cek harga saham BEI dan IHSG.
- Berita terbaru seputar IDX/BEI dengan navigasi halaman dan cache 5 menit.
- Download foto, carousel, dan video Instagram.
- Download video TikTok (tanpa/dengan watermark), foto slideshow, dan audio.
- Download video Facebook publik dalam kualitas HD atau SD.
- Download video YouTube; file di atas 50MB dikirim sebagai tautan unduhan.
- **`/play`** — aktifkan mode cari YouTube, lalu kirim judulnya tanpa command.
- **`/play <judul>`** — cari di YouTube langsung, lalu unduh video MP4 atau audio MP3.
- **Stiker** — ubah foto/video jadi stiker Telegram, dan stiker jadi PNG/MP4 (butuh ffmpeg).
- **Hapus pesan** — /del untuk menghapus pesan & media di chat.
- Semua navigasi memakai inline keyboard dengan tampilan ringkas.

## Perintah

| Perintah | Akses | Fungsi |
|---|---|---|
| `/start`, `/menu` | semua | Buka menu utama |
| `/help`, `/bantuan` | semua | Daftar perintah & cara cepat |
| `/id` | semua | Lihat ID Telegram sendiri |
| `/play` | semua | Masuk mode cari YouTube (kirim judul tanpa command) |
| `/play <judul>` | semua | Cari di YouTube lalu unduh video/audio |
| `/ai` | semua | Masuk mode asisten AI |
| `/ai <pertanyaan>` | semua | Tanya sekali tanpa masuk mode |
| `/ai_off` | semua | Keluar dari mode AI |
| `/ai_status` | semua | Status layanan AI & model aktif |
| `/admin` | admin | Panel admin (statistik, pengguna, broadcast) |

## Struktur Project

```text
ChrosttBot/
├── .dockerignore
├── .env.example
├── .github/workflows/ci.yml   # lint + compile + test
├── config.py
├── dev.py
├── docker-compose.yml
├── Dockerfile
├── LICENSE
├── main.py
├── pyproject.toml
├── README.md
├── requirements.txt
├── SECURITY.md
├── tests/                     # unit test (unittest, tanpa jaringan)
└── bot/
    ├── __init__.py          # instance TeleBot (tg_bot)
    ├── admin.py             # parsing ADMIN_IDS, cek akses, data pengguna
    ├── ai_prompt.py         # system prompt & aturan Chrostt AI
    ├── batas_laju.py        # pembatas laju per pengguna
    ├── keyboards.py         # semua inline keyboard
    ├── play_mode.py         # siklus mode tunggu judul /play
    ├── riwayat.py           # penyimpanan riwayat AI + registri pengguna (SQLite)
    ├── sessions.py          # cache sesi per chat (TTL)
    ├── telegram_io.py       # operasi Telegram yang tahan error + retry flood
    ├── utils.py             # helper format, escape HTML, konversi markdown
    ├── handlers/
    │   ├── __init__.py
    │   ├── admin.py
    │   ├── ai.py
    │   ├── background.py
    │   ├── facebook.py
    │   ├── gerbang.py       # gerbang batas laju untuk handler
    │   ├── hapus.py
    │   ├── idx_news.py
    │   ├── instagram.py
    │   ├── menu.py
    │   ├── saham.py
    │   ├── sticker.py
    │   ├── tiktok.py
    │   ├── unduhan.py
    │   └── youtube.py
    └── services/
        ├── __init__.py
        ├── aksi.py          # tool aksi bot yang dipanggil Chrostt AI
        ├── ai.py
        ├── diagnostik.py
        ├── facebook.py
        ├── idx_news.py
        ├── media.py
        ├── removebg.py
        ├── saham.py
        ├── saveinta.py
        ├── sticker.py
        ├── tiktok.py
        ├── websearch.py
        └── youtube.py
```

## Cara Kerja

- `config.py` memuat environment dari `.env` dan menghentikan startup jika `TELEGRAM_TOKEN` kosong.
- `main.py` mendaftarkan semua handler, menyetel daftar perintah bot, lalu menjalankan `tg_bot.infinity_polling()` dengan retry dan backoff otomatis.
- `bot/__init__.py` membuat instance bot Telegram (`tg_bot`).
- `bot/sessions.py` menyimpan sesi per chat (TikTok, Facebook, AI) dengan TTL, supaya memori tidak menumpuk.
- `bot/admin.py` membaca `ADMIN_IDS` dari `.env`, menyediakan cek akses admin, dan mencatat pengguna ke SQLite untuk panel & broadcast.
- `bot/batas_laju.py` membatasi aksi mahal per pengguna (unduh, stiker, AI) memakai jendela geser.
- `bot/ai_prompt.py` menyimpan system prompt Chrostt AI yang membatasi jawaban pada lingkup bot.
- `bot/services/*` menangani komunikasi ke sumber eksternal (gateway AI, rembg, Yahoo Finance, Google News, saveinta, tikwm, fdown, yt-dlp).
- `bot/handlers/*` menangani interaksi Telegram: menu, callback tombol, dan pengiriman media.
- `dev.py` menjalankan mode auto-reload dan mematikan proses lama sebelum restart.

## Ketahanan operasional

Hal-hal yang biasanya membuat bot terasa "kasar" ditangani terpusat:

- `bot/telegram_io.py` membungkus `send_message`, `edit_message_text`, `delete_message`, dan `answer_callback_query`. Error rutin tidak lagi jadi traceback: `message is not modified` dianggap sukses, pesan yang sudah hilang otomatis dikirim ulang, callback kedaluwarsa diabaikan, dan **flood limit diulang** setelah menunggu `retry_after` dari Telegram (maksimal 2 kali percobaan).
- `bot/decorators.py` (`@aman_handler`) menangkap error handler per fitur. Pengguna menerima pesan singkat yang bisa ditindaklanjuti dengan kode handler, traceback lengkap hanya ke log.
- `bot/batas_laju.py` + `bot/handlers/gerbang.py` membatasi aksi mahal per pengguna: 8 unduhan/menit, 10 konversi stiker/menit, 20 pertanyaan AI/menit. Admin tidak dibatasi untuk AI.
- Broadcast admin berjalan di thread terpisah dengan progres `n/total`, jadi worker telebot tidak tertahan dan admin tetap bisa memakai bot.
- Semua handler jaringan punya pesan kegagalan spesifik (ffmpeg tidak ada, video terlalu besar, halaman diblokir) alih-alih error mentah.
- Mode interaktif selalu punya jalan keluar eksplisit: `batal`, perintah lain, tombol keluar, atau TTL. Tidak ada mode yang bisa "nyangkut" tanpa batas.

## Persyaratan

- Python `>=3.10`
- ffmpeg di PATH (wajib untuk fitur Stiker dan menggabung video+audio YouTube)
- Token bot Telegram dari BotFather
- Poetry (opsional, bisa juga pakai pip atau Docker)

## Menjalankan dengan Docker

```bash
cp .env.example .env      # isi TELEGRAM_TOKEN
docker compose up -d --build
docker compose logs -f    # lihat log bot
```

Image sudah memuat `ffmpeg`, berjalan sebagai user non-root, dan memakai `HEALTHCHECK`. Folder `./data` di-mount ke `/app/data` supaya database riwayat dan registri pengguna tetap ada saat container dibuat ulang.

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

## Test & CI

Test memakai `unittest` bawaan Python, tanpa dependency tambahan dan **tanpa jaringan** — semua panggilan Telegram dan layanan luar di-stub.

```bash
poetry run python -m unittest discover -s tests -t . -v
```

Cakupan saat ini:

| Berkas | Yang diuji |
|---|---|
| `tests/test_utils.py` | escape HTML, pemotongan teks/HTML (tag tetap seimbang), konversi markdown |
| `tests/test_sessions.py` | TTL sesi, batas entri, isolasi antar chat |
| `tests/test_riwayat.py` | simpan/baca riwayat, pemangkasan, hapus, state, registri pengguna |
| `tests/test_batas_laju.py` | kuota per pengguna, kuota per jenis aksi, perilaku `periksa()` |
| `tests/test_telegram_io.py` | parsing `retry_after`, retry flood, menyerah setelah batas |
| `tests/test_media.py` | batas 50MB, isi pesan tautan unduhan, tombol alternatif |
| `tests/test_unduhan.py` | keempat downloader mengirim tautan (bukan error) saat file besar, dan batas laju benar-benar menghentikan unduhan |
| `tests/test_hapus.py` | `/del`: hapus per pesan, fallback bulk, batas 100, message_id kecil, escape argumen, laporan gagal |
| `tests/test_play_mode.py` | prompt ForceReply selalu dibersihkan, mode di grup selective, pembersihan sisa setelah restart |
| `tests/test_ai_service.py` | pemetaan error gateway, JSON bercampur sisa SSE, normalisasi konten, alur tool calling |
| `tests/test_youtube_service.py` | pencarian, terjemahan error yt-dlp, video >1 jam jadi tautan, `.part` tidak pernah dikirim |
| `tests/test_websearch.py` | validasi backend ddgs, parsing tanggal, prioritas kesegaran, fallback Wikipedia |
| `tests/test_admin.py` | cek admin dari `from_user`, penolakan di grup, pencatatan pengguna |
| `tests/test_broadcast.py` | broadcast async, hitungan sukses/gagal, penolakan broadcast ganda |
| `tests/test_dependency.py` | `pyproject.toml` dan `requirements.txt` tetap sinkron |

Total **231 test**. Coverage `bot/`: **45%** keseluruhan, dengan modul inti dan jalur berisiko tinggi di atas 85% (`riwayat` 91%, `hapus` 89%, `youtube` service 87%, `play_mode` 93%, `unduhan` 100%, `sessions` 100%, `gerbang` 93%).

Langkah verifikasi lengkap (sama seperti yang dijalankan CI):

```bash
poetry run ruff check bot main.py config.py tests
poetry run python -m compileall -q bot main.py config.py
poetry run python -m unittest discover -s tests -t .
```

Aturan lint ada di `[tool.ruff]` pada `pyproject.toml`: `F`, `E4`, `E7`, `E9`, `B`, `SIM`, `PIE`, `RUF100`, dengan `line-length = 100`. `BLE001` sengaja diabaikan karena handler bot memang menangkap `Exception` luas agar satu fitur gagal tidak menjatuhkan bot.

CI di `.github/workflows/ci.yml` menjalankan keempat langkah itu di Python 3.10 dan 3.12 untuk setiap push ke `dev/**`/`staging` dan setiap PR ke `main`/`staging`.

## Cara Pakai

- Kirim `/start` atau `/menu` untuk membuka menu utama.
- Ketik `/id` untuk melihat ID Telegram kamu (dipakai mengisi `ADMIN_IDS`).
- Tekan **✦ Chrostt AI** atau kirim `/ai` untuk masuk mode asisten. Setelah aktif, setiap teks yang kamu kirim otomatis jadi pertanyaan.
- `/ai <pertanyaan>` untuk tanya sekali tanpa masuk mode.
- `/ai_off` untuk keluar dari mode AI, `/ai_status` untuk melihat status layanan dan model.
- Pilih menu saham untuk cek IHSG atau cari kode emiten seperti `BBCA` dan `ASII`.
- Kirim foto biasa ke chat untuk proses hapus background.
- Kirim link Instagram, TikTok, Facebook, atau YouTube di chat; bot mendeteksi link otomatis dan link tidak akan dianggap pertanyaan AI.
- Menu **Stiker**: tekan "Buat Stiker" lalu kirim foto/video, atau "Stiker → PNG/MP4" lalu kirim stiker.

## Stiker

Fitur stiker memakai **ffmpeg** (tidak butuh Pillow). Pastikan `ffmpeg` dan `ffprobe` ada di PATH; kalau tidak, menu Stiker menampilkan pesan bahwa fitur belum siap.

| Arah | Input | Output |
|---|---|---|
| Foto → stiker | JPG/PNG/WebP | WebP statis 512×512, maks 512 KB |
| Video → stiker | MP4/MOV/animation | **WEBM VP9** 3 detik, maks 256 KB |
| Stiker statis → gambar | WebP | PNG frame pertama |
| Stiker video → gambar | WEBM VP9 | PNG frame pertama |
| Stiker bergerak → video | WEBM / WebP animasi | MP4 H.264 |

Detail teknis:

- **Video sticker Telegram wajib `.WEBM` codec VP9**, bukan animated WebP. Animated WebP ditolak `sendSticker`, jadi jalur video memakai `libvpx-vp9`.
- Batas ukuran berbeda: stiker statis 512 KB, stiker video hanya **256 KB** (batas Telegram). Video dikompres bertahap (bitrate 420k → 160k, fps 30 → 15) sampai lolos.
- Stiker Telegram ada 3 jenis dan ekstensinya beda: `.webp` (statis), `.webm` (video), `.tgs` (animasi vektor). `.tgs` berbasis Lottie-gzip dan **tidak bisa** diproses ffmpeg, jadi ditolak dengan pesan jelas.
- Skala memakai `force_original_aspect_ratio=decrease`, jadi rasio asli tidak dipotong dan sisi terpanjang maksimal 512 px.
- Stiker Telegram selalu tanpa audio, jadi trek suara dibuang (`-an`).
- Video dipotong 3 detik pertama; untuk stiker dari video yang lebih panjang, potongan bisa diatur lewat parameter `mulai` di service.
- File sementara disimpan di folder `chrostt-stiker-*` dan dihapus setelah selesai, termasuk kalau terjadi error.

## YouTube

YouTube sejak 2024 **tidak lagi menyediakan format progresif** (video+audio menyatu) untuk sebagian besar video. Semua format video bersifat video-only, jadi downloader ini mengunduh video dan audio terpisah lalu menggabungkannya dengan ffmpeg.

| Fitur | Cara |
|---|---|
| Unduh dari link | Kirim link YouTube (watch, shorts, live replay, youtu.be) |
| Mode cari | `/play` — bot menunggu, kirim judul tanpa command |
| Cari langsung | `/play judul lagu` — 20 hasil, 5 per halaman, user pilih nomor |
| Pilih format | Setelah memilih video: **🎬 Video MP4** atau **🎵 Audio MP3** |

`/play` mengambil **20 hasil** dari YouTube lalu menampilkannya **5 per halaman** (4 halaman) lengkap dengan judul, channel, durasi, dan jumlah tayangan.

### Mode tunggu query

`/play` tanpa argumen mengirim prompt dengan **ForceReply**: kolom input user otomatis berada dalam mode *balas* ke pesan bot (sama seperti menekan "Reply" lalu mengetik). User tinggal mengirim judulnya, dan bot langsung mencari **tanpa mengetik `/play` lagi**. Mode aktif 10 menit sejak aktivitas terakhir, jadi beberapa judul bisa dikirim berturut-turut.

- Di grup, prompt membalas pesan `/play` user dan ForceReply-nya `selective`, jadi hanya user yang meminta yang kolom inputnya terbuka.
- `/play <judul>` tetap bisa dipakai kapan saja untuk mencari langsung; mode tunggu ikut ditutup.
- Kata `batal` / `cancel` menghentikan mode, begitu juga perintah lain (`/start`, `/ai`, …), pengiriman media atau link.
- **Prompt ForceReply dihapus otomatis** begitu mode berakhir (judul diterima, dibatalkan, perintah lain, atau tombol apa pun ditekan). Ini yang membuat kolom balas tidak muncul lagi saat chat ditutup lalu dibuka kembali — ForceReply menempel pada pesan prompt, jadi selama pesan itu ada Telegram terus menampilkan status balas.
- ID prompt juga dicatat di SQLite. Kalau bot restart saat mode masih aktif, prompt lama dibersihkan saat startup (`play_mode.bersihkan_sisa()`) sehingga tidak menggantung di chat.
- Tombol **🔍 Judul Lain** di daftar hasil membuka prompt baru tanpa mengetik `/play`.
- Mode AI tidak merebut pesan selama mode `/play` aktif, dan sebaliknya `/play` menang di chat yang sama.


- Setiap hasil punya tombol sendiri dengan **indeks global** (`yt_pilih_0` … `yt_pilih_19`), jadi memilih dari halaman mana pun tetap mengunduh video yang benar.
- Navigasi: `« Prev` / `x/4` / `Next »`. Tombol Prev disembunyikan di halaman 1, Next disembunyikan di halaman terakhir.
- Nomor tombol melanjutkan penomoran global (halaman 2 mulai dari `6.`), sesuai teks di atasnya.
- Tombol `x/4` bersifat pasif; menekannya hanya menampilkan info jumlah hasil.
- Halaman di luar rentang otomatis diklem ke halaman 1 atau terakhir.
- Kalau hasil kurang dari 5, navigasi halaman tidak ditampilkan.

Contoh tampilan:

```
HASIL UNTUK "me at the zoo"

1. Me at the zoo
     jawed · 0:19 · 447.3jt

2. "Me at the Zoo" Is Now in a Museum
     Real Vintage Dolls House · 29:17 · 20rb
```

Detail teknis:

- Format: `bestvideo[filesize<50M][ext=mp4]+bestaudio[ext=m4a]`, lalu `merge_output_format=mp4`. Ada 3 tingkat fallback kalau batas ukuran tidak bisa diprediksi.
- Audio diekstrak ke MP3 128 kbps lewat post-processor `FFmpegExtractAudio`.
- **Durasi dicek sebelum unduh** (`skip_download=True`). Video >1 jam ditolak dalam ~2 detik, bukan setelah mengunduh ratusan MB.
- Batas 50MB (limit Bot API) dijaga dua lapis: `max_filesize` di yt-dlp dan pengecekan ulang setelah unduhan. Kalau file tetap lebih besar (atau video >1 jam), bot tidak menampilkan error melainkan mengirim **tautan unduhan** `youtu.be`/`watch?v=` supaya bisa diambil lewat browser.
- Live stream berjalan ditolak lewat `match_filter=!is_live`.
- Folder sementara dihapus di blok `finally`, termasuk saat download atau upload gagal.
- Error yt-dlp diterjemahkan ke bahasa manusia: video privat, tidak tersedia, butuh login umur, diblokir wilayah, timeout, dan ffmpeg hilang.

Contoh:

```
/play
lofi hip hop
tutorial python
batal

/play me at the zoo
```

## Hapus Pesan (/del)

Fitur untuk membersihkan chat: menghapus pesan teks, foto, video, stiker, atau dokumen.

| Perintah | Fungsi |
|---|---|
| `/del` | Hapus pesan perintah itu sendiri |
| `/del` (sebagai reply) | Hapus pesan/media yang dibalas + pesan perintah |
| `/del 5` | Hapus 5 pesan terakhir termasuk perintah |
| `/del all` | Hapus sampai 100 pesan terakhir |

Detail teknis:

- Memakai `deleteMessages` (bulk, maks 100 ID per request) dengan fallback `deleteMessage` per pesan kalau bulk gagal sebagian. `deleteMessages` tidak melempar exception saat ada pesan yang hilang, ia hanya mengembalikan `False`, jadi hasilnya dicek eksplisit.
- Rentang ID dihitung dari `message_id` perintah ke belakang (akhir - jumlah + 1). Pesan yang tidak ada dilewati otomatis.
- Bila semua berhasil, bot tidak mengirim laporan apa pun agar chat tetap bersih. Laporan hanya muncul kalau ada yang gagal.
- Error Telegram diterjemahkan: pesan tidak ditemukan, pesan lebih dari 48 jam, bot kurang izin, chat tidak ditemukan.
- Tombol **🗑️ Hapus Pesan** di menu utama menampilkan panduan + batasan.

Batasan Telegram yang tidak bisa dilanggar bot:

- Pesan hanya bisa dihapus dalam **48 jam** sejak dikirim.
- Di grup, bot harus **admin** dengan izin *Delete messages*.
- Pesan layanan sistem (pin, join, ganti foto grup) tidak bisa dihapus.

## Logging Aktivitas

Bot bisa mencetak setiap command, pesan teks, dan penekanan tombol ke console. Karena isi pesan pengguna adalah data pribadi, fitur ini **mati secara default** dan harus dinyalakan sadar-sadar saat debugging:

```env
LOG_USER_MESSAGES=false
LOG_USER_MEDIA=false
```

| Variabel | Default | Fungsi |
|---|---|---|
| `LOG_USER_MESSAGES` | `false` | Cetak command, teks, dan callback ke console |
| `LOG_USER_MEDIA` | `false` | Ikut cetak pesan berisi media (foto/video/stiker) |

Aktifkan hanya sementara di mesin development. Di server produksi biarkan `false` supaya percakapan pengguna tidak tersimpan di log.

Contoh output:

```
[20:04:02] CMD /play      /play lofi hip hop
           └─ id=987654321 | @ilham | Ilham Pratama | chat=private:12345
[20:04:05] CB             yt_pilih_3
           └─ id=987654321 | @ilham | Ilham Pratama
[20:04:09] MSG            halo bot
           └─ id=987654321 | @ilham | Ilham Pratama | chat=private:12345
```

Detail teknis:

- Dipasang sebagai **middleware** telebot (`bot/user_log.py`), bukan handler, jadi tidak ikut rantai handler dan tidak bisa "menelan" update.
- Middleware memakai `update_sensitive=True` dengan `pre_process_message` / `pre_process_callback_query`, karena dict `data` tidak membawa `update_type`.
- Isi pesan dipotong 120 karakter dan newline diubah jadi `⏎` agar console tidak banjir.
- Logging dibungkus `try/except`; kegagalan logging tidak pernah menjatuhkan handler.
- Media hanya dicetak bila `LOG_USER_MEDIA=true`, supaya tidak spam.
- `post_process_message` / `post_process_callback_query` juga diimplementasikan karena telebot mewajibkannya saat `update_sensitive=True` (kalau tidak, muncul ERROR "does not have post_process_<type>").

## Proteksi Error Handler

Setiap handler dibungkus decorator `@aman_handler` (`bot/decorators.py`) supaya kegagalan tidak membuat user menunggu tanpa balasan.

```python
@tg_bot.message_handler(commands=["start"])
@aman_handler
def tampilkan_menu(message):
    ...
```

**Aturan urutan penting:** `@aman_handler` harus berada **di bawah** decorator telebot (paling dekat `def`). Decorator Python dieksekusi bottom-up, jadi `@aman_handler` membungkus fungsi lebih dulu, baru telebot mendaftarkan hasilnya. Kalau dibalik, telebot mendaftarkan fungsi asli dan guard tidak pernah aktif.

Perilaku saat handler gagal:

- Traceback lengkap masuk log (`chrosttbot.handler`).
- User menerima pesan singkat "Terjadi kesalahan" berisi nama handler, tanpa detail internal.
- Untuk callback, `answerCallbackQuery` dipanggil dulu agar spinner tidak menggantung.
- Kalau chat tidak bisa dihubungi, cukup dicatat di log tanpa melempar error baru.

Handler yang sudah punya `try/except` sendiri (TikTok, YouTube, stiker, hapus, AI, Instagram, Facebook, background) **tidak** dibungkus guard agar pesan error spesifiknya tidak tertimpa. Konsekuensinya tidak ada jaring pengaman otomatis: kalau `except` di handler itu melewatkan jenis error tertentu, pengguna tidak menerima balasan apa pun. Repo ini belum punya test otomatis; verifikasi error masih manual dengan stub `send_message`/`edit_message_text` seperti di bagian **Verifikasi**.

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
- AI juga bisa **menjalankan** fitur bot (hapus background, stiker, putar lagu, saham, berita IDX) lewat tool — lihat [Aksi bot lewat AI](#aksi-bot-lewat-ai-tool).

### Akses admin vs pengguna biasa

Admin (`ADMIN_IDS`) mendapat asisten yang lebih dalam, tanpa membuka jalur eksekusi berbahaya:

| Aspek | Pengguna | Admin |
|---|---|---|
| Batas token | `AI_MAX_TOKENS` | `AI_MAX_TOKENS_ADMIN` |
| Putaran tool | 2 | 4 |
| Tool per putaran | 2 | 3 |
| Hasil web per pencarian | 5 | 8 |
| Isi halaman dibaca | 2.500 karakter | 6.000 karakter |
| Tool aksi bot | ada (5 tool) | ada (5 tool) |
| Tool `status_bot` | tidak ada | ada (read-only) |
| System prompt | dasar | dasar + `Mode admin` |
| `/ai_status` | ringkas | + batas admin & daftar tool |

`status_bot` hanya membaca: uptime proses, jumlah pengguna agregat, model AI, status web search, ketersediaan ffmpeg, versi Python, folder kerja, dan sisa disk. Tidak ada nilai kredensial di outputnya.

Batas yang **tidak** dibuka untuk admin — AI tetap tidak bisa:
- Menjalankan perintah shell, menghapus/menulis file, atau mengeksekusi kode di server.
- Mengubah konfigurasi, me-restart bot, atau mengirim broadcast.
- Menampilkan isi `AI_API_KEY`, `TELEGRAM_TOKEN`, atau kredensial lain.
- Membocorkan system prompt atau data pribadi pengguna lain.

Tool aksi yang bisa dijalankan AI terbatas pada lima fitur bot di `bot/services/aksi.py`. Tidak ada tool untuk menghapus pesan, mengunduh dari link, atau mengubah data; `/del` tetap harus dijalankan pengguna sendiri karena menghapus pesan berantai dari model tidak bisa dibatasi dengan aman.

Pemisahan konteks: sesi AI ditandai `akses` (`admin`/`user`). Kalau peran pengirim berubah di chat yang sama, riwayat otomatis dikosongkan supaya detail teknis milik admin tidak terbawa ke pengguna biasa — relevan terutama di grup. Model juga tidak bisa memaksa memakai `status_bot` saat melayani non-admin: permintaan tool seperti itu ditolak dengan pesan "hanya tersedia untuk admin".


### Riwayat permanen (SQLite)

Riwayat obrolan AI disimpan per chat ke **SQLite** (`data/riwayat-ai.db`), jadi percakapan tetap tersambung setelah bot restart.

Kenapa SQLite: sudah termasuk pustaka standar Python, tanpa server, tanpa dependency baru, dan tetap aman untuk tulisan paralel lewat mode WAL. Satu file saja, mudah dibackup.

- Tabel `chat` menyimpan metadata (ID, nama, username, tipe, tingkat akses, waktu terakhir), tabel `pesan` menyimpan isi percakapan.
- Database dibuat otomatis saat pertama kali dipakai; folder `data/` juga otomatis.
- Ditulis setiap kali ada pertanyaan/jawaban, jadi tidak ada data yang hilang kalau bot mati mendadak.
- Batas arsip: 300 pesan per chat dan maksimal 1.000 chat. Chat paling lama dibuang otomatis saat penuh.
- Yang dikirim ke model tetap dipotong ke 16 pesan / ±12.000 karakter (`MAKS_PESAN_RIWAYAT`), jadi arsip panjang tidak membengkakkan biaya token.
- Riwayat ditandai `akses` (`admin`/`user`). Kalau peran pengirim berubah di chat yang sama, riwayat lama dihapus supaya konteks admin tidak bocor ke pengguna biasa.
- Tombol **🧹 Reset Obrolan** di menu AI menghapus riwayat chat itu dari memori sekaligus dari database.
- `RIWAYAT_AKTIF=false` membuat database berjalan in-memory: riwayat tetap bekerja selama bot hidup, tetapi tidak menyentuh disk.
- `RIWAYAT_DB` bisa diubah untuk memindahkan lokasi file.
- `data/` dan berkas `*.db-wal` / `*.db-shm` sudah masuk `.gitignore`.

### Hapus riwayat lewat panel admin

Panel admin punya menu **🗂️ Riwayat AI** untuk melihat dan menghapus arsip:

- Ringkasan: jumlah chat, total pesan, ukuran database, dan lokasi file.
- Daftar per halaman (5 chat/halaman) berisi nama, ID chat, tipe, tingkat akses, jumlah pesan, dan waktu terakhir. Isi percakapan **tidak** ditampilkan.
- Tombol 🗑️ per chat membuka konfirmasi sebelum menghapus.
- Tombol 🧨 **Hapus Semua** juga meminta konfirmasi dan menyebut jumlah chat/pesan yang akan hilang.
- Semua tombol ini memanggil `_admin_call()`, jadi non-admin hanya mendapat alert "⛔ Hanya untuk admin." dan tidak ada data yang berubah.
- Setelah dihapus, sesi AI di memori untuk chat itu ikut dibersihkan agar riwayat tidak "hidup lagi".


Chrostt AI bisa mencari di internet lewat tool calling. Gateway Hisoka tidak menyediakan web search server-side, jadi pencarian dijalankan oleh bot sendiri.

- `web_search` — cari di web lewat `ddgs`. Backend dipilih dari yang **benar-benar terpasang** di versi ddgs aktif (daftar engine berubah antar versi: `google` sudah dihapus di ddgs 9.16), lalu diverifikasi terhadap `ddgs.engines.ENGINES`. Pasangan `duckduckgo + yahoo` dipakai untuk teks dan `bing + yahoo` untuk berita karena paling andal sekaligus jauh lebih cepat daripada `auto`.
- Rantai sumber: berita (ddgs news) → web (ddgs text) → Google News RSS → Wikipedia. Wikipedia selalu jadi jaring terakhir, jadi pertanyaan konseptual tetap terjawab walau seluruh engine teks sedang kena rate limit.
- `baca_halaman` — ambil isi halaman. Percobaan pertama fetch langsung, lalu fallback ke `r.jina.ai` kalau halaman terlalu berat atau butuh JavaScript.
- **Tanggal hasil**: ddgs news membawa tanggal terbit, sedangkan hasil web umumnya tidak. Untuk pertanyaan yang sensitif waktu, bot membaca `<meta property="article:published_time">` / JSON-LD `datePublished` / `<time datetime>` dari 3 halaman teratas secara paralel, dengan batas 6 detik. Pertanyaan konseptual melewati langkah ini karena tanggal tidak mengubah jawaban.
- **Prioritas kesegaran**: skor akhir = relevansi kata kunci + bonus umur hasil. Bonus lebih besar untuk query yang meminta info terkini ("hari ini", "tadi malam", "harga", "skor", "cuaca", "jadwal"), sehingga hasil baru menang atas arsip lama.
- Tanggal relatif hasil konversi pustaka hanya menampilkan **tanggal**, bukan jam, karena jamnya memakai waktu sekarang dan menyesatkan. Jam hanya ditampilkan kalau dibaca langsung dari halaman artikel. Tanggal yang jatuh di masa depan ditandai "tidak wajar".
- Hasil pencarian difilter skor relevansi terhadap kata kunci, jadi hasil "nyasar" tidak dipakai. Domain spam/judi/klikbait dibuang, URL didedup, dan maksimal 2 hasil per domain.
- Halaman yang isinya cuma pesan error, 404, captcha, atau boilerplate ditolak lewat penilaian kualitas teks.
- Semua URL dicek dulu: alamat private/loopback/link-local (`127.0.0.1`, `10.x`, `192.168.x`, `169.254.169.254`) dan skema selain http/https ditolak, supaya model tidak bisa dipakai SSRF.
- Batas biaya: maksimal 2 putaran tool, 2 tool per putaran, 5 hasil per pencarian, ringkasan 240 karakter. Query yang sudah pernah dicari dilewati agar tidak mengulang. Admin mendapat batas lebih longgar (4 putaran, 3 tool, 8 hasil, isi halaman 6.000 karakter).
- Putaran penutup mengirim `tool_choice: "none"` supaya model wajib menjawab dan tidak menulis tool call sebagai teks mentah.
- Log `primp` dan `ddgs` diturunkan ke WARNING; sebelumnya setiap request HTTP dicatat di level INFO sehingga console bot banjir.
- Matikan dengan `AI_WEB_SEARCH=false` di `.env` kalau ingin jawaban murni dari pengetahuan model.

### Aksi bot lewat AI (tool)

Selain menjawab, Chrostt AI bisa **menjalankan fitur bot** atas permintaan biasa — bukan cuma menjelaskan caranya. Contoh: "hapus background foto ini", "bikinin stiker dari foto tadi", "putarkan lagu lofi", "BBCA sekarang berapa?", "berita IDX terbaru".

Tool yang tersedia ada di `bot/services/aksi.py`:

| Tool | Yang dikirim ke chat | Batas laju |
|---|---|---|
| `hapus_background` | PNG transparan | `umum` |
| `buat_stiker` | stiker WebP/WEBM | `stiker` |
| `putar_lagu` | audio MP3, video MP4, atau daftar hasil | `unduh` |
| `cek_saham` | harga terakhir + catatan bukan rekomendasi | `umum` |
| `berita_idx` | judul, sumber, tanggal, tautan | `umum` |

- **Media terakhir diingat.** Foto yang dikirim pengguna disimpan di `SessionStore` (TTL 30 menit), jadi AI bisa memproses "foto tadi" tanpa pengguna mengirim ulang. Model tidak pernah menerima `file_id`.
- **Foto ber-caption.** Saat mode AI aktif, foto dengan caption diperlakukan sebagai instruksi (caption jadi pertanyaan, foto jadi bahan). Foto **tanpa** caption tetap otomatis dihapus background-nya seperti biasa. Caption `/ai ...` juga membuka alur ini walau mode AI belum aktif.
- **Alur lain tidak direbut.** Kalau `/play` sedang menunggu judul atau alur stiker sedang aktif, media tetap milik alur tersebut. Caption yang diawali perintah lain (mis. `/play`) tidak dianggap instruksi AI.
- **Hasil tool tidak disalin model.** Tool mengirim file/pesan sendiri, dan yang dikembalikan ke model hanya catatan singkat ("Berhasil: ..."). System prompt melarang model menulis ulang detail teknis atau menyebut nama tool.
- **Batas laju tetap berlaku.** Aksi lewat AI memakai `batas_laju` yang sama dengan perintah manual, jadi model tidak bisa dipakai untuk melewati kuota. Ini penting karena satu pesan bisa memicu beberapa tool.
- **File besar.** Kalau unduhan YouTube melewati 50MB, tool mengembalikan tautan sumber dan model menyampaikannya ke pengguna, bukan gagal diam-diam.
- Matikan dengan `AI_AKSI_BOT=false` di `.env` kalau ingin AI kembali hanya menjawab dan mencari web.

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
- 👥 **Pengguna** — 20 pengguna terakhir beserta ID Telegram (dibaca dari SQLite, jadi bertahan setelah restart).
- 📢 **Broadcast** — kirim satu pesan HTML ke semua pengguna yang pernah chat; ada preview, konfirmasi, progres `n/total`, dan laporan sukses/gagal. Berjalan di thread terpisah sehingga bot tetap responsif. Draft kedaluwarsa 10 menit.
- Perintah `/admin` otomatis muncul di menu `/` hanya untuk chat admin (BotCommandScopeChat).

Pengamanan: setiap aksi admin dicek ulang dari `from_user.id` (bukan `chat.id`), jadi menambah bot ke grup tidak memberi siapa pun akses admin. Pengguna non-admin yang mencoba `/admin` atau tombol panel mendapat pesan "Akses ditolak".

## Catatan

- `.env` berisi `TELEGRAM_TOKEN` dan kredensial AI; file ini sudah masuk `.gitignore`, jangan di-commit.
- `.gitignore` sudah mencakup `.env*`, virtualenv, `__pycache__`, cache tooling, `downloads/`, `.handler-saves/` (state pyTelegramBotAPI), log, serta folder editor/OS.
- Fitur hapus background memakai API rembg gratis, jadi tidak perlu `REMOVE_BG_API_KEY`.
- Batas upload Bot API Telegram adalah 50MB. File di atas batas itu (Instagram, TikTok, Facebook, YouTube) tidak lagi berakhir sebagai error: bot mengirim pesan **LINK UNDUHAN** berisi tautan sumber, ukuran file, dan tombol pembuka browser.
- Aksi mahal dibatasi per pengguna (unduhan, stiker, AI). Pesan penolakan menyebut sisa waktu tunggu, jadi pengguna tidak bingung.
- Registri pengguna (untuk panel & broadcast) disimpan di SQLite, bukan memori — daftar tidak hilang saat restart.
- Kebijakan keamanan dan data ada di `SECURITY.md`; kode berlisensi MIT (`LICENSE`).
- Kode saham Indonesia ditulis tanpa `.JK` saat input, misalnya `BBCA`.
- IHSG diambil melalui kode `^JKSE`.
- Dependensi utama ada di `pyproject.toml` (dikunci di `poetry.lock`), `requirements.txt` disediakan untuk instalasi berbasis pip dan Docker. `tests/test_dependency.py` menjaga keduanya tetap sinkron.
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
