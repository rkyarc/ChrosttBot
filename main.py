import logging
import time

from bot import tg_bot
import bot.handlers  # noqa: F401


class SembunyikanConflict(logging.Filter):
    """Filter biar log spam 409 Conflict tidak memenuhi terminal,
    tapi error lain (misal handler crash) tetap kelihatan."""

    def filter(self, record):
        pesan = record.getMessage()
        return "409" not in pesan and "Conflict" not in pesan


# Error handler tetap kelihatan, tapi spam 409 disaring
logging.getLogger("telebot").setLevel(logging.ERROR)
logging.getLogger("telebot").addFilter(SembunyikanConflict())


def run_bot():
    try:
        tg_bot.remove_webhook()
    except Exception:
        pass

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
        except Exception as e:
            if "409" in str(e) or "Conflict" in str(e):
                print(f"\n⚠️  [SYSTEM] Conflict 409: coba lagi dalam {delay} detik...")
            else:
                print(f"\n❌ [SYSTEM] Error polling: {e}")
                print(f"   Mencoba ulang dalam {delay} detik...")
            time.sleep(delay)
            delay = min(delay + 5, 30)  # backoff bertahap, maksimal 30 detik
        else:
            delay = 5  # reset kalau polling sempat jalan normal


if __name__ == "__main__":
    run_bot()