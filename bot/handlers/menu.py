from bot import tg_bot
from bot.admin import apakah_admin, pesan_dari_admin
from bot.keyboards import markup_kembali_menu_utama, markup_menu_utama
from bot.services.ai import model_aktif, tersedia
from bot.decorators import aman_handler

GARIS = "─" * 24

TEKS_SAMBUTAN = (
    "✦ <b>CHROSTT BOT</b>\n"
    f"<code>{GARIS}</code>\n\n"
    "Asisten serba bisa di Telegram.\n"
    "Pilih menu, atau langsung tanya Chrostt AI.\n\n"
    "<b>Fitur</b>\n"
    "✦ <b>Chrostt AI</b> — tanya apa saja\n"
    "✂️ <b>Hapus BG</b> — foto jadi transparan\n"
    "📈 <b>Saham</b> — IHSG &amp; emiten BEI\n"
    "📰 <b>Berita IDX</b> — kabar pasar terbaru\n"
    "📷 <b>Instagram</b> — foto, carousel, reels\n"
    "🎵 <b>TikTok</b> — video, foto, audio\n"
    "📘 <b>Facebook</b> — video HD/SD\n"
    "▶️ <b>YouTube</b> — video maks 50MB\n"
    "🎨 <b>Stiker</b> — foto/video ↔ stiker\n\n"
    f"<code>{GARIS}</code>\n"
    "<i>Pilih tombol di bawah untuk mulai</i>"
)


def _teks_info() -> str:
    status_ai = "aktif" if tersedia() else "belum dikonfigurasi"
    return (
        "ℹ️ <b>TENTANG BOT</b>\n"
        f"<code>{GARIS}</code>\n\n"
        "<b>Stack</b>\n"
        "• Python + pyTelegramBotAPI\n"
        "• yfinance untuk data saham\n"
        "• rembg untuk hapus background\n"
        "• saveinta, tikwm, yt-dlp untuk downloader\n"
        "• ffmpeg untuk konversi stiker\n"
        f"• {model_aktif()} untuk Chrostt AI\n\n"
        "<b>Status AI</b>\n"
        f"• Layanan: {status_ai}\n\n"
        "<b>Tim</b>\n"
        "• rkyarc — author\n"
        "• RusdiEneri — helper\n\n"
        f"<code>{GARIS}</code>\n"
        "<i>Dibuat untuk mempermudah kerja harian</i>"
    )


@tg_bot.message_handler(commands=["start", "menu"])
@aman_handler
def tampilkan_menu(message):
    tg_bot.send_message(
        message.chat.id,
        TEKS_SAMBUTAN,
        parse_mode="HTML",
        reply_markup=markup_menu_utama(admin=pesan_dari_admin(message)),
        disable_web_page_preview=True,
    )


@tg_bot.message_handler(commands=["help", "bantuan"])
@aman_handler
def tampilkan_bantuan(message):
    admin = pesan_dari_admin(message)
    admin_baris = "/admin — panel admin bot\n" if admin else ""
    tg_bot.send_message(
        message.chat.id,
        "<b>PERINTAH</b>\n"
        f"<code>{GARIS}</code>\n\n"
        "/start — buka menu utama\n"
        "/ai — mode asisten AI\n"
        "/ai &lt;pertanyaan&gt; — tanya langsung\n"
        "/ai_off — keluar mode AI\n"
        "/ai_status — cek status AI\n"
        "/play — cari &amp; unduh YouTube (kirim judul setelahnya)\n"
        "/play &lt;judul&gt; — cari langsung tanpa mode tunggu\n"
        "/del — hapus pesan/media di chat\n"
        "/id — lihat ID Telegram kamu\n"
        f"{admin_baris}"
        "/help — bantuan ini\n\n"
        "<b>Cara cepat</b>\n"
        "• Kirim foto → hapus background\n"
        "• Kirim link IG/TikTok/FB/YouTube → download\n"
        "• Modus AI aktif → semua teks jadi pertanyaan",
        parse_mode="HTML",
        reply_markup=markup_kembali_menu_utama(),
    )


@tg_bot.callback_query_handler(func=lambda call: call.data == "menu_utama")
def kembali_ke_menu_utama(call):
    tg_bot.answer_callback_query(call.id)
    is_admin = apakah_admin(getattr(getattr(call, "from_user", None), "id", None))
    try:
        tg_bot.edit_message_text(
            TEKS_SAMBUTAN,
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=markup_menu_utama(admin=is_admin),
            disable_web_page_preview=True,
        )
    except Exception:
        tg_bot.send_message(
            call.message.chat.id,
            TEKS_SAMBUTAN,
            parse_mode="HTML",
            reply_markup=markup_menu_utama(admin=is_admin),
            disable_web_page_preview=True,
        )


@tg_bot.callback_query_handler(func=lambda call: call.data == "menu_info")
@aman_handler
def tampilkan_info_bot(call):
    tg_bot.answer_callback_query(call.id)
    tg_bot.edit_message_text(
        _teks_info(),
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup_kembali_menu_utama(),
        disable_web_page_preview=True,
    )


@tg_bot.callback_query_handler(func=lambda call: call.data == "menu_bg")
@aman_handler
def mode_hapus_bg(call):
    tg_bot.answer_callback_query(call.id)
    tg_bot.send_message(
        call.message.chat.id,
        "✂️ <b>HAPUS BACKGROUND</b>\n"
        f"<code>{GARIS}</code>\n\n"
        "Kirim satu foto ke chat ini (sebagai foto biasa, bukan file).\n"
        "Bot akan mengirim balik versi PNG tanpa background.\n\n"
        "<i>Maksimal 12MB, proses ±5-20 detik.</i>",
        parse_mode="HTML",
        reply_markup=markup_kembali_menu_utama(),
    )


def _menu_fitur(judul: str, ikon: str, isi: str, catatan: str) -> str:
    return (
        f"{ikon} <b>{judul}</b>\n"
        f"<code>{GARIS}</code>\n\n"
        f"{isi}\n\n"
        f"<i>{catatan}</i>"
    )


@tg_bot.callback_query_handler(func=lambda call: call.data == "menu_instagram")
@aman_handler
def menu_instagram(call):
    tg_bot.answer_callback_query(call.id)
    tg_bot.edit_message_text(
        _menu_fitur(
            "INSTAGRAM DOWNLOADER",
            "📷",
            "Kirim link postingan, reel, atau carousel publik.\n\n"
            "• Foto &amp; carousel dikirim sebagai album\n"
            "• Video dikirim sebagai media Telegram\n"
            "• Media di atas 50MB dikirim sebagai link",
            "Cukup paste link Instagram di chat ini.",
        ),
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup_kembali_menu_utama(),
        disable_web_page_preview=True,
    )


@tg_bot.callback_query_handler(func=lambda call: call.data == "menu_tiktok")
@aman_handler
def menu_tiktok(call):
    tg_bot.answer_callback_query(call.id)
    tg_bot.edit_message_text(
        _menu_fitur(
            "TIKTOK DOWNLOADER",
            "🎵",
            "Kirim link TikTok (tiktok.com, vt.tiktok.com, vm.tiktok.com).\n\n"
            "• Video tanpa watermark / dengan watermark\n"
            "• Foto slideshow dikirim sebagai album\n"
            "• Audio bisa dikirim terpisah",
            "Pilih format lewat tombol setelah link diproses.",
        ),
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup_kembali_menu_utama(),
        disable_web_page_preview=True,
    )


@tg_bot.callback_query_handler(func=lambda call: call.data == "menu_facebook")
@aman_handler
def menu_facebook(call):
    tg_bot.answer_callback_query(call.id)
    tg_bot.edit_message_text(
        _menu_fitur(
            "FACEBOOK DOWNLOADER",
            "📘",
            "Kirim link video Facebook (facebook.com atau fb.watch).\n\n"
            "• Pilih kualitas HD atau SD\n"
            "• Video dikirim langsung jika di bawah 50MB\n"
            "• Kalau gagal, bot memberi link unduh manual",
            "Hanya video publik yang bisa diproses.",
        ),
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup_kembali_menu_utama(),
        disable_web_page_preview=True,
    )
