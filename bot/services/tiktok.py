import cloudscraper
import requests


_HEADERS = {
    "accept": "*/*",
    "accept-language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    ),
}

_EXTRACT_URL = "https://www.tikwm.com/api/"
_BASE_URL = "https://www.tikwm.com"  # Base URL untuk menggabungkan path relatif


class TikTokScraperError(Exception):
    pass


def _full_url(value):
    """
    Menggabungkan path relatif dari tikwm.com menjadi URL absolut.
    Kalau URL sudah absolut (http/https), dikembalikan apa adanya.
    """
    if not value:
        return ""
    if value.startswith("http://") or value.startswith("https://"):
        return value
    # Pastikan tidak double slash saat penggabungan
    if value.startswith("/"):
        return _BASE_URL + value
    return _BASE_URL + "/" + value


def _session():
    session = cloudscraper.create_scraper()
    session.headers.update(_HEADERS)
    return session


def extract_tiktok(url: str) -> dict:
    """
    Mengekstrak info video TikTok dari URL menggunakan tikwm.com (gratis, stabil).
    """
    session = _session()

    try:
        response = session.post(
            _EXTRACT_URL,
            data={"url": url, "hd": 1, "count": 12, "cursor": 0, "web": 1},
            timeout=30,
        )
    except requests.Timeout:
        raise TikTokScraperError("Request ke API timeout (>30 detik)")
    except requests.RequestException as e:
        raise TikTokScraperError(f"Request gagal: {e}")

    if response.status_code != 200:
        raise TikTokScraperError(f"API mengembalikan status {response.status_code}")

    try:
        result = response.json()
    except ValueError:
        raise TikTokScraperError("Response bukan JSON valid")

    if result.get("code") != 0:
        msg = result.get("msg", "Gagal mengekstrak video")
        raise TikTokScraperError(f"API error: {msg}")

    data = result.get("data", {})

    if not data:
        raise TikTokScraperError("Data video kosong. URL mungkin tidak valid atau video dihapus.")

    # Cek apakah ini slideshow (photo) atau video
    is_slideshow = "images" in data and data["images"]
    content_type = "photo" if is_slideshow else "video"

    # Data author
    author = data.get("author", {}) or {}

    # Data music
    music = data.get("music_info", {}) or {}

    # URL video (bisa path relatif, perlu digabung dengan base URL)
    video_no_wm = _full_url(data.get("play") or "")
    video_hd = _full_url(data.get("hdplay") or "")
    video_wm = _full_url(data.get("wmplay") or "")

    # URL slideshow (kalau ada, juga bisa path relatif)
    images = [_full_url(img) for img in (data.get("images") or [])]

    return {
        "author": {
            "username": author.get("unique_id", ""),
            "full_name": author.get("nickname", ""),
            "avatar": _full_url(author.get("avatar", "")),
            "verified": author.get("verified", False),
        },
        "stats": {
            "plays": data.get("play_count", 0),
            "likes": data.get("digg_count", 0),
            "comments": data.get("comment_count", 0),
            "shares": data.get("share_count", 0),
        },
        "music": {
            "title": music.get("title", ""),
            "author": music.get("author", ""),
            "duration": music.get("duration", 0),
            "cover": _full_url(music.get("cover", "")),
            # music.play juga path relatif di tikwm, jadi wajib di-_full_url
            "url": _full_url(music.get("play") or data.get("music") or ""),
        },
        "content": {
            "title": data.get("title", ""),
            "type": content_type,
            "resolution": f"{data.get('width', '?')}x{data.get('height', '?')}",
            "duration": data.get("duration", 0),
            "thumbnail": _full_url(data.get("origin_cover", "") or data.get("cover", "")),
            "video_no_wm": video_hd or video_no_wm,
            "video_wm": video_wm,
            "images": images,
        },
    }


def unduh_media(url: str, timeout: int = 120) -> bytes:
    """Download media (video/audio/foto) sebagai bytes."""
    session = _session()
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    return response.content
