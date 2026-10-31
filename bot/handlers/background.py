from io import BytesIO

from bot import tg_bot
from bot.services.removebg import RemoveBgError, hapus_background


@tg_bot.message_handler(content_types=["photo"])
def proses_hapus_bg(message):
    chat_id = message.chat.id

    pesan_loading = tg_bot.send_message(
        chat_id,
        "⏳ <i>Sedang memproses foto dan menghapus background...</i>",
        parse_mode="HTML",
    )

    try:
        file_info = tg_bot.get_file(message.photo[-1].file_id)
        downloaded_file = tg_bot.download_file(file_info.file_path)

        hasil = hapus_background(downloaded_file)

        tg_bot.send_document(
            chat_id,
            BytesIO(hasil),
            visible_file_name="hasil_nobg.png",
        )
        tg_bot.delete_message(chat_id, pesan_loading.message_id)

    except RemoveBgError as e:
        tg_bot.edit_message_text(
            f"❌ Gagal memproses gambar.\n\n{str(e)[:200]}",
            chat_id,
            pesan_loading.message_id,
        )
    except Exception as e:
        tg_bot.edit_message_text(
            f"❌ Terjadi kesalahan sistem: {str(e)[:200]}",
            chat_id,
            pesan_loading.message_id,
        )
