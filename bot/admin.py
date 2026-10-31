"""Utilitas admin: cek akses, pencatatan pengguna, dan format pesan admin."""

import logging
import time

import config
from bot import tg_bot

log = logging.getLogger("chrosttbot.admin")

# user_id -> info dasar, dipakai untuk panel pengguna & broadcast
_pengguna: dict[int, dict] = {}
_listener_aktif = False


# ================== IDENTITAS ==================

def admin_ids() -> tuple[int, ...]:
    return config.ADMIN_IDS


def ada_admin() -> bool:
    return bool(config.ADMIN_IDS)


def apakah_admin(user_id) -> bool:
    """True kalau user_id ada di ADMIN_IDS (.env)."""
    if not user_id:
        return False
    try:
        return int(user_id) in config.ADMIN_IDS_SET
    except (TypeError, ValueError):
        return False


def pesan_dari_admin(message) -> bool:
    """Admin check untuk Message. Memakai from_user, bukan chat id."""
    return apakah_admin(getattr(getattr(message, "from_user", None), "id", None))


def callback_dari_admin(call) -> bool:
    return apakah_admin(getattr(getattr(call, "from_user", None), "id", None))


def peran(user_id) -> str:
    return "admin" if apakah_admin(user_id) else "pengguna"


# ================== PENGGUNA ==================

def catat_pengguna(message) -> None:
    """Simpan info user yang pernah berinteraksi, untuk panel & broadcast."""
    from_user = getattr(message, "from_user", None)
    if not from_user or getattr(from_user, "is_bot", False):
        return

    chat = getattr(message, "chat", None)
    # Hanya chat pribadi; broadcast ke grup berisiko spam
    if chat is not None and getattr(chat, "type", "private") != "private":
        return

    _pengguna[from_user.id] = {
        "id": from_user.id,
        "nama": getattr(from_user, "full_name", "") or getattr(from_user, "first_name", "") or "",
        "username": getattr(from_user, "username", "") or "",
        "terakhir": time.time(),
    }


def daftar_pengguna() -> list[dict]:
    return sorted(_pengguna.values(), key=lambda u: u["terakhir"], reverse=True)


def jumlah_pengguna() -> int:
    return len(_pengguna)


def pasang_listener() -> None:
    """Daftarkan listener global untuk mencatat pengguna yang aktif."""
    global _listener_aktif
    if _listener_aktif:
        return

    def _listener(update_list):
        for pesan in update_list:
            try:
                catat_pengguna(pesan)
            except Exception:
                log.debug("Gagal mencatat pengguna", exc_info=True)

    tg_bot.set_update_listener(_listener)
    _listener_aktif = True


# ================== FORMAT ==================

def teks_admin(user_id) -> str:
    status = "✅ ya" if apakah_admin(user_id) else "❌ tidak"
    daftar = ", ".join(str(i) for i in config.ADMIN_IDS) or "(kosong)"
    return (
        "🛡️ <b>PANEL ADMIN</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"• ID kamu: <code>{user_id}</code>\n"
        f"• Status admin: {status}\n"
        f"• Admin terdaftar: <b>{len(config.ADMIN_IDS)}</b>\n\n"
        "<b>ADMIN_IDS di .env</b>\n"
        f"<code>{daftar}</code>\n\n"
        "<i>Ubah ADMIN_IDS lalu restart bot untuk memperbarui daftar.</i>"
    )
