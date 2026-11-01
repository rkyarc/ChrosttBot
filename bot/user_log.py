"""Logging aktivitas user ke console.

Dipasang sebagai middleware telebot supaya setiap pesan/callback yang masuk
tercatat SEBELUM handler dijalankan. Ini berguna untuk melihat command apa
yang dipakai user dan siapa pengirimnya.

Diaktifkan lewat LOG_USER_MESSAGES di .env (default: true).
"""

import logging
import time

import config
from bot.utils import escape_html  # noqa: F401  (dipakai saat debug)


log = logging.getLogger("chrosttbot.user")

# Batas panjang teks yang dicetak supaya console tidak banjir
MAKS_TEKS = 120

_HARI = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")


def _jam() -> str:
    return time.strftime("%H:%M:%S")


def _potong(teks: str, batas: int = MAKS_TEKS) -> str:
    teks = (teks or "").replace("\n", " ⏎ ").strip()
    if not teks:
        return ""
    if len(teks) <= batas:
        return teks
    return teks[: batas - 1] + "…"


def _identitas(user) -> str:
    if not user:
        return "unknown"

    uid = getattr(user, "id", "?")
    nama = getattr(user, "full_name", "") or getattr(user, "first_name", "") or ""
    username = getattr(user, "username", None)

    bagian = [f"id={uid}"]
    if username:
        bagian.append(f"@{username}")
    if nama:
        bagian.append(nama[:30])
    return " | ".join(bagian)


def _jenis_media(message) -> str:
    """Tebak jenis konten pesan untuk ditampilkan di log."""
    if getattr(message, "text", None):
        return "text"
    for nama in (
        "photo",
        "video",
        "animation",
        "sticker",
        "document",
        "audio",
        "voice",
        "video_note",
        "location",
        "contact",
    ):
        if getattr(message, nama, None):
            return nama
    return "other"


def _cetak(baris: str, level: int = logging.INFO) -> None:
    """Cetak ke console (print) sekaligus ke logger."""
    print(baris, flush=True)
    log.log(level, baris)


def catat_pesan(message) -> None:
    """Format & cetak satu pesan masuk."""
    if not config.LOG_USER_MESSAGES:
        return

    teks = getattr(message, "text", None) or getattr(message, "caption", None) or ""
    jenis = _jenis_media(message)
    chat = getattr(message, "chat", None)
    tipe_chat = getattr(chat, "type", "?") if chat else "?"

    # Command ditandai khusus supaya mudah dicari di log
    if teks.startswith("/"):
        perintah = teks.split()[0]
        label = f"CMD {perintah}"
        level = logging.INFO
    elif jenis == "text":
        label = "MSG"
        level = logging.INFO
    else:
        # Media hanya dicetak kalau LOG_USER_MEDIA aktif
        if not config.LOG_USER_MEDIA:
            return
        label = f"MEDIA {jenis}"
        level = logging.INFO

    isi = _potong(teks) if teks else f"({jenis})"

    _cetak(
        f"[{_jam()}] {label:14} {isi}\n"
        f"           └─ {_identitas(getattr(message, 'from_user', None))}"
        f" | chat={tipe_chat}:{getattr(chat, 'id', '?')}",
        level,
    )


def catat_callback(call) -> None:
    """Format & cetak penekanan tombol inline."""
    if not config.LOG_USER_MESSAGES:
        return

    data = getattr(call, "data", "") or "(tanpa data)"
    _cetak(
        f"[{_jam()}] {'CB':14} {_potong(data, 60)}\n"
        f"           └─ {_identitas(getattr(call, 'from_user', None))}",
        logging.INFO,
    )


def _buat_kelas():
    """Import BaseMiddleware secara lazy supaya modul ini ringan."""
    from telebot.handler_backends import BaseMiddleware

    class UserLogger(BaseMiddleware):
        """Middleware yang mencatat semua pesan & callback masuk.

        update_sensitive=True supaya telebot memanggil pre_process_message /
        pre_process_callback_query, karena dict `data` tidak membawa
        update_type.
        """

        def __init__(self):
            super().__init__()
            self.update_sensitive = True
            self.update_types = ["message", "callback_query"]

        def pre_process_message(self, message, data):
            try:
                catat_pesan(message)
            except Exception:
                log.debug("Gagal mencatat pesan", exc_info=True)

        def pre_process_callback_query(self, call, data):
            try:
                catat_callback(call)
            except Exception:
                log.debug("Gagal mencatat callback", exc_info=True)

        # post_process_* wajib ada saat update_sensitive=True, kalau tidak
        # telebot mencatat ERROR "does not have post_process_<type>".
        def post_process_message(self, message, data, exception):
            if exception:
                log.warning("Handler error (message): %s", exception)

        def post_process_callback_query(self, call, data, exception):
            if exception:
                log.warning("Handler error (callback): %s", exception)

        # Method generik tetap ada sebagai jaring pengaman
        def pre_process(self, message, data):
            pass

        def post_process(self, message, data, exception):
            if exception:
                log.warning("Handler error: %s", exception)

    return UserLogger


def pasang(bot_instance) -> bool:
    """Daftarkan middleware ke instance bot. Return True kalau aktif."""
    if not config.LOG_USER_MESSAGES:
        log.info("Log aktivitas user dimatikan (LOG_USER_MESSAGES=false)")
        return False

    try:
        Kelas = _buat_kelas()
        bot_instance.setup_middleware(Kelas())
    except Exception as e:
        log.warning("Gagal memasang middleware logging: %s", e)
        return False

    log.info("Log aktivitas user aktif")
    return True
