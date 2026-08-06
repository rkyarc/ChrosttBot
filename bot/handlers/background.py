from io import BytesIO

from bot import bot
from bot.keyboards import markup_kembali_menu_utama
from bot.services.removebg import hapus_background


@bot.callback_query_handler(func=lambda call: call.data == "menu_bg")
def aktifkan_mode_hapus_bg(call):
	bot.send_message(
		call.message.chat.id,
		"✂️ <b>Mode Hapus Background Aktif</b>\n\nKirim satu foto sebagai gambar biasa, bukan file dokumen.",
		parse_mode="HTML",
		reply_markup=markup_kembali_menu_utama(),
	)


@bot.message_handler(content_types=["photo"])
def proses_hapus_bg(message):
	chat_id = message.chat.id
	pesan_loading = bot.send_message(
		chat_id,
		"⏳ <i>Sedang memproses foto dan menghapus background...</i>",
		parse_mode="HTML",
	)

	try:
		file_info = bot.get_file(message.photo[-1].file_id)
		downloaded_file = bot.download_file(file_info.file_path)
		response = hapus_background(downloaded_file)

		if response.ok:
			hasil = BytesIO(response.content)
			hasil.name = "hasil_nobg.png"
			hasil.seek(0)
			bot.send_document(chat_id, hasil)
			bot.delete_message(chat_id, pesan_loading.message_id)
		else:
			bot.edit_message_text(
				f"❌ Gagal memproses gambar. Pastikan API key remove.bg valid atau kuotanya masih tersedia. Status: {response.status_code}",
				chat_id,
				pesan_loading.message_id,
			)
	except Exception as e:
		bot.edit_message_text(
			f"❌ Terjadi kesalahan sistem: {str(e)}",
			chat_id,
			pesan_loading.message_id,
		)
