"""Operasi Telegram yang tahan gangguan.

Bot produksi sering menerima error yang sebenarnya bukan kesalahan pengguna:
pesan diedit dengan isi sama, prompt sudah dihapus, atau kena flood limit.
Modul ini menangani kasus tersebut supaya log tidak penuh traceback dan
pengguna tidak melihat pesan gagal yang menyesatkan.
"""

import contextlib
import logging
import time

from bot import tg_bot

log = logging.getLogger("chrosttbot.telegram")

# Berapa kali percobaan ulang saat kena flood limit Telegram
MAKS_ULANG = 2


def _pesan_error(e: Exception) -> str:
    return str(e).lower()


def _retry_after(e: Exception) -> int | None:
    """Ambil saran waktu tunggu dari error flood limit Telegram.

    pyTelegramBotAPI mengisi ``retry_after`` di objek exception, tetapi
    sebagian jalur hanya menyertakan angka di deskripsi teks.
    """
    nilai = getattr(e, "retry_after", None)
    if isinstance(nilai, int) and nilai > 0:
        return nilai

    pesan = _pesan_error(e)
    penanda = "retry after "
    if penanda in pesan:
        sisa = pesan.split(penanda, 1)[1]
        angka = ""
        for karakter in sisa:
            if karakter.isdigit():
                angka += karakter
            else:
                break
        if angka:
            return max(1, int(angka))

    return None


def _kena_flood(e: Exception) -> bool:
    pesan = _pesan_error(e)
    return "flood" in pesan or "too many requests" in pesan or "retry after" in pesan


def _ulang(fungsi, *args, **kwargs):
    """Jalankan fungsi, tunggu lalu ulangi kalau kena flood limit.

    Telegram meminta tunggu sampai ``retry_after`` detik. Menunggu lebih murah
    daripada membuang pesan: pengguna tidak perlu mengirim ulang perintah.
    """
    percobaan = 0
    while True:
        try:
            return fungsi(*args, **kwargs)
        except Exception as e:
            if not _kena_flood(e) or percobaan >= MAKS_ULANG:
                raise

            tunggu = _retry_after(e) or 3
            percobaan += 1
            log.warning(
                "Flood limit: tunggu %s detik lalu ulangi (%s/%s)",
                tunggu,
                percobaan,
                MAKS_ULANG,
            )
            time.sleep(min(tunggu, 30))


def kirim(chat_id: int, teks: str, **kwargs):
    """Kirim pesan; kembalikan objek Message atau None kalau gagal."""
    try:
        return _ulang(tg_bot.send_message, chat_id, teks, **kwargs)
    except Exception as e:
        if _kena_flood(e):
            log.warning("Flood limit saat kirim ke %s, pesan dilepas", chat_id)
        else:
            log.warning("Gagal kirim pesan ke %s: %s", chat_id, e)
        return None


def edit(chat_id: int, message_id: int, teks: str, **kwargs) -> bool:
    """Edit pesan. Kalau gagal karena isi sama, dianggap berhasil."""
    try:
        _ulang(tg_bot.edit_message_text, teks, chat_id, message_id, **kwargs)
        return True
    except Exception as e:
        pesan = _pesan_error(e)

        # Bukan error: Telegram menolak edit kalau isinya identik
        if "message is not modified" in pesan:
            return True

        # Pesan lama tidak bisa diedit -> kirim baru supaya pengguna tetap dapat
        if "message to edit not found" in pesan or "message can't be edited" in pesan:
            kirim(chat_id, teks, **kwargs)
            return False

        log.warning("Gagal edit pesan %s di %s: %s", message_id, chat_id, e)
        kirim(chat_id, teks, **kwargs)
        return False


def hapus(chat_id: int, message_id: int) -> bool:
    """Hapus pesan. Error 'sudah tidak ada' bukan kegagalan."""
    try:
        tg_bot.delete_message(chat_id, message_id)
        return True
    except Exception as e:
        pesan = _pesan_error(e)
        if "not found" in pesan or "message to delete" in pesan:
            return False
        log.debug("Gagal hapus pesan %s di %s: %s", message_id, chat_id, e)
        return False


def jawab_callback(call, teks: str = "", alert: bool = False) -> None:
    """Jawab callback query tanpa melempar error kalau sudah kedaluwarsa."""
    try:
        if teks:
            tg_bot.answer_callback_query(call.id, teks, show_alert=alert)
        else:
            tg_bot.answer_callback_query(call.id)
    except Exception:
        # Callback lama memang tidak bisa dijawab lagi
        pass


def ketik(chat_id: int, aksi: str = "typing") -> None:
    """Kirim indikator aktivitas; abaikan kalau gagal."""
    with contextlib.suppress(Exception):
        tg_bot.send_chat_action(chat_id, aksi)


def tunggu(chat_id: int, detik: int = 60) -> None:
    """Tunda singkat sambil tetap terlihat aktif (dipakai sebelum operasi lambat)."""
    ketik(chat_id, "typing")
    time.sleep(min(max(detik, 0), 5))
