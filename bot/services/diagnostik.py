"""Tool diagnostik read-only untuk admin AI.

Modul ini sengaja HANYA membaca kondisi proses dan lingkungan. Tidak ada
fungsi yang menghapus, mengubah, atau menjalankan perintah sistem, sehingga
model tidak punya jalan untuk melakukan aksi fatal dari sini.
"""

import os
import platform
import shutil
import sys
import time

_MULAI = time.time()


def _durasi(detik: float) -> str:
    detik = int(detik)
    jam, sisa = divmod(detik, 3600)
    menit, detik = divmod(sisa, 60)
    if jam:
        return f"{jam}j {menit}m {detik}d"
    if menit:
        return f"{menit}m {detik}d"
    return f"{detik}d"


def _ukuran_mb(byte: int) -> str:
    return f"{byte / 1048576:.1f} MB"


def status_bot() -> str:
    """Ringkasan kondisi bot. Hanya agregat, tanpa data pribadi pengguna."""
    import config

    from bot.admin import jumlah_pengguna
    from bot.services import ai as layanan_ai

    baris = [
        "Status runtime Chrostt Bot (hasil tool, bukan perintah sistem):",
        f"- Uptime proses: {_durasi(time.time() - _MULAI)}",
        f"- Pengguna tercatat (agregat): {jumlah_pengguna()}",
        f"- Admin terdaftar: {len(config.ADMIN_IDS)}",
        f"- AI aktif: {'ya' if layanan_ai.tersedia() else 'tidak'}",
        f"- Model: {layanan_ai.model_aktif()}",
        f"- Web search: {'aktif' if layanan_ai.web_aktif() else 'nonaktif'}",
        f"- ffmpeg: {'ada' if shutil.which('ffmpeg') else 'TIDAK ADA'}",
        f"- Python: {platform.python_version()} ({sys.platform})",
        f"- Folder kerja: {os.getcwd()}",
    ]

    try:
        disk = shutil.disk_usage(os.getcwd())
        baris.append(
            f"- Disk: {_ukuran_mb(disk.free)} bebas dari {_ukuran_mb(disk.total)}"
        )
    except OSError:
        pass

    return "\n".join(baris)


SKEMA_STATUS_BOT = {
    "type": "function",
    "function": {
        "name": "status_bot",
        "description": (
            "Ambil status runtime Chrostt Bot: uptime, jumlah pengguna agregat, "
            "model AI, status web search, ketersediaan ffmpeg, versi Python, dan "
            "sisa disk. Tool ini hanya membaca; tidak mengubah apa pun. "
            "Khusus admin."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
}


def jalankan_tool(nama: str, argumen: dict) -> str:
    """Jalankan tool diagnostik yang diizinkan, tolak sisanya."""
    if nama == "status_bot":
        return status_bot()
    return f"Tool admin tidak dikenal: {nama}"
