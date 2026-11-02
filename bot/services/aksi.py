"""Aksi bot yang bisa dipanggil Chrostt AI lewat tool calling.

Setiap fungsi di sini membungkus fitur yang sudah ada (hapus background,
stiker, YouTube, saham, berita IDX) menjadi satu tool. Tujuannya supaya
pengguna cukup menulis "hapus background foto ini" atau "putarkan lagu X",
tanpa harus tahu perintah atau tombol menunya.

Aturan yang dijaga modul ini:

- Aksinya sama dengan fitur manual, jadi batas laju ``batas_laju`` tetap
  berlaku. Model tidak bisa dipakai untuk melewati kuota pengguna.
- Media dikirim langsung oleh bot; hasil tool hanya catatan singkat untuk
  model, bukan instruksi yang harus disalin ke jawaban.
- Tidak ada jalur eksekusi sistem: semua aksi berhenti di API Telegram dan
  layanan pihak ketiga yang sudah dipakai fitur manual.
"""

import logging
import os
import shutil
from dataclasses import dataclass
from io import BytesIO

from bot import batas_laju, tg_bot
from bot.services import idx_news, removebg
from bot.services import sticker as sticker_media
from bot.services import youtube as YT
from bot.services.media import MediaTerlaluBesar
from bot.services.removebg import RemoveBgError
from bot.services.saham import ambil_data_saham, format_kode_emiten, validasi_kode_emiten
from bot.services.sticker import StickerError
from bot.sessions import SessionStore
from bot.utils import escape_html, format_angka_rupiah

log = logging.getLogger("chrosttbot.aksi")


@dataclass
class Konteks:
    """Siapa dan di mana aksi dijalankan.

    ``media`` adalah media terakhir dari pengguna di chat ini (foto atau file
    gambar). Model tidak perlu mengirim file_id; bot mengingatnya sendiri.
    """

    chat_id: int
    user_id: int | None = None
    media: dict | None = None


# chat_id -> {"jenis": "foto", "file_id": ..., "ukuran": int, "user_id": int}
_MEDIA = SessionStore(ttl=1800, max_entries=500)

# Batas judul lagu yang mau diproses; jauh di atas kebutuhan manusia
MAKS_JUDUL = 200
MAKS_KODE_SAHAM = 12
MAKS_BERITA = 9


def simpan_media(
    chat_id: int, jenis: str, file_id: str, ukuran: int = 0, user_id: int | None = None
) -> None:
    """Ingat media terakhir pengguna supaya bisa dipakai permintaan berikutnya.

    ``user_id`` ikut disimpan karena di grup foto milik orang lain tidak boleh
    diproses atas permintaan pengguna lain.
    """
    if not file_id:
        return
    _MEDIA.set(
        chat_id,
        {
            "jenis": jenis,
            "file_id": file_id,
            "ukuran": int(ukuran or 0),
            "user_id": user_id,
        },
    )


def ambil_media(chat_id: int, user_id: int | None = None):
    """Media terakhir di chat ini, hanya kalau pengirimnya orang yang sama."""
    media = _MEDIA.get(chat_id)
    if not media:
        return None

    pemilik = media.get("user_id")
    if pemilik is not None and user_id is not None and pemilik != user_id:
        return None
    return media


def _media_aktif(konteks: Konteks):
    langsung = konteks.media
    if langsung is not None:
        return langsung
    return ambil_media(konteks.chat_id, konteks.user_id)


def _unduh(file_id: str) -> bytes:
    info = tg_bot.get_file(file_id)
    return tg_bot.download_file(info.file_path)


def _batas(user_id, jenis: str):
    """Pesan penolakan kalau kuota habis, None kalau masih boleh."""
    try:
        batas_laju.cek(user_id, jenis)
    except batas_laju.BatasTerlampaui as e:
        return f"Batas tercapai: {e.pesan} Sisa waktu tunggu sekitar {e.detik} detik."
    return None


# ==================== HAPUS BACKGROUND ====================


def hapus_background(konteks: Konteks, argumen: dict) -> str:
    media = _media_aktif(konteks)
    if not media:
        return (
            "Belum ada foto untuk diproses. Minta pengguna mengirim foto dulu "
            "(boleh dengan caption), lalu panggil tool ini lagi."
        )

    # Tolak lebih awal: unduh lalu buang kuota API hanya untuk ditolak handler
    if media.get("ukuran", 0) > removebg.MAX_IMAGE_BYTES:
        return "GAGAL: foto melebihi 12MB. Minta pengguna mengirim versi lebih kecil."

    terbatas = _batas(konteks.user_id, "umum")
    if terbatas:
        return terbatas

    try:
        data = _unduh(media["file_id"])
        hasil = removebg.hapus_background(data)
    except RemoveBgError as e:
        return f"GAGAL menghapus background: {e}"
    except Exception as e:
        log.warning("Aksi hapus background gagal", exc_info=True)
        return f"GAGAL menghapus background: {str(e)[:150]}"

    try:
        tg_bot.send_document(
            konteks.chat_id,
            BytesIO(hasil),
            visible_file_name="hasil_nobg.png",
        )
    except Exception as e:
        log.warning("Gagal mengirim hasil hapus background", exc_info=True)
        return f"Gambar sudah diproses tetapi gagal dikirim ke chat: {str(e)[:120]}"

    return "Berhasil: PNG tanpa background sudah dikirim ke chat."


# ==================== STIKER ====================


def _ekstensi_gambar(data: bytes) -> str:
    """Tebak ekstensi dari magic bytes; Telegram tidak memberi nama file foto."""
    if data[:8].startswith(b"\x89PNG"):
        return ".png"
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if data[:3] == b"GIF":
        return ".gif"
    return ".jpg"


def buat_stiker(konteks: Konteks, argumen: dict) -> str:
    media = _media_aktif(konteks)
    if not media:
        return "Belum ada foto untuk dijadikan stiker. Minta pengguna mengirim foto dulu."

    terbatas = _batas(konteks.user_id, "stiker")
    if terbatas:
        return terbatas

    if not sticker_media.tersedia():
        return "GAGAL: fitur stiker butuh ffmpeg di server, dan ffmpeg tidak terdeteksi."

    folder = None
    keluaran_dir = None
    jenis = "statis"
    try:
        data = _unduh(media["file_id"])
        folder = sticker_media.folder_sementara()
        sumber = os.path.join(folder, "sumber" + _ekstensi_gambar(data))
        with open(sumber, "wb") as f:
            f.write(data)

        keluaran_dir = sticker_media.folder_sementara()
        hasil, jenis = sticker_media.buat_stiker(sumber, keluaran_dir)
        with open(hasil, "rb") as f:
            tg_bot.send_sticker(konteks.chat_id, f)
    except StickerError as e:
        return f"GAGAL membuat stiker: {e}"
    except Exception as e:
        log.warning("Aksi buat stiker gagal", exc_info=True)
        return f"GAGAL membuat stiker: {str(e)[:150]}"
    finally:
        for path in (folder, keluaran_dir):
            if path:
                shutil.rmtree(path, ignore_errors=True)

    return f"Berhasil: stiker {jenis} sudah dikirim ke chat."


# ==================== PUTAR LAGU (YOUTUBE) ====================


def _format_durasi(detik) -> str:
    detik = int(detik or 0)
    if detik <= 0:
        return "-"
    jam, sisa = divmod(detik, 3600)
    menit, detik = divmod(sisa, 60)
    if jam:
        return f"{jam}:{menit:02d}:{detik:02d}"
    return f"{menit}:{detik:02d}"


def putar_lagu(konteks: Konteks, argumen: dict) -> str:
    judul = str(argumen.get("judul") or "").strip()[:MAKS_JUDUL]
    if not judul:
        return "Judul lagu atau video kosong."

    mode = str(argumen.get("format") or "audio").strip().lower()
    if mode not in ("audio", "video", "cari"):
        mode = "audio"

    if mode == "cari":
        terbatas = _batas(konteks.user_id, "umum")
        if terbatas:
            return terbatas
        try:
            hasil = YT.cari_video(judul, jumlah=5)
        except YT.YouTubeSearchError as e:
            return f"Pencarian gagal: {e}"
        except Exception as e:
            log.warning("Aksi cari lagu gagal", exc_info=True)
            return f"Pencarian gagal: {str(e)[:150]}"

        baris = [f"Hasil pencarian '{judul}':"]
        for i, video in enumerate(hasil, start=1):
            baris.append(
                f"{i}. {video.get('judul')} — {video.get('channel') or '-'} "
                f"({_format_durasi(video.get('durasi'))})"
            )
        baris.append("Sebutkan pilihannya, lalu panggil tool lagi dengan judul yang dipilih.")
        return "\n".join(baris)

    terbatas = _batas(konteks.user_id, "unduh")
    if terbatas:
        return terbatas

    if not YT.ffmpeg_tersedia():
        return "GAGAL: fitur ini butuh ffmpeg di server, dan ffmpeg tidak terdeteksi."

    try:
        hasil = YT.cari_video(judul, jumlah=1)
        video = hasil[0]
    except YT.YouTubeSearchError as e:
        return f"Tidak menemukan video untuk '{judul}': {e}"
    except Exception as e:
        log.warning("Aksi putar lagu: pencarian gagal", exc_info=True)
        return f"Pencarian gagal: {str(e)[:150]}"

    url = video.get("url", "")
    path = None
    try:
        if mode == "video":
            path = YT.download_youtube_video(url)
        else:
            path = YT.download_youtube_audio(url)

        ukuran_mb = os.path.getsize(path) / 1048576
        judul_video = str(video.get("judul") or judul)[:120]

        with open(path, "rb") as f:
            if mode == "video":
                tg_bot.send_video(
                    konteks.chat_id,
                    f,
                    caption=(
                        f"🎬 <b>{escape_html(judul_video)}</b>\n"
                        f"<i>{ukuran_mb:.1f} MB</i>"
                    ),
                    parse_mode="HTML",
                    supports_streaming=True,
                    timeout=300,
                )
            else:
                tg_bot.send_audio(
                    konteks.chat_id,
                    f,
                    title=video.get("judul") or judul,
                    performer=video.get("channel") or "YouTube",
                    caption=f"🎵 {escape_html(judul_video)}",
                    parse_mode="HTML",
                    timeout=180,
                )
    except MediaTerlaluBesar as e:
        return (
            f"File {mode} melebihi batas upload Telegram (50MB). "
            f"Kirim tautan ini ke pengguna: {e.url}"
        )
    except YT.YouTubeDownloadError as e:
        return f"GAGAL mengunduh: {e}"
    except Exception as e:
        log.warning("Aksi putar lagu gagal", exc_info=True)
        return f"GAGAL mengunduh: {str(e)[:150]}"
    finally:
        if path:
            YT.bersihkan_folder(os.path.dirname(path))

    jenis = "video" if mode == "video" else "audio"
    return f"Berhasil: {jenis} '{video.get('judul') or judul}' sudah dikirim ke chat."


# ==================== SAHAM & BERITA ====================


def cek_saham(konteks: Konteks, argumen: dict) -> str:
    kode = str(argumen.get("kode") or "").strip().upper()[:MAKS_KODE_SAHAM]
    if not kode:
        return "Kode saham kosong."

    # IHSG punya simbol sendiri di Yahoo Finance
    if kode in ("IHSG", "JKSE", "^JKSE"):
        kode = "^JKSE"

    if not validasi_kode_emiten(kode):
        return (
            f"Kode '{kode}' tidak valid. Gunakan kode emiten BEI 1-4 huruf, "
            "misalnya BBCA atau ASII, atau IHSG."
        )

    terbatas = _batas(konteks.user_id, "umum")
    if terbatas:
        return terbatas

    kode_emiten = kode if kode == "^JKSE" else format_kode_emiten(kode)
    try:
        data = ambil_data_saham(kode_emiten)
    except Exception as e:
        log.warning("Aksi cek saham gagal", exc_info=True)
        return f"Gagal menarik data {kode}: {str(e)[:150]}"

    if data is None or data.empty or "Close" not in data:
        return f"Data {kode} tidak ditemukan di bursa."

    harga = data["Close"].iloc[-1]
    if kode_emiten == "^JKSE":
        angka = format_angka_rupiah(harga, desimal=True)
        return f"IHSG: Rp {angka} (data terakhir via yfinance, bukan rekomendasi investasi)."

    angka = format_angka_rupiah(harga)
    return (
        f"{kode_emiten.replace('.JK', '')}: Rp {angka} "
        "(data terakhir via yfinance, bukan rekomendasi investasi)."
    )


def berita_idx(konteks: Konteks, argumen: dict) -> str:
    try:
        jumlah = int(argumen.get("jumlah") or 5)
    except (TypeError, ValueError):
        jumlah = 5
    jumlah = max(1, min(jumlah, MAKS_BERITA))

    terbatas = _batas(konteks.user_id, "umum")
    if terbatas:
        return terbatas

    try:
        berita = idx_news.ambil_berita_terbaru(jumlah=jumlah)
    except idx_news.IDXNewsError as e:
        return f"Gagal mengambil berita IDX: {e}"
    except Exception as e:
        log.warning("Aksi berita IDX gagal", exc_info=True)
        return f"Gagal mengambil berita IDX: {str(e)[:150]}"

    if not berita:
        return "Belum ada berita IDX terbaru yang ditemukan."

    baris = [f"Berita IDX terbaru ({len(berita)}):"]
    for i, item in enumerate(berita, start=1):
        baris.append(
            f"{i}. {item.get('judul')} — {item.get('sumber') or '-'} "
            f"({item.get('tanggal') or 'terbaru'}) {item.get('link') or ''}".strip()
        )
    return "\n".join(baris)


# ==================== REGISTRY ====================

_AKSI = {
    "hapus_background": hapus_background,
    "buat_stiker": buat_stiker,
    "putar_lagu": putar_lagu,
    "cek_saham": cek_saham,
    "berita_idx": berita_idx,
}

NAMA_TOOL = tuple(_AKSI)

_LABEL = {
    "hapus_background": "✂️ hapus background",
    "buat_stiker": "🎨 buat stiker",
    "putar_lagu": "🎵 putar lagu",
    "cek_saham": "📈 cek saham",
    "berita_idx": "📰 berita IDX",
}


def catatan(nama: str) -> str:
    """Label pendek untuk baris sumber di bawah jawaban AI."""
    return _LABEL.get(nama, f"⚙️ {nama}")


def jalankan(nama: str, argumen: dict, konteks: Konteks) -> str:
    """Jalankan aksi yang diminta model. Selalu mengembalikan teks."""
    fungsi = _AKSI.get(nama)
    if fungsi is None:
        return f"Tool aksi tidak dikenal: {nama}"

    try:
        return fungsi(konteks, argumen or {})
    except Exception as e:
        log.warning("Aksi %s gagal", nama, exc_info=True)
        return f"Aksi {nama} gagal: {str(e)[:150]}"


def _skema(nama: str, deskripsi: str, properti: dict, wajib=()) -> dict:
    return {
        "type": "function",
        "function": {
            "name": nama,
            "description": deskripsi,
            "parameters": {
                "type": "object",
                "properties": properti,
                "required": list(wajib),
            },
        },
    }


SKEMA_AKSI = [
    _skema(
        "hapus_background",
        (
            "Hapus background foto milik pengguna dan kirim hasil PNG transparan "
            "ke chat. Pakai kalau pengguna minta hapus background, bikin latar "
            "transparan, atau potong objek dari foto. Memakai foto terakhir yang "
            "dikirim pengguna di chat ini; tidak perlu file_id."
        ),
        {},
    ),
    _skema(
        "buat_stiker",
        (
            "Ubah foto terakhir dari pengguna menjadi stiker Telegram lalu kirim "
            "ke chat. Pakai kalau pengguna minta dibuatkan stiker."
        ),
        {},
    ),
    _skema(
        "putar_lagu",
        (
            "Cari lagu/video di YouTube lalu kirim audionya ke chat, atau kirim "
            "videonya. Pakai format 'cari' untuk menampilkan beberapa pilihan "
            "tanpa mengunduh, 'audio' (default) untuk lagu, 'video' untuk video."
        ),
        {
            "judul": {
                "type": "string",
                "description": "Judul lagu atau video yang dicari, mis. 'lofi hip hop'.",
            },
            "format": {
                "type": "string",
                "enum": ["audio", "video", "cari"],
                "description": "audio = MP3 (default), video = MP4, cari = daftar hasil.",
            },
        },
        ("judul",),
    ),
    _skema(
        "cek_saham",
        (
            "Ambil harga terakhir saham BEI atau IHSG lewat yfinance. Pakai kalau "
            "pengguna menyebut kode emiten (BBCA, GOTO) atau menanyakan IHSG."
        ),
        {
            "kode": {
                "type": "string",
                "description": "Kode emiten BEI 1-4 huruf, atau 'IHSG'.",
            }
        },
        ("kode",),
    ),
    _skema(
        "berita_idx",
        "Ambil berita terbaru seputar Bursa Efek Indonesia / IDX.",
        {
            "jumlah": {
                "type": "integer",
                "description": "Jumlah berita yang diambil (1-9, default 5).",
            }
        },
    ),
]
