import re
import io
import cloudscraper
from telebot import types

from bot import tg_bot
from bot.keyboards import markup_download_facebook, markup_kembali_menu_utama
from bot.services.facebook import extract_facebook, FacebookScraperError

# Cache hasil ekstraksi per chat (sama seperti TIKTOK_SESSIONS)
FB_SESSIONS = {}

# Regex untuk menangkap link facebook.com atau fb.watch
FB_URL_PATTERN = re.compile(
    r"https?://(?:www\.|web\.|m\.)?(?:facebook\.com|fb\.watch)/[^\s]+",
    re.IGNORECASE,
)

@tg_bot.message_handler(func=lambda m: bool(FB_URL_PATTERN.search(m.text or "")))
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
        FB_SESSIONS[chat_id] = info

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
                has_sd=bool(info.get('sdlink')),
                has_hd=bool(info.get('hdlink')),
            ),
        )

    except FacebookScraperError as e:
        tg_bot.edit_message_text(
            f"❌ <b>Gagal Mengekstrak</b>\n\n{str(e)}\n\n"
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

@tg_bot.callback_query_handler(func=lambda call: call.data.startswith("fb_"))
def aksi_download_facebook(call):
    """Mengunduh media Facebook ke memori server lalu mengirimnya ke chat."""
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
    
    # Tampilkan pesan loading agar user tahu bot sedang bekerja
    status_msg = tg_bot.send_message(
        chat_id, 
        f"⏳ <b>Facebook Downloader</b>\n<i>Sedang mengunduh & mengirim video kualitas {quality_text}...</i>", 
        parse_mode="HTML"
    )

    try:
        # PENTING: Fallback ke SD jika URL HD ternyata adalah playlist .m3u8
        if '.m3u8' in video_url and sd_url:
            video_url = sd_url
            quality_text = "SD (HD tidak didukung)"

        # Download video menggunakan cloudscraper
        scraper = cloudscraper.create_scraper()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Referer": "https://www.facebook.com/" 
        }
        
        response = scraper.get(video_url, headers=headers, stream=True, timeout=60)
        
        if response.status_code != 200:
            raise Exception(f"Server Facebook menolak unduhan (Status: {response.status_code})")

        # Simpan ke memori (BytesIO)
        video_bytes = io.BytesIO()
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                video_bytes.write(chunk)
                
        video_bytes.seek(0)
        
        video_file = types.InputFile(video_bytes, file_name=f"facebook_{quality_text}_{chat_id}.mp4")
        caption = f"🎥 <b>Facebook Downloader</b> - Kualitas {quality_text}"
        
        # Kirim video dari memori server ke Telegram
        tg_bot.send_video(
            chat_id, 
            video_file, 
            caption=caption, 
            parse_mode="HTML",
            supports_streaming=True,
            timeout=180  
        )
        
        # Hapus pesan loading HANYA JIKA video berhasil dikirim
        tg_bot.delete_message(chat_id, status_msg.message_id)

    except Exception as e:
        # Coba hapus pesan loading jika masih ada
        try:
            tg_bot.delete_message(chat_id, status_msg.message_id)
        except Exception:
            pass
            
        # FIX: Jika gagal upload (misal: > 50MB / 413 Error / Timeout), berikan tombol Link Download Manual
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton(f"🔗 Link {quality_text} (Buka/Download di Browser)", url=video_url))
        
        # Berikan alternatif link kualitas lain jika tersedia
        if quality_text == "HD" and sd_url:
            markup.add(types.InlineKeyboardButton("🔗 Alternatif Link SD", url=sd_url))
        elif quality_text.startswith("SD") and hd_url and '.m3u8' not in hd_url:
            markup.add(types.InlineKeyboardButton("🔗 Alternatif Link HD", url=hd_url))

        error_text = (
            f"❌ <b>Gagal mengirim video langsung ke Telegram</b>\n\n"
            f"<b>Alasan:</b>\n<code>{str(e)[:200]}</code>\n\n"
            "<i>File ini kemungkinan berukuran lebih dari 50MB (batas Bot API), server menolak, atau koneksi timeout. "
            "Silakan klik tombol di bawah untuk membuka dan mengunduh video secara manual melalui browser Anda.</i>"
        )
        
        tg_bot.send_message(
            chat_id,
            error_text,
            parse_mode="HTML",
            reply_markup=markup
        )