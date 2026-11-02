"""Batas ukuran bersama untuk fitur downloader.

Bot API Telegram menolak upload di atas 50MB. Service melempar
MediaTerlaluBesar begitu ukuran terlampaui, lalu handler mengirim tautan
unduhan supaya pengguna tetap bisa mengambil filenya.
"""

BATAS_UPLOAD_BYTES = 50 * 1024 * 1024


class MediaTerlaluBesar(Exception):
    """File melebihi batas upload Telegram; handler wajib mengirim tautan."""

    def __init__(self, url: str, ukuran_bytes: int | None = None, catatan: str = ""):
        self.url = url
        self.ukuran_bytes = ukuran_bytes
        self.catatan = catatan
        super().__init__(f"Ukuran file {ukuran_mb(ukuran_bytes)} melebihi batas 50MB.")


def ukuran_mb(ukuran_bytes) -> str:
    """Ukuran dalam MB; 'tidak diketahui' kalau header tidak memberi info."""
    if not ukuran_bytes:
        return "tidak diketahui"
    return f"{ukuran_bytes / 1048576:.1f} MB"
