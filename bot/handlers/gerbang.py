"""Gerbang batas laju untuk handler Telegram.

Satu tempat supaya semua fitur mahal memberi pesan penolakan yang sama:
callback dijawab (spinner berhenti) plus pesan singkat berisi saran waktu
tunggu. Pemanggil cukup ``if not lolos(...): return``.
"""

from bot import batas_laju, telegram_io as tg_io
from bot.utils import escape_html


def _jawab(obj) -> None:
    """Jawab callback query kalau objeknya CallbackQuery."""
    call_id = getattr(obj, "id", None) if hasattr(obj, "data") else None
    if call_id:
        tg_io.jawab_callback(obj)


def lolos(obj, jenis: str = "umum") -> bool:
    """True kalau aksi boleh jalan; kalau tidak, pengguna sudah diberi tahu."""
    user = getattr(obj, "from_user", None)
    user_id = getattr(user, "id", None)

    try:
        batas_laju.cek(user_id, jenis)
        return True
    except batas_laju.BatasTerlampaui as e:
        _jawab(obj)
        chat_id = _chat_id(obj)
        if chat_id is not None:
            tg_io.kirim(
                chat_id,
                "⏳ <b>Batas tercapai</b>\n\n"
                f"{escape_html(e.pesan)}\n\n"
                f"<i>Sisa waktu tunggu sekitar {e.detik} detik.</i>",
                parse_mode="HTML",
            )
        return False


def _chat_id(obj):
    chat = getattr(obj, "chat", None)
    if chat is not None and getattr(chat, "id", None):
        return chat.id

    pesan = getattr(obj, "message", None)
    chat = getattr(pesan, "chat", None)
    if chat is not None and getattr(chat, "id", None):
        return chat.id

    return None
