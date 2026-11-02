# Kebijakan Keamanan

## Melaporkan kerentanan

Jangan membuka issue publik untuk masalah keamanan. Kirim laporan lewat
**Security → Report a vulnerability** di repository GitHub, atau hubungi
maintainer langsung (`@rkyarc`, `@RusdiEneri`).

Sertakan:

- Versi/branch yang terdampak
- Langkah reproduksi (tanpa menyertakan token asli)
- Dampak yang mungkin terjadi

Laporan akan ditinjau dalam 7 hari kerja.

## Data yang disimpan bot

| Data | Lokasi | Retensi |
|---|---|---|
| Riwayat obrolan AI | `data/riwayat-ai.db` (SQLite) | 300 pesan per chat, maks 1000 chat |
| Registri pengguna (ID, nama, username) | tabel `pengguna` di database yang sama | sampai dihapus manual |
| ID prompt `/play` | tabel `state` | dihapus otomatis saat mode berakhir |
| Berkas media sementara | folder `chrostt-*` di temp sistem | dihapus setelah dikirim |

Isi percakapan **tidak** dicatat ke log secara default (`LOG_USER_MESSAGES=false`).

## Rahasia

- `TELEGRAM_TOKEN` dan `AI_API_KEY` hanya dibaca dari `.env`, yang tidak
  di-commit (`.gitignore`).
- Jangan pernah menempelkan isi `.env` ke issue, PR, atau log.
- Jika token bocor: cabut lewat BotFather (`/revoke`) lalu ganti di server.

## Batasan yang sudah diterapkan

- Panel admin hanya bisa dibuka di chat pribadi, dan setiap aksi dicek ulang
  dari `from_user.id`.
- AI tidak punya jalur eksekusi: tidak ada shell, tulis/hapus file, ubah
  konfigurasi, atau broadcast otomatis.
- Pengambilan halaman web menolak alamat private/loopback/link-local (anti-SSRF).
- Perintah eksternal memakai bentuk list tanpa `shell=True`.
- Ukuran unduhan dibatasi 50MB sebelum masuk memori/RAM server.
