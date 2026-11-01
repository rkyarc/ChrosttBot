"""Ekstraksi & unduhan TikTok lewat tikwm.com.

Tikwm kadang lambat saat menerima POST body (write timeout) atau balas
dengan koneksi terputus, jadi semua panggilan diberi retry + timeout
terpisah untuk connect/read, dan exception apa pun dinormalkan menjadi
TikTokScraperError supaya tidak bocor ke pengguna sebagai traceback.
"""

import time

import cloudscraper


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
_BASE_URL = "https://www.tikwm.com"

# (connect, read). Write timeout mengikuti nilai read.
_TIMEOUT_EKSTRAK = (10, 45)
_TIMEOUT_UNDUH = (15, 180)

_MAX_UNDUH_BYTES = 50 * 1024 * 1024
MAKS_PERCOBAAN = 3


class TikTokScraperError(Exception):
    pass


def _full_url(value):
    """Gabungkan path relatif tikwm menjadi URL absolut."""
    if not value:
        return ""
    if value.startswith(("http://", "https://")):
        return value
    if value.startswith("/"):
        return _BASE_URL + value
    return _BASE_URL + "/" + value


def _session():
    session = cloudscraper.create_scraper()
    session.headers.update(_HEADERS)
    return session


def _pesan_jaringan(e: Exception) -> str:
    """Terjemahkan error jaringan jadi pesan yang bisa dibaca pengguna."""
    teks = str(e)
    rendah = teks.lower()

    # Write timeout: server lambat menerima body upload kita
    if "write operation timed out" in rendah or "write timeout" in rendah:
        return "Server TikTok lambat menerima data. Coba lagi sebentar lagi."

    if "read timed out" in rendah or "read timeout" in rendah:
        return "Server TikTok tidak merespons tepat waktu. Coba lagi."

    if "connection aborted" in rendah or "connection reset" in rendah:
        return "Koneksi ke server TikTok terputus. Coba lagi."

    if "nameresolutionerror" in rendah or "failed to resolve" in rendah:
        return "Tidak bisa menghubungi server TikTok. Cek koneksi internet."

    if "ssl" in rendah:
        return "Koneksi aman ke server TikTok gagal. Coba lagi."

    return f"Gagal menghubungi server TikTok: {teks[:150]}"


def _post_ekstrak(url: str) -> dict:
    """POST ke tikwm dengan retry untuk error jaringan sementara."""
    galat_terakhir = None

    for percobaan in range(MAKS_PERCOBAAN):
        if percobaan:
            time.sleep(1.5 * percobaan)  # backoff: 1.5s, 3s

        session = _session()
        try:
            response = session.post(
                _EXTRACT_URL,
                data={"url": url, "hd": 1, "count": 12, "cursor": 0, "web": 1},
                timeout=_TIMEOUT_EKSTRAK,
            )
        except Exception as e:
            # Jangan batasi ke requests.RequestException: error tulis bisa
            # muncul sebagai ProtocolError/OSError/timeout level socket.
            galat_terakhir = e
            continue

        if response.status_code != 200:
            galat_terakhir = TikTokScraperError(
                f"API TikTok menolak permintaan (HTTP {response.status_code})."
            )
            # 5xx biasanya sementara, 4xx tidak perlu diulang
            if 500 <= response.status_code < 600:
                continue
            raise galat_terakhir

        try:
            return response.json()
        except ValueError:
            galat_terakhir = TikTokScraperError("Respons API bukan JSON yang valid.")
            continue

    if isinstance(galat_terakhir, TikTokScraperError):
        raise galat_terakhir
    raise TikTokScraperError(_pesan_jaringan(galat_terakhir))


def extract_tiktok(url: str) -> dict:
    """Ambil metadata video/slideshow TikTok."""
    result = _post_ekstrak(url)

    if result.get("code") != 0:
        msg = result.get("msg", "Gagal mengekstrak video")
        raise TikTokScraperError(f"API error: {msg}")

    data = result.get("data") or {}
    if not data:
        raise TikTokScraperError(
            "Data video kosong. URL mungkin tidak valid atau video sudah dihapus."
        )

    is_slideshow = bool(data.get("images"))
    content_type = "photo" if is_slideshow else "video"

    author = data.get("author") or {}
    music = data.get("music_info") or {}

    video_no_wm = _full_url(data.get("play") or "")
    video_hd = _full_url(data.get("hdplay") or "")
    video_wm = _full_url(data.get("wmplay") or "")
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
            "url": _full_url(music.get("play") or data.get("music") or ""),
        },
        "content": {
            "title": data.get("title", ""),
            "type": content_type,
            "resolution": f"{data.get('width', '?')}x{data.get('height', '?')}",
            "duration": data.get("duration", 0),
            "thumbnail": _full_url(
                data.get("origin_cover", "") or data.get("cover", "")
            ),
            "video_no_wm": video_hd or video_no_wm,
            "video_wm": video_wm,
            "images": images,
        },
    }


def unduh_media(url: str, timeout=None) -> bytes:
    """Download media TikTok dengan retry dan batas ukuran."""
    if not url:
        raise TikTokScraperError("URL media kosong.")

    batas_waktu = timeout or _TIMEOUT_UNDUH
    galat_terakhir = None

    for percobaan in range(MAKS_PERCOBAAN):
        if percobaan:
            time.sleep(1.2 * percobaan)

        session = _session()
        try:
            with session.get(url, timeout=batas_waktu, stream=True) as response:
                if response.status_code != 200:
                    galat_terakhir = TikTokScraperError(
                        f"Server media menolak unduhan (HTTP {response.status_code})."
                    )
                    if 500 <= response.status_code < 600:
                        continue
                    raise galat_terakhir

                panjang = response.headers.get("content-length")
                if panjang and panjang.isdigit() and int(panjang) > _MAX_UNDUH_BYTES:
                    mb = int(panjang) // 1048576
                    raise TikTokScraperError(
                        f"Media {mb}MB melebihi batas upload Telegram (50MB)."
                    )

                potongan = []
                total = 0
                for chunk in response.iter_content(chunk_size=65536):
                    if not chunk:
                        continue
                    potongan.append(chunk)
                    total += len(chunk)
                    if total > _MAX_UNDUH_BYTES:
                        raise TikTokScraperError(
                            "Media melebihi batas upload Telegram (50MB)."
                        )

                if not potongan:
                    galat_terakhir = TikTokScraperError("Media kosong.")
                    continue

                return b"".join(potongan)

        except TikTokScraperError:
            raise
        except Exception as e:
            galat_terakhir = e
            continue

    if isinstance(galat_terakhir, TikTokScraperError):
        raise galat_terakhir
    raise TikTokScraperError(_pesan_jaringan(galat_terakhir))
