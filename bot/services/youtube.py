import yt_dlp
import os
import tempfile

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class YouTubeDownloadError(Exception):
    pass


def download_youtube_video(url: str, output_path: str = None) -> str:
    """
    Mendownload video YouTube dan mengembalikan path file video tersebut.

    Video dibatasi di bawah 50MB karena itu batas upload Bot API Telegram.
    Kalau ukurannya tidak bisa dipastikan, hasil download dicek ulang setelah selesai.
    """
    folder = output_path or tempfile.mkdtemp(prefix="chrostt-yt-")

    if not os.path.exists(folder):
        os.makedirs(folder)

    ydl_opts = {
        # Batasi ke format progresif (video+audio menyatu) agar tidak perlu ffmpeg
        "format": (
            f"best[filesize<{MAX_UPLOAD_BYTES // 1048576}M][ext=mp4]/"
            f"best[filesize<{MAX_UPLOAD_BYTES // 1048576}M]/best[ext=mp4]/best"
        ),
        "outtmpl": os.path.join(folder, "%(title).150B-%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "restrictfilenames": True,
        "max_filesize": MAX_UPLOAD_BYTES,
        "socket_timeout": 30,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info_dict)
    except Exception as e:
        raise YouTubeDownloadError(f"Gagal mengunduh video: {e}")

    if not os.path.exists(file_path):
        raise YouTubeDownloadError("File hasil unduhan tidak ditemukan.")

    if os.path.getsize(file_path) > MAX_UPLOAD_BYTES:
        os.remove(file_path)
        raise YouTubeDownloadError(
            "Ukuran video melebihi batas upload Telegram (50MB). Coba video lain yang lebih pendek."
        )

    return file_path
