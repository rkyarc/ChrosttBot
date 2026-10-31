from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup


# ========================
# NAVIGASI UMUM
# ========================

def markup_menu_utama(admin: bool = False):
    """Menu utama: asisten AI paling atas, fitur dikelompokkan 2 kolom."""
    markup = InlineKeyboardMarkup(row_width=2)

    markup.add(InlineKeyboardButton("✦ Chrostt AI", callback_data="menu_ai"))

    markup.row(
        InlineKeyboardButton("✂️ Hapus BG", callback_data="menu_bg"),
        InlineKeyboardButton("📈 Saham", callback_data="menu_saham"),
    )
    markup.row(
        InlineKeyboardButton("📰 Berita IDX", callback_data="menu_berita"),
        InlineKeyboardButton("ℹ️ Info Bot", callback_data="menu_info"),
    )
    markup.row(
        InlineKeyboardButton("📷 Instagram", callback_data="menu_instagram"),
        InlineKeyboardButton("🎵 TikTok", callback_data="menu_tiktok"),
    )
    markup.row(
        InlineKeyboardButton("📘 Facebook", callback_data="menu_facebook"),
        InlineKeyboardButton("▶️ YouTube", callback_data="menu_youtube"),
    )

    if admin:
        markup.add(InlineKeyboardButton("🛡️ Panel Admin", callback_data="admin_panel"))

    return markup


def markup_admin():
    """Panel admin: statistik, pengguna, broadcast."""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("📊 Statistik", callback_data="admin_stats"),
        InlineKeyboardButton("👥 Pengguna", callback_data="admin_users"),
    )
    markup.add(InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"))
    markup.add(InlineKeyboardButton("← Menu Utama", callback_data="menu_utama"))
    return markup


def markup_batal_broadcast():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✕ Batalkan", callback_data="admin_batal"))
    return markup


def markup_konfirmasi_broadcast():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("✅ Kirim", callback_data="admin_kirim"),
        InlineKeyboardButton("✕ Batal", callback_data="admin_batal"),
    )
    return markup


def markup_kembali_menu_utama():
    """Tombol tunggal untuk kembali ke menu utama."""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("← Menu Utama", callback_data="menu_utama"))
    return markup


def markup_kembali_dan_menu():
    """Kembali ke fitur sebelumnya + menu utama."""
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("← Menu Utama", callback_data="menu_utama"))
    return markup


# ========================
# FITUR AI
# ========================

def markup_ai():
    """Keyboard saat mode AI aktif."""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("🧹 Reset Obrolan", callback_data="ai_reset"),
        InlineKeyboardButton("✕ Keluar AI", callback_data="ai_keluar"),
    )
    markup.add(InlineKeyboardButton("← Menu Utama", callback_data="menu_utama"))
    return markup


def markup_ai_tertutup():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("✦ Buka Lagi", callback_data="menu_ai"),
        InlineKeyboardButton("← Menu Utama", callback_data="menu_utama"),
    )
    return markup


# ========================
# FITUR SAHAM
# ========================

def markup_menu_saham():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("📊 IHSG", callback_data="cek_^JKSE"),
        InlineKeyboardButton("🔍 Cari Emiten", callback_data="cari_saham"),
    )
    markup.add(InlineKeyboardButton("← Menu Utama", callback_data="menu_utama"))
    return markup


def markup_hasil_saham():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("🔍 Cari Lagi", callback_data="cari_saham"),
        InlineKeyboardButton("← Menu Saham", callback_data="menu_saham"),
    )
    markup.add(InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_utama"))
    return markup


def markup_saham_tidak_ditemukan():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("🔄 Coba Lagi", callback_data="cari_saham"),
        InlineKeyboardButton("← Menu Saham", callback_data="menu_saham"),
    )
    markup.add(InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_utama"))
    return markup


# ========================
# FITUR DOWNLOADER
# ========================

def markup_download_facebook(has_sd=False, has_hd=False):
    """Keyboard hasil Facebook Downloader untuk memilih kualitas."""
    markup = InlineKeyboardMarkup(row_width=2)

    tombol = []
    if has_hd:
        tombol.append(InlineKeyboardButton("🎥 HD", callback_data="fb_hd"))
    if has_sd:
        tombol.append(InlineKeyboardButton("📱 SD", callback_data="fb_sd"))

    if tombol:
        markup.row(*tombol)

    markup.add(InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_utama"))
    return markup


def markup_download_tiktok(has_images=False, image_count=0, has_music=True):
    """Keyboard hasil TikTok — media dikirim langsung ke chat."""
    markup = InlineKeyboardMarkup(row_width=2)

    if has_images:
        markup.add(
            InlineKeyboardButton(
                f"🖼️ Semua Foto ({image_count})",
                callback_data="tiktok_photos",
            )
        )

    markup.row(
        InlineKeyboardButton("🎥 Tanpa WM", callback_data="tiktok_nowm"),
        InlineKeyboardButton("🎬 Dengan WM", callback_data="tiktok_wm"),
    )

    if has_music:
        markup.add(InlineKeyboardButton("🎵 Kirim Musik", callback_data="tiktok_music"))

    markup.add(InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_utama"))
    return markup


# ========================
# FITUR BERITA IDX
# ========================

def markup_berita_idx(halaman_sekarang: int, total_halaman: int):
    """Navigasi halaman berita IDX."""
    markup = InlineKeyboardMarkup(row_width=3)

    tombol_nav = []
    if halaman_sekarang > 1:
        tombol_nav.append(
            InlineKeyboardButton(
                "«",
                callback_data=f"berita_idx_page_{halaman_sekarang - 1}",
            )
        )

    tombol_nav.append(
        InlineKeyboardButton(
            f"{halaman_sekarang}/{total_halaman}",
            callback_data="noop",
        )
    )

    if halaman_sekarang < total_halaman:
        tombol_nav.append(
            InlineKeyboardButton(
                "»",
                callback_data=f"berita_idx_page_{halaman_sekarang + 1}",
            )
        )

    markup.row(*tombol_nav)

    markup.row(
        InlineKeyboardButton("🔄 Refresh", callback_data="berita_idx_refresh"),
        InlineKeyboardButton("← Menu Utama", callback_data="menu_utama"),
    )
    return markup
