# Aturan Project Chrostt Bot

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

## Catatan

- Saat ini `dev/ilham` dan `staging` sudah berada di atas `origin/main`
  (perbaikan bug, Chrostt AI, panel admin), sedangkan `dev/ricky` masih di
  `b4ea2a1` dan belum memuat perubahan tersebut.
- Jangan merge `main` ke branch kerja tanpa diminta.
