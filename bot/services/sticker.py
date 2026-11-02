"""Konversi media jadi stiker Telegram, dan sebaliknya.

Semua pemrosesan memakai ffmpeg, jadi tidak perlu Pillow.

Batasan stiker Telegram yang dipatuhi:
- statis: WebP 512x512, maks 512 KB
- animasi: WebP animasi, maks 512 KB, durasi maks 3 detik
"""

import os
import re
import shutil
import subprocess
import tempfile


class StickerError(Exception):
    """Error yang aman ditampilkan ke pengguna."""


MAX_STATIC_BYTES = 512 * 1024
# Stiker video (WEBM VP9) dibatasi Telegram lebih ketat: 256 KB
MAX_ANIM_BYTES = 256 * 1024
SISI = 512
DURASI_ANIM = 3.0
FPS_ANIM = 30

# Stiker statis tidak punya durasi. Saat dijadikan MP4, frame tunggal itu
# diberi durasi supaya hasilnya bisa diputar (sebelumnya cuma 0,04 detik).
DURASI_MP4_STATIS = 3.0

# Batas media masuk yang mau diproses (hindari OOM/CPU lama)
MAX_INPUT_BYTES = 50 * 1024 * 1024

_FFMPEG = shutil.which("ffmpeg")
_FFPROBE = shutil.which("ffprobe")


def tersedia() -> bool:
    return bool(_FFMPEG and _FFPROBE)


def _jalankan(perintah: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    try:
        hasil = subprocess.run(
            perintah,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise StickerError("Proses konversi terlalu lama. Coba media yang lebih kecil.")
    except OSError as e:
        raise StickerError(f"Gagal menjalankan ffmpeg: {e}")
    return hasil


def _error_ffmpeg(hasil: subprocess.CompletedProcess) -> str:
    pesan = (hasil.stderr or b"").decode("utf-8", "replace")
    # Ambil baris terakhir yang biasanya berisi penyebab
    baris = [b.strip() for b in pesan.splitlines() if b.strip()]
    return baris[-1][:200] if baris else "ffmpeg gagal tanpa keterangan."


def _hitung_durasi_frame(path: str) -> float:
    """Hitung durasi dari jumlah frame; ffprobe tidak melaporkan WebP animasi."""
    hasil = _jalankan(
        [
            _FFPROBE,
            "-v", "error",
            "-select_streams", "v:0",
            "-count_frames",
            "-show_entries", "stream=nb_read_frames,avg_frame_rate",
            "-of", "default=noprint_wrappers=1",
            path,
        ],
        timeout=30,
    )
    if hasil.returncode != 0:
        return 0.0

    teks = hasil.stdout.decode("utf-8", "replace")
    nb = re.search(r"nb_read_frames=(\d+)", teks)
    fps = re.search(r"avg_frame_rate=(\d+)/(\d+)", teks)
    if not nb or not fps:
        return 0.0

    pembilang, penyebut = int(fps.group(1)), int(fps.group(2))
    if pembilang <= 0 or penyebut <= 0:
        return 0.0

    return int(nb.group(1)) * penyebut / pembilang


def info_media(path: str) -> dict:
    """Ambil durasi dan ada/tidaknya video stream."""
    hasil = _jalankan(
        [
            _FFPROBE,
            "-v", "error",
            "-show_entries",
            "format=duration:stream=codec_type,duration,nb_frames,avg_frame_rate",
            "-of", "default=noprint_wrappers=1",
            path,
        ],
        timeout=30,
    )
    if hasil.returncode != 0:
        raise StickerError("File tidak bisa dibaca. Pastikan formatnya didukung.")

    teks = hasil.stdout.decode("utf-8", "replace")
    tipe = set(re.findall(r"codec_type=(\w+)", teks))

    durasi = 0.0

    # WebP animasi tidak melaporkan duration di level format,
    # jadi hitung dari jumlah frame / fps.
    for nilai in re.findall(r"duration=([\d.]+)", teks):
        try:
            durasi = max(durasi, float(nilai))
        except ValueError:
            continue

    if durasi <= 0:
        nb = re.search(r"nb_frames=(\d+)", teks)
        fps = re.search(r"avg_frame_rate=(\d+)/(\d+)", teks)
        if nb and fps:
            pembilang, penyebut = int(fps.group(1)), int(fps.group(2))
            if pembilang > 0 and penyebut > 0:
                durasi = int(nb.group(1)) * penyebut / pembilang

    # WebP animasi melaporkan durasi N/A, jadi frame dihitung langsung.
    if durasi <= 0:
        durasi = _hitung_durasi_frame(path)

    return {
        "durasi": durasi,
        "ada_video": "video" in tipe,
        "ada_audio": "audio" in tipe,
    }


# ==================== KE STIKER ====================

def _filter_skala() -> str:
    """Skala ke sisi terpanjang 512 tanpa memotong, jaga rasio & transparansi."""
    return (
        f"scale={SISI}:{SISI}:force_original_aspect_ratio=decrease:"
        "flags=lanczos"
    )


def gambar_ke_stiker(sumber: str, tujuan_dir: str) -> str:
    """Foto -> stiker WebP statis."""
    keluaran = os.path.join(tujuan_dir, "stiker.webp")

    # Kualitas diturunkan bertahap kalau melebihi batas ukuran
    for kualitas in (90, 75, 60, 45):
        hasil = _jalankan(
            [
                _FFMPEG, "-y",
                "-i", sumber,
                "-vf", _filter_skala(),
                "-frames:v", "1",
                "-c:v", "libwebp",
                "-lossless", "0",
                "-q:v", str(kualitas),
                "-compression_level", "6",
                keluaran,
            ]
        )
        if hasil.returncode != 0:
            raise StickerError(_error_ffmpeg(hasil))

        if os.path.getsize(keluaran) <= MAX_STATIC_BYTES:
            return keluaran

    raise StickerError("Gambar tetap terlalu besar setelah dikompres. Coba foto lain.")


def video_ke_stiker(sumber: str, tujuan_dir: str, mulai: float = 0.0) -> str:
    """Video -> stiker video WEBM VP9.

    Telegram TIDAK menerima animated WebP untuk sendSticker; format stiker
    bergerak yang sah adalah .WEBM dengan codec VP9, maks 256 KB, tanpa audio,
    durasi maks 3 detik, sisi terpanjang 512 px.
    """
    keluaran = os.path.join(tujuan_dir, "stiker.webm")

    # Bitrate diturunkan bertahap sampai di bawah batas 256 KB
    for fps, bitrate in ((30, "420k"), (24, "320k"), (20, "240k"), (15, "160k")):
        hasil = _jalankan(
            [
                _FFMPEG, "-y",
                "-ss", f"{max(mulai, 0):.2f}",
                # -t diletakkan setelah -i supaya pasti membatasi output. Kalau
                # sebelum -i, sebagian input (GIF/WebP animasi) mengabaikannya
                # dan hasilnya cuma 1 frame sehingga stiker tidak bergerak.
                "-i", sumber,
                "-t", f"{DURASI_ANIM:.2f}",
                "-vf", f"fps={fps},scale={SISI}:{SISI}:"
                       "force_original_aspect_ratio=decrease:flags=lanczos,"
                       "format=yuv420p",
                "-c:v", "libvpx-vp9",
                "-b:v", bitrate,
                "-deadline", "good",
                "-cpu-used", "4",
                "-row-mt", "1",
                "-pix_fmt", "yuv420p",
                "-an",
                keluaran,
            ],
            timeout=300,
        )
        if hasil.returncode != 0:
            raise StickerError(_error_ffmpeg(hasil))

        if os.path.getsize(keluaran) <= MAX_ANIM_BYTES:
            return keluaran

    raise StickerError(
        "Video terlalu berat untuk jadi stiker 256 KB. "
        "Coba video yang lebih pendek atau sederhana (sedikit gerakan)."
    )


def buat_stiker(sumber: str, tujuan_dir: str, mulai: float = 0.0) -> tuple[str, str]:
    """Deteksi otomatis foto/video lalu konversi. Return (path, jenis)."""
    if not tersedia():
        raise StickerError(
            "ffmpeg tidak ditemukan di server. Fitur stiker butuh ffmpeg terpasang."
        )

    if os.path.getsize(sumber) > MAX_INPUT_BYTES:
        raise StickerError("File melebihi 50MB, tidak diproses.")

    info = info_media(sumber)

    if info["ada_video"] and info["durasi"] > 0.05:
        return video_ke_stiker(sumber, tujuan_dir, mulai), "animasi"

    return gambar_ke_stiker(sumber, tujuan_dir), "statis"


# ==================== DARI STIKER ====================

def _filter_media(kotak: bool = False) -> str:
    """Skala ke sisi terpanjang 512 dengan dimensi genap.

    H.264 menolak lebar/tinggi ganjil, dan ``force_original_aspect_ratio``
    bisa menghasilkan angka ganjil (mis. 512x333), jadi hasilnya dibulatkan
    ke bawah ke bilangan genap.
    """
    dasar = f"scale={SISI}:{SISI}:force_original_aspect_ratio=decrease:flags=lanczos"
    if kotak:
        # Kanvas persegi 512x512 dengan latar transparan, supaya semua stiker
        # keluar dengan ukuran sama tanpa memotong isinya.
        return (
            f"{dasar},scale=trunc(iw/2)*2:trunc(ih/2)*2,"
            f"pad={SISI}:{SISI}:(ow-iw)/2:(oh-ih)/2:color=black@0"
        )
    return f"{dasar},scale=trunc(iw/2)*2:trunc(ih/2)*2"


def _durasi(path: str) -> float:
    """Durasi media dalam detik, 0.0 kalau tidak bisa dibaca."""
    try:
        return float(info_media(path)["durasi"] or 0.0)
    except (StickerError, TypeError, ValueError):
        return 0.0


def stiker_ke_png(sumber: str, tujuan_dir: str) -> str:
    """Stiker (webp/webm) -> PNG frame pertama.

    WEBM VP9 dari Telegram tidak menyimpan alpha, sedangkan WEBP statis bisa.
    PNG keluarannya tetap RGBA supaya konsisten.
    """
    if not tersedia():
        raise StickerError("ffmpeg tidak ditemukan di server. Fitur ini butuh ffmpeg.")
    if not os.path.isfile(sumber):
        raise StickerError("Media tidak ditemukan. Kirim ulang stikernya.")

    keluaran = os.path.join(tujuan_dir, "hasil.png")
    hasil = _jalankan(
        [
            _FFMPEG, "-y",
            "-i", sumber,
            "-vf", f"{_filter_media()},format=rgba",
            "-frames:v", "1",
            "-update", "1",
            keluaran,
        ],
        timeout=120,
    )
    if hasil.returncode != 0:
        raise StickerError(_error_ffmpeg(hasil))
    if not os.path.exists(keluaran) or os.path.getsize(keluaran) == 0:
        raise StickerError("Konversi PNG gagal menghasilkan file.")
    return keluaran


def stiker_ke_mp4(sumber: str, tujuan_dir: str) -> str:
    """Stiker -> MP4 H.264 yang benar-benar bisa diputar.

    Dua kasus dibedakan karena perilakunya berbeda:

    - **Stiker bergerak** (WEBM VP9 / WEBP animasi): semua frame dipertahankan.
    - **Stiker statis** (WEBP satu frame): frame tunggal itu diberi durasi
      ``DURASI_MP4_STATIS``. Sebelumnya frame tunggal ikut di-encode apa adanya,
      jadi hasilnya video 0,04 detik yang di Telegram tampak seperti gambar rusak.

    Latar transparan diratakan ke putih karena MP4 H.264 tidak mendukung alpha.
    """
    if not tersedia():
        raise StickerError("ffmpeg tidak ditemukan di server. Fitur ini butuh ffmpeg.")
    if not os.path.isfile(sumber):
        raise StickerError("Media tidak ditemukan. Kirim ulang stikernya.")

    keluaran = os.path.join(tujuan_dir, "hasil.mp4")

    # Ratakan alpha ke putih lalu encode H.264.
    rata_putih = (
        f"{_filter_media()},format=rgba,"
        "split[isi][latar];[latar]drawbox=c=white:t=fill[bg];[bg][isi]overlay=shortest=1,"
        "format=yuv420p"
    )

    if _durasi(sumber) <= 0.05:
        # Stiker statis: putar frame tunggal selama beberapa detik.
        perintah = [
            _FFMPEG, "-y",
            "-loop", "1",
            "-t", f"{DURASI_MP4_STATIS:.2f}",
            "-i", sumber,
            "-vf", rata_putih,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-r", str(FPS_ANIM),
            "-an",
            "-movflags", "+faststart",
            keluaran,
        ]
    else:
        perintah = [
            _FFMPEG, "-y",
            "-i", sumber,
            "-vf", rata_putih,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-an",
            "-movflags", "+faststart",
            keluaran,
        ]

    hasil = _jalankan(perintah, timeout=240)
    if hasil.returncode != 0:
        # Fallback: encode langsung tanpa meratakan alpha (WEBM Telegram tidak
        # menyimpan alpha, jadi langkah overlay tidak diperlukan).
        fallback = [p for p in perintah]
        idx = fallback.index("-vf") + 1
        fallback[idx] = f"{_filter_media()},format=yuv420p"
        hasil = _jalankan(fallback, timeout=240)
        if hasil.returncode != 0:
            raise StickerError(_error_ffmpeg(hasil))

    if not os.path.exists(keluaran) or os.path.getsize(keluaran) == 0:
        raise StickerError("Konversi MP4 gagal menghasilkan file.")
    return keluaran


def folder_sementara() -> str:
    return tempfile.mkdtemp(prefix="chrostt-stiker-")
