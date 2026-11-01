import math

from bot import tg_bot
from bot.keyboards import markup_berita_idx, markup_kembali_menu_utama
from bot.services.idx_news import IDXNewsError, ambil_berita_terbaru, hapus_cache
from bot.utils import escape_html
from bot.decorators import aman_handler


BERITA_PER_HALAMAN = 3
JUMLAH_FETCH = 9  # Total berita yang diambil dari Google News (untuk 3 halaman)


def _truncate(text: str, max_len: int) -> str:
    """Potong teks kalau kepanjangan."""
    if not text:
        return "-"
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def _edit_atau_kirim(chat_id: int, message_id: int, teks: str, markup):
    """Edit pesan lama; kalau gagal (misal isinya sama), kirim pesan baru."""
    try:
        tg_bot.edit_message_text(
            teks,
            chat_id,
            message_id,
            parse_mode="HTML",
            reply_markup=markup,
            disable_web_page_preview=True,
        )
    except Exception:
        tg_bot.send_message(
            chat_id,
            teks,
            parse_mode="HTML",
            reply_markup=markup,
            disable_web_page_preview=True,
        )


# ================== HANDLER UTAMA ==================

@tg_bot.callback_query_handler(func=lambda call: call.data == "menu_berita")
@aman_handler
def menu_berita_idx(call):
    """Tombol menu berita di menu utama."""
    tg_bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id

    pesan_loading = tg_bot.send_message(
        chat_id,
        "⏳ <i>Mengambil berita terbaru...</i>",
        parse_mode="HTML",
    )

    tampilkan_berita(chat_id, pesan_loading.message_id, halaman=1)


@tg_bot.callback_query_handler(func=lambda call: call.data.startswith("berita_idx_page_"))
def navigasi_halaman(call):
    """Handler navigasi halaman (Berikutnya / Sebelumnya)."""
    try:
        halaman = int(call.data.replace("berita_idx_page_", ""))
    except ValueError:
        halaman = 1

    tg_bot.answer_callback_query(call.id, f"📄 Halaman {halaman}")
    tampilkan_berita(call.message.chat.id, call.message.message_id, halaman=halaman)


@tg_bot.callback_query_handler(func=lambda call: call.data == "berita_idx_refresh")
@aman_handler
def refresh_berita_idx(call):
    """Tombol refresh paksa (fetch ulang dari Google News)."""
    tg_bot.answer_callback_query(call.id, "🔄 Memuat ulang dari sumber...")

    # Hapus cache supaya fetch ulang
    hapus_cache()
    tampilkan_berita(call.message.chat.id, call.message.message_id, halaman=1)


@tg_bot.callback_query_handler(func=lambda call: call.data == "noop")
@aman_handler
def tombol_pasif(call):
    """Handler tombol pasif (label halaman)."""
    tg_bot.answer_callback_query(call.id)


# ================== FUNGSI TAMPILAN ==================

def tampilkan_berita(chat_id: int, message_id: int, halaman: int = 1):
    """
    Ambil berita dan tampilkan sesuai halaman yang diminta.
    3 berita per halaman, total 9 berita di-cache selama 5 menit.
    """
    try:
        # Ambil data (dari cache atau fetch baru)
        semua_berita = ambil_berita_terbaru(jumlah=JUMLAH_FETCH)

        if not semua_berita:
            _edit_atau_kirim(
                chat_id,
                message_id,
                "⚠️ <b>Berita IDX</b>\n\nTidak ada berita terbaru yang ditemukan saat ini.",
                markup_kembali_menu_utama(),
            )
            return

        # Hitung pagination
        total_berita = len(semua_berita)
        total_halaman = math.ceil(total_berita / BERITA_PER_HALAMAN)

        # Validasi halaman
        halaman = max(1, min(halaman, total_halaman))

        # Slice berita untuk halaman ini
        start_idx = (halaman - 1) * BERITA_PER_HALAMAN
        berita_halaman = semua_berita[start_idx:start_idx + BERITA_PER_HALAMAN]

        teks = (
            f"📰 <b>Berita Terbaru IDX</b>  <i>(Hal {halaman}/{total_halaman})</i>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        # Nomor urut dimulai dari (halaman-1)*3 + 1
        nomor_awal = start_idx + 1

        for i, berita in enumerate(berita_halaman, start=nomor_awal):
            judul = escape_html(_truncate(berita.get("judul", ""), 140))
            tanggal = escape_html(_truncate(berita.get("tanggal", "Terbaru"), 30))
            sumber = escape_html(_truncate(berita.get("sumber", ""), 25))
            link = berita.get("link", "")

            teks += f"<b>{i}. {judul}</b>\n"
            teks += f"📅 {tanggal}"
            if sumber:
                teks += f" • 📰 {sumber}"
            teks += "\n"

            if link:
                teks += f"🔗 <a href=\"{escape_html(link)}\">Baca Selengkapnya</a>\n"
            teks += "\n"

        teks += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        teks += f"<i>Total {total_berita} berita • Cache 5 menit</i>"

        # Cek panjang teks, fallback versi ringkas kalau kepanjangan
        if len(teks) > 4000:
            teks = f"📰 <b>Berita IDX</b> (Hal {halaman}/{total_halaman})\n\n"
            for i, berita in enumerate(berita_halaman, start=nomor_awal):
                judul = escape_html(_truncate(berita.get("judul", ""), 90))
                link = escape_html(berita.get("link", ""))
                teks += f'{i}. <a href="{link}">{judul}</a>\n\n'
            teks += "<i>Tap judul untuk baca selengkapnya.</i>"

        _edit_atau_kirim(
            chat_id,
            message_id,
            teks,
            markup_berita_idx(halaman_sekarang=halaman, total_halaman=total_halaman),
        )

    except IDXNewsError as e:
        _edit_atau_kirim(
            chat_id,
            message_id,
            f"❌ <b>Gagal Mengambil Berita</b>\n\n{escape_html(str(e))}\n\n"
            "<i>Silakan coba lagi dalam beberapa saat.</i>",
            markup_kembali_menu_utama(),
        )
    except Exception as e:
        _edit_atau_kirim(
            chat_id,
            message_id,
            f"⚠️ <b>Error tidak terduga</b>\n\n<code>{escape_html(str(e)[:200])}</code>",
            markup_kembali_menu_utama(),
        )
