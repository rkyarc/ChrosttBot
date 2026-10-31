import re
import threading

from bot import tg_bot
from bot.admin import apakah_admin
from bot.ai_prompt import (
    MAKS_KARAKTER_RIWAYAT,
    MAKS_PESAN_RIWAYAT,
    SAPANAN_AWAL,
    SAPANAN_SINGKAT,
    system_prompt,
)
from bot.keyboards import markup_ai, markup_ai_tertutup, markup_kembali_menu_utama
from bot.services.ai import AIError, model_aktif, tanya, tersedia, web_aktif
from bot.sessions import SessionStore
from bot.utils import ke_telegram_html, potong_html, strip_html

# chat_id -> {"riwayat": [{"role", "content"}, ...]}
AI_SESSIONS = SessionStore(ttl=3600, max_entries=500)

# pyTelegramBotAPI memproses update paralel; kunci per chat supaya riwayat tidak tabrakan
_LOCKS: dict[int, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock_chat(chat_id: int) -> threading.Lock:
    with _LOCKS_GUARD:
        lock = _LOCKS.get(chat_id)
        if lock is None:
            lock = threading.Lock()
            _LOCKS[chat_id] = lock
        return lock


SIMBOL = "✦"

# Pesan berisi link media tetap diproses downloader, bukan AI
POLA_LINK = re.compile(
    r"https?://\S*(?:instagram\.com|instagr\.am|tiktok\.com|facebook\.com|fb\.watch"
    r"|youtube\.com|youtu\.be|youtu\.?be)",
    re.IGNORECASE,
)


# ================== STATE ==================

def _sesi(chat_id: int) -> dict:
    sesi = AI_SESSIONS.get(chat_id)
    if sesi:
        # Set ulang supaya TTL ikut diperpanjang selama user aktif
        AI_SESSIONS.set(chat_id, sesi)
        return sesi

    sesi = {"riwayat": []}
    AI_SESSIONS.set(chat_id, sesi)
    return sesi


def _aktif(chat_id: int) -> bool:
    return AI_SESSIONS.get(chat_id) is not None


def _reset(chat_id: int) -> None:
    sesi = _sesi(chat_id)
    sesi["riwayat"] = []
    AI_SESSIONS.set(chat_id, sesi)


def _tambah_riwayat(sesi: dict, role: str, konten: str) -> None:
    sesi["riwayat"].append({"role": role, "content": konten})

    if len(sesi["riwayat"]) > MAKS_PESAN_RIWAYAT:
        sesi["riwayat"] = sesi["riwayat"][-MAKS_PESAN_RIWAYAT:]

    total = sum(len(p["content"]) for p in sesi["riwayat"])
    while total > MAKS_KARAKTER_RIWAYAT and len(sesi["riwayat"]) > 2:
        total -= len(sesi["riwayat"].pop(0)["content"])


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


def _jawab(
    chat_id: int,
    pertanyaan: str,
    tampilkan_judul: bool = True,
    user_id: int | None = None,
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

    sesi = _sesi(chat_id)

    # Kunci per chat: riwayat dibaca & ditulis di dalam lock supaya tidak tabrakan
    with _lock_chat(chat_id):
        pesan = [{"role": "system", "content": system_prompt()}]
        pesan += sesi["riwayat"]
        pesan.append({"role": "user", "content": pertanyaan})

        try:
            with _Mengetik(chat_id):
                hasil = tanya(chat_id, pesan, admin=apakah_admin(user_id))
        except AIError as e:
            tg_bot.send_message(
                chat_id,
                f"⚠️ <b>AI tidak bisa menjawab sekarang</b>\n\n{e}",
                parse_mode="HTML",
                reply_markup=markup_ai(),
            )
            return

        _tambah_riwayat(sesi, "user", pertanyaan)
        _tambah_riwayat(sesi, "assistant", hasil["teks"])
        AI_SESSIONS.set(chat_id, sesi)

    tail = _catatan_sumber(hasil.get("sumber") or [])

    if tampilkan_judul:
        _kirim_ai(chat_id, f"{SIMBOL} {hasil['teks']}{tail}", markup=markup_ai())
    else:
        _kirim_ai(chat_id, f"{hasil['teks']}{tail}", markup=markup_ai())


# ================== HANDLER ==================

@tg_bot.message_handler(commands=["ai"])
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

    _sesi(chat_id)

    if not pertanyaan:
        tg_bot.send_message(
            chat_id,
            SAPANAN_AWAL,
            parse_mode="HTML",
            reply_markup=markup_ai(),
        )
        return

    _jawab(chat_id, pertanyaan, user_id=_user_id(message))


@tg_bot.callback_query_handler(func=lambda call: call.data == "menu_ai")
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

    _sesi(chat_id)
    tg_bot.edit_message_text(
        SAPANAN_AWAL,
        chat_id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup_ai(),
    )


@tg_bot.callback_query_handler(func=lambda call: call.data == "ai_reset")
def reset_obrolan(call):
    _reset(call.message.chat.id)
    tg_bot.answer_callback_query(call.id, "🧹 Riwayat obrolan dihapus.")


@tg_bot.callback_query_handler(func=lambda call: call.data == "ai_keluar")
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


@tg_bot.message_handler(
    func=lambda m: _aktif(m.chat.id) and _layak_diteruskan(m.text or ""),
    content_types=["text"],
)
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

    _jawab(message.chat.id, teks, tampilkan_judul=False, user_id=_user_id(message))


@tg_bot.message_handler(commands=["ai_off"])
def matikan_mode_ai(message):
    AI_SESSIONS.clear(message.chat.id)
    tg_bot.send_message(
        message.chat.id,
        "✅ <b>Mode AI dinonaktifkan.</b>\n\nBot kembali ke mode normal.",
        parse_mode="HTML",
        reply_markup=markup_kembali_menu_utama(),
    )


@tg_bot.message_handler(commands=["ai_status"])
def status_ai(message):
    chat_id = message.chat.id
    siap = tersedia()
    mode = "aktif" if _aktif(chat_id) else "nonaktif"
    web = "aktif 🔎" if web_aktif() else "nonaktif"

    tg_bot.send_message(
        chat_id,
        f"{SIMBOL} <b>Status AI Assistant</b>\n\n"
        f"• Koneksi: {'<b>siap</b>' if siap else '<b>belum dikonfigurasi</b>'}\n"
        f"• Model: <code>{model_aktif()}</code>\n"
        f"• Web search: {web}\n"
        f"• Mode chat: {mode}",
        parse_mode="HTML",
        reply_markup=markup_ai() if siap else markup_kembali_menu_utama(),
    )


@tg_bot.message_handler(func=lambda m: (m.text or "").strip().lower() in ("ai", "chrostt ai"))
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
