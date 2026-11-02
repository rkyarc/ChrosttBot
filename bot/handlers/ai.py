import logging
import re
import threading

from bot import batas_laju, play_mode, tg_bot
from bot.admin import apakah_admin
from bot.ai_prompt import (
    MAKS_KARAKTER_RIWAYAT,
    MAKS_PESAN_RIWAYAT,
    SAPANAN_AWAL,
    SAPANAN_SINGKAT,
    system_prompt,
)
from bot.keyboards import markup_ai, markup_ai_tertutup, markup_kembali_menu_utama
from bot.riwayat import RIWAYAT
from bot.services import aksi
from bot.services.ai import (
    HASIL_WEB_ADMIN,
    MAKS_KARAKTER_HALAMAN_ADMIN,
    MAKS_PUTARAN_TOOL_ADMIN,
    TOOL_ADMIN_NAMA,
    AIError,
    aksi_aktif,
    model_aktif,
    tanya,
    tersedia,
    web_aktif,
)
from bot.sessions import SessionStore
from bot.utils import escape_html, ke_telegram_html, potong_html, strip_html
from bot.decorators import aman_handler

log = logging.getLogger("chrosttbot.ai")

# chat_id -> {"riwayat": [{"role", "content"}, ...]}
AI_SESSIONS = SessionStore(ttl=3600, max_entries=500)

# pyTelegramBotAPI memproses update paralel; kunci per chat supaya riwayat tidak
# tabrakan. Disimpan di SessionStore agar ikut kedaluwarsa — kalau tidak, bot
# yang hidup berbulan-bulan menumpuk satu Lock untuk setiap chat selamanya.
_LOCKS = SessionStore(ttl=3600, max_entries=500)
_LOCKS_GUARD = threading.Lock()


def _lock_chat(chat_id: int) -> threading.Lock:
    """Lock milik satu chat, dibuat sekali dan ikut TTL sesi AI."""
    with _LOCKS_GUARD:
        lock = _LOCKS.get(chat_id)
        if lock is None:
            lock = threading.Lock()
        # Selalu set ulang: sekaligus memperpanjang TTL supaya lock tidak
        # kedaluwarsa saat chat masih aktif dipakai.
        _LOCKS.set(chat_id, lock)
        return lock


SIMBOL = "✦"

# Pesan berisi link media tetap diproses downloader, bukan AI
POLA_LINK = re.compile(
    r"https?://\S*(?:instagram\.com|instagr\.am|tiktok\.com|facebook\.com|fb\.watch"
    r"|youtube\.com|youtu\.be|youtu\.?be)",
    re.IGNORECASE,
)


# ================== STATE ==================

def _potong_riwayat(riwayat: list[dict]) -> list[dict]:
    """Batasi riwayat ke batas konteks model.

    Database menyimpan lebih banyak pesan (supaya arsip tetap utuh), tetapi
    yang dikirim ke model harus tetap kecil agar biaya dan latensi wajar.
    """
    if len(riwayat) > MAKS_PESAN_RIWAYAT:
        riwayat = riwayat[-MAKS_PESAN_RIWAYAT:]

    total = sum(len(p.get("content") or "") for p in riwayat)
    while total > MAKS_KARAKTER_RIWAYAT and len(riwayat) > 2:
        total -= len(riwayat.pop(0).get("content") or "")

    return riwayat


def _sesi(chat_id: int, akses: str | None = None) -> dict:
    """Ambil sesi AI chat ini, buat baru kalau belum ada.

    Riwayat permanen dibaca dari SQLite saat sesi pertama kali dibuka, jadi
    percakapan tetap tersambung setelah bot restart. Kalau ``akses`` diberikan
    dan berbeda dari pemilik riwayat sebelumnya, riwayat dikosongkan. Ini
    mencegah konteks admin terbawa ke pengguna biasa di grup yang sama.
    """
    sesi = AI_SESSIONS.get(chat_id)

    if sesi:
        if akses is not None and sesi.get("akses") != akses:
            sesi["riwayat"] = []
            sesi["akses"] = akses
        else:
            # Set ulang supaya TTL ikut diperpanjang selama user aktif
            AI_SESSIONS.set(chat_id, sesi)
        return sesi

    riwayat = []
    if akses is not None:
        try:
            riwayat = _potong_riwayat(RIWAYAT.siapkan(chat_id, akses))
        except Exception:
            log.warning("Gagal memuat riwayat chat %s", chat_id, exc_info=True)

    sesi = {"riwayat": riwayat, "akses": akses}
    AI_SESSIONS.set(chat_id, sesi)
    return sesi


def _aktif(chat_id: int) -> bool:
    return AI_SESSIONS.get(chat_id) is not None


def _reset(chat_id: int) -> None:
    sesi = _sesi(chat_id)
    sesi["riwayat"] = []
    AI_SESSIONS.set(chat_id, sesi)

    try:
        RIWAYAT.hapus(chat_id)
    except Exception:
        log.warning("Gagal menghapus riwayat chat %s", chat_id, exc_info=True)


def _tambah_riwayat(
    sesi: dict,
    role: str,
    konten: str,
    chat_id: int | None = None,
    info: dict | None = None,
    user_id: int | None = None,
) -> None:
    sesi["riwayat"].append({"role": role, "content": konten})

    if len(sesi["riwayat"]) > MAKS_PESAN_RIWAYAT:
        sesi["riwayat"] = sesi["riwayat"][-MAKS_PESAN_RIWAYAT:]

    total = sum(len(p["content"]) for p in sesi["riwayat"])
    while total > MAKS_KARAKTER_RIWAYAT and len(sesi["riwayat"]) > 2:
        total -= len(sesi["riwayat"].pop(0)["content"])

    if chat_id is None:
        return

    try:
        RIWAYAT.catat(
            chat_id,
            role,
            konten,
            akses=sesi.get("akses") or "user",
            user_id=user_id,
            info=info,
        )
    except Exception:
        log.warning("Gagal menyimpan riwayat chat %s", chat_id, exc_info=True)


# ================== INDIKATOR MENGETIK ==================

class _Mengetik:
    """Kirim status 'typing' berkala selama model berpikir."""

    def __init__(self, chat_id: int, jeda: int = 4):
        self.chat_id = chat_id
        self.jeda = jeda
        self._stop = threading.Event()
        self._thread = None

    def __enter__(self):
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *args):
        self._stop.set()

    def _loop(self):
        while not self._stop.is_set():
            try:
                tg_bot.send_chat_action(self.chat_id, "typing")
            except Exception:
                return
            self._stop.wait(self.jeda)


# ================== PENGIRIMAN ==================

def _kirim_ai(chat_id: int, teks_markdown: str, markup=None) -> None:
    html = ke_telegram_html(teks_markdown)
    bagian = potong_html(html) or ["(jawaban kosong)"]

    for i, potongan in enumerate(bagian):
        terakhir = i == len(bagian) - 1
        kirim_markup = markup if terakhir else None
        try:
            tg_bot.send_message(
                chat_id,
                potongan,
                parse_mode="HTML",
                reply_markup=kirim_markup,
                disable_web_page_preview=True,
            )
        except Exception:
            # Kalau Telegram menolak HTML-nya, kirim sebagai teks polos
            tg_bot.send_message(
                chat_id,
                strip_html(potongan),
                reply_markup=kirim_markup,
                disable_web_page_preview=True,
            )


def _catatan_sumber(sumber: list[str]) -> str:
    """Baris kecil penanda bahwa jawaban memakai pencarian web."""
    if not sumber:
        return ""
    tampil = " · ".join(sumber[:4])
    return f"\n\n<i>{tampil}</i>"


def _user_id(message) -> int | None:
    """ID user pengirim, aman kalau from_user tidak ada (misal channel post)."""
    return getattr(getattr(message, "from_user", None), "id", None)


def _akses(user_id: int | None) -> str:
    """Label tingkat akses, dipakai untuk memisahkan konteks admin & user."""
    return "admin" if apakah_admin(user_id) else "user"


def _info_chat(message) -> dict:
    """Metadata ringkas untuk ditulis ke database riwayat."""
    chat = getattr(message, "chat", None)
    from_user = getattr(message, "from_user", None)

    tipe = getattr(chat, "type", "") or ""
    # Di chat pribadi judul chat kosong; pakai nama pengirim supaya panel admin
    # menampilkan sesuatu yang bisa dikenali.
    nama = getattr(chat, "title", "") or ""
    if not nama:
        nama = getattr(from_user, "full_name", "") or getattr(
            from_user, "first_name", ""
        ) or ""

    return {
        "nama": nama,
        "username": getattr(chat, "username", "")
        or getattr(from_user, "username", "")
        or "",
        "tipe": tipe,
    }


def _jawab(
    chat_id: int,
    pertanyaan: str,
    tampilkan_judul: bool = True,
    user_id: int | None = None,
    info: dict | None = None,
    media: dict | None = None,
) -> None:
    if not tersedia():
        tg_bot.send_message(
            chat_id,
            "⚙️ <b>AI Assistant belum aktif</b>\n\n"
            "Isi <code>AI_API_KEY</code> di file <code>.env</code> lalu restart bot.",
            parse_mode="HTML",
            reply_markup=markup_kembali_menu_utama(),
        )
        return

    admin = apakah_admin(user_id)

    # AI adalah fitur paling mahal (token berbayar). Admin tidak dibatasi supaya
    # tetap bisa menguji; pengguna biasa dibatasi per menit.
    if not admin:
        try:
            batas_laju.cek(user_id, "ai")
        except batas_laju.BatasTerlampaui as e:
            tg_bot.send_message(
                chat_id,
                "⏳ <b>Batas tercapai</b>\n\n"
                f"{e.pesan}\n\n"
                f"<i>Sisa waktu tunggu sekitar {e.detik} detik.</i>",
                parse_mode="HTML",
                reply_markup=markup_ai(),
            )
            return

    sesi = _sesi(chat_id, _akses(user_id))
    konteks = aksi.Konteks(chat_id=chat_id, user_id=user_id, media=media)

    # Kunci per chat: riwayat dibaca & ditulis di dalam lock supaya tidak tabrakan
    with _lock_chat(chat_id):
        pesan = [{"role": "system", "content": system_prompt(admin=admin)}]
        pesan += sesi["riwayat"]
        pesan.append({"role": "user", "content": pertanyaan})

        try:
            with _Mengetik(chat_id):
                hasil = tanya(chat_id, pesan, admin=admin, konteks=konteks)
        except AIError as e:
            tg_bot.send_message(
                chat_id,
                "⚠️ <b>AI tidak bisa menjawab sekarang</b>\n\n"
                f"{escape_html(str(e))}",
                parse_mode="HTML",
                reply_markup=markup_ai(),
            )
            return

        _tambah_riwayat(
            sesi, "user", pertanyaan, chat_id=chat_id, info=info, user_id=user_id
        )
        _tambah_riwayat(
            sesi, "assistant", hasil["teks"], chat_id=chat_id, info=info,
            user_id=user_id,
        )
        AI_SESSIONS.set(chat_id, sesi)

    tail = _catatan_sumber(hasil.get("sumber") or [])

    if tampilkan_judul:
        _kirim_ai(chat_id, f"{SIMBOL} {hasil['teks']}{tail}", markup=markup_ai())
    else:
        _kirim_ai(chat_id, f"{hasil['teks']}{tail}", markup=markup_ai())


# ================== HANDLER ==================

@tg_bot.message_handler(commands=["ai"])
@aman_handler
def masuk_mode_ai(message):
    """/ai untuk masuk mode asisten, atau /ai <pertanyaan> untuk tanya langsung."""
    chat_id = message.chat.id

    if not tersedia():
        tg_bot.send_message(
            chat_id,
            "⚙️ <b>AI Assistant belum aktif</b>\n\n"
            "Isi <code>AI_API_KEY</code> di file <code>.env</code> lalu restart bot.",
            parse_mode="HTML",
            reply_markup=markup_kembali_menu_utama(),
        )
        return

    bagian = (message.text or "").split(maxsplit=1)
    pertanyaan = bagian[1].strip() if len(bagian) > 1 else ""

    _sesi(chat_id, _akses(_user_id(message)))

    if not pertanyaan:
        tg_bot.send_message(
            chat_id,
            SAPANAN_AWAL,
            parse_mode="HTML",
            reply_markup=markup_ai(),
        )
        return

    _jawab(
        chat_id,
        pertanyaan,
        user_id=_user_id(message),
        info=_info_chat(message),
    )


@tg_bot.callback_query_handler(func=lambda call: call.data == "menu_ai")
@aman_handler
def buka_ai_dari_menu(call):
    chat_id = call.message.chat.id
    tg_bot.answer_callback_query(call.id)

    if not tersedia():
        tg_bot.edit_message_text(
            "⚙️ <b>AI Assistant belum aktif</b>\n\n"
            "Isi <code>AI_API_KEY</code> di file <code>.env</code> lalu restart bot.",
            chat_id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=markup_kembali_menu_utama(),
        )
        return

    _sesi(chat_id, _akses(getattr(call.from_user, "id", None)))
    tg_bot.edit_message_text(
        SAPANAN_AWAL,
        chat_id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup_ai(),
    )


@tg_bot.callback_query_handler(func=lambda call: call.data == "ai_reset")
@aman_handler
def reset_obrolan(call):
    _reset(call.message.chat.id)
    tg_bot.answer_callback_query(call.id, "🧹 Riwayat obrolan dihapus.")


@tg_bot.callback_query_handler(func=lambda call: call.data == "ai_keluar")
@aman_handler
def keluar_mode_ai(call):
    AI_SESSIONS.clear(call.message.chat.id)
    tg_bot.answer_callback_query(call.id, "Keluar dari mode AI.")
    tg_bot.edit_message_text(
        "✅ <b>Mode AI dinonaktifkan.</b>\n\n"
        "Bot kembali ke mode normal. Ketik /ai kalau mau lanjut ngobrol lagi.",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup_ai_tertutup(),
    )


@tg_bot.callback_query_handler(func=lambda call: call.data == "ai_tanya")
@aman_handler
def petunjuk_tanya(call):
    tg_bot.answer_callback_query(
        call.id,
        "Ketik pertanyaanmu langsung di chat ini 🙂",
        show_alert=True,
    )


def _layak_diteruskan(teks: str) -> bool:
    """Jangan bajak pesan berisi link media, biar handler downloader tetap jalan."""
    if not teks or teks.startswith("/"):
        return False
    return not POLA_LINK.search(teks)


# ================== MEDIA UNTUK AKSI ==================

def _media_dari(message) -> dict | None:
    """Foto atau dokumen gambar pada pesan ini, dalam bentuk ringkas."""
    foto = getattr(message, "photo", None)
    if foto:
        terbesar = foto[-1]
        return {
            "jenis": "foto",
            "file_id": terbesar.file_id,
            "ukuran": getattr(terbesar, "file_size", 0) or 0,
        }

    dokumen = getattr(message, "document", None)
    if dokumen and str(getattr(dokumen, "mime_type", "") or "").startswith("image/"):
        return {
            "jenis": "foto",
            "file_id": dokumen.file_id,
            "ukuran": getattr(dokumen, "file_size", 0) or 0,
        }

    return None


def _caption(message) -> str:
    return (getattr(message, "caption", None) or "").strip()


def _perintah_ai(teks: str) -> bool:
    """True kalau caption berupa /ai, /ai@bot, atau '/ai <pertanyaan>'."""
    rendah = teks.lower()
    if not rendah.startswith("/ai"):
        return False
    sisa = rendah[3:]
    return not sisa or sisa[0].isspace() or sisa.startswith("@")


def _stiker_menunggu_media(chat_id: int) -> bool:
    """True kalau alur stiker sedang menunggu media dari pengguna.

    Sesi stiker tidak langsung dihapus setelah hasil dibuat (tombol PNG/MP4
    masih memakai ``path``), jadi keberadaan sesi saja bukan alasan untuk
    mengalah. Yang menang hanya saat pengguna baru memilih alur dan medianya
    belum diterima.
    """
    from bot.handlers.sticker import STIKER_SESSIONS

    sesi = STIKER_SESSIONS.get(chat_id)
    return bool(sesi) and not sesi.get("path")


def direbut_ai(message) -> bool:
    """True kalau foto ber-caption harus diproses AI, bukan auto hapus background.

    Foto tanpa caption tetap jatuh ke handler otomatis. Alur stiker yang baru
    dibuka juga diprioritaskan: handler AI didaftarkan lebih dulu, jadi tanpa
    cek ini foto untuk stiker akan tertelan AI. Mode /play tidak perlu dicek
    karena media sudah menutupnya di ``handlers/sesi.py`` sebelum handler ini
    berjalan.
    """
    if not tersedia():
        return False

    teks = _caption(message)
    if not teks or not _media_dari(message):
        return False

    # Caption perintah lain (mis. /play) tetap milik handler-nya sendiri
    if teks.startswith("/") and not _perintah_ai(teks):
        return False

    if _stiker_menunggu_media(message.chat.id):
        return False

    return _aktif(message.chat.id) or _perintah_ai(teks)


def _pertanyaan_media(teks: str) -> str:
    """Buang prefix /ai pada caption, sisakan pertanyaannya."""
    if not _perintah_ai(teks):
        return teks

    bagian = teks.split(maxsplit=1)
    if len(bagian) < 2:
        return ""
    return bagian[1].strip()


@tg_bot.message_handler(content_types=["photo", "document"], func=direbut_ai)
@aman_handler
def tangkap_media_ai(message):
    """Foto ber-caption saat mode AI aktif: caption jadi instruksi, foto jadi bahan."""
    chat_id = message.chat.id
    media = _media_dari(message)
    if not media:
        return

    user_id = _user_id(message)
    aksi.simpan_media(
        chat_id, media["jenis"], media["file_id"], media["ukuran"], user_id=user_id
    )
    _sesi(chat_id, _akses(user_id))

    pertanyaan = _pertanyaan_media(_caption(message))
    if not pertanyaan:
        tg_bot.send_message(
            chat_id,
            "📎 Foto diterima. Mau diapakan?\n"
            "<i>Contoh: hapus background-nya, atau buatkan stiker.</i>",
            parse_mode="HTML",
            reply_markup=markup_ai(),
        )
        return

    _jawab(
        chat_id,
        pertanyaan,
        tampilkan_judul=False,
        user_id=user_id,
        info=_info_chat(message),
        media=media,
    )


@tg_bot.message_handler(
    func=lambda m: _aktif(m.chat.id)
    and _layak_diteruskan(m.text or "")
    and not play_mode.aktif(m.chat.id),
    content_types=["text"],
)
@aman_handler
def tangkap_pertanyaan_ai(message):
    """Teks biasa saat mode AI aktif diarahkan ke asisten."""
    teks = (message.text or "").strip()

    if not teks:
        return

    if teks.lower() in ("keluar ai", "exit ai", "stop ai"):
        AI_SESSIONS.clear(message.chat.id)
        tg_bot.send_message(
            message.chat.id,
            "✅ Mode AI dinonaktifkan.",
            reply_markup=markup_ai_tertutup(),
        )
        return

    if teks.lower() in ("reset", "mulai ulang", "clear"):
        _reset(message.chat.id)
        tg_bot.send_message(
            message.chat.id,
            "🧹 Riwayat obrolan dihapus. Silakan mulai pertanyaan baru.",
            reply_markup=markup_ai(),
        )
        return

    _jawab(
        message.chat.id,
        teks,
        tampilkan_judul=False,
        user_id=_user_id(message),
        info=_info_chat(message),
        media=aksi.ambil_media(message.chat.id, _user_id(message)),
    )


@tg_bot.message_handler(commands=["ai_off"])
@aman_handler
def matikan_mode_ai(message):
    AI_SESSIONS.clear(message.chat.id)
    tg_bot.send_message(
        message.chat.id,
        "✅ <b>Mode AI dinonaktifkan.</b>\n\nBot kembali ke mode normal.",
        parse_mode="HTML",
        reply_markup=markup_kembali_menu_utama(),
    )


@tg_bot.message_handler(commands=["ai_status"])
@aman_handler
def status_ai(message):
    chat_id = message.chat.id
    siap = tersedia()
    mode = "aktif" if _aktif(chat_id) else "nonaktif"
    web = "aktif 🔎" if web_aktif() else "nonaktif"
    admin = apakah_admin(_user_id(message))

    baris = [
        f"{SIMBOL} <b>Status AI Assistant</b>",
        "",
        f"• Koneksi: {'<b>siap</b>' if siap else '<b>belum dikonfigurasi</b>'}",
        f"• Model: <code>{model_aktif()}</code>",
        f"• Web search: {web}",
        f"• Aksi bot: {'aktif ⚙️' if aksi_aktif() else 'nonaktif'}",
        f"• Mode chat: {mode}",
        f"• Akses: {'<b>admin</b>' if admin else 'pengguna'}",
    ]

    if admin:
        baris += [
            "",
            "<b>Batas admin</b>",
            f"• Putaran riset: {MAKS_PUTARAN_TOOL_ADMIN}",
            f"• Hasil web per cari: {HASIL_WEB_ADMIN}",
            f"• Isi halaman: {MAKS_KARAKTER_HALAMAN_ADMIN} karakter",
            f"• Tool aksi bot: {', '.join(aksi.NAMA_TOOL)}",
            f"• Tool diagnostik: {', '.join(TOOL_ADMIN_NAMA)}",
        ]

    tg_bot.send_message(
        chat_id,
        "\n".join(baris),
        parse_mode="HTML",
        reply_markup=markup_ai() if siap else markup_kembali_menu_utama(),
    )


@tg_bot.message_handler(
    func=lambda m: (m.text or "").strip().lower() in ("ai", "chrostt ai")
    and not play_mode.aktif(m.chat.id)
)
@aman_handler
def sapa_ai(message):
    if _aktif(message.chat.id):
        return
    if not tersedia():
        return
    tg_bot.send_message(
        message.chat.id,
        SAPANAN_SINGKAT,
        parse_mode="HTML",
        reply_markup=markup_ai(),
    )
