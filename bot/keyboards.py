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
        InlineKeyboardButton("🎨 Stiker", callback_data="menu_stiker"),
    )
    markup.row(
        InlineKeyboardButton("🗑️ Hapus Pesan", callback_data="menu_hapus"),
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
    """Panel admin: statistik, pengguna, riwayat, broadcast."""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("📊 Statistik", callback_data="admin_stats"),
        InlineKeyboardButton("👥 Pengguna", callback_data="admin_users"),
    )
    markup.row(
        InlineKeyboardButton("🗂️ Riwayat AI", callback_data="admin_riwayat"),
    )
    markup.add(InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"))
    markup.add(InlineKeyboardButton("← Menu Utama", callback_data="menu_utama"))
    return markup


def markup_riwayat(daftar: list[dict], halaman: int = 1, per_halaman: int = 5):
    """Daftar chat yang punya riwayat AI, plus tombol hapus per chat."""
    markup = InlineKeyboardMarkup(row_width=1)

    total = len(daftar)
    total_halaman = max(1, (total + per_halaman - 1) // per_halaman)
    halaman = max(1, min(halaman, total_halaman))
    mulai = (halaman - 1) * per_halaman

    for item in daftar[mulai : mulai + per_halaman]:
        chat_id = item["chat_id"]
        label = _label_riwayat(item)
        markup.add(
            InlineKeyboardButton(
                f"🗑️ {label}", callback_data=f"admin_hapus_{chat_id}"
            )
        )

    if total_halaman > 1:
        nav = []
        if halaman > 1:
            nav.append(
                InlineKeyboardButton(
                    "« Prev", callback_data=f"admin_riwayat_{halaman - 1}"
                )
            )
        nav.append(
            InlineKeyboardButton(
                f"{halaman}/{total_halaman}", callback_data="admin_riwayat_info"
            )
        )
        if halaman < total_halaman:
            nav.append(
                InlineKeyboardButton(
                    "Next »", callback_data=f"admin_riwayat_{halaman + 1}"
                )
            )
        markup.row(*nav)

    markup.row(
        InlineKeyboardButton(
            "🧨 Hapus Semua", callback_data="admin_riwayat_hapus_semua"
        ),
        InlineKeyboardButton("← Panel", callback_data="admin_panel"),
    )
    return markup


def markup_konfirmasi_hapus_riwayat(chat_id: str):
    """Konfirmasi sebelum menghapus riwayat satu chat."""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("✅ Hapus", callback_data=f"admin_hapus_ok_{chat_id}"),
        InlineKeyboardButton("✕ Batal", callback_data="admin_riwayat"),
    )
    return markup


def markup_konfirmasi_hapus_semua():
    """Konfirmasi sebelum menghapus seluruh riwayat AI."""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("✅ Hapus Semua", callback_data="admin_riwayat_hapus_ok"),
        InlineKeyboardButton("✕ Batal", callback_data="admin_riwayat"),
    )
    return markup


def _label_riwayat(item: dict) -> str:
    """Label tombol riwayat: nama/username + jumlah pesan, dipotong."""
    nama = (item.get("nama") or "").strip()
    username = (item.get("username") or "").strip()
    jumlah = item.get("jumlah_pesan") or 0

    if username:
        identitas = f"@{username}"
    elif nama:
        identitas = nama[:18]
    else:
        identitas = str(item.get("chat_id", "?"))

    label = f"{identitas} · {jumlah} pesan"
    return label[:60]


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


# ========================
# FITUR STIKER
# ========================

def markup_stiker_tipe():
    """Menu awal: mau buat stiker atau balikkan stiker."""
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🎨 Buat Stiker", callback_data="stiker_buat"),
        InlineKeyboardButton("🖼️ Stiker → PNG/MP4", callback_data="stiker_balik"),
        InlineKeyboardButton("← Menu Utama", callback_data="menu_utama"),
    )
    return markup


def markup_stiker_mode():
    """Tombol saat menunggu media dari pengguna."""
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🎨 Buat Stiker", callback_data="stiker_buat"),
        InlineKeyboardButton("🖼️ Stiker → PNG/MP4", callback_data="stiker_balik"),
        InlineKeyboardButton("✕ Batal", callback_data="stiker_batal"),
    )
    return markup


def markup_stiker_hasil():
    """Pilihan konversi setelah stiker diterima / selesai dibuat."""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("🖼️ Jadi PNG", callback_data="stiker_ke_png"),
        InlineKeyboardButton("🎬 Jadi MP4", callback_data="stiker_ke_mp4"),
    )
    markup.add(InlineKeyboardButton("← Menu Stiker", callback_data="menu_stiker"))
    return markup


# ========================
# FITUR YOUTUBE
# ========================

def markup_youtube_pilihan():
    """Menu info YouTube: tombol mulai pencarian."""
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🔍 Cari Video", callback_data="yt_panduan_play"),
        InlineKeyboardButton("← Menu Utama", callback_data="menu_utama"),
    )
    return markup


def markup_youtube_hasil(url: str):
    """Pilihan format unduhan setelah link/results didapat."""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("🎬 Video MP4", callback_data="yt_video"),
        InlineKeyboardButton("🎵 Audio MP3", callback_data="yt_audio"),
    )
    markup.row(
        InlineKeyboardButton("▶️ Buka di YouTube", callback_data="yt_buka"),
        InlineKeyboardButton("← Menu Utama", callback_data="menu_utama"),
    )
    return markup


def markup_youtube_daftar(hasil: list[dict], halaman: int = 1, per_halaman: int = 5):
    """Daftar hasil pencarian: 5 tombol per halaman plus navigasi.

    callback_data memakai indeks GLOBAL (yt_pilih_<i>), jadi pilihan tetap
    benar walau user berpindah halaman.
    """
    total = len(hasil)
    total_halaman = max(1, (total + per_halaman - 1) // per_halaman)
    halaman = max(1, min(halaman, total_halaman))

    mulai = (halaman - 1) * per_halaman
    potongan = hasil[mulai : mulai + per_halaman]

    markup = InlineKeyboardMarkup(row_width=1)

    for offset, item in enumerate(potongan):
        indeks_global = mulai + offset
        nomor = indeks_global + 1
        judul = (item.get("judul") or "Tanpa judul")[:36]
        durasi = item.get("durasi") or 0
        label = f"{nomor}. {judul}"
        if durasi:
            menit, detik = divmod(int(durasi), 60)
            jam, menit = divmod(menit, 60)
            label_waktu = (
                f"{jam}:{menit:02d}:{detik:02d}" if jam else f"{menit}:{detik:02d}"
            )
            label = f"{nomor}. {judul} \u00b7 {label_waktu}"
        markup.add(
            InlineKeyboardButton(label, callback_data=f"yt_pilih_{indeks_global}")
        )

    # Navigasi halaman
    if total_halaman > 1:
        tombol_nav = []
        if halaman > 1:
            tombol_nav.append(
                InlineKeyboardButton(
                    "\u00ab Prev", callback_data=f"yt_hal_{halaman - 1}"
                )
            )
        tombol_nav.append(
            InlineKeyboardButton(
                f"{halaman}/{total_halaman}", callback_data="yt_hal_info"
            )
        )
        if halaman < total_halaman:
            tombol_nav.append(
                InlineKeyboardButton(
                    "Next \u00bb", callback_data=f"yt_hal_{halaman + 1}"
                )
            )
        markup.row(*tombol_nav)

    markup.row(
        InlineKeyboardButton("\U0001f504 Cari Lagi", callback_data="yt_cari_lagi"),
        InlineKeyboardButton("\U0001f50d Judul Lain", callback_data="yt_cari_baru"),
    )
    markup.row(
        InlineKeyboardButton("\u2190 Menu Utama", callback_data="menu_utama"),
    )
    return markup


# ========================
# FITUR HAPUS PESAN
# ========================

def markup_hapus_hasil():
    """Tombol setelah operasi hapus selesai."""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("ℹ️ Cara Pakai", callback_data="hapus_panduan"),
        InlineKeyboardButton("← Menu Utama", callback_data="menu_utama"),
    )
    return markup
