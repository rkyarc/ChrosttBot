"""YouTube downloader berbasis yt-dlp.

Catatan penting: YouTube saat ini TIDAK lagi menyediakan format progresif
(video+audio menyatu) untuk sebagian besar video. Semua format video bersifat
video-only, jadi audio harus diunduh terpisah lalu digabung ffmpeg.

Semua hasil dibatasi 50MB karena itu batas upload Bot API Telegram.
"""

import os
import re
import shutil
import tempfile

import yt_dlp

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_MB = MAX_UPLOAD_BYTES // 1048576

# Batas durasi agar tidak mencoba mengunduh video 3 jam
_MAX_DURASI = 3600


class YouTubeDownloadError(Exception):
    """Error yang aman ditampilkan ke pengguna."""


class YouTubeSearchError(Exception):
    """Pencarian YouTube gagal atau tidak ada hasil."""


def ffmpeg_tersedia() -> bool:
    return bool(shutil.which("ffmpeg"))


def _opsi_dasar() -> dict:
    opsi = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "restrictfilenames": True,
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 3,
        "nocheckcertificate": True,
        # Batasi agar tidak menarik live stream tanpa akhir
        "match_filter": yt_dlp.utils.match_filter_func("!is_live"),
    }
    ff = shutil.which("ffmpeg")
    if ff:
        opsi["ffmpeg_location"] = os.path.dirname(ff)
    return opsi


def _pesan_error(e: Exception) -> str:
    """Terjemahkan error yt-dlp jadi pesan yang bisa dibaca."""
    teks = str(e)
    rendah = teks.lower()

    if "requested format is not available" in rendah:
        return "Format video tidak tersedia. Coba video lain."
    if "video unavailable" in rendah or "not available" in rendah:
        return "Video tidak tersedia, privat, atau sudah dihapus."
    if "private video" in rendah:
        return "Video ini privat, tidak bisa diunduh."
    if "sign in" in rendah or ("age" in rendah and "confirm" in rendah):
        return "Video ini butuh login/verifikasi umur, tidak bisa diunduh."
    if "is_live" in rendah or "live event" in rendah:
        return "Live stream tidak didukung."
    if "timed out" in rendah or "timeout" in rendah:
        return "Koneksi ke YouTube timeout. Coba lagi."
    if "urlopen error" in rendah or "getaddrinfo" in rendah:
        return "Tidak bisa menghubungi YouTube. Cek koneksi internet."
    if "copyright" in rendah or "blocked" in rendah:
        return "Video diblokir di wilayah server ini."
    if "ffmpeg" in rendah or "ffprobe" in rendah:
        return "ffmpeg tidak ditemukan, tidak bisa menggabung video+audio."

    # Ambil baris ERROR: ... kalau ada, tanpa prefix teknisnya
    for baris in teks.splitlines():
        bersih = baris.strip()
        if bersih.startswith("ERROR:"):
            bersih = bersih[len("ERROR:"):].strip()
            # Buang "[youtube] <id>:" di depan pesan
            bersih = re.sub(r"^\[[^\]]+\]\s*[^:]*:\s*", "", bersih)
            return bersih[:200]

    return teks[:200] or "Gagal mengunduh video."


# ==================== PENCARIAN ====================

def cari_video(query: str, jumlah: int = 1) -> list[dict]:
    """Cari video YouTube, kembalikan metadata ringkas."""
    query = (query or "").strip()
    if not query:
        raise YouTubeSearchError("Query pencarian kosong.")

    opsi = _opsi_dasar()
    opsi.update({"extract_flat": True, "skip_download": True})

    try:
        with yt_dlp.YoutubeDL(opsi) as ydl:
            info = ydl.extract_info(f"ytsearch{jumlah}:{query}", download=False)
    except Exception as e:
        raise YouTubeSearchError(_pesan_error(e))

    entries = (info or {}).get("entries") or []
    hasil = []
    for entry in entries:
        if not entry:
            continue
        vid = entry.get("id")
        if not vid:
            continue
        hasil.append(
            {
                "id": vid,
                "judul": entry.get("title") or "(tanpa judul)",
                "channel": entry.get("uploader") or entry.get("channel") or "",
                "durasi": entry.get("duration") or 0,
                "views": entry.get("view_count") or 0,
                "url": f"https://www.youtube.com/watch?v={vid}",
                "thumbnail": entry.get("thumbnail") or "",
            }
        )

    if not hasil:
        raise YouTubeSearchError(f"Tidak ada hasil untuk '{query}'.")

    return hasil


# ==================== UNDUHAN ====================

def _cek_durasi(url: str) -> dict:
    """Ambil metadata tanpa mengunduh, untuk cek durasi & ketersediaan.

    Penting: tanpa ini, video 10 jam akan diunduh dulu (ratusan MB)
    sebelum ditolak.
    """
    opsi = _opsi_dasar()
    opsi["skip_download"] = True

    try:
        with yt_dlp.YoutubeDL(opsi) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        raise YouTubeDownloadError(_pesan_error(e))

    if not info:
        raise YouTubeDownloadError("Video tidak bisa dibaca.")

    if info.get("is_live"):
        raise YouTubeDownloadError("Live stream tidak didukung.")

    durasi = info.get("duration") or 0
    if durasi > _MAX_DURASI:
        raise YouTubeDownloadError(
            f"Video terlalu panjang ({_format_durasi(durasi)}). "
            "Maksimal 1 jam agar tidak melebihi batas 50MB."
        )

    return info


def download_youtube_video(url: str, output_path: str = None) -> str:
    """Unduh video YouTube (video+audio digabung) maksimal 50MB."""
    if not ffmpeg_tersedia():
        raise YouTubeDownloadError(
            "ffmpeg tidak ditemukan. Pasang ffmpeg untuk mengunduh video YouTube."
        )

    # Cek durasi dulu supaya video raksasa tidak diunduh percuma
    _cek_durasi(url)

    folder = output_path or tempfile.mkdtemp(prefix="chrostt-yt-")
    os.makedirs(folder, exist_ok=True)

    opsi = _opsi_dasar()
    opsi.update(
        {
            # Ambil video terbaik <=50MB, lalu audio terbaik, gabung ke mp4.
            # filesize kadang kosong, jadi pakai filesize_approx sebagai cadangan
            # dan biarkan max_filesize sebagai jaring pengaman.
            "format": (
                f"bestvideo[filesize<{MAX_MB}M][ext=mp4]+bestaudio[ext=m4a]/"
                f"bestvideo[filesize<{MAX_MB}M]+bestaudio/"
                f"bestvideo+bestaudio/best"
            ),
            "merge_output_format": "mp4",
            "outtmpl": os.path.join(folder, "%(title).120B-%(id)s.%(ext)s"),
            "max_filesize": MAX_UPLOAD_BYTES,
            "postprocessors": [
                # Pastikan hasil akhir mp4 agar bisa diputar di Telegram
                {"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"},
            ],
        }
    )

    try:
        with yt_dlp.YoutubeDL(opsi) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as e:
        raise YouTubeDownloadError(_pesan_error(e))

    if not info:
        raise YouTubeDownloadError("Video tidak bisa diproses.")

    path = _cari_file_hasil(folder, info.get("id", ""))
    if not path:
        raise YouTubeDownloadError(
            "File hasil unduhan tidak ditemukan. "
            "Kemungkinan video melebihi batas 50MB."
        )

    ukuran = os.path.getsize(path)
    if ukuran > MAX_UPLOAD_BYTES:
        _hapus(path)
        raise YouTubeDownloadError(
            f"Ukuran video {ukuran // 1048576}MB melebihi batas upload Telegram "
            "(50MB). Coba video yang lebih pendek."
        )

    return path


def download_youtube_audio(url: str, output_path: str = None) -> str:
    """Unduh audio YouTube sebagai MP3 maksimal 50MB."""
    if not ffmpeg_tersedia():
        raise YouTubeDownloadError(
            "ffmpeg tidak ditemukan. Pasang ffmpeg untuk mengunduh audio."
        )

    folder = output_path or tempfile.mkdtemp(prefix="chrostt-yta-")
    os.makedirs(folder, exist_ok=True)

    opsi = _opsi_dasar()
    opsi.update(
        {
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": os.path.join(folder, "%(title).120B-%(id)s.%(ext)s"),
            "max_filesize": MAX_UPLOAD_BYTES,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "128",
                }
            ],
        }
    )

    try:
        with yt_dlp.YoutubeDL(opsi) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as e:
        raise YouTubeDownloadError(_pesan_error(e))

    if not info:
        raise YouTubeDownloadError("Audio tidak bisa diproses.")

    path = _cari_file_hasil(folder, info.get("id", ""), ekstensi=".mp3")
    if not path:
        raise YouTubeDownloadError("File audio hasil unduhan tidak ditemukan.")

    if os.path.getsize(path) > MAX_UPLOAD_BYTES:
        _hapus(path)
        raise YouTubeDownloadError("Audio melebihi batas upload Telegram (50MB).")

    return path


# ==================== HELPER ====================

def _cari_file_hasil(folder: str, video_id: str, ekstensi: str = None):
    """Cari file hasil di folder (nama bisa berubah setelah post-processing)."""
    kandidat = []
    for nama in os.listdir(folder):
        path = os.path.join(folder, nama)
        if not os.path.isfile(path):
            continue
        if video_id and video_id not in nama:
            continue
        if ekstensi and not nama.lower().endswith(ekstensi):
            continue
        kandidat.append(path)

    if not kandidat:
        # Fallback: file apa pun yang bukan part/temp
        for nama in os.listdir(folder):
            if nama.endswith((".part", ".ytdl", ".temp")):
                continue
            path = os.path.join(folder, nama)
            if os.path.isfile(path):
                kandidat.append(path)

    if not kandidat:
        return None

    return max(kandidat, key=os.path.getsize)


def _format_durasi(detik) -> str:
    detik = int(detik or 0)
    jam, sisa = divmod(detik, 3600)
    menit, detik = divmod(sisa, 60)
    if jam:
        return f"{jam}j {menit}m"
    if menit:
        return f"{menit}m {detik}d"
    return f"{detik} detik"


def _hapus(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def bersihkan_folder(path: str) -> None:
    """Hapus folder unduhan beserta isinya."""
    try:
        if path and os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
    except OSError:
        pass


def folder_sementara(prefix: str = "chrostt-yt-") -> str:
    return tempfile.mkdtemp(prefix=prefix)
