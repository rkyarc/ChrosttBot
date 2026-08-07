from bot import tg_bot
from bot.services.removebg import hapus_background


@tg_bot.message_handler(content_types=['photo'])
def proses_hapus_bg(message):
    chat_id = message.chat.id

    pesan_loading = tg_bot.send_message(
        chat_id, "⏳ <i>Sedang memproses foto dan menghapus background...</i>", parse_mode="HTML"
    )

    try:
        file_info = tg_bot.get_file(message.photo[-1].file_id)
        downloaded_file = tg_bot.download_file(file_info.file_path)

        response = hapus_background(downloaded_file)

        if response and response.ok:
            tg_bot.send_document(chat_id, response.content, visible_file_name="hasil_nobg.png")
            tg_bot.delete_message(chat_id, pesan_loading.message_id)
        else:
            status = response.status_code if response else "no response"
            tg_bot.edit_message_text(
                f"❌ Gagal memproses gambar. Pastikan API Key valid atau kuota masih ada. "
                f"Status: {status}",
                chat_id,
                pesan_loading.message_id,
            )

    except Exception as e:
        tg_bot.edit_message_text(
            f"❌ Terjadi kesalahan sistem: {str(e)}", chat_id, pesan_loading.message_id
        )