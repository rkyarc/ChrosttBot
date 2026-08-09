import cloudscraper
from bs4 import BeautifulSoup

class FacebookScraperError(Exception):
    """Custom exception untuk error pada scraper Facebook."""
    pass

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

    data = {"URLz": url}

    # Buat session khusus untuk bypass Cloudflare dasar
    scraper = cloudscraper.create_scraper()
    response = scraper.post(api_url, headers=headers, data=data)
    html_raw = response.text

    if response.status_code != 200:
        raise FacebookScraperError(f"Server fdown.net menolak request (Status: {response.status_code}). Kemungkinan Cloudflare memblokir.")

    soup = BeautifulSoup(html_raw, 'html.parser')
    
    # Ekstrak elemen berdasarkan ID
    sd_tag = soup.find('a', id='sdlink')
    hd_tag = soup.find('a', id='hdlink')
    
    sd_url = sd_tag['href'].replace('&amp;', '&') if sd_tag and sd_tag.has_attr('href') else None
    hd_url = hd_tag['href'].replace('&amp;', '&') if hd_tag and hd_tag.has_attr('href') else None
    
    if not sd_url and not hd_url:
        raise FacebookScraperError("Tidak dapat menemukan link video. Pastikan video Facebook bersifat publik.")

    return {
        "sdlink": sd_url,
        "hdlink": hd_url,
    }