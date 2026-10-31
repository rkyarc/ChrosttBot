import time

import feedparser
import requests


# URL RSS Google News
_GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search?"
    "q=%22Bursa+Efek+Indonesia%22+OR+BEI+OR+IDX&hl=id&gl=ID&ceid=ID:id"
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    ),
}

# Cache hasil fetch biar tidak re-fetch tiap ganti halaman
_CACHE = {"berita": [], "timestamp": 0.0}
CACHE_DURATION = 300  # 5 menit


class IDXNewsError(Exception):
    pass


def ambil_berita_terbaru(jumlah: int = 9) -> list[dict]:
    """
    Ambil berita IDX/BEI terbaru dari Google News RSS.
    Default 9 berita untuk 3 halaman (3 berita per halaman).
    Pakai cache 5 menit biar cepat saat ganti halaman.
    """
    now = time.time()

    # Kalau cache masih segar, pakai cache
    if _CACHE["berita"] and (now - _CACHE["timestamp"]) < CACHE_DURATION:
        return _CACHE["berita"][:jumlah]

    try:
        response = requests.get(_GOOGLE_NEWS_RSS, headers=_HEADERS, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        # Kalau gagal tapi ada cache lama, pakai itu
        if _CACHE["berita"]:
            return _CACHE["berita"][:jumlah]
        raise IDXNewsError(f"Gagal mengakses Google News: {e}")

    feed = feedparser.parse(response.content)

    if not feed.entries:
        if _CACHE["berita"]:
            return _CACHE["berita"][:jumlah]
        raise IDXNewsError("Tidak ada berita ditemukan")

    berita_list = []
    for entry in feed.entries[:jumlah]:
        judul_full = entry.get("title", "").strip()
        judul, sumber = _pisah_judul_sumber(judul_full)
        tanggal = _format_tanggal(entry.get("published", ""))
        link = entry.get("link", "")

        berita_list.append({
            "tanggal": tanggal,
            "judul": judul,
            "link": link,
            "sumber": sumber or entry.get("source", {}).get("title", ""),
        })

    # Simpan ke cache
    _CACHE["berita"] = berita_list
    _CACHE["timestamp"] = now

    return berita_list


def hapus_cache():
    """Hapus cache supaya fetch ulang dari Google News (dipakai tombol Refresh)."""
    _CACHE["berita"] = []
    _CACHE["timestamp"] = 0.0


def _pisah_judul_sumber(judul_full: str) -> tuple:
    """Pisahkan 'Judul Berita - Kompas.com' jadi ('Judul Berita', 'Kompas.com')."""
    if " - " in judul_full:
        parts = judul_full.rsplit(" - ", 1)
        return parts[0].strip(), parts[1].strip()
    return judul_full, ""


def _format_tanggal(tanggal_raw: str) -> str:
    """Format tanggal Google News jadi lebih ringkas."""
    if not tanggal_raw:
        return "Terbaru"
    try:
        parts = tanggal_raw.split(",")
        if len(parts) >= 2:
            return " ".join(parts[1].strip().split(" ")[:3])
    except Exception:
        pass
    return tanggal_raw[:20]
