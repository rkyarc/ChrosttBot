import re
from io import BytesIO

from telebot import types

from bot import tg_bot
from bot.keyboards import markup_download_tiktok, markup_kembali_menu_utama
from bot.services.tiktok import TikTokScraperError, extract_tiktok, unduh_media
from bot.sessions import SessionStore
from bot.utils import escape_html
from bot.decorators import aman_handler


# Cache hasil ekstraksi per chat, supaya tombol callback bisa mengambil datanya
TIKTOK_SESSIONS = SessionStore()

# Batas upload Bot API Telegram = 50MB
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

TIKTOK_URL_PATTERN = re.compile(
    r"https?://(?:vm|vt|www|m)?\.?tiktok\.com/[^\s]+",
    re.IGNORECASE,
)


@tg_bot.message_handler(func=lambda m: bool(TIKTOK_URL_PATTERN.search(m.text or "")))
@aman_handler
def proses_link_tiktok(message):
    """Otomatis menangkap pesan yang berisi link TikTok."""
    chat_id = message.chat.id
    url_tiktok = TIKTOK_URL_PATTERN.search(message.text).group(0)

    pesan_loading = tg_bot.send_message(
        chat_id,
        "⏳ <i>Sedang mengekstrak data video TikTok...</i>",
        parse_mode="HTML",
    )

    try:
        info = extract_tiktok(url_tiktok)

        # Simpan hasil ekstraksi supaya tombol callback bisa pakai
        TIKTOK_SESSIONS.set(chat_id, info)

        author = info["author"]
        content = info["content"]
        music = info["music"]
        stats = info.get("stats", {})

        durasi = f"{content['duration']} detik" if content["duration"] else "-"
        tipe = "🖼️ Foto/Slideshow" if content["type"] == "photo" else "🎥 Video"

        teks_info = (
            "🎬 <b>TikTok Downloader</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 <b>{escape_html(author['full_name'])}</b> (@{escape_html(author['username'])})\n\n"
            "📝 <b>Caption:</b>\n"
            f"<code>{escape_html(_truncate(content['title'], 250))}</code>\n\n"
            "📊 <b>Detail:</b>\n"
            f"• Tipe: {tipe}\n"
            f"• Durasi: {durasi}\n"
            f"• ▶️ {_angka(stats.get('plays'))}x ditonton\n"
            f"• ❤️ {_angka(stats.get('likes'))} suka\n"
            f"• 🎵 {escape_html(_truncate(music['title'], 60))}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📥 <b>Pilih format — media dikirim langsung ke chat:</b>"
        )

        tg_bot.edit_message_text(
            teks_info,
            chat_id,
            pesan_loading.message_id,
            parse_mode="HTML",
            reply_markup=markup_download_tiktok(
                has_images=bool(content["images"]),
                image_count=len(content["images"]),
                has_music=bool(music["url"]),
            ),
        )

    except TikTokScraperError as e:
        tg_bot.edit_message_text(
            f"❌ <b>Gagal Mengekstrak</b>\n\n{escape_html(str(e))}\n\n"
            "<i>Pastikan link TikTok valid dan akun tidak diprivate.</i>",
            chat_id,
            pesan_loading.message_id,
            parse_mode="HTML",
            reply_markup=markup_kembali_menu_utama(),
        )
    except Exception as e:
        tg_bot.edit_message_text(
            f"⚠️ <b>Error tidak terduga</b>\n\n<code>{escape_html(str(e)[:200])}</code>",
            chat_id,
            pesan_loading.message_id,
            parse_mode="HTML",
            reply_markup=markup_kembali_menu_utama(),
        )


# ================= TOMBOL DOWNLOAD =================

@tg_bot.callback_query_handler(func=lambda call: call.data.startswith("tiktok_"))
def aksi_download_tiktok(call):
    """Mengirim media langsung ke chat saat tombol diklik."""
    chat_id = call.message.chat.id
    info = TIKTOK_SESSIONS.get(chat_id)

    if not info:
        tg_bot.answer_callback_query(
            call.id,
            "Sesi sudah kedaluwarsa 🙂\nKirim ulang link TikTok-nya ya.",
            show_alert=True,
        )
        return

    content = info["content"]
    music = info["music"]
    author = info["author"]

    try:
        if call.data == "tiktok_photos":
            images = content.get("images", [])
            if not images:
                tg_bot.answer_callback_query(
                    call.id, "Tidak ada foto untuk video ini.", show_alert=True
                )
                return
            tg_bot.answer_callback_query(call.id, f"⏳ Mengirim {len(images)} foto...")
            kirim_foto(chat_id, images)

        elif call.data == "tiktok_nowm":
            tg_bot.answer_callback_query(call.id, "⏳ Mengunduh & mengirim video tanpa WM...")
            kirim_video(chat_id, content["video_no_wm"], content["title"], author)

        elif call.data == "tiktok_wm":
            tg_bot.answer_callback_query(call.id, "⏳ Mengunduh & mengirim video dengan WM...")
            kirim_video(chat_id, content["video_wm"], content["title"], author)

        elif call.data == "tiktok_music":
            tg_bot.answer_callback_query(call.id, "⏳ Mengirim musik...")
            kirim_musik(chat_id, music)

        else:
            tg_bot.answer_callback_query(call.id)

    except TikTokScraperError as e:
        tg_bot.send_message(
            chat_id,
            "❌ <b>Gagal mengunduh media</b>\n\n"
            f"{escape_html(str(e))}\n\n"
            "<i>Coba lagi beberapa saat, atau buka link di bawah.</i>",
            parse_mode="HTML",
            reply_markup=_markup_tautan(call.data, content, music),
        )
    except Exception as e:
        tg_bot.send_message(
            chat_id,
            f"❌ <b>Gagal mengirim media</b>\n\n<code>{escape_html(str(e)[:200])}</code>",
            parse_mode="HTML",
        )


def _markup_tautan(aksi: str, content: dict, music: dict):
    """Tombol tautan langsung kalau unduhan lewat bot gagal."""
    if aksi == "tiktok_nowm":
        url = content.get("video_no_wm")
    elif aksi == "tiktok_wm":
        url = content.get("video_wm")
    elif aksi == "tiktok_music":
        url = music.get("url")
    else:
        url = None

    if not url:
        return markup_kembali_menu_utama()

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🔗 Buka Media di Browser", url=url),
        types.InlineKeyboardButton("← Menu Utama", callback_data="menu_utama"),
    )
    return markup


# ================= FUNGSI PENGIRIMAN MEDIA =================

def kirim_video(chat_id, url, title, author):
    """Download video lalu kirim sebagai video Telegram."""
    if not url:
        tg_bot.send_message(chat_id, "❌ Link video tidak tersedia untuk media ini.")
        return

    data = unduh_media(url)

    if len(data) > MAX_UPLOAD_BYTES:
        tg_bot.send_message(
            chat_id,
            f"⚠️ Ukuran video {len(data) // 1048576}MB melebihi batas upload Telegram (50MB).\n\n"
            f"Gunakan link langsung ini:\n{url}",
            disable_web_page_preview=True,
        )
        return

    caption = f"🎬 {_truncate(title, 900)}\n\n👤 @{author['username']} • via Chrostt Bot"
    tg_bot.send_video(chat_id, BytesIO(data), caption=caption)


def kirim_foto(chat_id, images):
    """Kirim semua foto slideshow sebagai album (maks 10 per album)."""
    for i in range(0, len(images), 10):
        chunk = images[i:i + 10]
        try:
            media = [types.InputMediaPhoto(url) for url in chunk]
            tg_bot.send_media_group(chat_id, media)
        except Exception:
            # Fallback: download manual kalau Telegram gagal fetch URL
            media = []
            for url in chunk:
                data = unduh_media(url)
                if len(data) > MAX_UPLOAD_BYTES:
                    tg_bot.send_message(
                        chat_id,
                        f"⚠️ Foto melebihi batas upload Telegram (50MB).\n\nURL langsung:\n{url}",
                        disable_web_page_preview=True,
                    )
                    continue
                media.append(types.InputMediaPhoto(BytesIO(data)))
            if media:
                tg_bot.send_media_group(chat_id, media)


def kirim_musik(chat_id, music):
    """Download musik lalu kirim sebagai audio Telegram."""
    if not music.get("url"):
        tg_bot.send_message(chat_id, "❌ Audio tidak tersedia untuk media ini.")
        return

    data = unduh_media(music["url"])

    if len(data) > MAX_UPLOAD_BYTES:
        tg_bot.send_message(
            chat_id,
            "⚠️ Ukuran audio melebihi batas upload Telegram (50MB).\n\n"
            f"URL langsung:\n{music['url']}",
            disable_web_page_preview=True,
        )
        return

    tg_bot.send_audio(
        chat_id,
        BytesIO(data),
        title=music.get("title") or "TikTok Sound",
        performer=music.get("author") or "TikTok",
    )


def _truncate(text, max_len):
    if not text:
        return "-"
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _angka(nilai):
    try:
        return f"{int(nilai):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"
