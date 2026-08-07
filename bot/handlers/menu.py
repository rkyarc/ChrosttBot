from bot import tg_bot
from bot.keyboards import markup_kembali_menu_utama, markup_menu_utama


TEKS_SAMBUTAN = (
    "🤖 <b>Selamat Datang di Chrostt Bot!</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "Halo! Saya bot multiguna yang siap membantu Anda dengan beberapa layanan praktis:\n\n"
    "✂️ <b>Hapus Background</b>\n"
    "   Remove background foto secara otomatis\n\n"
    "📈 <b>Cek Saham</b>\n"
    "   Pantau harga saham & IHSG real-time\n\n"
    "📰 <b>Berita IDX</b>\n"
    "   Berita terbaru dari Bursa Efek Indonesia\n\n"
    "🎵 <b>TikTok Downloader</b>\n"
    "   Download video TikTok tanpa watermark\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "💡 <i>Pilih menu di bawah untuk memulai</i>"
)


TEKS_INFO = (
    "ℹ️ <b>Tentang Chrostt Bot</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "🤖 <b>Teknologi:</b>\n"
    "   • Python 3.x\n"
    "   • pyTelegramBotAPI\n"
    "   • yfinance\n"
		"   • rembg API\n"
    "   • tikwm API\n\n"
    "🎯 <b>Tujuan:</b>\n"
    "   Membantu tugas harian Anda dengan alur yang sederhana dan efisien.\n\n"
    "👨‍💻 <b>Developer:</b>\n"
    "   Dibuat dengan ❤️ untuk kemudahan Anda.\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "💬 <i>Tekan tombol di bawah untuk kembali</i>"
)


@tg_bot.message_handler(commands=["start", "menu"])
def tampilkan_menu(message):
    tg_bot.send_message(
        message.chat.id,
        TEKS_SAMBUTAN,
        parse_mode="HTML",
        reply_markup=markup_menu_utama(),
    )


@tg_bot.callback_query_handler(func=lambda call: call.data == "menu_utama")
def kembali_ke_menu_utama(call):
    tg_bot.answer_callback_query(call.id)
    tg_bot.edit_message_text(
        TEKS_SAMBUTAN,
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup_menu_utama(),
    )


@tg_bot.callback_query_handler(func=lambda call: call.data == "menu_info")
def tampilkan_info_bot(call):
    tg_bot.answer_callback_query(call.id)
    tg_bot.edit_message_text(
        TEKS_INFO,
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup_kembali_menu_utama(),
    )


@tg_bot.callback_query_handler(func=lambda call: call.data == "menu_bg")
def mode_hapus_bg(call):
    tg_bot.answer_callback_query(call.id)
    tg_bot.send_message(
        call.message.chat.id,
        "📸 <b>Mode Hapus Background Aktif!</b>\nSilakan kirimkan satu foto (kirim sebagai foto biasa, bukan file dokumen).",
        parse_mode="HTML",
    )


@tg_bot.callback_query_handler(func=lambda call: call.data == "menu_tiktok")
def menu_tiktok(call):
    tg_bot.answer_callback_query(call.id)
    tg_bot.edit_message_text(
        "🎵 <b>TikTok Downloader</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Kirim link TikTok (vt.tiktok.com atau tiktok.com) untuk mendapatkan:\n\n"
        "• 🎥 Video tanpa watermark (HD)\n"
        "• 🎬 Video dengan watermark\n"
        "• 🎵 Musik/audio\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>Cukup paste link di chat ini, bot akan otomatis proses.</i>",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup_kembali_menu_utama(),
    )