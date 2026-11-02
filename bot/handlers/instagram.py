import re
from io import BytesIO

from telebot import types

from bot import tg_bot
from bot.handlers.gerbang import lolos
from bot.handlers.unduhan import kirim_tautan_unduh
from bot.keyboards import markup_kembali_menu_utama
from bot.services.media import MediaTerlaluBesar
from bot.services.saveinta import SaveInta
from bot.utils import escape_html
from bot.decorators import aman_handler


INSTAGRAM_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:instagram\.com|instagr\.am)/[^\s]+",
    re.IGNORECASE,
)


@tg_bot.message_handler(func=lambda m: bool(INSTAGRAM_URL_PATTERN.search(m.text or "")))
@aman_handler
def proses_link_instagram(message):
    chat_id = message.chat.id
    url_instagram = INSTAGRAM_URL_PATTERN.search(message.text).group(0)

    if not lolos(message, "unduh"):
        return

    pesan_loading = tg_bot.send_message(
        chat_id,
        "⏳ <i>Sedang mengekstrak data Instagram...</i>",
        parse_mode="HTML",
    )

    try:
        scraper = SaveInta()
        scraper.refresh_tokens()
        resp = scraper.search(url_instagram)
        media = scraper.parse_media(resp)
        items = media.get("items", [])

        if not items:
            tg_bot.edit_message_text(
                "❌ <b>Media tidak ditemukan</b>\n\n"
                "Link Instagram valid, tetapi tidak ada media yang bisa diambil.\n\n"
                "<i>Coba kirim link postingan, reel, atau carousel yang publik.</i>",
                chat_id,
                pesan_loading.message_id,
                parse_mode="HTML",
                reply_markup=markup_kembali_menu_utama(),
            )
            return

        jumlah_video = sum(1 for kind, _ in items if kind == "VIDEO")
        jumlah_foto = sum(1 for kind, _ in items if kind == "FOTO")

        teks_info = (
            "📷 <b>Instagram Downloader</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"• Video: <b>{jumlah_video}</b>\n"
            f"• Foto: <b>{jumlah_foto}</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📥 <i>Media sedang dikirim ke chat...</i>"
        )
        tg_bot.edit_message_text(
            teks_info,
            chat_id,
            pesan_loading.message_id,
            parse_mode="HTML",
            reply_markup=markup_kembali_menu_utama(),
        )

        kirim_media_berurutan(chat_id, scraper, items)

    except Exception as e:
        tg_bot.edit_message_text(
            f"❌ <b>Gagal memproses Instagram</b>\n\n<code>{escape_html(str(e)[:300])}</code>",
            chat_id,
            pesan_loading.message_id,
            parse_mode="HTML",
            reply_markup=markup_kembali_menu_utama(),
        )


def kirim_media_berurutan(chat_id, scraper, items):
    foto_buffer = []

    def flush_foto_buffer():
        nonlocal foto_buffer
        if not foto_buffer:
            return
        kirim_foto_instagram(chat_id, scraper, foto_buffer)
        foto_buffer = []

    for index, (kind, url) in enumerate(items, 1):
        if kind == "FOTO":
            foto_buffer.append(url)
            continue

        flush_foto_buffer()
        kirim_video_instagram(chat_id, scraper, url, index)

    flush_foto_buffer()


def kirim_video_instagram(chat_id, scraper, url, index):
    try:
        data = scraper.unduh_media(url)
    except MediaTerlaluBesar as e:
        kirim_tautan_unduh(
            chat_id,
            url,
            ukuran=e.ukuran_bytes,
            jenis=f"video Instagram #{index}",
        )
        return

    tg_bot.send_video(
        chat_id,
        BytesIO(data),
        caption=f"📹 Video Instagram #{index}",
    )


def kirim_foto_instagram(chat_id, scraper, images):
    for i in range(0, len(images), 10):
        chunk = images[i:i + 10]

        try:
            media = [types.InputMediaPhoto(url) for url in chunk]
            tg_bot.send_media_group(chat_id, media)
        except Exception:
            # Fallback: unduh manual kalau Telegram gagal fetch URL langsung
            for url in chunk:
                try:
                    data = scraper.unduh_media(url)
                except MediaTerlaluBesar as e:
                    kirim_tautan_unduh(
                        chat_id, url, ukuran=e.ukuran_bytes, jenis="foto Instagram"
                    )
                    continue
                tg_bot.send_photo(chat_id, BytesIO(data))
