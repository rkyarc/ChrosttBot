from bot import tg_bot
from bot.keyboards import (
    markup_hasil_saham,
    markup_menu_saham,
    markup_saham_tidak_ditemukan,
)
from bot.services.saham import ambil_data_saham, format_kode_emiten, validasi_kode_emiten
from bot.utils import escape_html, format_angka_rupiah
from bot.decorators import aman_handler


def _ambil_harga(kode_emiten):
    """Ambil harga terakhir, None kalau datanya kosong/tidak tersedia."""
    data_market = ambil_data_saham(kode_emiten)

    if data_market is None or data_market.empty or "Close" not in data_market:
        return None

    return data_market["Close"].iloc[-1]


def _teks_harga(kode_emiten, judul, harga_terakhir):
    if kode_emiten == "^JKSE":
        nama_tampilan = "IHSG"
        harga_formatted = format_angka_rupiah(harga_terakhir, desimal=True)
    else:
        nama_tampilan = kode_emiten.replace(".JK", "")
        harga_formatted = format_angka_rupiah(harga_terakhir)

    return (
        f"📊 <b>{escape_html(judul)}: {escape_html(nama_tampilan)}</b>\n"
        f"Harga Terakhir: <b>Rp {harga_formatted}</b>\n\n"
        "<i>*Data ditarik via yfinance</i>"
    )


@tg_bot.callback_query_handler(func=lambda call: call.data == "menu_saham")
@aman_handler
def tampilkan_menu_saham(call):
    tg_bot.answer_callback_query(call.id)
    tg_bot.edit_message_text(
        "📈 <b>Pusat Data Market</b>\n\nPilih indeks atau cari emiten yang ingin dicek:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup_menu_saham(),
    )


@tg_bot.callback_query_handler(func=lambda call: call.data.startswith("cek_"))
@aman_handler
def cek_saham(call):
    tg_bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    kode_emiten = call.data.split("_", 1)[1]

    pesan_loading = tg_bot.send_message(
        chat_id,
        f"🔍 <i>Menarik data {escape_html(kode_emiten)} dari bursa...</i>",
        parse_mode="HTML",
    )

    try:
        harga_terakhir = _ambil_harga(kode_emiten)

        if harga_terakhir is None:
            tg_bot.edit_message_text(
                f"❌ Data {escape_html(kode_emiten)} tidak ditemukan. Silakan coba lagi nanti.",
                chat_id,
                pesan_loading.message_id,
                reply_markup=markup_saham_tidak_ditemukan(),
            )
            return

        tg_bot.edit_message_text(
            _teks_harga(kode_emiten, "Update", harga_terakhir),
            chat_id,
            pesan_loading.message_id,
            parse_mode="HTML",
            reply_markup=markup_hasil_saham(),
        )
    except Exception:
        tg_bot.edit_message_text(
            f"❌ Gagal menarik data {escape_html(kode_emiten)}. Pastikan kode emitennya benar.",
            chat_id,
            pesan_loading.message_id,
            reply_markup=markup_saham_tidak_ditemukan(),
        )


@tg_bot.callback_query_handler(func=lambda call: call.data == "cari_saham")
@aman_handler
def mulai_cari_saham(call):
    tg_bot.answer_callback_query(call.id)
    pesan_instruksi = tg_bot.send_message(
        call.message.chat.id,
        "🔍 <b>Mode Pencarian Saham</b>\n\n"
        "Ketik kode saham BEI yang ingin dicari, misalnya <code>ASII</code>, "
        "<code>GOTO</code>, atau <code>BBCA</code>:",
        parse_mode="HTML",
    )
    tg_bot.register_next_step_handler(pesan_instruksi, proses_cari_saham)


def proses_cari_saham(message):
    chat_id = message.chat.id

    if not message.text:
        tg_bot.send_message(
            chat_id,
            "❌ Mohon kirim kode saham dalam bentuk teks, misalnya <code>BBCA</code>.",
            parse_mode="HTML",
            reply_markup=markup_saham_tidak_ditemukan(),
        )
        return

    kode_input = message.text.upper().strip()

    if not validasi_kode_emiten(kode_input):
        tg_bot.send_message(
            chat_id,
            "❌ Format kode emiten tidak valid. Gunakan kode 1-4 huruf/angka, "
            "misalnya <code>BBCA</code> atau <code>ASII</code>.",
            parse_mode="HTML",
            reply_markup=markup_saham_tidak_ditemukan(),
        )
        return

    kode_emiten = format_kode_emiten(kode_input)

    pesan_loading = tg_bot.send_message(
        chat_id,
        f"⏳ <i>Mencari data {escape_html(kode_input)} di server bursa...</i>",
        parse_mode="HTML",
    )

    try:
        harga_terakhir = _ambil_harga(kode_emiten)

        if harga_terakhir is None:
            tg_bot.edit_message_text(
                f"❌ Saham <b>{escape_html(kode_input)}</b> tidak ditemukan atau tidak "
                "terdaftar di BEI.\n\nSilakan periksa kembali kode emitennya.",
                chat_id,
                pesan_loading.message_id,
                parse_mode="HTML",
                reply_markup=markup_saham_tidak_ditemukan(),
            )
            return

        tg_bot.edit_message_text(
            _teks_harga(kode_emiten, f"Hasil Pencarian {kode_input}", harga_terakhir),
            chat_id,
            pesan_loading.message_id,
            parse_mode="HTML",
            reply_markup=markup_hasil_saham(),
        )
    except Exception:
        tg_bot.edit_message_text(
            f"❌ Terjadi kesalahan saat mencari {escape_html(kode_input)}. Silakan coba lagi.",
            chat_id,
            pesan_loading.message_id,
            reply_markup=markup_saham_tidak_ditemukan(),
        )
