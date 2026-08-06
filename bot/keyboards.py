from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup


def markup_menu_utama():
	markup = InlineKeyboardMarkup()
	markup.add(InlineKeyboardButton("✂️ Hapus Background Foto", callback_data="menu_bg"))
	markup.add(InlineKeyboardButton("📈 Cek Saham", callback_data="menu_saham"))
	markup.add(InlineKeyboardButton("ℹ️ Info Bot", callback_data="menu_info"))
	return markup


def markup_kembali_menu_utama():
	markup = InlineKeyboardMarkup()
	markup.add(InlineKeyboardButton("🔙 Kembali ke Menu Utama", callback_data="menu_utama"))
	return markup


def markup_menu_saham():
	markup = InlineKeyboardMarkup()
	markup.add(InlineKeyboardButton("📊 IHSG", callback_data="cek_^JKSE"))
	markup.add(InlineKeyboardButton("🔍 Cari Emiten Manual", callback_data="cari_saham"))
	markup.add(InlineKeyboardButton("🔙 Kembali ke Menu Utama", callback_data="menu_utama"))
	return markup


def markup_cari_saham():
	markup = InlineKeyboardMarkup()
	markup.add(InlineKeyboardButton("🔍 Cari Saham Lain", callback_data="cari_saham"))
	markup.add(InlineKeyboardButton("🔙 Kembali ke Menu Saham", callback_data="menu_saham"))
	return markup


def markup_hasil_saham():
	markup = InlineKeyboardMarkup()
	markup.add(InlineKeyboardButton("🔍 Cari Saham Lain", callback_data="cari_saham"))
	markup.add(InlineKeyboardButton("🔙 Kembali ke Menu Saham", callback_data="menu_saham"))
	markup.add(InlineKeyboardButton("🏠 Kembali ke Menu Utama", callback_data="menu_utama"))
	return markup


def markup_error_cari_saham(with_back=True):
	markup = InlineKeyboardMarkup()
	markup.add(InlineKeyboardButton("🔄 Coba Lagi", callback_data="cari_saham"))
	if with_back:
		markup.add(InlineKeyboardButton("🔙 Kembali ke Menu Saham", callback_data="menu_saham"))
	return markup
