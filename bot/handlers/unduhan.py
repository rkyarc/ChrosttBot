"""Pesan tautan unduhan untuk media yang melebihi batas upload Telegram.

Bot API menolak file di atas 50MB. Daripada menampilkan error, downloader
mengirim tautan sumbernya supaya pengguna tetap bisa mengambil file lewat
browser.
"""

from telebot import types

from bot import telegram_io as tg_io
from bot.services.media import ukuran_mb
from bot.utils import escape_html


def kirim_tautan_unduh(
    chat_id: int,
    url: str,
    ukuran: int | None = None,
    jenis: str = "file",
    judul: str = "",
    catatan: str = "",
    alternatif: list[tuple[str, str]] | None = None,
) -> bool:
    """Kirim tautan unduhan plus tombol pembuka browser. True kalau terkirim."""
    if not url:
        return False

    baris = [
        "🔗 <b>LINK UNDUHAN</b>",
        "<code>" + "─" * 24 + "</code>",
        "",
        f"⚠️ Ukuran {jenis} {ukuran_mb(ukuran)} melebihi batas upload "
        "Telegram (50MB).",
        "<i>File tidak dikirim ke chat, tapi bisa diunduh lewat tautan di bawah.</i>",
    ]

    if judul:
        baris += ["", f"🎬 <b>{escape_html(str(judul)[:150])}</b>"]
    if catatan:
        baris += ["", f"<i>{escape_html(catatan)}</i>"]

    baris += ["", "<b>Tautan:</b>", f"<code>{escape_html(url)}</code>"]

    alternatif = [(label, tautan) for label, tautan in (alternatif or []) if tautan]
    for label, tautan in alternatif:
        baris.append(f"{escape_html(label)}: <code>{escape_html(tautan)}</code>")

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("⬇️ Buka / Unduh di Browser", url=url))
    for label, tautan in alternatif:
        markup.add(types.InlineKeyboardButton(label, url=tautan))
    markup.add(types.InlineKeyboardButton("← Menu Utama", callback_data="menu_utama"))

    return (
        tg_io.kirim(
            chat_id,
            "\n".join(baris),
            parse_mode="HTML",
            reply_markup=markup,
            disable_web_page_preview=True,
        )
        is not None
    )
