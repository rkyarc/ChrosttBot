"""Pembatas laju per pengguna untuk operasi berat.

Downloader, konversi stiker, hapus background, dan AI semuanya memicu kerja
jaringan atau CPU yang mahal. Tanpa batas, satu pengguna bisa menghabiskan
kuota API dan bandwidth server. Modul ini memakai jendela geser sederhana:
setiap aksi mahal dicatat, dan kalau jumlahnya melewati batas dalam jendela
waktu tertentu, permintaan ditolak dengan pesan yang bisa ditindaklanjuti.
"""

import threading
import time

# (batas aksi, jendela detik). Dipisah karena biayanya berbeda jauh.
BATAS_UNDUH = (8, 60)  # 8 unduhan per menit
BATAS_STIKER = (10, 60)  # 10 konversi stiker per menit
BATAS_AI = (20, 60)  # 20 pertanyaan AI per menit
BATAS_UMUM = (30, 60)  # jaring pengaman untuk aksi lain

_PESAN = {
    "unduh": "Terlalu banyak unduhan. Tunggu sebentar lalu coba lagi.",
    "stiker": "Terlalu banyak konversi stiker. Tunggu sebentar lalu coba lagi.",
    "ai": "Terlalu banyak pertanyaan AI. Tunggu sebentar lalu coba lagi.",
    "umum": "Terlalu banyak permintaan. Tunggu sebentar lalu coba lagi.",
}

_BATAS = {
    "unduh": BATAS_UNDUH,
    "stiker": BATAS_STIKER,
    "ai": BATAS_AI,
    "umum": BATAS_UMUM,
}

# kunci -> daftar timestamp aksi
_JEJAK: dict[tuple[str, int], list[float]] = {}
_LOCK = threading.Lock()

# Jaga memori: kalau entri melewati batas ini, buang yang paling lama.
_MAKS_ENTRI = 5000


class BatasTerlampaui(Exception):
    """Pengguna melewati kuota aksi. ``detik`` = saran waktu tunggu."""

    def __init__(self, detik: int, pesan: str):
        self.detik = max(1, int(detik))
        self.pesan = pesan
        super().__init__(pesan)


def _bersihkan(jendela: float, now: float) -> None:
    """Buang jejak yang sudah keluar dari jendela waktu."""
    kedaluwarsa = []
    for kunci, waktu in _JEJAK.items():
        if not waktu or now - waktu[-1] > jendela:
            kedaluwarsa.append(kunci)
    for kunci in kedaluwarsa:
        _JEJAK.pop(kunci, None)


def cek(user_id, jenis: str = "umum", naikkan: bool = True) -> None:
    """Rekam aksi dan lempar BatasTerlampaui kalau kuota habis.

    ``naikkan=False`` hanya memeriksa tanpa mencatat, berguna untuk tombol
    yang menampilkan status alih-alih menjalankan aksi.
    """
    if not user_id:
        return

    batas, jendela = _BATAS.get(jenis, BATAS_UMUM)
    kunci = (jenis, int(user_id))
    now = time.time()

    with _LOCK:
        if len(_JEJAK) > _MAKS_ENTRI:
            _bersihkan(jendela, now)

        waktu = [t for t in _JEJAK.get(kunci, []) if now - t < jendela]

        if len(waktu) >= batas:
            sisa = int(jendela - (now - waktu[0])) + 1
            _JEJAK[kunci] = waktu
            raise BatasTerlampaui(sisa, _PESAN.get(jenis, _PESAN["umum"]))

        if naikkan:
            waktu.append(now)
        _JEJAK[kunci] = waktu


def periksa(user_id, jenis: str = "umum") -> bool:
    """True kalau pengguna masih boleh melakukan aksi, tanpa mencatat apa pun."""
    try:
        cek(user_id, jenis, naikkan=False)
    except BatasTerlampaui:
        return False
    return True


def reset() -> None:
    """Kosongkan semua jejak. Dipakai oleh test."""
    with _LOCK:
        _JEJAK.clear()
