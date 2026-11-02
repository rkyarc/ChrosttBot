"""Setup test: token dummy supaya `config.py` tidak menolak start.

Test tidak pernah memanggil Telegram; semua operasi jaringan di-stub.

AI_API_KEY dikosongkan SEBELUM `config` diimpor. `load_dotenv()` tidak menimpa
environment yang sudah ada, jadi test berperilaku sama di mesin developer (yang
punya `.env` dengan key asli) dan di CI (tanpa `.env`). Tanpa ini, test yang
membaca `config.AI_ENABLED` lulus di lokal tapi gagal di CI.
"""

import os

os.environ.setdefault("TELEGRAM_TOKEN", "0:test-token")
os.environ.setdefault("RIWAYAT_AKTIF", "false")
os.environ["AI_API_KEY"] = ""
