"""Reset mode tunggu input sebelum handler lain berjalan.

Modul ini sengaja diimpor paling awal di bot/handlers/__init__.py supaya
handler-nya dievaluasi lebih dulu, lalu mengembalikan ContinueHandling agar
pesan tetap diproses handler aslinya.
"""

import re

from telebot.handler_backends import ContinueHandling

from bot import play_mode, tg_bot

# Perintah yang justru mengaktifkan mode tunggu, jangan dibatalkan
_PERINTAH_PLAY = ("/play", "/putar")

# Pesan berisi link media bukan query pencarian, biarkan downloader menanganinya
_POLA_LINK = re.compile(r"https?://", re.IGNORECASE)


def _nama_perintah(teks: str) -> str:
    """Ambil '/play' dari '/play@ChrosttBot lofi hip hop'."""
    return (teks or "").split()[0].split("@", 1)[0].lower()


def _chat_dari_call(call):
    pesan = getattr(call, "message", None)
    return getattr(getattr(pesan, "chat", None), "id", None)


def _bukan_query_play(teks: str) -> bool:
    teks = (teks or "").strip()
    if not teks:
        return False
    if teks.startswith("/"):
        return _nama_perintah(teks) not in _PERINTAH_PLAY
    return bool(_POLA_LINK.search(teks))


@tg_bot.message_handler(
    content_types=["text"],
    func=lambda m: _bukan_query_play(m.text or ""),
)
def reset_sebelum_perintah(message):
    """Command lain atau link media menutup mode tunggu judul YouTube."""
    play_mode.tutup(message.chat.id)
    return ContinueHandling()


@tg_bot.message_handler(
    content_types=[
        "photo",
        "video",
        "document",
        "audio",
        "voice",
        "sticker",
        "animation",
        "video_note",
        "location",
        "contact",
    ],
)
def reset_sebelum_media(message):
    """Media yang dikirim bukan judul pencarian, jadi mode tunggu ditutup."""
    play_mode.tutup(message.chat.id)
    return ContinueHandling()


@tg_bot.callback_query_handler(func=lambda call: True)
def reset_sebelum_callback(call):
    """Menekan tombol apa pun berakhir dari mode tunggu judul.

    Termasuk tombol alur YouTube lain: setelah pengguna memilih video atau
    halaman, prompt ForceReply tidak relevan lagi dan harus dibersihkan.
    """
    chat_id = _chat_dari_call(call)
    if chat_id is not None:
        play_mode.tutup(chat_id)
    return ContinueHandling()
