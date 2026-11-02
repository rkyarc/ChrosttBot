"""Setup test: token dummy supaya `config.py` tidak menolak start.

Test tidak pernah memanggil Telegram; semua operasi jaringan di-stub.
"""

import os

os.environ.setdefault("TELEGRAM_TOKEN", "0:test-token")
os.environ.setdefault("RIWAYAT_AKTIF", "false")
