import time

from bot import tg_bot
from bot.admin import (
    admin_ids,
    apakah_admin,
    daftar_pengguna,
    jumlah_pengguna,
    pesan_dari_admin,
    teks_admin,
)
from bot.keyboards import (
    markup_admin,
    markup_batal_broadcast,
    markup_konfirmasi_broadcast,
    markup_kembali_menu_utama,
)
from bot.services.ai import model_aktif, tersedia

WAKTU_MULAI = time.time()

# user_id admin -> draft broadcast yang menunggu konfirmasi
_draft_broadcast: dict[int, dict] = {}
DRAFT_TTL = 600  # 10 menit


def _draft_valid(user_id: int) -> dict | None:
    """Ambil draft broadcast kalau masih dalam masa berlaku."""
    draft = _draft_broadcast.get(user_id)
    if not draft:
        return None
    if time.time() - draft.get("dibuat", 0) > DRAFT_TTL:
        _draft_broadcast.pop(user_id, None)
        return None
    return draft


def _durasi(detik: float) -> str:
    detik = int(detik)
    jam, sisa = divmod(detik, 3600)
    menit, detik = divmod(sisa, 60)
    if jam:
        return f"{jam}j {menit}m {detik}d"
    if menit:
        return f"{menit}m {detik}d"
    return f"{detik}d"


def _admin_call(call) -> bool:
    """Validasi admin untuk callback, sekaligus balas alert kalau ditolak."""
    if apakah_admin(getattr(getattr(call, "from_user", None), "id", None)):
        return True
    tg_bot.answer_callback_query(call.id, "⛔ Hanya untuk admin.", show_alert=True)
    return False


# ================== ID ==================

@tg_bot.message_handler(commands=["id"])
def tampilkan_id(message):
    """Siapa pun boleh lihat ID sendiri, supaya mudah mengisi ADMIN_IDS."""
    from_user = message.from_user
    user_id = getattr(from_user, "id", 0)
    username = getattr(from_user, "username", None)
    nama = getattr(from_user, "full_name", "") or ""

    baris = [
        "🆔 <b>INFO ID TELEGRAM</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"• ID: <code>{user_id}</code>",
        f"• Nama: {nama}",
    ]
    if username:
        baris.append(f"• Username: @{username}")
    baris.append(f"• Chat ID: <code>{message.chat.id}</code>")
    baris.append("")
    baris.append(f"• Admin bot: {'✅ ya' if apakah_admin(user_id) else '❌ tidak'}")
    baris.append("")
    baris.append("<i>Salin ID di atas ke ADMIN_IDS pada file .env, lalu restart bot.</i>")

    tg_bot.send_message(
        message.chat.id,
        "\n".join(baris),
        parse_mode="HTML",
        reply_markup=markup_kembali_menu_utama(),
    )


# ================== PANEL ==================

@tg_bot.message_handler(commands=["admin"])
def panel_admin(message):
    """Panel admin: hanya untuk ID yang terdaftar di ADMIN_IDS."""
    if not pesan_dari_admin(message):
        tg_bot.send_message(
            message.chat.id,
            "⛔ <b>Akses ditolak</b>\n\n"
            "Perintah ini hanya untuk admin bot.\n"
            f"ID kamu: <code>{message.from_user.id}</code>\n\n"
            "<i>Ketik /id untuk melihat ID, lalu tambahkan ke ADMIN_IDS di .env.</i>",
            parse_mode="HTML",
        )
        return

    tg_bot.send_message(
        message.chat.id,
        teks_admin(message.from_user.id),
        parse_mode="HTML",
        reply_markup=markup_admin(),
    )


@tg_bot.callback_query_handler(func=lambda call: call.data == "admin_panel")
def panel_admin_callback(call):
    if not _admin_call(call):
        return

    tg_bot.answer_callback_query(call.id)
    tg_bot.edit_message_text(
        teks_admin(call.from_user.id),
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup_admin(),
    )


@tg_bot.callback_query_handler(func=lambda call: call.data == "admin_stats")
def statistik_bot(call):
    if not _admin_call(call):
        return

    tg_bot.answer_callback_query(call.id)

    teks = (
        "📊 <b>STATISTIK BOT</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"• Uptime: <b>{_durasi(time.time() - WAKTU_MULAI)}</b>\n"
        f"• Pengguna tercatat: <b>{jumlah_pengguna()}</b>\n"
        f"• Admin: <b>{len(admin_ids())}</b>\n"
        f"• AI: <b>{'siap' if tersedia() else 'nonaktif'}</b>\n"
        f"• Model: <code>{model_aktif()}</code>"
    )

    tg_bot.edit_message_text(
        teks,
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup_admin(),
    )


@tg_bot.callback_query_handler(func=lambda call: call.data == "admin_users")
def daftar_user(call):
    if not _admin_call(call):
        return

    tg_bot.answer_callback_query(call.id)

    pengguna = daftar_pengguna()
    if not pengguna:
        isi = "<i>Belum ada pengguna yang tercatat sejak bot dijalankan.</i>"
    else:
        baris = []
        for i, u in enumerate(pengguna[:20], 1):
            username = f" @{u['username']}" if u["username"] else ""
            baris.append(f"{i}. {u['nama'][:28]}{username}\n    <code>{u['id']}</code>")
        isi = "\n".join(baris)
        if len(pengguna) > 20:
            isi += f"\n\n<i>… dan {len(pengguna) - 20} pengguna lain.</i>"

    tg_bot.edit_message_text(
        "👥 <b>PENGGUNA BOT</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{isi}",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup_admin(),
    )


# ================== BROADCAST ==================

@tg_bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast")
def mulai_broadcast(call):
    if not _admin_call(call):
        return

    tg_bot.answer_callback_query(call.id)
    tg_bot.send_message(
        call.message.chat.id,
        "📢 <b>BROADCAST</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Kirim pesan yang mau disiarkan ke semua pengguna bot.\n\n"
        "• Format HTML Telegram didukung (<code>&lt;b&gt;</code>, <code>&lt;i&gt;</code>, dst.)\n"
        "• Satu pesan saja, tanpa media\n"
        "• Kamu akan diminta konfirmasi sebelum dikirim\n\n"
        f"<i>Penerima saat ini: {jumlah_pengguna()} pengguna.</i>",
        parse_mode="HTML",
        reply_markup=markup_batal_broadcast(),
    )

    # Pesan berikutnya dari admin ini dianggap isi broadcast
    tg_bot.register_next_step_handler_by_chat_id(call.message.chat.id, _terima_broadcast)


def _terima_broadcast(message):
    if not pesan_dari_admin(message):
        return

    teks = (message.text or "").strip()
    if not teks:
        tg_bot.send_message(
            message.chat.id,
            "❌ Broadcast kosong, dibatalkan.",
            reply_markup=markup_admin(),
        )
        return

    if len(teks) > 4000:
        tg_bot.send_message(
            message.chat.id,
            "❌ Pesan terlalu panjang (maks 4000 karakter). Broadcast dibatalkan.",
            reply_markup=markup_admin(),
        )
        return

    _draft_broadcast[message.from_user.id] = {"teks": teks, "dibuat": time.time()}

    tg_bot.send_message(
        message.chat.id,
        "👀 <b>PREVIEW BROADCAST</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{teks}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Akan dikirim ke {jumlah_pengguna()} pengguna.</i>",
        parse_mode="HTML",
        reply_markup=markup_konfirmasi_broadcast(),
    )


@tg_bot.callback_query_handler(func=lambda call: call.data == "admin_kirim")
def kirim_broadcast(call):
    if not _admin_call(call):
        return

    draft = _draft_valid(call.from_user.id)
    if not draft:
        tg_bot.answer_callback_query(
            call.id, "Draft tidak ada atau sudah kedaluwarsa.", show_alert=True
        )
        return

    _draft_broadcast.pop(call.from_user.id, None)
    tg_bot.answer_callback_query(call.id, "📤 Mengirim...")

    penerima = daftar_pengguna()
    if not penerima:
        tg_bot.send_message(
            call.message.chat.id,
            "ℹ️ Belum ada pengguna yang tercatat.",
            reply_markup=markup_admin(),
        )
        return

    sukses, gagal = 0, 0
    for u in penerima:
        try:
            tg_bot.send_message(u["id"], draft["teks"], parse_mode="HTML")
            sukses += 1
        except Exception:
            gagal += 1
        time.sleep(0.05)  # hindari rate limit Telegram (~30 pesan/detik)

    tg_bot.send_message(
        call.message.chat.id,
        "✅ <b>BROADCAST SELESAI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"• Terkirim: <b>{sukses}</b>\n"
        f"• Gagal: <b>{gagal}</b>",
        parse_mode="HTML",
        reply_markup=markup_admin(),
    )


@tg_bot.callback_query_handler(func=lambda call: call.data == "admin_batal")
def batal_broadcast(call):
    _draft_broadcast.pop(call.from_user.id, None)
    tg_bot.answer_callback_query(call.id, "Broadcast dibatalkan.")

    if apakah_admin(getattr(getattr(call, "from_user", None), "id", None)):
        tg_bot.edit_message_text(
            teks_admin(call.from_user.id),
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=markup_admin(),
        )
    else:
        tg_bot.edit_message_text(
            "❌ Dibatalkan.",
            call.message.chat.id,
            call.message.message_id,
        )
