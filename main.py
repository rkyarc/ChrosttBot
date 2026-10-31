import logging
import sys
import time

import config
import bot.handlers  # noqa: F401  (mendaftarkan semua handler)
from bot import tg_bot
from bot.admin import pasang_listener
from telebot.types import BotCommand, BotCommandScopeChat


def _perbaiki_encoding_console():
    """Windows console (cp1252/cp437) tidak bisa cetak emoji -> pakai UTF-8."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


class SembunyikanConflict(logging.Filter):
    """Saring log spam 409 Conflict, tapi error lain tetap kelihatan."""

    def filter(self, record):
        pesan = record.getMessage()
        return "409" not in pesan and "Conflict" not in pesan


_perbaiki_encoding_console()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("telebot").setLevel(logging.ERROR)
logging.getLogger("telebot").addFilter(SembunyikanConflict())

log = logging.getLogger("chrosttbot")

PERINTAH_UMUM = [
    BotCommand("start", "Buka menu utama"),
    BotCommand("ai", "Tanya Chrostt AI"),
    BotCommand("ai_off", "Keluar dari mode AI"),
    BotCommand("ai_status", "Cek status AI"),
    BotCommand("id", "Lihat ID Telegram kamu"),
    BotCommand("help", "Bantuan & daftar perintah"),
]

PERINTAH_ADMIN = PERINTAH_UMUM + [
    BotCommand("admin", "Panel admin bot"),
]


def daftarkan_perintah():
    """Daftarkan perintah global + perintah khusus admin (scope per chat)."""
    try:
        tg_bot.set_my_commands(PERINTAH_UMUM)
    except Exception as e:
        log.warning("Gagal mendaftarkan perintah umum: %s", e)

    for admin_id in config.ADMIN_IDS:
        try:
            tg_bot.set_my_commands(PERINTAH_ADMIN, scope=BotCommandScopeChat(admin_id))
        except Exception as e:
            log.warning("Gagal mendaftarkan perintah admin untuk %s: %s", admin_id, e)


def run_bot():
    try:
        tg_bot.remove_webhook()
    except Exception:
        pass

    daftarkan_perintah()
    pasang_listener()

    log.info("Chrostt Bot siap (AI: %s, model: %s, admin: %s)",
             "aktif" if config.AI_ENABLED else "nonaktif",
             config.AI_MODEL,
             len(config.ADMIN_IDS))
    print("[SYSTEM] Super App Bot sedang berjalan. Silakan buka Telegram Anda!")

    # Jeda singkat biar sesi lama sempat terlepas dari server Telegram
    time.sleep(2)

    delay = 5
    while True:
        try:
            tg_bot.infinity_polling(
                timeout=40,
                long_polling_timeout=40,
                skip_pending=True,
            )
        except KeyboardInterrupt:
            print("\n[SYSTEM] Bot dihentikan.")
            break
        except Exception as e:
            if "409" in str(e) or "Conflict" in str(e):
                log.warning("Conflict 409: coba lagi dalam %s detik", delay)
            else:
                log.error("Error polling: %s (retry dalam %s detik)", e, delay)
            time.sleep(delay)
            delay = min(delay + 5, 30)  # backoff bertahap, maksimal 30 detik
        else:
            delay = 5  # reset kalau polling sempat jalan normal


if __name__ == "__main__":
    run_bot()
