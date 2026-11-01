from dotenv import load_dotenv
import os
import re


load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
# REMOVE_BG_API_KEY = os.getenv("REMOVE_BG_API_KEY")


def _parse_id_list(nilai: str) -> tuple[int, ...]:
    """Parse daftar ID dari .env: '123,456' / '[123, 456]' / '123 456'."""
    if not nilai:
        return ()

    bersih = nilai.strip().strip("[]")
    hasil = []

    for bagian in re.split(r"[,\s]+", bersih):
        bagian = bagian.strip().strip("'\"")
        if not bagian:
            continue
        try:
            hasil.append(int(bagian))
        except ValueError:
            # Abaikan entri rusak, jangan sampai bot gagal start
            continue

    # Buang duplikat, pertahankan urutan
    return tuple(dict.fromkeys(hasil))



# ========================
# LOGGING AKTIVITAS USER
# ========================
def _env_bool(nama: str, default: bool = False) -> bool:
    nilai = (os.getenv(nama) or "").strip().lower()
    if not nilai:
        return default
    return nilai not in ("0", "false", "no", "off")


# Cetak setiap pesan/command user ke console
LOG_USER_MESSAGES = _env_bool("LOG_USER_MESSAGES", True)

# Ikut cetak pesan berisi media (foto/video/stiker), bukan hanya teks
LOG_USER_MEDIA = _env_bool("LOG_USER_MEDIA", False)

# ========================
# ADMIN
# ========================
# Array ID Telegram yang punya akses admin. Contoh di .env:
#   ADMIN_IDS=123456789,987654321
ADMIN_IDS = _parse_id_list(os.getenv("ADMIN_IDS") or "")
ADMIN_IDS_SET = frozenset(ADMIN_IDS)

# ========================
# AI ASSISTANT (OpenAI-compatible gateway)
# ========================
AI_BASE_URL = (os.getenv("AI_BASE_URL") or "https://ai.hisoka.net/api/v1").rstrip("/")
AI_API_KEY = (os.getenv("AI_API_KEY") or "").strip()
AI_MODEL = (os.getenv("AI_MODEL") or "deepseek-v4.1-flash-1017").strip()
AI_ENABLED = bool(AI_API_KEY)

AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE") or "0.7")
AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS") or "1400")
AI_MAX_TOKENS_ADMIN = int(os.getenv("AI_MAX_TOKENS_ADMIN") or "2400")

# Web search: model boleh cari & baca halaman sendiri lewat tool calling
AI_WEB_SEARCH = (os.getenv("AI_WEB_SEARCH") or "true").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)

# ========================
# PENYIMPANAN RIWAYAT AI
# ========================
# Riwayat obrolan AI disimpan permanen di SQLite (tanpa server, tanpa dependency).
RIWAYAT_DB = (
    os.getenv("RIWAYAT_DB") or os.path.join("data", "riwayat-ai.db")
).strip()

# false = jangan simpan ke disk (database in-memory, hilang saat bot berhenti)
RIWAYAT_AKTIF = _env_bool("RIWAYAT_AKTIF", True)

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN belum diisi. Cek file .env kamu.")
