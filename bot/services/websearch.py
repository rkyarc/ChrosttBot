"""Web search dan pembacaan halaman untuk Chrostt AI.

Strategi:
1. Tanya beberapa backend `ddgs` sekaligus (duckduckgo, yahoo, brave, mojeek)
   lalu gabungkan hasilnya. Nama backend divalidasi terhadap engine yang benar
   benar terpasang, karena daftar engine berubah antar versi ddgs.
2. Berita: ddgs news (bing + duckduckgo + yahoo) lalu Google News RSS.
3. Ensiklopedia: Wikipedia API (id lalu en).
4. Setiap hasil diberi tanggal bila sumbernya menyediakannya, supaya model
   bisa membedakan info baru dan lama.
5. Semua hasil difilter skor relevansi, dedup per URL, dan dibatasi per domain.
6. Baca halaman: fetch langsung, fallback ke r.jina.ai (markdown bersih).

Semua akses keluar dibatasi supaya model tidak bisa disuruh membuka alamat
internal (SSRF).
"""

import html
import ipaddress
import logging
import re
import socket
import time
import urllib.parse
from datetime import datetime, timezone

import requests

try:
    from ddgs import DDGS
    from ddgs.engines import ENGINES as _DDGS_ENGINES
except ImportError:  # pragma: no cover - ddgs opsional saat runtime
    DDGS = None
    _DDGS_ENGINES = {}

log = logging.getLogger("chrosttbot.websearch")

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
    "gacor",
    "maxwin",
    "togel",
)

_CACHE_TTL = 600
_CACHE_MAKS = 120

# Backend diuji berulang terhadap query Indonesia nyata. `auto` memang cukup
# andal tetapi memanggil semua engine (2,5 detik); pasangan di bawah memberi
# hasil sama dengan waktu jauh lebih singkat. Kandidat kedua dipakai kalau
# percobaan pertama kena rate limit.
_KANDIDAT_TEXT = (("duckduckgo", "yahoo"), ("brave", "mojeek", "yahoo"))
_KANDIDAT_NEWS = (("bing", "yahoo"), ("duckduckgo", "yahoo"))

# Batas waktu per percobaan pencarian (detik)
_TIMEOUT_DDGS = 12

# Batas waktu saat mengambil tanggal dari halaman hasil
_TIMEOUT_TANGGAL = 6

# Kata yang terlalu umum untuk dihitung sebagai kata kunci pencarian.
_STOPWORD = frozenset(
    [
        "dan", "atau", "yang", "untuk", "dengan", "dari", "pada", "ini", "itu",
        "apa", "adalah", "cara", "bagaimana", "siapa", "kapan", "dimana",
        "mengapa", "berapa", "hari", "tadi", "malam", "besok", "kemarin",
        "the", "and", "for", "with", "from", "what", "how", "who", "when",
        "where", "why", "which", "is", "are", "of", "to", "in", "on", "at",
        "today", "now", "latest", "update",
    ]
)

# Kata yang menandakan pengguna mencari info terkini, dipakai untuk memilih
# timelimit dan memberi prioritas pada berita.
_KATA_TERKINI = (
    "hari ini", "tadi malam", "kemarin", "terbaru", "terkini", "sekarang",
    "malam ini", "pagi ini", "siang ini", "besok", "minggu ini", "bulan ini",
    "tahun ini", "harga", "skor", "jadwal", "cuaca", "gempa", "kurs", "hasil",
    "breaking", "today", "current", "latest", "now", "live", "score",
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


class WebSearchError(Exception):
    """Error yang aman ditampilkan ke model/pengguna."""


# ==================== CACHE ====================

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


def _kosongkan_cache() -> None:
    """Dipakai test supaya hasil tidak bocor antar kasus."""
    _cache.clear()


# ==================== UTIL ====================

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


def _bersihkan_html(teks: str) -> str:
    teks = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", teks or "", flags=re.S)
    teks = re.sub(r"<(script|style|noscript)\b.*?</\1>", " ", teks, flags=re.S | re.I)
    teks = re.sub(r"<[^>]+>", " ", teks)
    teks = html.unescape(teks)
    return re.sub(r"\s+", " ", teks).strip()


# ==================== TANGGAL ====================

def _parse_tanggal(nilai) -> datetime | None:
    """Normalisasi tanggal dari berbagai format jadi datetime UTC.

    Sumber berita memberi format berbeda: ISO 8601 dari ddgs, RFC 822 dari
    RSS, dan teks bebas seperti "2 jam yang lalu". Yang tidak bisa dipahami
    diabaikan, bukan ditebak.
    """
    if not nilai:
        return None

    if isinstance(nilai, datetime):
        return nilai if nilai.tzinfo else nilai.replace(tzinfo=timezone.utc)

    teks = str(nilai).strip()
    if not teks:
        return None

    # ISO 8601 (2026-11-02T01:00:00+00:00)
    bersih = teks.replace("Z", "+00:00")
    try:
        hasil = datetime.fromisoformat(bersih)
        return hasil if hasil.tzinfo else hasil.replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    # RFC 822 (Mon, 02 Nov 2026 08:00:00 GMT) — format RSS
    for pola in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M %z",
    ):
        try:
            hasil = datetime.strptime(teks, pola)
            return hasil if hasil.tzinfo else hasil.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    # Tanggal saja (2026-11-02 atau 2 November 2026)
    for pola in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(teks[:20], pola).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    # Relatif: "2 hours ago", "3 hari yang lalu"
    cocok = re.search(r"(\d+)\s*(menit|jam|hari|minggu|minute|hour|day|week)", teks, re.I)
    if cocok:
        jumlah = int(cocok.group(1))
        satuan = cocok.group(2).lower()
        detik = {
            "menit": 60, "minute": 60,
            "jam": 3600, "hour": 3600,
            "hari": 86400, "day": 86400,
            "minggu": 604800, "week": 604800,
        }.get(satuan)
        if detik:
            return datetime.fromtimestamp(time.time() - jumlah * detik, timezone.utc)

    return None


def _format_tanggal(hasil: dict) -> str:
    """Tanggal + label umur, atau string kosong kalau tidak diketahui.

    Tanggal dari hasil pencarian sering berasal dari teks relatif ("2 hari
    lalu") yang dikonversi pustaka memakai waktu sekarang, sehingga jamnya
    palsu. Untuk sumber seperti itu hanya tanggalnya yang ditampilkan. Jam
    hanya ditampilkan kalau dibaca langsung dari halaman artikel.
    """
    waktu = hasil.get("waktu")
    if not isinstance(waktu, datetime):
        return ""

    sekarang = datetime.now(timezone.utc)
    umur = (sekarang - waktu).total_seconds()

    if umur < -3600:
        # Tanggal di masa depan biasanya salah di sumbernya (artikel terjadwal
        # atau zona waktu situs). Ditandai supaya model tidak menganggapnya
        # sebagai berita paling baru.
        return f"{waktu.strftime('%Y-%m-%d')} (tanggal tidak wajar: mendatang)"

    if umur < 0:
        label = "baru saja"
    elif umur < 3600:
        label = f"{max(1, int(umur // 60))} menit lalu"
    elif umur < 86400:
        label = f"{int(umur // 3600)} jam lalu"
    elif umur < 7 * 86400:
        label = f"{int(umur // 86400)} hari lalu"
    else:
        label = waktu.strftime("%d %b %Y")

    if hasil.get("waktu_dari_halaman"):
        return f"{waktu.strftime('%Y-%m-%d %H:%M UTC')} ({label}, dari halaman)"

    return f"{waktu.strftime('%Y-%m-%d')} ({label})"



# ==================== TANGGAL DARI HALAMAN ====================

# Tag meta yang lazim memuat tanggal terbit
_POLA_META_TANGGAL = (
    r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)',
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']article:published_time["\']',
    r'<meta[^>]+name=["\'](?:pubdate|publish-date|publication_date|date|DC.date(?:\.issued)?)["\']'
    r'[^>]+content=["\']([^"\']+)',
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\'](?:pubdate|publish-date|date)["\']',
    r'"datePublished"\s*:\s*"([^"]+)"',
    r'"dateModified"\s*:\s*"([^"]+)"',
    r'<time[^>]+datetime=["\']([^"\']+)',
)


def _tanggal_dari_html(teks: str) -> datetime | None:
    """Ambil tanggal terbit dari tag meta / JSON-LD sebuah halaman."""
    if not teks:
        return None

    for pola in _POLA_META_TANGGAL:
        for cocok in re.finditer(pola, teks, re.I):
            waktu = _parse_tanggal(cocok.group(1))
            if waktu:
                return waktu

    return None


def _lengkapi_tanggal(hasil: list[dict], terkini: bool) -> None:
    """Isi tanggal yang kosong dengan membaca halaman sumbernya (paralel).

    Hanya dijalankan untuk pertanyaan yang sensitif waktu. Untuk pertanyaan
    konseptual ("apa itu X") tanggal terbit tidak mengubah jawaban, jadi
    membaca beberapa halaman hanya menambah latensi tanpa manfaat.
    """
    if not terkini:
        return

    perlu = [h for h in hasil if h.get("waktu") is None][:3]
    if not perlu:
        return

    def ambil(h: dict) -> None:
        try:
            response = requests.get(
                h["url"], headers=_HEADERS, timeout=_TIMEOUT_TANGGAL, stream=True
            )
            if response.status_code != 200:
                return
            if "html" not in response.headers.get("content-type", ""):
                return

            # Tanggal biasanya ada di <head>; beberapa KB pertama cukup.
            potongan = b""
            for chunk in response.iter_content(chunk_size=8192):
                potongan += chunk
                if len(potongan) > 60_000:
                    break

            waktu = _tanggal_dari_html(potongan.decode("utf-8", "replace"))
            if waktu:
                h["waktu"] = waktu
                h["waktu_dari_halaman"] = True
        except requests.RequestException:
            return

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=len(perlu)) as executor:
        list(executor.map(ambil, perlu))



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


def _butuh_terkini(query: str) -> bool:
    """True kalau query terdengar mencari info yang berubah cepat."""
    rendah = (query or "").lower()
    return any(kata in rendah for kata in _KATA_TERKINI)


# ==================== ENGINE ddgs ====================

def _backend_tersedia(kategori: str, kandidat: tuple[str, ...]) -> str | None:
    """Kembalikan daftar backend yang benar-benar ada di versi ddgs aktif.

    Ini yang mencegah peringatan "backends do not exist or are disabled":
    daftar engine berubah antar versi (mis. google dihapus di ddgs 9.16), jadi
    backend harus dicek, bukan diasumsikan.
    """
    tersedia = _DDGS_ENGINES.get(kategori) or {}
    lolos = [nama for nama in kandidat if nama in tersedia]
    return ", ".join(lolos) if lolos else None


def _cari_ddgs(query: str, jumlah: int) -> list[dict]:
    """Cari teks lewat backend ddgs, digabung lalu didedup.

    Backend dikirim sebagai satu panggilan supaya ddgs mengumpulkan hasil
    paralel. Kalau gagal (rate limit), dicoba sekali lagi dengan set backend
    cadangan dan jeda.
    """
    if DDGS is None:
        return []

    timelimit = "w" if _butuh_terkini(query) else None

    for percobaan, tunggu in enumerate((0, 2.0)):
        if tunggu:
            time.sleep(tunggu)

        backend = _backend_tersedia("text", _KANDIDAT_TEXT[percobaan % 2])
        if not backend:
            continue

        try:
            with DDGS(timeout=_TIMEOUT_DDGS) as d:
                mentah = d.text(
                    query,
                    max_results=max(jumlah * 2, 8),
                    backend=backend,
                    region="id-id",
                    safesearch="moderate",
                    **({"timelimit": timelimit} if timelimit else {}),
                )
        except Exception as e:
            log.debug("ddgs text gagal (%s): %s", backend, e)
            continue

        hasil = []
        for item in mentah or []:
            judul = (item.get("title") or "").strip()
            url = (item.get("href") or item.get("url") or "").strip()
            ringkas = (item.get("body") or item.get("excerpt") or "").strip()
            if judul and url:
                hasil.append(
                    {
                        "judul": judul,
                        "url": url,
                        "ringkas": ringkas[:400],
                        "sumber": "web",
                        "waktu": _parse_tanggal(item.get("date")),
                    }
                )

        if hasil:
            return hasil

    return []


def _cari_berita_ddgs(query: str, jumlah: int) -> list[dict]:
    """Berita lewat ddgs news: hasilnya sudah bertanggal dan biasanya segar."""
    if DDGS is None:
        return []

    for percobaan, tunggu in enumerate((0, 1.5)):
        if tunggu:
            time.sleep(tunggu)

        backend = _backend_tersedia("news", _KANDIDAT_NEWS[percobaan % 2])
        if not backend:
            continue

        try:
            with DDGS(timeout=_TIMEOUT_DDGS) as d:
                mentah = d.news(
                    query,
                    max_results=max(jumlah * 2, 8),
                    backend=backend,
                    region="id-id",
                    safesearch="moderate",
                )
        except Exception as e:
            log.debug("ddgs news gagal (%s): %s", backend, e)
            continue

        hasil = []
        for item in mentah or []:
            judul = (item.get("title") or "").strip()
            url = (item.get("url") or item.get("href") or "").strip()
            if not judul or not url:
                continue

            sumber = (item.get("source") or "").strip()
            ringkas = (item.get("body") or "").strip()
            if sumber:
                ringkas = f"{sumber}. {ringkas}".strip()

            hasil.append(
                {
                    "judul": judul,
                    "url": url,
                    "ringkas": ringkas[:400],
                    "sumber": "berita",
                    "waktu": _parse_tanggal(item.get("date")),
                }
            )

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
                        "waktu": None,
                    }
                )
        except (requests.RequestException, ValueError):
            continue

        if hasil:
            break

    return hasil[:jumlah]


def _cari_berita_rss(query: str, jumlah: int) -> list[dict]:
    """Google News RSS: cadangan berita kalau ddgs news diblokir."""
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

        if judul_bersih:
            hasil.append(
                {
                    "judul": judul_bersih,
                    "url": link.group(1).strip(),
                    "ringkas": sumber.strip()[:400],
                    "sumber": "berita",
                    "waktu": _parse_tanggal(tanggal.group(1) if tanggal else None),
                }
            )

        if len(hasil) >= jumlah:
            break

    return hasil


# ==================== GABUNG HASIL ====================

def _gabung(kumpulan: list[dict], jumlah: int, terkini: bool) -> list[dict]:
    """Dedup per URL, batasi 2 hasil per domain, urutkan yang paling berguna.

    Skor akhir = relevansi kata kunci + bonus kesegaran. Kalau query mencari
    info terkini, hasil bertanggal baru naik; kalau tidak, kesegaran hanya
    jadi pemecah seri supaya artikel referensi tidak kalah oleh berita sehari.
    """
    sekarang = datetime.now(timezone.utc)
    unik: dict[str, dict] = {}

    for h in kumpulan:
        url = (h.get("url") or "").strip()
        if not url:
            continue
        kunci = url.split("#", 1)[0].rstrip("/").lower()
        lama = unik.get(kunci)
        # Simpan versi dengan ringkasan terpanjang untuk URL yang sama
        if lama is None or len(h.get("ringkas") or "") > len(lama.get("ringkas") or ""):
            unik[kunci] = h

    berperingkat = []
    for h in unik.values():
        skor = h.get("_skor", 0)
        bonus = 0.0

        waktu = h.get("waktu")
        if isinstance(waktu, datetime):
            umur_jam = max(0.0, (sekarang - waktu).total_seconds() / 3600)
            if umur_jam <= 24:
                bonus = 3.0 if terkini else 1.0
            elif umur_jam <= 72:
                bonus = 1.5 if terkini else 0.5
            elif umur_jam <= 168:
                bonus = 0.5 if terkini else 0.2
            elif terkini and umur_jam > 30 * 24:
                # Untuk pertanyaan "hari ini", artikel berumur bulanan tidak
                # boleh menang hanya karena judulnya mirip. Judul lama sering
                # memuat frasa identik ("Prakiraan Cuaca X Hari Ini").
                bonus = -8.0
            elif terkini:
                bonus = -2.0
        elif h.get("sumber") == "berita":
            # Berita tanpa tanggal tetap lebih segar daripada artikel statis
            bonus = 1.0 if terkini else 0.3

        berperingkat.append((skor + bonus, h))

    berperingkat.sort(key=lambda pasangan: pasangan[0], reverse=True)

    hasil, per_domain = [], {}
    for _, h in berperingkat:
        d = _domain(h["url"])
        if per_domain.get(d, 0) >= 2:
            continue
        per_domain[d] = per_domain.get(d, 0) + 1
        h.pop("_skor", None)
        hasil.append(h)
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
    terkini = _butuh_terkini(query)

    # Urutan sumber: berita dulu kalau query mencari info terkini, karena
    # halaman berita paling mungkin memuat angka/jadwal yang berlaku hari ini.
    # Wikipedia selalu jadi jaring terakhir: untuk pertanyaan konseptual ia
    # tetap memberi hasil walau semua engine teks sedang kena rate limit.
    sumber = (
        (_cari_berita_ddgs, _cari_ddgs, _cari_berita_rss, _cari_wikipedia)
        if terkini
        else (_cari_ddgs, _cari_wikipedia, _cari_berita_ddgs, _cari_berita_rss)
    )

    kumpulan: list[dict] = []
    for pencari in sumber:
        try:
            kumpulan.extend(pencari(query, jumlah))
        except Exception:
            log.debug("Sumber %s gagal", pencari.__name__, exc_info=True)
            continue

        for h in kumpulan:
            h["_skor"] = _skor(tokens, h.get("judul", ""), h.get("ringkas", ""), h["url"])

        relevan = [h for h in kumpulan if _layak(h, tokens, 1)]
        # Lanjut ke sumber berikutnya sampai hasilnya cukup. Berhenti lebih awal
        # membuat sumber paling relevan (mis. BMKG untuk cuaca) terlewat hanya
        # karena berita sudah memberi beberapa hasil.
        if len(relevan) >= jumlah:
            kumpulan = relevan
            break

    for h in kumpulan:
        h["_skor"] = _skor(tokens, h.get("judul", ""), h.get("ringkas", ""), h["url"])

    relevan = [h for h in kumpulan if _layak(h, tokens, 1)]
    if not relevan:
        _cache_set(kunci, [])
        return []

    # Hasil web search jarang membawa tanggal. Baca halaman kandidat teratas
    # lebih dulu supaya bonus kesegaran ikut menentukan peringkat, bukan hanya
    # label yang ditempel setelah urutan dikunci.
    relevan.sort(key=lambda h: h.get("_skor", 0), reverse=True)
    _lengkapi_tanggal(relevan, terkini)

    hasil = _gabung(relevan, jumlah, terkini)

    _cache_set(kunci, hasil)
    return hasil


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
        raise WebSearchError(
            "Halaman tidak berisi artikel yang bisa dibaca (mungkin 404 atau diblokir)."
        )

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
            "Cari informasi terbaru di internet. Pakai untuk berita, harga, jadwal, "
            "cuaca, skor, kurs, atau fakta yang berubah cepat dan perlu diverifikasi. "
            "Hasil sudah dilengkapi tanggal terbit bila sumbernya menyediakan."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Kata kunci spesifik. Sertakan tempat, nama, atau tanggal bila "
                        "relevan, mis. 'prakiraan cuaca Tuban 2 November 2026'."
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


def _baris_hasil(query: str, hasil: list[dict], terkini: bool) -> str:
    """Format hasil untuk dibaca model, lengkap dengan tanggal dan sumber."""
    catatan_waktu = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    baris = [f"Hasil pencarian untuk: {query}", f"Waktu pencarian: {catatan_waktu}"]

    if terkini:
        baris.append(
            "Catatan: query ini meminta info terkini, jadi hasil bertanggal baru "
            "diutamakan. Kalau tanggal hasil lebih lama dari hari ini, sebutkan "
            "tanggalnya di jawaban alih-alih menyajikannya sebagai kondisi sekarang."
        )

    for i, h in enumerate(hasil, 1):
        tanggal = _format_tanggal(h)
        baris.append(
            f"\n[{i}] {h['judul']}"
            f"\nSumber: {_domain(h['url'])}"
            + (f"\nTanggal: {tanggal}" if tanggal else "")
            + f"\nURL: {h['url']}"
            f"\nRingkasan: {(h.get('ringkas') or '')[:240]}"
        )

    return "\n".join(baris)


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

        return _baris_hasil(query, hasil, _butuh_terkini(query))

    if nama == "baca_halaman":
        url = str(argumen.get("url") or "").strip()
        try:
            teks = baca_halaman(url, maks_karakter=maks_karakter)
        except WebSearchError as e:
            return f"Gagal membaca halaman: {e}"
        return f"Isi halaman {url}:\n\n{teks}"

    return f"Tool tidak dikenal: {nama}"
