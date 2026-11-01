"""Web search dan pembacaan halaman untuk Chrostt AI.

Strategi:
1. Coba beberapa backend lewat `ddgs` (google -> brave -> duckduckgo -> mojeek).
2. Fallback ke Wikipedia API dan Google News RSS.
3. Semua hasil difilter skor relevansi, supaya hasil "nyasar" tidak dipakai.
4. Baca halaman: fetch langsung, fallback ke r.jina.ai (markdown bersih).

Semua akses keluar dibatasi supaya model tidak bisa disuruh membuka alamat
internal (SSRF).
"""

import html
import ipaddress
import re
import socket
import time
import urllib.parse

import requests

try:
    from ddgs import DDGS
except ImportError:  # pragma: no cover - ddgs opsional saat runtime
    DDGS = None


_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
)

_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Domain yang sering muncul sebagai hasil sampah/clickbait
_DOMAIN_BURUK = (
    "pasarbokep",
    "memeksiana",
    "bokep",
    "xxx",
    "porn",
    "judi",
    "slot",
    "togel",
    "gacor",
    "maxwin",
)

_CACHE_TTL = 600
_CACHE_MAKS = 120

# Urutan backend ddgs; google paling relevan untuk bahasa Indonesia
_BACKEND_DDGS = ("google", "brave", "duckduckgo", "mojeek")

_STOPWORD = frozenset(
    "dan atau yang untuk dengan dari pada ini itu apa adalah cara bagaimana "
    "siapa kapan dimana mengapa berapa the and for with from what how who when "
    "where why which is are of to in on at".split()
)

# Kalimat/pesan yang menandakan halaman gagal atau diblokir, bukan isi artikel
_POLA_BOILERPLATE = (
    "turn on more accessible mode",
    "skip ribbon commands",
    "turn off animations",
    "please enable javascript",
    "enable javascript and cookies",
    "access denied",
    "403 forbidden",
    "404 not found",
    "halaman tidak ditemukan",
    "page not found",
    "verify you are human",
    "checking your browser",
    "just a moment",
    "requiring captcha",
    "performing security verification",
    "security verification",
    "please make sure you are authorized",
    "are you a robot",
    "cf-browser-verification",
    "cloudflare",
)

# Navigasi yang tidak berguna kalau muncul di teks
_POLA_NAV = (
    "skip to main content",
    "langsung ke konten utama",
    "lompat ke isi",
    "toggle navigation",
    "lompat ke navigasi",
)


def _kualitas(teks: str) -> int:
    """Skor kasar: makin tinggi, makin mungkin isinya artikel sungguhan."""
    if not teks:
        return 0

    rendah = teks.lower()
    skor = 0

    for pola in _POLA_BOILERPLATE:
        if pola in rendah:
            skor -= 80

    for pola in _POLA_NAV:
        skor -= 15 * rendah.count(pola)

    skor += min(len(teks) // 200, 30)

    kata = re.findall(r"\w+", rendah)
    if len(kata) < 30:
        # Terlalu pendek untuk jadi artikel; rasio kata unik jadi tidak bermakna
        skor -= 40
    else:
        rasio_unik = len(set(kata)) / len(kata)
        skor += int(rasio_unik * 40)

    skor += min(teks.count(". ") * 2, 20)
    return skor


def _rapikan_isi(teks: str) -> str:
    """Buang potongan navigasi yang tersisa."""
    for pola in _POLA_NAV:
        teks = re.sub(rf"\b{re.escape(pola)}\b", " ", teks, flags=re.I)
    return re.sub(r"\s{2,}", " ", teks).strip()


class WebSearchError(Exception):
    """Error yang aman ditampilkan ke model/pengguna."""


_cache: dict[str, tuple[float, object]] = {}


def _cache_get(kunci: str):
    item = _cache.get(kunci)
    if not item:
        return None
    waktu, nilai = item
    if time.time() - waktu > _CACHE_TTL:
        _cache.pop(kunci, None)
        return None
    return nilai


def _cache_set(kunci: str, nilai) -> None:
    if len(_cache) >= _CACHE_MAKS:
        for k, _ in sorted(_cache.items(), key=lambda kv: kv[1][0])[:20]:
            _cache.pop(k, None)
    _cache[kunci] = (time.time(), nilai)


def _bersihkan_html(teks: str) -> str:
    teks = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", teks or "", flags=re.S)
    teks = re.sub(r"<(script|style|noscript)\b.*?</\1>", " ", teks, flags=re.S | re.I)
    teks = re.sub(r"<[^>]+>", " ", teks)
    teks = html.unescape(teks)
    return re.sub(r"\s+", " ", teks).strip()


# ==================== RELEVANSI ====================

def _token(query: str) -> list[str]:
    kata = re.findall(r"[0-9a-zA-Z\u00c0-\u024f]+", (query or "").lower())
    return [k for k in kata if len(k) > 2 and k not in _STOPWORD]


def _skor(query_tokens: list[str], judul: str, ringkas: str, url: str) -> int:
    """Hitung berapa kata kunci query yang muncul di judul/ringkasan."""
    if not query_tokens:
        return 1

    judul = (judul or "").lower()
    gabung = f"{judul} {ringkas or ''} {url or ''}".lower()

    skor = 0
    for kata in query_tokens:
        if kata in judul:
            skor += 3
        elif kata in gabung:
            skor += 1
    return skor


def _domain(url: str) -> str:
    try:
        host = urllib.parse.urlparse(url).hostname or ""
        return host[4:] if host.startswith("www.") else host
    except ValueError:
        return ""


def _layak(hasil: dict, query_tokens: list[str], minimal: int) -> bool:
    url = hasil.get("url") or ""
    domain = _domain(url).lower()

    if not domain or not url.startswith("http"):
        return False

    if any(buruk in domain or buruk in url.lower() for buruk in _DOMAIN_BURUK):
        return False

    return _skor(query_tokens, hasil.get("judul", ""), hasil.get("ringkas", ""), url) >= minimal


# ==================== ENGINE ====================

def _cari_ddgs(query: str, jumlah: int) -> list[dict]:
    """Cari lewat ddgs dengan retry; google paling relevan untuk id-ID.

    "No results found" dari ddgs biasanya berarti rate limit sementara,
    bukan benar-benar tidak ada hasil, jadi dicoba beberapa kali dengan jeda.
    """
    if DDGS is None:
        return []

    jeda = (0, 2.0, 4.0)

    for percobaan, tunggu in enumerate(jeda):
        if tunggu:
            time.sleep(tunggu)

        for backend in _BACKEND_DDGS:
            try:
                with DDGS(timeout=20) as d:
                    mentah = d.text(
                        query, max_results=jumlah, backend=backend, region="id-id"
                    )
            except Exception:
                time.sleep(0.4)
                continue

            hasil = []
            for item in mentah or []:
                judul = (item.get("title") or "").strip()
                url = (item.get("href") or item.get("url") or "").strip()
                ringkas = (item.get("body") or item.get("excerpt") or "").strip()
                if judul and url:
                    hasil.append({"judul": judul, "url": url, "ringkas": ringkas[:400], "sumber": "ddgs"})

            if hasil:
                return hasil

    return []


def _cari_wikipedia(query: str, jumlah: int) -> list[dict]:
    hasil = []

    for bahasa in ("id", "en"):
        try:
            response = requests.get(
                f"https://{bahasa}.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "format": "json",
                    "srlimit": jumlah,
                },
                headers=_HEADERS,
                timeout=20,
            )
            if response.status_code != 200:
                continue

            for item in response.json().get("query", {}).get("search", []):
                judul = item.get("title", "")
                if not judul:
                    continue
                url = (
                    f"https://{bahasa}.wikipedia.org/wiki/"
                    + urllib.parse.quote(judul.replace(" ", "_"))
                )
                hasil.append(
                    {
                        "judul": judul,
                        "url": url,
                        "ringkas": _bersihkan_html(item.get("snippet", ""))[:400],
                        "sumber": "wiki",
                    }
                )
        except (requests.RequestException, ValueError):
            continue

        if hasil:
            break

    return hasil[:jumlah]


def _cari_berita(query: str, jumlah: int) -> list[dict]:
    """Google News RSS: bagus untuk berita/kejadian terbaru."""
    try:
        response = requests.get(
            "https://news.google.com/rss/search",
            params={"q": query, "hl": "id", "gl": "ID", "ceid": "ID:id"},
            headers=_HEADERS,
            timeout=20,
        )
    except requests.RequestException:
        return []

    if response.status_code != 200:
        return []

    hasil = []
    for blok in re.findall(r"<item>(.*?)</item>", response.text, re.S):
        judul = re.search(r"<title>(.*?)</title>", blok, re.S)
        link = re.search(r"<link>(.*?)</link>", blok, re.S)
        tanggal = re.search(r"<pubDate>(.*?)</pubDate>", blok, re.S)

        if not judul or not link:
            continue

        judul_bersih = _bersihkan_html(judul.group(1))
        sumber = ""
        if " - " in judul_bersih:
            judul_bersih, sumber = judul_bersih.rsplit(" - ", 1)

        ringkas = f"{sumber.strip()}. {_bersihkan_html(tanggal.group(1)) if tanggal else ''}".strip()
        url = link.group(1).strip()

        if judul_bersih:
            hasil.append(
                {
                    "judul": judul_bersih,
                    "url": url,
                    "ringkas": ringkas[:400],
                    "sumber": "berita",
                }
            )

        if len(hasil) >= jumlah:
            break

    return hasil


def cari(query: str, jumlah: int = 5) -> list[dict]:
    """Cari di web dan kembalikan hasil yang sudah difilter relevansinya."""
    query = (query or "").strip()
    if not query:
        return []

    kunci = f"cari:{query.lower()}:{jumlah}"
    cached = _cache_get(kunci)
    if cached is not None:
        return cached

    tokens = _token(query)
    kumpulan: list[dict] = []

    # 1) Web search dulu (paling umum), 2) berita (paling segar), 3) ensiklopedia.
    # Semua sumber digabung supaya hasil tetap ada walau satu engine kena rate limit.
    for sumber in (_cari_ddgs, _cari_berita, _cari_wikipedia):
        try:
            kumpulan.extend(sumber(query, jumlah))
        except Exception:
            continue

        relevan = [h for h in kumpulan if _layak(h, tokens, 1)]
        if len(relevan) >= jumlah:
            break

    # Simpan hanya hasil relevan, dan tandai prioritas sumbernya
    bobot_sumber = {"ddgs": 2, "berita": 1, "wiki": 0}
    hasil = [h for h in kumpulan if _layak(h, tokens, 1)]

    if not hasil:
        return []

    hasil.sort(
        key=lambda h: (
            _skor(tokens, h["judul"], h["ringkas"], h["url"]),
            bobot_sumber.get(h.get("sumber", ""), 0),
        ),
        reverse=True,
    )

    unik, domain_terpakai = [], {}
    for h in hasil:
        d = _domain(h["url"])
        if domain_terpakai.get(d, 0) >= 2:
            continue
        domain_terpakai[d] = domain_terpakai.get(d, 0) + 1
        unik.append(h)
        if len(unik) >= jumlah:
            break

    _cache_set(kunci, unik)
    return unik


# ==================== BACA HALAMAN ====================

def _host_aman(host: str) -> bool:
    """Tolak host internal/loopback supaya model tidak bisa dipakai SSRF."""
    if not host:
        return False

    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False

    for info in infos:
        alamat = info[4][0]
        try:
            ip = ipaddress.ip_address(alamat)
        except ValueError:
            return False

        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False

    return True


def _baca_langsung(url: str, maks: int) -> str:
    response = requests.get(url, headers=_HEADERS, timeout=20, stream=True)
    if response.status_code != 200:
        raise WebSearchError(f"Halaman menolak akses (HTTP {response.status_code}).")

    tipe = response.headers.get("content-type", "")
    if "html" not in tipe and "text" not in tipe:
        raise WebSearchError("Konten bukan teks/HTML.")

    potongan, total = [], 0
    for chunk in response.iter_content(chunk_size=32768, decode_unicode=True):
        if not chunk:
            continue
        potongan.append(chunk)
        total += len(chunk)
        if total > 300_000:
            break

    teks = _bersihkan_html("".join(potongan))
    return teks[:maks]


def _baca_jina(url: str, maks: int) -> str:
    """Fallback: pembaca pihak ketiga yang mengubah halaman jadi markdown bersih."""
    response = requests.get(
        f"https://r.jina.ai/{url}",
        headers={"User-Agent": _USER_AGENT, "Accept-Language": "id-ID,id;q=0.9"},
        timeout=35,
    )
    if response.status_code != 200:
        raise WebSearchError(f"Pembaca cadangan gagal (HTTP {response.status_code}).")

    teks = response.text or ""

    # Jina menuliskan URL final; kalau situs me-redirect ke halaman error, tolak
    m = re.search(r"^Final URL:\s*(\S+)", teks, flags=re.M)
    if m:
        final = m.group(1).lower()
        pola_error = ("404", "not-found", "notfound", "error", "blocked", "captcha", "denied")
        if any(p in final for p in pola_error) and final != url.lower():
            raise WebSearchError("Halaman dialihkan ke halaman error.")

    # Buang header metadata jina
    teks = re.sub(
        r"^(Title|URL Source|Published Time|Final URL|Markdown Content):.*$",
        "",
        teks,
        flags=re.M,
    )
    teks = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", teks)  # buang gambar markdown
    teks = re.sub(r"\n{3,}", "\n\n", teks).strip()
    if not teks:
        raise WebSearchError("Halaman kosong.")
    return teks[:maks]


def baca_halaman(url: str, maks_karakter: int = 2500) -> str:
    """Ambil teks utama sebuah halaman web."""
    url = (url or "").strip()
    if not url:
        raise WebSearchError("URL kosong.")

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise WebSearchError("Hanya URL http/https yang didukung.")

    if not _host_aman(parsed.hostname or ""):
        raise WebSearchError("Alamat tersebut tidak diizinkan.")

    kunci = f"baca:{url}:{maks_karakter}"
    cached = _cache_get(kunci)
    if cached is not None:
        return cached

    kesalahan = None
    terbaik = None
    skor_terbaik = -999

    for pembaca in (_baca_langsung, _baca_jina):
        try:
            teks = pembaca(url, maks_karakter)
        except WebSearchError as e:
            kesalahan = e
            continue
        except requests.exceptions.Timeout:
            kesalahan = WebSearchError("Halaman terlalu lama direspons.")
            continue
        except requests.exceptions.RequestException as e:
            kesalahan = WebSearchError(f"Gagal membuka halaman: {e}")
            continue

        teks = _rapikan_isi(teks or "")
        if len(teks) < 120:
            kesalahan = WebSearchError("Isi halaman terlalu pendek untuk dibaca.")
            continue

        skor = _kualitas(teks)
        if skor > skor_terbaik:
            skor_terbaik, terbaik = skor, teks

        # Sudah bagus, tidak perlu pembaca cadangan
        if skor >= 30:
            break

    if terbaik is None:
        raise kesalahan or WebSearchError("Halaman tidak bisa dibaca.")

    if skor_terbaik < 0:
        raise WebSearchError("Halaman tidak berisi artikel yang bisa dibaca (mungkin 404 atau diblokir).")

    if len(terbaik) > maks_karakter:
        terbaik = terbaik[:maks_karakter].rstrip() + " …"

    _cache_set(kunci, terbaik)
    return terbaik


# ==================== SKEMA TOOL ====================

SKEMA_WEB_SEARCH = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Cari informasi di internet. Pakai untuk berita terkini, harga, jadwal, "
            "skor, kejadian terbaru, atau fakta yang perlu diverifikasi. "
            "Bisa dipakai untuk topik apa pun."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Kata kunci pencarian yang spesifik. Sertakan konteks seperti "
                        "tahun, nama tempat, atau merek bila relevan."
                    ),
                }
            },
            "required": ["query"],
        },
    },
}

SKEMA_BACA_HALAMAN = {
    "type": "function",
    "function": {
        "name": "baca_halaman",
        "description": (
            "Ambil isi teks sebuah halaman web. Pakai setelah web_search kalau "
            "ringkasan hasil pencarian belum cukup untuk menjawab."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL lengkap http/https dari hasil pencarian.",
                }
            },
            "required": ["url"],
        },
    },
}


def jalankan_tool(
    nama: str,
    argumen: dict,
    jumlah: int = 5,
    maks_karakter: int = 2500,
) -> str:
    """Jalankan tool yang diminta model, kembalikan teks untuk dikirim balik.

    ``jumlah`` dan ``maks_karakter`` bisa diperbesar untuk admin yang butuh
    riset lebih dalam. Keduanya tetap punya batas atas di pemanggil.
    """
    if nama == "web_search":
        query = str(argumen.get("query") or "").strip()
        if not query:
            return "Query kosong."

        hasil = cari(query, jumlah=jumlah)
        if not hasil:
            return (
                f"Tidak ada hasil relevan untuk '{query}'. "
                "Coba query yang lebih spesifik atau jawab dari pengetahuan sendiri."
            )

        baris = [f"Hasil pencarian untuk: {query}"]
        for i, h in enumerate(hasil, 1):
            baris.append(
                f"\n[{i}] {h['judul']}\nSumber: {_domain(h['url'])}\nURL: {h['url']}"
                f"\nRingkasan: {h['ringkas'][:240]}"
            )
        return "\n".join(baris)

    if nama == "baca_halaman":
        url = str(argumen.get("url") or "").strip()
        try:
            teks = baca_halaman(url, maks_karakter=maks_karakter)
        except WebSearchError as e:
            return f"Gagal membaca halaman: {e}"
        return f"Isi halaman {url}:\n\n{teks}"

    return f"Tool tidak dikenal: {nama}"

