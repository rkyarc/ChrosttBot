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

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN belum diisi. Cek file .env kamu.")
