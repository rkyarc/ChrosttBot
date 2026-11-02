import contextlib
import logging
import signal
import sys
import threading
import time

import config
import bot.handlers  # noqa: F401  (mendaftarkan semua handler)
from bot import play_mode, tg_bot
from bot.admin import pasang_listener
from bot import user_log
from telebot.types import BotCommand, BotCommandScopeChat


def _perbaiki_encoding_console():
    """Windows console (cp1252/cp437) tidak bisa cetak emoji -> pakai UTF-8."""
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            stream.reconfigure(encoding="utf-8", errors="replace")


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

# primp (HTTP client di balik ddgs) mencatat setiap request di level INFO.
# Itu membanjiri console bot tanpa nilai operasional, jadi diturunkan.
logging.getLogger("primp").setLevel(logging.WARNING)
logging.getLogger("ddgs").setLevel(logging.WARNING)

log = logging.getLogger("chrosttbot")

PERINTAH_UMUM = [
    BotCommand("start", "Buka menu utama"),
    BotCommand("play", "Cari YouTube (kirim judul setelahnya)"),
    BotCommand("ai", "Tanya Chrostt AI"),
    BotCommand("ai_off", "Keluar dari mode AI"),
    BotCommand("ai_status", "Cek status AI"),
    BotCommand("del", "Hapus pesan/media di chat"),
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


def _pasang_sinyal_berhenti() -> None:
    """Tangkap SIGTERM/SIGINT supaya shutdown rapi, termasuk dari Docker.

    Tanpa ini, `docker compose down` mengirim SIGTERM yang mematikan proses
    tanpa membersihkan prompt ForceReply /play, sehingga kolom balas bisa
    menggantung di chat pengguna setelah container naik lagi.
    """
    if threading.current_thread() is not threading.main_thread():
        # signal.signal hanya boleh dipanggil di thread utama
        return

    def _berhenti(signum, _frame):
        log.info("Sinyal %s diterima, menutup bot...", signal.Signals(signum).name)
        with contextlib.suppress(Exception):
            play_mode.tutup_semua()
        raise SystemExit(0)

    for nama in ("SIGTERM", "SIGINT", "SIGHUP"):
        sinyal = getattr(signal, nama, None)
        if sinyal is None:
            continue
        with contextlib.suppress(ValueError, OSError):
            signal.signal(sinyal, _berhenti)


def run_bot():
    with contextlib.suppress(Exception):
        tg_bot.remove_webhook()

    _pasang_sinyal_berhenti()

    daftarkan_perintah()
    pasang_listener()
    user_log.pasang(tg_bot)

    # Prompt ForceReply /play dari sesi sebelumnya bisa menggantung setelah
    # restart (kolom balas tetap muncul saat chat dibuka). Bersihkan di awal.
    try:
        play_mode.bersihkan_sisa()
    except Exception:
        log.warning("Gagal membersihkan prompt /play lama", exc_info=True)

    from bot.services.sticker import tersedia as ffmpeg_tersedia

    log.info("Chrostt Bot siap (AI: %s, model: %s, admin: %s, ffmpeg: %s)",
             "aktif" if config.AI_ENABLED else "nonaktif",
             config.AI_MODEL,
             len(config.ADMIN_IDS),
             "ada" if ffmpeg_tersedia() else "TIDAK ADA")

    if not ffmpeg_tersedia():
        log.warning("ffmpeg tidak ditemukan - fitur Stiker nonaktif sampai ffmpeg terpasang")

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
        except (KeyboardInterrupt, SystemExit):
            print("\n[SYSTEM] Bot dihentikan.")
            with contextlib.suppress(Exception):
                play_mode.tutup_semua()
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
