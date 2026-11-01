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
                "-t", f"{DURASI_ANIM:.2f}",
                "-i", sumber,
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

def stiker_ke_png(sumber: str, tujuan_dir: str) -> str:
    """Stiker (webp/webm) -> PNG frame pertama.

    WEBM VP9 dari Telegram tidak menyimpan alpha, sedangkan WEBP statis bisa.
    PNG keluarannya tetap RGBA supaya konsisten.
    """
    keluaran = os.path.join(tujuan_dir, "hasil.png")
    hasil = _jalankan(
        [
            _FFMPEG, "-y",
            "-i", sumber,
            "-vf", f"scale={SISI}:{SISI}:force_original_aspect_ratio=decrease:"
                   "flags=lanczos,format=rgba",
            "-frames:v", "1",
            keluaran,
        ],
        timeout=120,
    )
    if hasil.returncode != 0:
        raise StickerError(_error_ffmpeg(hasil))
    return keluaran


def stiker_ke_mp4(sumber: str, tujuan_dir: str) -> str:
    """Stiker bergerak (webm/webp animasi) -> MP4 H.264.

    Latar transparan diratakan ke putih karena MP4 H.264 tidak mendukung alpha.
    """
    keluaran = os.path.join(tujuan_dir, "hasil.mp4")
    hasil = _jalankan(
        [
            _FFMPEG, "-y",
            "-i", sumber,
            # Ratakan alpha ke putih, lalu encode H.264
            "-vf", f"scale={SISI}:{SISI}:force_original_aspect_ratio=decrease:"
                   "flags=lanczos,"
                   "format=rgba,color=white:size=512x512[bg];"
                   "[bg][0:v]scale2ref[bg2][fg];[bg2][fg]overlay=shortest=1,"
                   "format=yuv420p",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-an",
            keluaran,
        ],
        timeout=240,
    )
    if hasil.returncode != 0:
        # Fallback: encode langsung tanpa alpha (webm tidak punya alpha)
        hasil = _jalankan(
            [
                _FFMPEG, "-y",
                "-i", sumber,
                "-vf", f"scale={SISI}:{SISI}:force_original_aspect_ratio=decrease:"
                       "flags=lanczos,format=yuv420p",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-an",
                keluaran,
            ],
            timeout=240,
        )
        if hasil.returncode != 0:
            raise StickerError(_error_ffmpeg(hasil))

    return keluaran


def folder_sementara() -> str:
    return tempfile.mkdtemp(prefix="chrostt-stiker-")
