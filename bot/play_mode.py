"""Mode tunggu judul untuk fitur /play (YouTube).

Satu tempat untuk seluruh siklus mode:

1. ``minta_judul()`` mengirim prompt ForceReply dan mencatat ID pesannya.
2. ``sedang_menunggu()`` dipakai handler teks untuk mengetahui chat mana yang
   sedang menunggu judul, dan apakah pengirimnya berhak.
3. ``tutup()`` menghapus prompt sekaligus statusnya.

Kenapa prompt harus dihapus: ForceReply menempel pada pesan prompt. Selama
pesan itu ada dan menjadi pesan terakhir bot, Telegram tetap membuka kolom
balas walau pengguna sudah keluar-masuk chat. Menghapus prompt membuat
status tersebut bersih dan tidak muncul lagi saat chat dibuka kembali.

ID prompt juga dicatat di SQLite. Jadi kalau bot restart saat mode masih
aktif, prompt lama tetap bisa dihapus dan tidak menggantung di chat.
"""

import logging

from telebot import types

from bot import tg_bot, telegram_io as tg_io
from bot.riwayat import RIWAYAT
from bot.sessions import SessionStore

log = logging.getLogger("chrosttbot.play")

# chat_id -> {"user_id": int | None, "prompt_id": int | None}
_STATE = SessionStore(ttl=600, max_entries=200)

# Prefix kunci state di database
_PREFIX_DB = "play_prompt:"

PETUNJUK = "Judul lagu atau video"

_TEKS_PROMPT = (
    "<b>PLAY</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "Balas pesan ini dengan judul lagu atau video yang mau dicari.\n"
    "Tidak perlu mengetik <code>/play</code> lagi.\n\n"
    "<b>Contoh</b>\n"
    "<code>me at the zoo</code>\n"
    "<code>lofi hip hop</code>\n"
    "<code>tutorial python</code>\n\n"
    "<i>Ketik <code>batal</code> atau jalankan perintah lain untuk "
    "keluar dari mode ini.</i>"
)


def sedang_menunggu(chat_id: int, user_id: int | None = None) -> bool:
    """True kalau chat ini sedang menunggu judul dari pengguna tersebut."""
    state = _STATE.get(chat_id)
    if not state:
        return False

    pemilik = state.get("user_id")
    # Tanpa info user (mis. chat pribadi lama) mode tetap diterima
    return pemilik is None or user_id is None or pemilik == user_id


def aktif(chat_id: int) -> bool:
    return _STATE.get(chat_id) is not None


def minta_judul(
    chat_id: int,
    user_id: int | None = None,
    balas_pesan_id: int | None = None,
) -> None:
    """Kirim prompt ForceReply dan tandai chat sedang menunggu judul.

    ``balas_pesan_id`` dipakai di grup: prompt membalas pesan /play pengguna
    supaya ForceReply-nya ``selective`` dan hanya terbuka untuk dia.
    """
    tutup(chat_id)

    balas = None
    if balas_pesan_id:
        balas = types.ReplyParameters(
            message_id=balas_pesan_id, allow_sending_without_reply=True
        )

    try:
        prompt = tg_bot.send_message(
            chat_id,
            _TEKS_PROMPT,
            parse_mode="HTML",
            reply_parameters=balas,
            reply_markup=types.ForceReply(
                selective=balas_pesan_id is not None,
                input_field_placeholder=PETUNJUK,
            ),
        )
    except Exception:
        log.warning("Gagal mengirim prompt /play di chat %s", chat_id, exc_info=True)
        return

    prompt_id = getattr(prompt, "message_id", None)

    _STATE.set(chat_id, {"user_id": user_id, "prompt_id": prompt_id})
    _simpan_prompt(chat_id, prompt_id)


def lepas_prompt(chat_id: int) -> None:
    """Hapus prompt ForceReply tetapi biarkan mode tetap menunggu.

    Dipakai setelah judul diterima: hasil pencarian menjadi pesan terakhir,
    jadi kolom balas tidak perlu menempel lagi. Pengguna masih bisa mengirim
    judul berikutnya tanpa /play selama mode belum kedaluwarsa.
    """
    state = _STATE.get(chat_id)
    if not state:
        return

    _hapus_prompt(chat_id, state.get("prompt_id"))

    state["prompt_id"] = None
    _STATE.set(chat_id, state)
    _lupakan_prompt(chat_id)


def tutup(chat_id: int) -> None:
    """Akhiri mode tunggu dan hapus prompt-nya."""
    state = _STATE.get(chat_id)
    _STATE.clear(chat_id)

    prompt_id = state.get("prompt_id") if isinstance(state, dict) else None
    if not prompt_id:
        # Mungkin tercatat di DB dari sesi sebelum restart
        prompt_id = _ambil_prompt_db(chat_id)

    _hapus_prompt(chat_id, prompt_id)
    _lupakan_prompt(chat_id)


def bersihkan_sisa() -> None:
    """Hapus prompt yang tercatat di DB tapi mode-nya sudah tidak ada.

    Dipanggil saat startup: setelah bot restart, mode di memori hilang, jadi
    prompt ForceReply lama harus dibersihkan agar kolom balas tidak muncul.
    """
    try:
        sisa = RIWAYAT.state_dengan_prefix(_PREFIX_DB)
    except Exception:
        log.debug("Tidak bisa membaca state prompt", exc_info=True)
        return

    for kunci, nilai in sisa:
        try:
            chat_id = int(kunci[len(_PREFIX_DB) :])
            prompt_id = int(nilai)
        except (TypeError, ValueError):
            RIWAYAT.hapus_state(kunci)
            continue

        if _STATE.get(chat_id) is not None:
            continue

        _hapus_prompt(chat_id, prompt_id)
        RIWAYAT.hapus_state(kunci)


def tutup_semua() -> None:
    """Akhiri semua mode yang tercatat (dipakai saat shutdown)."""
    for chat_id, state in _STATE.items():
        if isinstance(state, dict):
            _hapus_prompt(chat_id, state.get("prompt_id"))
            _lupakan_prompt(chat_id)

    for chat_id, _ in _STATE.items():
        _STATE.clear(chat_id)
        _lupakan_prompt(chat_id)


# ================== PENYIMPANAN ID PROMPT ==================

def _simpan_prompt(chat_id: int, prompt_id: int | None) -> None:
    if not prompt_id:
        return
    try:
        RIWAYAT.simpan_state(f"{_PREFIX_DB}{chat_id}", str(prompt_id))
    except Exception:
        log.debug("Gagal menyimpan state prompt", exc_info=True)


def _ambil_prompt_db(chat_id: int) -> int | None:
    try:
        nilai = RIWAYAT.ambil_state(f"{_PREFIX_DB}{chat_id}")
        return int(nilai) if nilai else None
    except Exception:
        return None


def _lupakan_prompt(chat_id: int) -> None:
    try:
        RIWAYAT.hapus_state(f"{_PREFIX_DB}{chat_id}")
    except Exception:
        log.debug("Gagal menghapus state prompt", exc_info=True)


def _hapus_prompt(chat_id: int, prompt_id: int | None) -> None:
    if not prompt_id:
        return

    # Prompt mungkin sudah dihapus pengguna atau lewat batas 48 jam
    tg_io.hapus(chat_id, prompt_id)
