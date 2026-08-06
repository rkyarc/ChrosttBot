from bot import bot
from bot.keyboards import markup_kembali_menu_utama, markup_menu_utama


@bot.message_handler(commands=["start", "menu"])
def tampilkan_menu(message):
	teks_sambutan = (
		"🤖 <b>Selamat datang di Chrostt Bot!</b>\n\n"
		"Pilih layanan yang ingin Anda gunakan:"
	)

	bot.send_message(
		message.chat.id,
		teks_sambutan,
		parse_mode="HTML",
		reply_markup=markup_menu_utama(),
	)


@bot.callback_query_handler(func=lambda call: call.data == "menu_utama")
def kembali_ke_menu_utama(call):
	teks_sambutan = (
		"🤖 <b>Selamat datang di Chrostt Bot!</b>\n\n"
		"Pilih layanan yang ingin Anda gunakan:"
	)

	bot.edit_message_text(
		teks_sambutan,
		call.message.chat.id,
		call.message.message_id,
		parse_mode="HTML",
		reply_markup=markup_menu_utama(),
	)


@bot.callback_query_handler(func=lambda call: call.data == "menu_info")
def tampilkan_info_bot(call):
	bot.send_message(
		call.message.chat.id,
		"ℹ️ <b>Info Bot</b>\n\nBot ini dibangun menggunakan Python dan pyTelegramBotAPI. Fokusnya adalah membantu tugas harian dengan alur yang sederhana.",
		parse_mode="HTML",
		reply_markup=markup_kembali_menu_utama(),
	)
