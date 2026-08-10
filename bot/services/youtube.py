import yt_dlp
import os

def download_youtube_video(url: str, output_path: str = "./downloads") -> str:
    """
    Mendownload video YouTube dan mengembalikan path file video tersebut.
    """
    # Memastikan folder downloads tersedia
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    # Konfigurasi yt-dlp (Mencari video dengan ukuran maksimal mendekati 50MB karena limit Telegram)
    ydl_opts = {
        'format': 'best[filesize<50M]/best', 
        'outtmpl': f'{output_path}/%(title)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Mengambil info dan mendownload
            info_dict = ydl.extract_info(url, download=True)
            # Mendapatkan nama file hasil download
            file_path = ydl.prepare_filename(info_dict)
            return file_path
    except Exception as e:
        print(f"Error downloading YouTube video: {e}")
        return None
