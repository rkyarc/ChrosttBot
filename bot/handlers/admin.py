import re
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
    markup_konfirmasi_hapus_riwayat,
    markup_konfirmasi_hapus_semua,
    markup_kembali_menu_utama,
    markup_riwayat,
)
from bot.riwayat import RIWAYAT
from bot.services.ai import model_aktif, tersedia
from bot.utils import escape_html
from bot.decorators import aman_handler

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
    if not apakah_admin(getattr(getattr(call, "from_user", None), "id", None)):
        tg_bot.answer_callback_query(
            call.id, "⛔ Hanya untuk admin.", show_alert=True
        )
        return False

    # Panel admin memuat data sensitif (ID, riwayat). Di grup pesan panel bisa
    # dibaca semua anggota, jadi hanya boleh dibuka di chat pribadi.
    tipe = getattr(getattr(call.message, "chat", None), "type", "private")
    if tipe != "private":
        tg_bot.answer_callback_query(
            call.id,
            "🔒 Panel admin hanya bisa dibuka di chat pribadi bot.",
            show_alert=True,
        )
        return False

    return True


# ================== ID ==================

@tg_bot.message_handler(commands=["id"])
@aman_handler
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
@aman_handler
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

    # Panel memuat ID & riwayat pengguna; jangan pernah dikirim ke grup.
    if getattr(message.chat, "type", "private") != "private":
        tg_bot.send_message(
            message.chat.id,
            "🔒 <b>Panel admin hanya di chat pribadi</b>\n\n"
            "Buka chat langsung dengan bot, lalu jalankan /admin di sana.",
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
@aman_handler
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
@aman_handler
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
@aman_handler
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


# ================== RIWAYAT AI ==================

RIWAYAT_PER_HALAMAN = 5

# Callback halaman riwayat: "admin_riwayat_<angka>" saja
_POLA_HALAMAN_RIWAYAT = re.compile(r"^admin_riwayat_(\d+)$")
# Callback konfirmasi hapus satu chat: "admin_hapus_<chat_id>"
_POLA_HAPUS_RIWAYAT = re.compile(r"^admin_hapus_(-?\d+)$")


def _teks_riwayat(halaman: int = 1) -> str:
    """Teks daftar riwayat AI, dikelompokkan per halaman."""
    semua = RIWAYAT.daftar()
    stat = RIWAYAT.statistik()

    baris = [
        "🗂️ <b>RIWAYAT AI</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"• Chat tersimpan: <b>{stat['jumlah_chat']}</b>",
        f"• Total pesan: <b>{stat['jumlah_pesan']}</b>",
        f"• Ukuran database: <b>{_ukuran_stat(stat['ukuran_byte'])}</b>",
        f"• Lokasi: <code>{escape_html(_lokasi_db())}</code>",
        "",
    ]

    if not semua:
        baris.append("<i>Belum ada riwayat AI yang tersimpan.</i>")
        return "\n".join(baris)

    total_halaman = max(
        1, (len(semua) + RIWAYAT_PER_HALAMAN - 1) // RIWAYAT_PER_HALAMAN
    )
    halaman = max(1, min(halaman, total_halaman))
    mulai = (halaman - 1) * RIWAYAT_PER_HALAMAN
    potongan = semua[mulai : mulai + RIWAYAT_PER_HALAMAN]

    baris.append(
        f"<i>Menampilkan {mulai + 1}-{mulai + len(potongan)} dari "
        f"{len(semua)} chat · halaman {halaman}/{total_halaman}</i>"
    )
    baris.append("")

    for item in potongan:
        nama = (item.get("nama") or "-")[:30]
        username = f" @{item['username']}" if item.get("username") else ""
        akses = item.get("akses") or "user"
        tipe = item.get("tipe") or "-"
        kapan = _waktu_relatif(item.get("diperbarui") or 0)

        baris.append(f"• <b>{escape_html(nama)}</b>{escape_html(username)}")
        baris.append(
            f"    <code>{item['chat_id']}</code> · {escape_html(tipe)} · "
            f"{escape_html(akses)} · {item['jumlah_pesan']} pesan"
        )
        baris.append(f"    <i>Terakhir: {escape_html(kapan)}</i>")
        baris.append("")

    baris.append("<i>Tekan tombol 🗑️ untuk menghapus riwayat chat tersebut.</i>")
    return "\n".join(baris).rstrip()


def _waktu_relatif(ts: float) -> str:
    if not ts:
        return "-"
    selisih = max(0, time.time() - ts)
    if selisih < 60:
        return "baru saja"
    if selisih < 3600:
        return f"{int(selisih // 60)} menit lalu"
    if selisih < 86400:
        return f"{int(selisih // 3600)} jam lalu"
    return f"{int(selisih // 86400)} hari lalu"


def _ukuran_stat(byte: int) -> str:
    if byte < 1024:
        return f"{byte} B"
    if byte < 1048576:
        return f"{byte / 1024:.1f} KB"
    return f"{byte / 1048576:.1f} MB"


def _lokasi_db() -> str:
    from bot.riwayat import RIWAYAT as store

    return store.path


@tg_bot.callback_query_handler(func=lambda call: call.data == "admin_riwayat")
@aman_handler
def buka_riwayat(call):
    if not _admin_call(call):
        return

    tg_bot.answer_callback_query(call.id)
    semua = RIWAYAT.daftar()

    tg_bot.edit_message_text(
        _teks_riwayat(1),
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup_riwayat(semua, 1, RIWAYAT_PER_HALAMAN),
    )


@tg_bot.callback_query_handler(
    func=lambda call: bool(_POLA_HALAMAN_RIWAYAT.match(call.data or ""))
)
@aman_handler
def ganti_halaman_riwayat(call):
    if not _admin_call(call):
        return

    cocok = _POLA_HALAMAN_RIWAYAT.match(call.data)
    halaman = int(cocok.group(1))

    semua = RIWAYAT.daftar()
    tg_bot.answer_callback_query(call.id)

    tg_bot.edit_message_text(
        _teks_riwayat(halaman),
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup_riwayat(semua, halaman, RIWAYAT_PER_HALAMAN),
    )


@tg_bot.callback_query_handler(func=lambda call: call.data == "admin_riwayat_info")
@aman_handler
def info_halaman_riwayat(call):
    if not _admin_call(call):
        return

    semua = RIWAYAT.daftar()
    total_halaman = max(
        1, (len(semua) + RIWAYAT_PER_HALAMAN - 1) // RIWAYAT_PER_HALAMAN
    )
    tg_bot.answer_callback_query(
        call.id, f"{len(semua)} chat · {total_halaman} halaman"
    )


@tg_bot.callback_query_handler(
    func=lambda call: bool(_POLA_HAPUS_RIWAYAT.match(call.data or ""))
)
@aman_handler
def konfirmasi_hapus_riwayat(call):
    if not _admin_call(call):
        return

    cocok = _POLA_HAPUS_RIWAYAT.match(call.data)
    ID_AI = int(cocok.group(1))
    info = RIWAYAT.info(ID_AI)

    if not info:
        tg_bot.answer_callback_query(
            call.id, "Riwayat chat itu sudah tidak ada.", show_alert=True
        )
        return

    nama = info.get("nama") or "-"
    username = f" @{info['username']}" if info.get("username") else ""

    tg_bot.answer_callback_query(call.id)
    tg_bot.edit_message_text(
        "🗑️ <b>HAPUS RIWAYAT?</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"• Chat: <b>{escape_html(nama)}</b>{escape_html(username)}\n"
        f"• ID: <code>{info['chat_id']}</code>\n"
        f"• Pesan: <b>{info['jumlah_pesan']}</b>\n\n"
        "<i>Tindakan ini permanen dan tidak bisa dibatalkan.</i>",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup_konfirmasi_hapus_riwayat(str(info["chat_id"])),
    )


@tg_bot.callback_query_handler(
    func=lambda call: call.data.startswith("admin_hapus_ok_")
)
@aman_handler
def hapus_riwayat_chat(call):
    if not _admin_call(call):
        return

    chat_id = call.data.replace("admin_hapus_ok_", "", 1)
    if not chat_id.lstrip("-").isdigit():
        tg_bot.answer_callback_query(call.id, "ID tidak valid.", show_alert=True)
        return

    ID_AI = int(chat_id)
    dihapus = RIWAYAT.hapus(ID_AI)

    # Sesi di memori juga dibersihkan supaya tidak "hidup lagi"
    try:
        from bot.handlers.ai import AI_SESSIONS

        AI_SESSIONS.clear(ID_AI)
    except Exception:
        pass

    tg_bot.answer_callback_query(
        call.id, "🗑️ Riwayat dihapus." if dihapus else "Riwayat sudah kosong."
    )

    semua = RIWAYAT.daftar()
    tg_bot.edit_message_text(
        _teks_riwayat(1),
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup_riwayat(semua, 1, RIWAYAT_PER_HALAMAN),
    )


@tg_bot.callback_query_handler(
    func=lambda call: call.data == "admin_riwayat_hapus_semua"
)
@aman_handler
def konfirmasi_hapus_semua_riwayat(call):
    if not _admin_call(call):
        return

    stat = RIWAYAT.statistik()
    tg_bot.answer_callback_query(call.id)

    tg_bot.edit_message_text(
        "🧨 <b>HAPUS SEMUA RIWAYAT AI?</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"• Chat: <b>{stat['jumlah_chat']}</b>\n"
        f"• Pesan: <b>{stat['jumlah_pesan']}</b>\n"
        f"• Ukuran: <b>{_ukuran_stat(stat['ukuran_byte'])}</b>\n\n"
        "<i>Tindakan ini permanen. Semua percakapan AI di semua chat "
        "akan hilang.</i>",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup_konfirmasi_hapus_semua(),
    )


@tg_bot.callback_query_handler(func=lambda call: call.data == "admin_riwayat_hapus_ok")
@aman_handler
def hapus_semua_riwayat(call):
    if not _admin_call(call):
        return

    # Kumpulkan ID dulu: setelah dihapus, daftar sudah kosong
    semua_chat = RIWAYAT.daftar()
    jumlah = RIWAYAT.hapus_semua()

    try:
        from bot.handlers.ai import AI_SESSIONS

        for item in semua_chat:
            AI_SESSIONS.clear(int(item["chat_id"]))
    except Exception:
        pass

    tg_bot.answer_callback_query(call.id, f"🧨 {jumlah} chat dihapus.")

    tg_bot.edit_message_text(
        _teks_riwayat(1),
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup_riwayat([], 1, RIWAYAT_PER_HALAMAN),
    )


# ================== BROADCAST ==================

@tg_bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast")
@aman_handler
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
@aman_handler
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
@aman_handler
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
