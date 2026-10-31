import os
import re

from bot import tg_bot
from bot.keyboards import markup_kembali_menu_utama
from bot.services.youtube import YouTubeDownloadError, download_youtube_video
from bot.utils import escape_html

# Regex untuk mendeteksi link YouTube otomatis (video, shorts, live)
YOUTUBE_URL_PATTERN = re.compile(
    r"https?://(?:www\.|m\.)?(?:youtube\.com/(?:watch\?|shorts/|live/)|youtu\.be/)[^\s]+",
    re.IGNORECASE,
)


@tg_bot.message_handler(func=lambda m: bool(YOUTUBE_URL_PATTERN.search(m.text or "")))
def proses_link_youtube(message):
    """Menangkap link YouTube dan mendownload videonya."""
    chat_id = message.chat.id
    url = YOUTUBE_URL_PATTERN.search(message.text).group(0)

    pesan_loading = tg_bot.send_message(
        chat_id,
        "⏳ <i>Sedang mendownload video YouTube (bisa makan waktu), mohon tunggu...</i>",
        parse_mode="HTML",
    )

    file_path = None
    try:
        file_path = download_youtube_video(url)

        with open(file_path, "rb") as video:
            tg_bot.send_video(
                chat_id,
                video,
                caption="🎬 Berhasil didownload!",
                supports_streaming=True,
                timeout=180,
            )

        tg_bot.delete_message(chat_id, pesan_loading.message_id)

    except YouTubeDownloadError as e:
        tg_bot.edit_message_text(
            f"❌ <b>Gagal mendownload video</b>\n\n{escape_html(e)}",
            chat_id,
            pesan_loading.message_id,
            parse_mode="HTML",
            reply_markup=markup_kembali_menu_utama(),
        )
    except Exception as e:
        tg_bot.edit_message_text(
            f"⚠️ <b>Gagal mengirim video ke Telegram</b>\n\n"
            f"<code>{escape_html(str(e)[:200])}</code>",
            chat_id,
            pesan_loading.message_id,
            parse_mode="HTML",
            reply_markup=markup_kembali_menu_utama(),
        )
    finally:
        # Hapus file video lokal setelah dikirim supaya disk tidak penuh
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
