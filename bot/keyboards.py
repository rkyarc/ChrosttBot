from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup


# ========================
# NAVIGASI UMUM
# ========================

def markup_menu_utama():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("✂️ Hapus Background Foto", callback_data="menu_bg"),
        InlineKeyboardButton("📈 Cek Saham", callback_data="menu_saham"),
		InlineKeyboardButton("📰 Berita IDX", callback_data="menu_berita"),
        InlineKeyboardButton("📷 Instagram Downloader", callback_data="menu_instagram"),
        InlineKeyboardButton("🎵 TikTok Downloader", callback_data="menu_tiktok"),
        InlineKeyboardButton("📘 Facebook Downloader", callback_data="menu_facebook"),
        InlineKeyboardButton("▶️ Youtube Downloader", callback_data="menu_youtube"),
        InlineKeyboardButton("ℹ️ Info Bot", callback_data="menu_info"),
    )
    return markup

def markup_download_facebook(has_sd=False, has_hd=False):
    """Keyboard hasil Facebook Downloader untuk memilih kualitas."""
    markup = InlineKeyboardMarkup(row_width=1)
    
    if has_hd:
        markup.add(InlineKeyboardButton("🎥 Download Video HD (Kualitas Tinggi)", callback_data="fb_hd"))
    if has_sd:
        markup.add(InlineKeyboardButton("📱 Download Video SD (Kualitas Normal)", callback_data="fb_sd"))
        
    markup.add(InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_utama"))
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

def markup_berita_idx(halaman_sekarang: int, total_halaman: int, force_refresh: bool = False):
    """Keyboard untuk menu berita IDX dengan navigasi halaman."""
    markup = InlineKeyboardMarkup(row_width=3)

    # Baris 1: navigasi halaman
    tombol_nav = []
    if halaman_sekarang > 1:
        tombol_nav.append(
            InlineKeyboardButton(
                "◀️ Sebelumnya",
                callback_data=f"berita_idx_page_{halaman_sekarang - 1}",
            )
        )
    
    # Label halaman (di tengah, tidak clickable)
    label_halaman = f"Hal {halaman_sekarang}/{total_halaman}"
    tombol_nav.append(
        InlineKeyboardButton(
            label_halaman,
            callback_data="noop",  # tombol pasif
        )
    )
    
    if halaman_sekarang < total_halaman:
        tombol_nav.append(
            InlineKeyboardButton(
                "Berikutnya ▶️",
                callback_data=f"berita_idx_page_{halaman_sekarang + 1}",
            )
        )
    
    markup.row(*tombol_nav)

    # Baris 2: refresh + kembali
    if force_refresh:
        markup.add(
            InlineKeyboardButton("🔄 Refresh Paksa (Fetch Ulang)", callback_data="berita_idx_refresh"),
        )
    else:
        markup.add(
            InlineKeyboardButton("🔄 Refresh", callback_data="berita_idx_refresh"),
        )
    
    markup.add(
        InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_utama"),
    )
    return markup