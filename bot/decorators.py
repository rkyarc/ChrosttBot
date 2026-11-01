"""Decorator proteksi handler.

Tujuan: kalau sebuah handler gagal, user tetap dapat balasan yang jelas
alih-alih pesan yang hilang begitu saja. Traceback lengkap hanya masuk log,
tidak pernah dikirim ke user.

Dipakai HANYA pada handler yang belum punya try/except sendiri, supaya
pesan error khusus (mis. TikTok/YouTube/stiker) tidak tertimpa.
"""

import functools
import logging
import traceback

from bot import tg_bot
from bot.utils import escape_html

log = logging.getLogger("chrosttbot.handler")


def _chat_dari(obj):
    """Ambil chat_id dari Message atau CallbackQuery, aman kalau tidak ada."""
    chat = getattr(obj, "chat", None)
    if chat is not None and getattr(chat, "id", None):
        return chat.id

    pesan = getattr(obj, "message", None)
    if pesan is not None:
        chat = getattr(pesan, "chat", None)
        if chat is not None and getattr(chat, "id", None):
            return chat.id

    return None


def _beri_tahu(obj, chat_id, nama_handler):
    """Kirim pesan gagal ke user. Tidak boleh melempar error lagi."""
    if chat_id is None:
        return

    teks = (
        "⚠️ <b>Terjadi kesalahan</b>\n\n"
        "Perintah ini gagal diproses. Coba lagi beberapa saat lagi.\n\n"
        f"<i>Kode: {escape_html(nama_handler)}</i>"
    )

    # Callback perlu dijawab dulu supaya indikator loading berhenti
    cb_id = getattr(obj, "id", None) if hasattr(obj, "data") else None
    if cb_id:
        try:
            tg_bot.answer_callback_query(cb_id, "Terjadi kesalahan.", show_alert=False)
        except Exception:
            pass

    try:
        tg_bot.send_message(chat_id, teks, parse_mode="HTML")
    except Exception:
        # Kalau pun ini gagal (chat diblokir dsb), cukup catat
        log.debug("Gagal mengirim pesan error ke %s", chat_id, exc_info=True)


def aman_handler(fungsi):
    """Bungkus handler supaya error tidak membuat user menunggu tanpa balasan."""

    @functools.wraps(fungsi)
    def pembungkus(*args, **kwargs):
        try:
            return fungsi(*args, **kwargs)
        except Exception as e:
            log.error(
                "Handler %s gagal: %s\n%s",
                fungsi.__name__,
                e,
                traceback.format_exc(),
            )
            obj = args[0] if args else None
            _beri_tahu(obj, _chat_dari(obj), fungsi.__name__)
            return None

    return pembungkus
