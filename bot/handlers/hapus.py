"""Fitur /del: hapus pesan dan media di chat.

Cara pakai:
- /del            -> hapus pesan perintah itu sendiri
- /del (reply)    -> hapus pesan yang dibalas, lalu pesan perintah
- /del 5          -> hapus 5 pesan terakhir termasuk perintah
- /del all        -> hapus sebanyak mungkin (maks 100)

Batasan Telegram yang ditangani:
- Pesan hanya bisa dihapus dalam 48 jam
- Di grup, bot harus admin dengan izin delete
- Pesan yang sudah tidak ada akan dilewati
"""

import re

from telebot.apihelper import ApiTelegramException

from bot import tg_bot
from bot.keyboards import markup_hapus_hasil, markup_kembali_menu_utama
from bot.utils import escape_html
from bot.decorators import aman_handler


GARIS = "─" * 24

# Batas bulk delete Bot API
MAKS_SEKALI_HAPUS = 100

# Perkiraan umur pesan yang masih bisa dihapus (detik)
BATAS_UMUR = 48 * 3600


def _header(judul: str) -> str:
    return f"🗑️ <b>{judul}</b>\n<code>{GARIS}</code>\n"


def _deskripsi_error(e: ApiTelegramException) -> str:
    """Terjemahkan error Telegram jadi alasan yang bisa dibaca."""
    teks = (getattr(e, "description", "") or str(e)).lower()

    if "message to delete not found" in teks:
        return "pesan sudah tidak ada"
    if "message can't be deleted" in teks:
        return "pesan terlalu lama (batas 48 jam)"
    if "not enough rights" in teks:
        return "bot tidak punya izin menghapus di sini"
    if "chat not found" in teks:
        return "chat tidak ditemukan"
    if "message identifier not specified" in teks:
        return "ID pesan tidak valid"

    return (getattr(e, "description", "") or str(e))[:120]


def _hapus_banyak(chat_id: int, ids: list[int]) -> tuple[int, list[str]]:
    """Hapus sekumpulan message_id. Return (jumlah berhasil, daftar alasan gagal).

    delete_messages() mengembalikan bool, bukan melempar exception saat sebagian
    pesan tidak ada. Karena itu hasil True dianggap sukses, dan False memicu
    fallback hapus satu per satu supaya hitungannya akurat.
    """
    if not ids:
        return 0, []

    berhasil = 0
    alasan: list[str] = []

    for mulai in range(0, len(ids), MAKS_SEKALI_HAPUS):
        potongan = ids[mulai : mulai + MAKS_SEKALI_HAPUS]
        sukses_bulk = False

        try:
            sukses_bulk = bool(tg_bot.delete_messages(chat_id, potongan))
        except ApiTelegramException as e:
            alasan.append(_deskripsi_error(e))
        except Exception as e:
            alasan.append(str(e)[:120])

        if sukses_bulk:
            berhasil += len(potongan)
            continue

        # Fallback: hapus satu per satu supaya yang valid tetap terhapus
        for mid in potongan:
            try:
                tg_bot.delete_message(chat_id, mid)
                berhasil += 1
            except ApiTelegramException as e:
                pesan = _deskripsi_error(e)
                if pesan not in alasan:
                    alasan.append(pesan)
            except Exception as e:
                pesan = str(e)[:120]
                if pesan not in alasan:
                    alasan.append(pesan)

    return berhasil, alasan


def _laporan(berhasil: int, gagal: int, alasan: list[str]) -> str:
    teks = _header("HASIL HAPUS")
    teks += f"\n✅ Terhapus: <b>{berhasil}</b> pesan\n"
    if gagal:
        teks += f"⚠️ Dilewati: <b>{gagal}</b> pesan\n"
    if alasan:
        teks += "\n<b>Alasan</b>\n"
        for a in alasan[:3]:
            teks += f"• {escape_html(a)}\n"
    return teks


@tg_bot.message_handler(commands=["del", "hapus"])
@aman_handler
def perintah_hapus(message):
    """/del — hapus pesan sendiri, media yang dibalas, atau beberapa pesan terakhir."""
    chat_id = message.chat.id
    argumen = (message.text or "").split(maxsplit=1)
    argumen = argumen[1].strip().lower() if len(argumen) > 1 else ""

    # ---------- mode reply: hapus pesan yang dibalas ----------
    if message.reply_to_message:
        target = message.reply_to_message.message_id
        berhasil, alasan = _hapus_banyak(chat_id, [target])

        # Hapus juga pesan perintahnya supaya chat bersih
        sisa_berhasil, alasan2 = _hapus_banyak(chat_id, [message.message_id])
        berhasil += sisa_berhasil
        for a in alasan2:
            if a not in alasan:
                alasan.append(a)

        gagal = 2 - berhasil
        if berhasil == 0:
            tg_bot.send_message(
                chat_id,
                _header("GAGAL MENGHAPUS")
                + "\nBot tidak bisa menghapus pesan itu.\n\n"
                + "\n".join(f"• {escape_html(a)}" for a in alasan[:3]),
                parse_mode="HTML",
                reply_markup=markup_kembali_menu_utama(),
            )
            return

        if gagal:
            tg_bot.send_message(
                chat_id,
                _laporan(berhasil, gagal, alasan),
                parse_mode="HTML",
                reply_markup=markup_hapus_hasil(),
            )
        return

    # ---------- tanpa argumen: hapus pesan perintah saja ----------
    if not argumen:
        berhasil, alasan = _hapus_banyak(chat_id, [message.message_id])
        if berhasil:
            return

        teks = _header("TIDAK BISA MENGHAPUS") + "\n"
        if alasan:
            teks += "\n<b>Alasan</b>\n"
            for a in alasan[:2]:
                teks += f"• {escape_html(a)}\n"
            teks += "\n"

        teks += (
            "<b>Cara pakai /del</b>\n"
            "• Balas pesan/media lalu kirim <code>/del</code>\n"
            "• <code>/del 5</code> untuk hapus 5 pesan terakhir\n"
            "• <code>/del all</code> untuk bersihkan sampai 100 pesan\n\n"
            "<i>Di grup, jadikan bot admin dengan izin hapus pesan.</i>"
        )

        tg_bot.send_message(
            chat_id,
            teks,
            parse_mode="HTML",
            reply_markup=markup_hapus_hasil(),
        )
        return

    # ---------- mode jumlah ----------
    if argumen in ("all", "semua", "*"):
        jumlah = MAKS_SEKALI_HAPUS
    else:
        cocok = re.fullmatch(r"(\d{1,3})", argumen)
        if not cocok:
            tg_bot.send_message(
                chat_id,
                _header("ARGUMEN TIDAK VALID")
                + f"\n<code>{escape_html(argumen[:40])}</code> bukan angka.\n\n"
                "Contoh: <code>/del 5</code> atau <code>/del all</code>",
                parse_mode="HTML",
                reply_markup=markup_kembali_menu_utama(),
            )
            return
        jumlah = int(cocok.group(1))

    jumlah = max(1, min(jumlah, MAKS_SEKALI_HAPUS))

    akhir = message.message_id
    awal = max(1, akhir - jumlah + 1)
    ids = list(range(awal, akhir + 1))

    berhasil, alasan = _hapus_banyak(chat_id, ids)
    gagal = len(ids) - berhasil

    if berhasil == 0:
        tg_bot.send_message(
            chat_id,
            _header("GAGAL MENGHAPUS")
            + "\nTidak ada pesan yang bisa dihapus.\n\n"
            + "\n".join(f"• {escape_html(a)}" for a in alasan[:3]),
            parse_mode="HTML",
            reply_markup=markup_kembali_menu_utama(),
        )
        return

    # Kalau semua beres dan pesan perintah ikut terhapus, tidak perlu laporan
    if gagal == 0:
        return

    tg_bot.send_message(
        chat_id,
        _laporan(berhasil, gagal, alasan),
        parse_mode="HTML",
        reply_markup=markup_hapus_hasil(),
    )


@tg_bot.callback_query_handler(func=lambda call: call.data == "menu_hapus")
@aman_handler
def menu_hapus(call):
    """Panduan /del dari menu."""
    tg_bot.answer_callback_query(call.id)
    tg_bot.edit_message_text(
        _header("HAPUS PESAN")
        + "\n<b>Cara pakai</b>\n"
        "• Balas media/pesan lalu kirim <code>/del</code>\n"
        "• <code>/del 5</code> — hapus 5 pesan terakhir\n"
        "• <code>/del all</code> — bersihkan sampai 100 pesan\n\n"
        "<b>Batasan Telegram</b>\n"
        "• Hanya pesan dalam 48 jam terakhir\n"
        "• Di grup, bot harus admin dengan izin hapus\n"
        "• Pesan layanan sistem tidak bisa dihapus\n\n"
        "<i>Perintah ini juga menghapus balasan bot di chat ini.</i>",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup_hapus_hasil(),
    )


@tg_bot.callback_query_handler(func=lambda call: call.data == "hapus_panduan")
@aman_handler
def panduan_hapus(call):
    tg_bot.answer_callback_query(
        call.id,
        "Balas pesan lalu ketik /del, atau /del 5 untuk 5 pesan terakhir.",
        show_alert=True,
    )
