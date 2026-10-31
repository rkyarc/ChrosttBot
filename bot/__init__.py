import logging

import telebot

from config import TELEGRAM_TOKEN

log = logging.getLogger("chrosttbot")


def _tangani_error(exception):
    """Catat error handler, jangan biarkan bot berhenti diam-diam."""
    log.exception("Error saat memproses update: %s", exception)
    return True


# Rename dari 'bot' jadi 'tg_bot' untuk hindari konflik namespace
tg_bot = telebot.TeleBot(
    TELEGRAM_TOKEN,
    # AI butuh waktu lama, jadi worker diperbesar supaya user lain tidak ikut menunggu
    num_threads=12,
    disable_web_page_preview=True,
    exception_handler=_tangani_error,
)

