import re
from io import BytesIO

from telebot import types

from bot import tg_bot
from bot.keyboards import markup_download_facebook, markup_kembali_menu_utama
from bot.services.facebook import FacebookScraperError, extract_facebook, unduh_video
from bot.sessions import SessionStore
from bot.decorators import aman_handler


# Cache hasil ekstraksi per chat (auto expired, lihat bot/sessions.py)
FB_SESSIONS = SessionStore()

# Batas upload Bot API Telegram = 50MB
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

# Regex untuk menangkap link facebook.com atau fb.watch
FB_URL_PATTERN = re.compile(
    r"https?://(?:www\.|web\.|m\.)?(?:facebook\.com|fb\.watch)/[^\s]+",
    re.IGNORECASE,
)


@tg_bot.message_handler(func=lambda m: bool(FB_URL_PATTERN.search(m.text or "")))
@aman_handler
def proses_link_facebook(message):
    """Otomatis menangkap pesan yang berisi link Facebook."""
    chat_id = message.chat.id
    url_fb = FB_URL_PATTERN.search(message.text).group(0)

    pesan_loading = tg_bot.send_message(
        chat_id,
        "⏳ <i>Sedang mengekstrak data video Facebook...</i>",
        parse_mode="HTML",
    )

    try:
        info = extract_facebook(url_fb)

        # Simpan hasil ke cache sementara
        FB_SESSIONS.set(chat_id, info)

        teks_info = (
            "📘 <b>Facebook Downloader</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ <b>Video berhasil diekstrak!</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📥 <b>Pilih kualitas video:</b>"
        )

        tg_bot.edit_message_text(
            teks_info,
            chat_id,
            pesan_loading.message_id,
            parse_mode="HTML",
            reply_markup=markup_download_facebook(
                has_sd=bool(info.get("sdlink")),
                has_hd=bool(info.get("hdlink")),
            ),
        )

    except FacebookScraperError as e:
        tg_bot.edit_message_text(
            f"❌ <b>Gagal Mengekstrak</b>\n\n{str(e)[:300]}\n\n"
            "<i>Pastikan link Facebook valid dan video tidak diprivate.</i>",
            chat_id,
            pesan_loading.message_id,
            parse_mode="HTML",
            reply_markup=markup_kembali_menu_utama(),
        )
    except Exception as e:
        tg_bot.edit_message_text(
            f"⚠️ <b>Error tidak terduga</b>\n\n<code>{str(e)[:200]}</code>",
            chat_id,
            pesan_loading.message_id,
            parse_mode="HTML",
            reply_markup=markup_kembali_menu_utama(),
        )


# ================= TOMBOL DOWNLOAD =================

@tg_bot.callback_query_handler(func=lambda call: call.data in ("fb_hd", "fb_sd"))
def aksi_download_facebook(call):
    """Mengunduh video Facebook ke memori server lalu mengirimnya ke chat."""
    chat_id = call.message.chat.id
    info = FB_SESSIONS.get(chat_id)

    if not info:
        tg_bot.answer_callback_query(
            call.id,
            "Sesi sudah kedaluwarsa 🙂\nKirim ulang link Facebook-nya ya.",
            show_alert=True,
        )
        return

    sd_url = info.get("sdlink")
    hd_url = info.get("hdlink")

    # Tentukan URL dan kualitas yang dipilih
    if call.data == "fb_hd" and hd_url:
        video_url = hd_url
        quality_text = "HD"
    elif call.data == "fb_sd" and sd_url:
        video_url = sd_url
        quality_text = "SD"
    else:
        tg_bot.answer_callback_query(call.id, "❌ Link tidak tersedia.", show_alert=True)
        return

    tg_bot.answer_callback_query(call.id, f"⏳ Mengunduh video kualitas {quality_text}...")

    status_msg = tg_bot.send_message(
        chat_id,
        f"⏳ <b>Facebook Downloader</b>\n"
        f"<i>Sedang mengunduh & mengirim video kualitas {quality_text}...</i>",
        parse_mode="HTML",
    )

    try:
        # HD kadang berupa playlist .m3u8 yang tidak bisa dikirim sebagai video biasa
        if ".m3u8" in video_url and sd_url:
            video_url = sd_url
            quality_text = "SD (HD tidak didukung)"

        video_bytes = unduh_video(video_url, max_bytes=MAX_UPLOAD_BYTES)

        video_file = types.InputFile(
            BytesIO(video_bytes),
            file_name=f"facebook_{quality_text.split()[0].lower()}_{chat_id}.mp4",
        )
        caption = f"🎥 <b>Facebook Downloader</b> - Kualitas {quality_text}"

        tg_bot.send_video(
            chat_id,
            video_file,
            caption=caption,
            parse_mode="HTML",
            supports_streaming=True,
            timeout=180,
        )

        tg_bot.delete_message(chat_id, status_msg.message_id)

    except Exception as e:
        try:
            tg_bot.delete_message(chat_id, status_msg.message_id)
        except Exception:
            pass

        # Kalau upload gagal (misal > 50MB / timeout), kasih link download manual
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton(
                f"🔗 Link {quality_text} (Buka/Download di Browser)", url=video_url
            )
        )

        if quality_text == "HD" and sd_url:
            markup.add(types.InlineKeyboardButton("🔗 Alternatif Link SD", url=sd_url))
        elif quality_text.startswith("SD") and hd_url and ".m3u8" not in hd_url:
            markup.add(types.InlineKeyboardButton("🔗 Alternatif Link HD", url=hd_url))

        error_text = (
            "❌ <b>Gagal mengirim video langsung ke Telegram</b>\n\n"
            f"<b>Alasan:</b>\n<code>{str(e)[:200]}</code>\n\n"
            "<i>File ini kemungkinan lebih dari 50MB (batas Bot API), server menolak, "
            "atau koneksi timeout. Klik tombol di bawah untuk mengunduh manual lewat browser.</i>"
        )

        tg_bot.send_message(chat_id, error_text, parse_mode="HTML", reply_markup=markup)
