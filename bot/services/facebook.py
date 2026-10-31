from io import BytesIO

import cloudscraper
from bs4 import BeautifulSoup


class FacebookScraperError(Exception):
    """Custom exception untuk error pada scraper Facebook."""
    pass


def _session():
    return cloudscraper.create_scraper()


def extract_facebook(url: str) -> dict:
    """
    Mengekstrak link download SD dan HD dari fdown.net.
    Mengembalikan dictionary berisi 'sdlink' dan 'hdlink'.
    """
    api_url = "https://www.fdown.net/download.php"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Referer": "https://www.fdown.net/index.php",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    }

    # Session khusus untuk bypass Cloudflare dasar
    scraper = _session()

    try:
        response = scraper.post(api_url, headers=headers, data={"URLz": url}, timeout=45)
    except Exception as e:
        raise FacebookScraperError(f"Request ke fdown.net gagal: {e}")

    if response.status_code != 200:
        raise FacebookScraperError(
            f"Server fdown.net menolak request (Status: {response.status_code}). "
            "Kemungkinan Cloudflare memblokir."
        )

    soup = BeautifulSoup(response.text, "html.parser")

    # Ekstrak elemen berdasarkan ID
    sd_tag = soup.find("a", id="sdlink")
    hd_tag = soup.find("a", id="hdlink")

    sd_url = sd_tag["href"].replace("&amp;", "&") if sd_tag and sd_tag.has_attr("href") else None
    hd_url = hd_tag["href"].replace("&amp;", "&") if hd_tag and hd_tag.has_attr("href") else None

    if not sd_url and not hd_url:
        raise FacebookScraperError(
            "Tidak dapat menemukan link video. Pastikan video Facebook bersifat publik."
        )

    return {"sdlink": sd_url, "hdlink": hd_url}


def unduh_video(url: str, max_bytes: int, timeout: int = 60) -> bytes:
    """Unduh video ke memori dengan batas ukuran supaya RAM server tidak jebol."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Referer": "https://www.facebook.com/",
    }

    scraper = _session()

    with scraper.get(url, headers=headers, stream=True, timeout=timeout) as response:
        if response.status_code != 200:
            raise FacebookScraperError(
                f"Server Facebook menolak unduhan (Status: {response.status_code})"
            )

        panjang = response.headers.get("content-length")
        if panjang and panjang.isdigit() and int(panjang) > max_bytes:
            raise FacebookScraperError(
                f"Ukuran video {int(panjang) // 1048576}MB melebihi batas upload Telegram (50MB)."
            )

        buffer = BytesIO()
        for chunk in response.iter_content(chunk_size=65536):
            if not chunk:
                continue
            buffer.write(chunk)
            if buffer.tell() > max_bytes:
                raise FacebookScraperError(
                    "Ukuran video melebihi batas upload Telegram (50MB)."
                )

    return buffer.getvalue()
