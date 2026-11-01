"""Handler YouTube: unduh dari link, /play <query>, dan konversi audio."""

import logging
import os
import re

from telebot import types

from bot import play_mode, tg_bot, telegram_io as tg_io
from bot.keyboards import (
    markup_kembali_menu_utama,
    markup_youtube_daftar,
    markup_youtube_hasil,
    markup_youtube_pilihan,
)
from bot.services import youtube as YT
from bot.sessions import SessionStore
from bot.utils import escape_html
from bot.decorators import aman_handler

log = logging.getLogger("chrosttbot.youtube")


# chat_id -> {"url":..., "judul":..., "durasi":...}
YT_SESSIONS = SessionStore(ttl=1800, max_entries=200)

YOUTUBE_URL_PATTERN = re.compile(
    r"https?://(?:www\.|m\.)?(?:youtube\.com/(?:watch\?|shorts/|live/)|youtu\.be/)[^\s]+",
    re.IGNORECASE,
)

GARIS = "─" * 24

# Jumlah hasil pencarian yang ditampilkan
JUMLAH_HASIL = 20   # total hasil yang diambil dari YouTube
HASIL_PER_HALAMAN = 5  # tombol per halaman

# Kata yang membatalkan mode tunggu query /play
KATA_BATAL = ("batal", "cancel", "batalin")

# Petunjuk singkat selama bot masih menunggu judul berikutnya
CATATAN_TUNGGU = (
    "<i>Kirim judul lain untuk mencari lagi, atau ketik <code>batal</code>.</i>"
)


def _header(judul: str) -> str:
    return f"▶️ <b>{judul}</b>\n<code>{GARIS}</code>\n"


def _format_durasi(detik) -> str:
    detik = int(detik or 0)
    if detik <= 0:
        return "-"
    jam, sisa = divmod(detik, 3600)
    menit, detik = divmod(sisa, 60)
    if jam:
        return f"{jam}:{menit:02d}:{detik:02d}"
    return f"{menit}:{detik:02d}"


def _bersihkan(path: str) -> None:
    if path:
        YT.bersihkan_folder(os.path.dirname(path))


def _kirim_status(chat_id: int, teks: str):
    return tg_io.kirim(chat_id, teks, parse_mode="HTML")


def _edit_status(chat_id: int, message_id: int, teks: str, markup=None):
    """Edit status pencarian; fallback kirim baru kalau pesan sudah hilang."""
    tg_io.edit(
        chat_id,
        message_id,
        teks,
        parse_mode="HTML",
        reply_markup=markup,
    )


# ================== MENU ==================

@tg_bot.callback_query_handler(func=lambda call: call.data == "menu_youtube")
@aman_handler
def menu_youtube(call):
    tg_bot.answer_callback_query(call.id)

    if not YT.ffmpeg_tersedia():
        tg_bot.edit_message_text(
            _header("YOUTUBE")
            + "\n⚠️ Fitur ini butuh <code>ffmpeg</code> di server untuk "
            "menggabungkan video dan audio.\n\n"
            "<i>Pasang ffmpeg lalu restart bot.</i>",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=markup_kembali_menu_utama(),
        )
        return

    tg_bot.edit_message_text(
        _header("YOUTUBE DOWNLOADER")
        + "\n<b>Cara pakai</b>\n"
        "• Kirim link YouTube langsung ke chat\n"
        "• Ketik <code>/play</code> lalu kirim judulnya\n"
        "• Atau <code>/play judul lagu</code> sekali jalan\n\n"
        "<b>Yang didukung</b>\n"
        "• Video MP4 (video+audio digabung)\n"
        "• Audio MP3 dari video yang sama\n"
        "• Shorts, live replay, youtu.be\n\n"
        "<b>Batas</b>\n"
        "• Maksimal 50MB (limit Bot API Telegram)\n"
        "• Video maksimal 1 jam\n"
        "• Live stream berjalan tidak didukung",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup_youtube_pilihan(),
    )


@tg_bot.callback_query_handler(func=lambda call: call.data == "yt_panduan_play")
@aman_handler
def panduan_play(call):
    chat_id = call.message.chat.id
    tg_bot.answer_callback_query(call.id, "Ketik judul lagu atau video yang dicari.")

    play_mode.minta_judul(chat_id, getattr(call.from_user, "id", None))


# ================== /play ==================

def _lepas_alur_lain(chat_id: int) -> None:
    """Lepas next-step handler lain (mis. cari saham) yang akan menelan pesan.

    pyTelegramBotAPI menjalankan next-step handler sebelum handler biasa,
    jadi pesan judul bisa 'hilang' kalau alur lain masih terpasang.
    """
    try:
        tg_bot.clear_step_handler_by_chat_id(chat_id)
    except Exception:
        pass


def mode_tunggu_play(
    chat_id: int,
    user_id: int | None = None,
    balas_pesan_id: int | None = None,
) -> None:
    """Minta judul dari pengguna, sekaligus melepas alur next-step lain."""
    _lepas_alur_lain(chat_id)
    play_mode.minta_judul(chat_id, user_id, balas_pesan_id)


def _user_id(message):
    return getattr(getattr(message, "from_user", None), "id", None)


def _menunggu_query(chat_id: int, user_id: int | None) -> bool:
    return play_mode.sedang_menunggu(chat_id, user_id)


def _catatan_tunggu(chat_id: int) -> str:
    """Petunjuk 'kirim judul lain' hanya muncul selama mode tunggu aktif."""
    return CATATAN_TUNGGU if play_mode.aktif(chat_id) else ""


def cari_dan_tampilkan(chat_id: int, query: str) -> None:
    """Cari query di YouTube lalu tampilkan daftar hasil berhalaman."""
    status = _kirim_status(
        chat_id, f"🔍 <i>Mencari \"{escape_html(query[:80])}\"...</i>"
    )

    try:
        hasil = YT.cari_video(query, jumlah=JUMLAH_HASIL)
    except YT.YouTubeSearchError as e:
        _edit_status(
            chat_id,

            status.message_id,
            _header("TIDAK DITEMUKAN")
            + f"\n{escape_html(str(e))}\n\n<i>Coba kata kunci lain.</i>",
            markup_kembali_menu_utama(),
        )
        return
    except Exception as e:
        _edit_status(
            chat_id,
            status.message_id,
            _header("PENCARIAN GAGAL")
            + f"\n<code>{escape_html(str(e)[:200])}</code>",
            markup_kembali_menu_utama(),
        )
        return

    # Simpan daftar hasil supaya tombol bisa memilih salah satunya
    YT_SESSIONS.set(
        chat_id,
        {
            "mode": "daftar",
            "query": query,
            "hasil": hasil,
            "url": "",
            "judul": "",
            "durasi": 0,
            "video_id": "",
        },
    )

    _edit_status(
        chat_id,
        status.message_id,
        _teks_daftar(
            query,
            hasil,
            halaman=1,
            per_halaman=HASIL_PER_HALAMAN,
            catatan=_catatan_tunggu(chat_id),
        ),
        markup_youtube_daftar(hasil, halaman=1, per_halaman=HASIL_PER_HALAMAN),
    )


@tg_bot.message_handler(commands=["play", "putar"])
@aman_handler
def perintah_play(message):
    """/play — minta judul, /play <query> — langsung cari."""
    chat_id = message.chat.id

    if not YT.ffmpeg_tersedia():
        tg_bot.send_message(
            chat_id,
            "⚠️ Fitur ini butuh <code>ffmpeg</code> di server.",
            parse_mode="HTML",
            reply_markup=markup_kembali_menu_utama(),
        )
        return

    bagian = (message.text or "").split(maxsplit=1)
    query = bagian[1].strip() if len(bagian) > 1 else ""

    if not query:
        # Di grup, prompt membalas pesan /play supaya ForceReply-nya hanya
        # muncul untuk user yang meminta. Di chat pribadi cukup direct.
        if getattr(message.chat, "type", "private") == "private":
            balas_id = None
        else:
            balas_id = getattr(message, "message_id", None)

        mode_tunggu_play(chat_id, _user_id(message), balas_pesan_id=balas_id)
        return

    play_mode.tutup(chat_id)
    cari_dan_tampilkan(chat_id, query)


@tg_bot.message_handler(
    content_types=["text"],
    func=lambda m: _menunggu_query(m.chat.id, _user_id(m)),
)
@aman_handler
def terima_query_play(message):
    """Teks biasa saat mode /play aktif — langsung jadi query pencarian."""
    chat_id = message.chat.id
    teks = (message.text or "").strip()

    # Command lain (mis. /start, /ai) tetap diproses handler-nya sendiri
    if not teks or teks.startswith("/"):
        return

    if teks.lower() in KATA_BATAL:
        play_mode.tutup(chat_id)
        tg_bot.send_message(
            chat_id,
            "✅ Pencarian dibatalkan. Ketik /play lagi kapan saja.",
            reply_markup=markup_kembali_menu_utama(),
        )
        return

    if not YT.ffmpeg_tersedia():
        play_mode.tutup(chat_id)
        tg_bot.send_message(
            chat_id,
            "⚠️ Fitur ini butuh <code>ffmpeg</code> di server.",
            parse_mode="HTML",
            reply_markup=markup_kembali_menu_utama(),
        )
        return

    # Prompt ForceReply dilepas: hasil pencarian jadi pesan terakhir, tapi
    # mode tetap aktif supaya judul berikutnya tidak perlu /play lagi.
    play_mode.lepas_prompt(chat_id)
    cari_dan_tampilkan(chat_id, teks)


@tg_bot.callback_query_handler(func=lambda call: call.data == "yt_cari_baru")
@aman_handler
def cari_judul_lain(call):
    """Minta judul baru tanpa perlu mengetik /play lagi."""
    tg_bot.answer_callback_query(call.id, "Balas pesan bot dengan judul baru.")
    mode_tunggu_play(call.message.chat.id, getattr(call.from_user, "id", None))


def _angka(nilai) -> str:
    try:
        nilai = int(nilai)
    except (TypeError, ValueError):
        return "0"
    if nilai >= 1_000_000_000:
        return f"{nilai / 1_000_000_000:.1f}M".replace(".0M", "M")
    if nilai >= 1_000_000:
        return f"{nilai / 1_000_000:.1f}jt".replace(".0jt", "jt")
    if nilai >= 1_000:
        return f"{nilai / 1_000:.0f}rb"
    return str(nilai)


def _teks_daftar(
    query: str,
    hasil: list[dict],
    halaman: int = 1,
    per_halaman: int = 5,
    catatan: str = "",
) -> str:
    """Teks daftar untuk halaman aktif saja, bernomor sesuai tombol."""
    total = len(hasil)
    total_halaman = max(1, (total + per_halaman - 1) // per_halaman)
    halaman = max(1, min(halaman, total_halaman))

    mulai = (halaman - 1) * per_halaman
    potongan = hasil[mulai : mulai + per_halaman]

    baris = [
        _header(f"HASIL UNTUK \"{escape_html(query[:60])}\""),
        "",
        f"<i>Menampilkan {mulai + 1}-{mulai + len(potongan)} dari {total} hasil "
        f"\u00b7 halaman {halaman}/{total_halaman}</i>",
        "",
    ]

    for offset, item in enumerate(potongan):
        nomor = mulai + offset + 1
        judul = escape_html((item.get("judul") or "Tanpa judul")[:90])
        channel = escape_html((item.get("channel") or "-")[:35])
        durasi = _format_durasi(item.get("durasi"))
        views = _angka(item.get("views"))

        baris.append(f"<b>{nomor}.</b> {judul}")
        baris.append(f"     \U0001f464 {channel}  \u00b7  \u23f1\ufe0f {durasi}  \u00b7  \U0001f441\ufe0f {views}")
        baris.append("")

    if total_halaman > 1:
        baris.append("<i>Pakai tombol Prev/Next untuk halaman lain.</i>")

    if catatan:
        baris.append(catatan)

    return "\n".join(baris).rstrip()


# ================== LINK LANGSUNG ==================

@tg_bot.message_handler(func=lambda m: bool(YOUTUBE_URL_PATTERN.search(m.text or "")))
@aman_handler
def proses_link_youtube(message):
    """Tangkap link YouTube dan tawarkan pilihan format."""
    chat_id = message.chat.id
    url = YOUTUBE_URL_PATTERN.search(message.text).group(0)

    if not YT.ffmpeg_tersedia():
        tg_bot.send_message(
            chat_id,
            "⚠️ Fitur ini butuh <code>ffmpeg</code> di server.",
            parse_mode="HTML",
            reply_markup=markup_kembali_menu_utama(),
        )
        return

    status = _kirim_status(chat_id, "🔍 <i>Mengambil info video...</i>")

    try:
        info = YT.cari_video(url, jumlah=1)
        video = info[0]
    except YT.YouTubeSearchError:
        # Fallback: link valid walau metadata gagal diambil
        video = {
            "url": url,
            "judul": "Video YouTube",
            "channel": "",
            "durasi": 0,
            "id": "",
        }
    except Exception:
        video = {
            "url": url,
            "judul": "Video YouTube",
            "channel": "",
            "durasi": 0,
            "id": "",
        }

    YT_SESSIONS.set(
        chat_id,
        {
            "url": url,
            "judul": video.get("judul", ""),
            "durasi": video.get("durasi", 0),
            "video_id": video.get("id", ""),
        },
    )

    teks = (
        _header("YOUTUBE")
        + f"\n🎬 <b>{escape_html(str(video.get('judul', 'Video YouTube'))[:150])}</b>\n"
    )
    if video.get("channel"):
        teks += f"👤 {escape_html(str(video['channel'])[:60])}\n"
    if video.get("durasi"):
        teks += f"⏱️ {_format_durasi(video['durasi'])}\n"
    teks += "\nPilih format yang mau diunduh:"

    _edit_status(chat_id, status.message_id, teks, markup_youtube_hasil(url))


# ================== PILIH DARI DAFTAR HASIL ==================

@tg_bot.callback_query_handler(
    func=lambda call: call.data.startswith("yt_pilih_")
)
def pilih_hasil_pencarian(call):
    """User memilih salah satu hasil pencarian."""
    chat_id = call.message.chat.id
    sesi = YT_SESSIONS.get(chat_id)

    if not sesi or sesi.get("mode") != "daftar":
        tg_bot.answer_callback_query(
            call.id,
            "Daftar sudah kedaluwarsa. Ketik /play lagi ya.",
            show_alert=True,
        )
        return

    try:
        indeks = int(call.data.replace("yt_pilih_", ""))
    except ValueError:
        tg_bot.answer_callback_query(call.id, "Pilihan tidak valid.", show_alert=True)
        return

    hasil = sesi.get("hasil") or []
    if indeks < 0 or indeks >= len(hasil):
        tg_bot.answer_callback_query(call.id, "Pilihan tidak ada.", show_alert=True)
        return

    video = hasil[indeks]
    tg_bot.answer_callback_query(call.id, f"Dipilih: {video['judul'][:40]}")

    # Simpan pilihan aktif untuk tombol unduh
    sesi.update(
        {
            "mode": "pilih",
            "url": video["url"],
            "judul": video["judul"],
            "durasi": video.get("durasi", 0),
            "video_id": video.get("id", ""),
            "judul_kanal": video.get("channel", ""),
        }
    )
    YT_SESSIONS.set(chat_id, sesi)

    teks = (
        _header("SIAP DIUNDUH")
        + f"\n🎬 <b>{escape_html(str(video['judul'])[:150])}</b>\n"
        f"👤 {escape_html(str(video.get('channel', '-'))[:60])}\n"
        f"⏱️ {_format_durasi(video.get('durasi'))}"
    )
    if video.get("views"):
        teks += f"  ·  👁️ {_angka(video['views'])}"
    teks += "\n\nPilih format yang mau diunduh:"

    _edit_status(
        chat_id, call.message.message_id, teks, markup_youtube_hasil(video["url"])
    )


@tg_bot.callback_query_handler(func=lambda call: call.data == "yt_hal_info")
@aman_handler
def info_halaman(call):
    """Tombol label halaman (pasif)."""
    sesi = YT_SESSIONS.get(call.message.chat.id) or {}
    total = len(sesi.get("hasil") or [])
    total_halaman = max(1, (total + HASIL_PER_HALAMAN - 1) // HASIL_PER_HALAMAN)
    tg_bot.answer_callback_query(
        call.id, f"{total} hasil \u00b7 {total_halaman} halaman", show_alert=False
    )


@tg_bot.callback_query_handler(
    func=lambda call: call.data.startswith("yt_hal_")
    and call.data != "yt_hal_info"
)
def ganti_halaman(call):
    """Pindah halaman daftar hasil pencarian."""
    chat_id = call.message.chat.id
    sesi = YT_SESSIONS.get(chat_id)

    if not sesi or sesi.get("mode") != "daftar":
        tg_bot.answer_callback_query(
            call.id, "Daftar kedaluwarsa. Ketik /play lagi ya.", show_alert=True
        )
        return

    try:
        halaman = int(call.data.replace("yt_hal_", ""))
    except ValueError:
        tg_bot.answer_callback_query(call.id, "Halaman tidak valid.", show_alert=True)
        return

    hasil = sesi.get("hasil") or []
    total_halaman = max(1, (len(hasil) + HASIL_PER_HALAMAN - 1) // HASIL_PER_HALAMAN)
    halaman = max(1, min(halaman, total_halaman))

    query = sesi.get("query") or ""
    tg_bot.answer_callback_query(call.id, f"Halaman {halaman}/{total_halaman}")

    _edit_status(
        chat_id,
        call.message.message_id,
        _teks_daftar(
            query, hasil, halaman, HASIL_PER_HALAMAN, catatan=_catatan_tunggu(chat_id)
        ),
        markup_youtube_daftar(hasil, halaman, HASIL_PER_HALAMAN),
    )


@tg_bot.callback_query_handler(func=lambda call: call.data == "yt_cari_lagi")
def cari_lagi(call):
    """Ulangi pencarian terakhir."""
    chat_id = call.message.chat.id
    sesi = YT_SESSIONS.get(chat_id) or {}
    query = sesi.get("query")

    if not query:
        tg_bot.answer_callback_query(call.id, "Tidak ada query tersimpan.", show_alert=True)
        return

    tg_bot.answer_callback_query(call.id, "🔍 Mencari ulang...")

    try:
        hasil = YT.cari_video(query, jumlah=JUMLAH_HASIL)
    except Exception as e:
        tg_bot.send_message(
            chat_id,
            _header("PENCARIAN GAGAL") + f"\n{escape_html(str(e)[:200])}",
            parse_mode="HTML",
            reply_markup=markup_kembali_menu_utama(),
        )
        return

    sesi.update({"mode": "daftar", "hasil": hasil})
    YT_SESSIONS.set(chat_id, sesi)

    _edit_status(
        chat_id,
        call.message.message_id,
        _teks_daftar(
            query,
            hasil,
            halaman=1,
            per_halaman=HASIL_PER_HALAMAN,
            catatan=_catatan_tunggu(chat_id),
        ),
        markup_youtube_daftar(hasil, halaman=1, per_halaman=HASIL_PER_HALAMAN),
    )


# ================== UNDUH VIDEO ==================


@tg_bot.callback_query_handler(func=lambda call: call.data in ("yt_video", "yt_audio"))
def unduh_youtube(call):
    chat_id = call.message.chat.id
    sesi = YT_SESSIONS.get(chat_id)

    if not sesi:
        tg_bot.answer_callback_query(
            call.id,
            "Sesi kedaluwarsa. Kirim link atau /play lagi ya.",
            show_alert=True,
        )
        return

    mau_audio = call.data == "yt_audio"
    tg_bot.answer_callback_query(
        call.id, "⏳ Mengunduh audio..." if mau_audio else "⏳ Mengunduh video..."
    )

    status = _kirim_status(
        chat_id,
        f"⏳ <i>{'Mengunduh audio MP3' if mau_audio else 'Mengunduh video MP4'} "
        "(video+audio digabung)...</i>",
    )

    path = None
    try:
        if mau_audio:
            path = YT.download_youtube_audio(sesi["url"])
        else:
            path = YT.download_youtube_video(sesi["url"])

        ukuran_mb = os.path.getsize(path) / 1048576

        with open(path, "rb") as f:
            if mau_audio:
                tg_bot.send_audio(
                    chat_id,
                    f,
                    title=sesi.get("judul") or "YouTube Audio",
                    performer="YouTube",
                    caption=f"🎵 {escape_html(str(sesi.get('judul', ''))[:120])}",
                    parse_mode="HTML",
                    timeout=180,
                )
            else:
                tg_bot.send_video(
                    chat_id,
                    f,
                    caption=(
                        f"🎬 <b>{escape_html(str(sesi.get('judul', ''))[:120])}</b>\n"
                        f"<i>{ukuran_mb:.1f} MB</i>"
                    ),
                    parse_mode="HTML",
                    supports_streaming=True,
                    timeout=300,
                )

        tg_bot.delete_message(chat_id, status.message_id)

    except YT.YouTubeDownloadError as e:
        _edit_status(
            chat_id,
            status.message_id,
            _header("GAGAL MENGUNDUH")
            + f"\n{escape_html(str(e))}\n\n"
            f"<i>Link sumber:</i>\n{sesi['url']}",
            markup_kembali_menu_utama(),
        )
    except Exception as e:
        _edit_status(
            chat_id,
            status.message_id,
            _header("ERROR")
            + f"\n<code>{escape_html(str(e)[:200])}</code>",
            markup_kembali_menu_utama(),
        )
    finally:
        _bersihkan(path)


@tg_bot.callback_query_handler(func=lambda call: call.data == "yt_buka")
@aman_handler
def buka_di_youtube(call):
    sesi = YT_SESSIONS.get(call.message.chat.id)
    if not sesi:
        tg_bot.answer_callback_query(call.id, "Sesi kedaluwarsa.", show_alert=True)
        return
    tg_bot.answer_callback_query(call.id, "Link dikirim di bawah.")

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("▶️ Buka di YouTube", url=sesi["url"]))
    tg_bot.send_message(
        call.message.chat.id,
        f"🔗 {sesi['url']}",
        reply_markup=markup,
        disable_web_page_preview=False,
    )
