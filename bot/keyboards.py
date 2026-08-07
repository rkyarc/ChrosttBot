from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup


# ========================
# NAVIGASI UMUM
# ========================

def markup_menu_utama():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("✂️ Hapus Background Foto", callback_data="menu_bg"),
        InlineKeyboardButton("📈 Cek Saham", callback_data="menu_saham"),
        InlineKeyboardButton("🎵 TikTok Downloader", callback_data="menu_tiktok"),
        InlineKeyboardButton("ℹ️ Info Bot", callback_data="menu_info"),
    )
    return markup


def markup_kembali_menu_utama():
    """Tombol tunggal untuk kembali ke menu utama."""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 Kembali ke Menu Utama", callback_data="menu_utama"))
    return markup


# ========================
# FITUR SAHAM
# ========================

def markup_menu_saham():
    """Keyboard untuk menu cek saham (3 tombol vertikal)."""
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📊 Cek IHSG", callback_data="cek_^JKSE"),
        InlineKeyboardButton("🔍 Cari Emiten Manual", callback_data="cari_saham"),
        InlineKeyboardButton("🔙 Kembali ke Menu Utama", callback_data="menu_utama"),
    )
    return markup


def markup_hasil_saham():
    """Keyboard setelah saham berhasil ditemukan."""
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🔍 Cari Saham Lain", callback_data="cari_saham"),
        InlineKeyboardButton("📈 Kembali ke Menu Saham", callback_data="menu_saham"),
        InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_utama"),
    )
    return markup


def markup_saham_tidak_ditemukan():
    """Keyboard jika kode saham tidak ditemukan."""
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🔄 Coba Cari Lagi", callback_data="cari_saham"),
        InlineKeyboardButton("📈 Kembali ke Menu Saham", callback_data="menu_saham"),
        InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_utama"),
    )
    return markup


def markup_error_saham():
    """Keyboard jika terjadi error saat mengambil data saham."""
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🔄 Coba Lagi", callback_data="cari_saham"),
        InlineKeyboardButton("📈 Kembali ke Menu Saham", callback_data="menu_saham"),
        InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_utama"),
    )
    return markup

def markup_download_tiktok(has_images=False, image_count=0, has_music=True):
    """Keyboard hasil TikTok — media dikirim langsung ke chat."""
    markup = InlineKeyboardMarkup(row_width=1)

    if has_images:
        markup.add(
            InlineKeyboardButton(
                f"🖼️ Kirim Semua Foto ({image_count})",
                callback_data="tiktok_photos",
            )
        )

    markup.add(InlineKeyboardButton("🎥 Video Tanpa Watermark", callback_data="tiktok_nowm"))
    markup.add(InlineKeyboardButton("🎬 Video Dengan Watermark", callback_data="tiktok_wm"))

    if has_music:
        markup.add(InlineKeyboardButton("🎵 Kirim Musik", callback_data="tiktok_music"))

    markup.add(InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_utama"))
    return markup