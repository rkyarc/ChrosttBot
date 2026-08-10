import re
import os
from bot import tg_bot
from bot.services.youtube import download_youtube_video

# Regex untuk mendeteksi link YouTube otomatis
YOUTUBE_URL_PATTERN = re.compile(
    r"(https?://)?(www\.)?(youtube\.com|youtu\.?be)/.+",
    re.IGNORECASE
)

@tg_bot.message_handler(func=lambda m: bool(YOUTUBE_URL_PATTERN.search(m.text or "")))
def proses_link_youtube(message):
    """Menangkap link YouTube dan mendownload videonya."""
    chat_id = message.chat.id
    url = YOUTUBE_URL_PATTERN.search(message.text).group(0)

    pesan_loading = tg_bot.send_message(
        chat_id,
        "⏳ <i>Sedang mendownload video YouTube (bisa makan waktu), mohon tunggu...</i>",
        parse_mode="HTML"
    )

    # 1. Mulai download menggunakan file service tadi
    file_path = download_youtube_video(url)

    # 2. Jika berhasil didownload dan file-nya ada
    if file_path and os.path.exists(file_path):
        try:
            with open(file_path, 'rb') as video:
                tg_bot.send_video(chat_id, video, caption="🎬 Berhasil didownload!")
            
            # Hapus pesan loading jika sukses
            tg_bot.delete_message(chat_id, pesan_loading.message_id)
        except Exception as e:
            tg_bot.edit_message_text(f"⚠️ Gagal mengirim video ke Telegram: {e}", chat_id, pesan_loading.message_id)
        finally:
            # Hapus file video lokal (di PC/Server) setelah dikirim untuk menghemat disk space
            if os.path.exists(file_path):
                os.remove(file_path)
    else:
        # Jika gagal atau video terlalu besar (>50MB)
        tg_bot.edit_message_text(
            "❌ <b>Gagal mendownload video</b>\nMungkin videonya terlalu besar dari limit Telegram (50MB) atau link diprivate.",
            chat_id,
            pesan_loading.message_id,
            parse_mode="HTML"
        )
