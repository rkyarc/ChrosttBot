from bot import bot
from bot.keyboards import markup_cari_saham, markup_error_cari_saham, markup_hasil_saham, markup_menu_saham
from bot.services.saham import ambil_data_saham, format_kode_emiten, validasi_kode_emiten
from bot.utils import format_angka_rupiah


@bot.callback_query_handler(func=lambda call: call.data == "menu_saham")
def tampilkan_menu_saham(call):
	bot.edit_message_text(
		"📈 <b>Pusat Data Market</b>\n\nPilih indeks atau cari emiten yang ingin dicek:",
		call.message.chat.id,
		call.message.message_id,
		parse_mode="HTML",
		reply_markup=markup_menu_saham(),
	)


@bot.callback_query_handler(func=lambda call: call.data.startswith("cek_"))
def cek_saham(call):
	chat_id = call.message.chat.id
	kode_emiten = call.data.split("_", 1)[1]
	pesan_loading = bot.send_message(
		chat_id,
		f"🔍 <i>Menarik data {kode_emiten} dari bursa...</i>",
		parse_mode="HTML",
	)

	try:
		data_market = ambil_data_saham(kode_emiten)
		harga_terakhir = data_market["Close"].iloc[-1]

		if kode_emiten == "^JKSE":
			nama_tampilan = "IHSG"
			harga_formatted = format_angka_rupiah(harga_terakhir, desimal=True)
		else:
			nama_tampilan = kode_emiten.replace(".JK", "")
			harga_formatted = format_angka_rupiah(harga_terakhir)

		teks_balasan = (
			f"📊 <b>Update: {nama_tampilan}</b>\n"
			f"Harga Terakhir: <b>Rp {harga_formatted}</b>\n\n"
			"<i>*Data ditarik secara real-time via yfinance</i>"
		)

		bot.edit_message_text(
			teks_balasan,
			chat_id,
			pesan_loading.message_id,
			parse_mode="HTML",
			reply_markup=markup_hasil_saham(),
		)
	except Exception:
		bot.edit_message_text(
			f"❌ Gagal menarik data {kode_emiten}. Pastikan kode emitennya benar.",
			chat_id,
			pesan_loading.message_id,
		)


@bot.callback_query_handler(func=lambda call: call.data == "cari_saham")
def mulai_cari_saham(call):
	pesan_instruksi = bot.send_message(
		call.message.chat.id,
		"🔍 <b>Mode Pencarian Saham</b>\n\n"
		"Ketik kode saham BEI yang ingin dicari, misalnya <code>ASII</code>, <code>GOTO</code>, atau <code>BBCA</code>:",
		parse_mode="HTML",
	)
	bot.register_next_step_handler(pesan_instruksi, proses_cari_saham)


def proses_cari_saham(message):
	chat_id = message.chat.id
	kode_input = message.text.upper().strip()

	if not validasi_kode_emiten(kode_input):
		bot.send_message(
			chat_id,
			"❌ Format kode emiten tidak valid. Gunakan kode saham 1-4 huruf/angka, misalnya <code>BBCA</code> atau <code>ASII</code>.",
			parse_mode="HTML",
			reply_markup=markup_error_cari_saham(),
		)
		return

	kode_emiten = format_kode_emiten(kode_input)

	pesan_loading = bot.send_message(
		chat_id,
		f"⏳ <i>Mencari data {kode_input} di server bursa...</i>",
		parse_mode="HTML",
	)

	try:
		data_market = ambil_data_saham(kode_emiten)

		if data_market.empty:
			bot.edit_message_text(
				f"❌ Saham <b>{kode_input}</b> tidak ditemukan atau tidak terdaftar di BEI.\n\nSilakan periksa kembali kode emitennya.",
				chat_id,
				pesan_loading.message_id,
				parse_mode="HTML",
				reply_markup=markup_error_cari_saham(),
			)
			return

		harga_terakhir = data_market["Close"].iloc[-1]
		harga_formatted = format_angka_rupiah(harga_terakhir)

		teks_balasan = (
			f"📊 <b>Hasil Pencarian: {kode_input}</b>\n"
			f"Harga Terakhir: <b>Rp {harga_formatted}</b>\n\n"
			"<i>*Data ditarik secara real-time via yfinance</i>"
		)

		bot.edit_message_text(
			teks_balasan,
			chat_id,
			pesan_loading.message_id,
			parse_mode="HTML",
			reply_markup=markup_hasil_saham(),
		)
	except Exception:
		bot.edit_message_text(
			f"❌ Terjadi kesalahan saat mencari {kode_input}. Silakan coba lagi.",
			chat_id,
			pesan_loading.message_id,
			reply_markup=markup_error_cari_saham(),
		)
