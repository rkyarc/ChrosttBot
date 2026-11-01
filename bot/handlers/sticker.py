import os
import shutil

from bot import tg_bot
from bot.keyboards import (
    markup_kembali_menu_utama,
    markup_stiker_hasil,
    markup_stiker_mode,
    markup_stiker_tipe,
)
from bot.services import sticker
from bot.services.sticker import (
    StickerError,
    buat_stiker,
    folder_sementara,
    stiker_ke_mp4,
    stiker_ke_png,
    tersedia,
)
from bot.sessions import SessionStore
from bot.utils import escape_html
from bot.decorators import aman_handler


# chat_id -> path file media yang dikirim pengguna (sudah diunduh)
STIKER_SESSIONS = SessionStore(ttl=1800, max_entries=200)

TIPE_MEDIA = ("photo", "video", "document", "animation", "sticker")


def _teks_header(judul: str) -> str:
    return (
        f"🎨 <b>{judul}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )


def _bersihkan(paths: list[str]) -> None:
    """Hapus file & folder sementara."""
    for path in paths:
        try:
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            elif os.path.exists(path):
                os.remove(path)
        except OSError:
            pass


def _unduh_media(message) -> tuple[str, str] | None:
    """Simpan media dari pesan ke folder sementara. Return (path, ekstensi)."""
    chat_id = message.chat.id

    if message.photo:
        file_id = message.photo[-1].file_id
        ekstensi = ".jpg"
    elif message.video:
        file_id = message.video.file_id
        ekstensi = ".mp4"
    elif message.animation:
        file_id = message.animation.file_id
        ekstensi = ".mp4"
    elif message.sticker:
        stiker = message.sticker
        file_id = stiker.file_id

        # Stiker Telegram ada 3 jenis dan ekstensinya beda:
        #   is_video=True    -> .webm (VP9)
        #   is_animated=True -> .tgs (gzip Lottie, tidak bisa dibaca ffmpeg)
        #   statis           -> .webp
        if getattr(stiker, "is_video", False):
            ekstensi = ".webm"
        elif getattr(stiker, "is_animated", False):
            tg_bot.send_message(
                chat_id,
                "❌ Stiker animasi (.tgs) berbasis vektor, tidak bisa dikonversi.\n\n"
                "<i>Yang didukung: stiker statis (.webp) dan stiker video (.webm).</i>",
                parse_mode="HTML",
                reply_markup=markup_kembali_menu_utama(),
            )
            return None
        else:
            ekstensi = ".webp"
    elif message.document:
        berkas = message.document
        mime = (berkas.mime_type or "").lower()
        nama = (berkas.file_name or "").lower()

        # Stiker .tgs tidak bisa diproses ffmpeg
        if nama.endswith(".tgs") or "tgs" in mime:
            tg_bot.send_message(
                chat_id,
                "❌ File .tgs berbasis vektor dan tidak bisa dikonversi.\n\n"
                "<i>Kirim stiker statis atau stiker video.</i>",
                parse_mode="HTML",
                reply_markup=markup_kembali_menu_utama(),
            )
            return None

        if not (mime.startswith(("image/", "video/")) or nama.endswith((".webp", ".webm"))):
            tg_bot.send_message(
                chat_id,
                "❌ File harus berupa gambar, video, atau stiker.",
                reply_markup=markup_kembali_menu_utama(),
            )
            return None

        file_id = berkas.file_id
        ekstensi = os.path.splitext(berkas.file_name or "")[1] or ".bin"
    else:
        return None

    try:
        info = tg_bot.get_file(file_id)
        data = tg_bot.download_file(info.file_path)
    except Exception as e:
        tg_bot.send_message(
            chat_id,
            f"❌ Gagal mengunduh media: {escape_html(str(e)[:150])}",
            parse_mode="HTML",
        )
        return None

    folder = folder_sementara()
    path = os.path.join(folder, f"sumber{ekstensi}")
    with open(path, "wb") as f:
        f.write(data)

    return path


# ================== ENTRY DARI MENU ==================

@tg_bot.callback_query_handler(func=lambda call: call.data == "menu_stiker")
@aman_handler
def menu_stiker(call):
    chat_id = call.message.chat.id
    tg_bot.answer_callback_query(call.id)

    if not tersedia():
        tg_bot.edit_message_text(
            _teks_header("STIKER") + "⚠️ Fitur stiker butuh <code>ffmpeg</code> di server.\n\n"
            "<i>Pasang ffmpeg lalu restart bot.</i>",
            chat_id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=markup_kembali_menu_utama(),
        )
        return

    tg_bot.edit_message_text(
        _teks_header("STIKER TELEGRAM")
        + "\nBuat stiker dari foto atau video, atau balikkan stiker jadi gambar/video.\n\n"
        "<b>Yang didukung</b>\n"
        "• Foto → stiker statis 512×512 WebP\n"
        "• Video → stiker animasi maks 3 detik\n"
        "• Stiker → PNG atau MP4\n\n"
        "<b>Aturan Telegram</b>\n"
        "• Stiker statis &amp; animasi maks 512 KB\n"
        "• Video dipotong otomatis 3 detik pertama\n"
        "• Suara tidak ikut (stiker selalu tanpa audio)",
        chat_id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup_stiker_tipe(),
    )


@tg_bot.callback_query_handler(
    func=lambda call: call.data
    in ("stiker_buat", "stiker_balik", "stiker_batal")
)
@aman_handler
def aksi_stiker(call):
    chat_id = call.message.chat.id
    aksi = call.data.replace("stiker_", "", 1)

    if aksi == "batal":
        STIKER_SESSIONS.clear(chat_id)
        tg_bot.answer_callback_query(call.id, "Dibatalkan.")
        tg_bot.edit_message_text(
            "❌ Dibatalkan.",
            chat_id,
            call.message.message_id,
            reply_markup=markup_kembali_menu_utama(),
        )
        return

    if aksi == "buat":
        tg_bot.answer_callback_query(call.id)
        # Set sesi supaya handler media tahu ini masuk alur stiker
        STIKER_SESSIONS.set(chat_id, {"mode": "buat"})
        tg_bot.send_message(
            chat_id,
            _teks_header("BUAT STIKER")
            + "\nKirim <b>foto</b>, <b>video</b>, atau <b>stiker</b> ke chat ini.\n\n"
            "• Foto → stiker statis\n"
            "• Video → stiker animasi 3 detik\n"
            "• Stiker → dijadikan PNG/MP4\n\n"
            "<i>Bisa juga kirim sebagai file dokumen kalau media tidak muncul.</i>",
            parse_mode="HTML",
            reply_markup=markup_stiker_mode(),
        )
        return

    if aksi == "balik":
        tg_bot.answer_callback_query(call.id)
        STIKER_SESSIONS.set(chat_id, {"mode": "balik"})
        tg_bot.send_message(
            chat_id,
            _teks_header("STIKER → MEDIA")
            + "\nKirim <b>stiker</b> ke chat ini (kirim sebagai file .webp juga bisa).\n\n"
            "Lalu pilih mau dijadikan PNG atau MP4.",
            parse_mode="HTML",
            reply_markup=markup_stiker_mode(),
        )
        return

    tg_bot.answer_callback_query(call.id)


# ================== TERIMA MEDIA ==================

@tg_bot.message_handler(
    content_types=list(TIPE_MEDIA),
    func=lambda m: STIKER_SESSIONS.get(m.chat.id) is not None,
)
@aman_handler
def proses_media_stiker(message):
    """Dipanggil kalau pengguna sedang dalam alur stiker dan kirim media."""
    chat_id = message.chat.id
    sesi = STIKER_SESSIONS.get(chat_id) or {}
    mode = sesi.get("mode", "buat")

    path = _unduh_media(message)
    if not path:
        return

    sesi.update({"path": path, "folder": os.path.dirname(path)})
    STIKER_SESSIONS.set(chat_id, sesi)

    # Stiker yang dikirim (atau mode balik) langsung ditawari PNG/MP4
    if mode == "balik" or message.sticker:
        tg_bot.send_message(
            chat_id,
            _teks_header("STIKER DITERIMA")
            + "\nMau dijadikan apa?",
            parse_mode="HTML",
            reply_markup=markup_stiker_hasil(),
        )
        return

    _buat_dan_kirim(chat_id, path)


def _buat_dan_kirim(chat_id: int, path: str, mulai: float = 0.0):
    status = tg_bot.send_message(
        chat_id,
        "⏳ <i>Mengonversi media jadi stiker...</i>",
        parse_mode="HTML",
    )

    keluaran_dir = folder_sementara()
    try:
        hasil, jenis = buat_stiker(path, keluaran_dir, mulai=mulai)
        ukuran = os.path.getsize(hasil)

        with open(hasil, "rb") as f:
            # Parameter 'sticker' menerima file apa pun; Telegram mengenali
            # formatnya dari isi file (.webp statis / .webm VP9 video)
            tg_bot.send_sticker(chat_id, f)

        batas = sticker.MAX_ANIM_BYTES if jenis == "animasi" else sticker.MAX_STATIC_BYTES
        format_info = "WEBM VP9" if jenis == "animasi" else "WebP"

        tg_bot.edit_message_text(
            _teks_header("STIKER SELESAI")
            + f"\n• Jenis: <b>{jenis}</b> ({format_info})\n"
            f"• Ukuran: {ukuran / 1024:.0f} KB / {batas // 1024} KB\n"
            f"• Resolusi: maks 512 px\n\n"
            "<i>Tekan stikernya di Telegram, lalu simpan ke favorit.</i>",
            chat_id,
            status.message_id,
            parse_mode="HTML",
            reply_markup=markup_stiker_hasil(),
        )
    except StickerError as e:
        tg_bot.edit_message_text(
            _teks_header("GAGAL MEMBUAT STIKER")
            + f"\n{escape_html(str(e))}",
            chat_id,
            status.message_id,
            parse_mode="HTML",
            reply_markup=markup_stiker_hasil(),
        )
    except Exception as e:
        tg_bot.edit_message_text(
            _teks_header("ERROR")
            + f"\n<code>{escape_html(str(e)[:200])}</code>",
            chat_id,
            status.message_id,
            parse_mode="HTML",
            reply_markup=markup_stiker_hasil(),
        )
    finally:
        _bersihkan([keluaran_dir])


@tg_bot.callback_query_handler(func=lambda call: call.data == "stiker_ke_png")
@aman_handler
def ubah_ke_png(call):
    _ubah_stiker(call, "png")


@tg_bot.callback_query_handler(func=lambda call: call.data == "stiker_ke_mp4")
@aman_handler
def ubah_ke_mp4(call):
    _ubah_stiker(call, "mp4")


def _ubah_stiker(call, target: str):
    chat_id = call.message.chat.id
    sesi = STIKER_SESSIONS.get(chat_id) or {}
    path = sesi.get("path")

    if not path or not os.path.exists(path):
        tg_bot.answer_callback_query(
            call.id,
            "Media tidak ditemukan. Kirim ulang stikernya.",
            show_alert=True,
        )
        return

    tg_bot.answer_callback_query(call.id, "⏳ Memproses...")

    keluaran_dir = folder_sementara()
    try:
        if target == "png":
            hasil = stiker_ke_png(path, keluaran_dir)
            with open(hasil, "rb") as f:
                tg_bot.send_document(
                    chat_id,
                    f,
                    visible_file_name="stiker.png",
                    caption="🖼️ Stiker diubah jadi PNG (latar transparan).",
                )
        else:
            hasil = stiker_ke_mp4(path, keluaran_dir)
            with open(hasil, "rb") as f:
                tg_bot.send_video(
                    chat_id,
                    f,
                    caption="🎬 Stiker diubah jadi MP4.",
                    supports_streaming=True,
                )
    except StickerError as e:
        tg_bot.send_message(
            chat_id,
            f"❌ {escape_html(str(e))}",
            parse_mode="HTML",
            reply_markup=markup_stiker_hasil(),
        )
    except Exception as e:
        tg_bot.send_message(
            chat_id,
            f"⚠️ <code>{escape_html(str(e)[:200])}</code>",
            parse_mode="HTML",
        )
    finally:
        _bersihkan([keluaran_dir])
