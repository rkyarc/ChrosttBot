"""Uji service YouTube tanpa yt-dlp sungguhan.

YoutubeDL dan ffmpeg di-stub, jadi test berjalan offline dan bisa di CI.
Yang dikunci: pemetaan error, pencarian, dan aturan "terlalu besar jadi
tautan" pada video maupun audio.
"""

import os
import tempfile
import unittest
from unittest import mock

from bot.services import youtube as yt
from bot.services.media import MediaTerlaluBesar


class PesanErrorTest(unittest.TestCase):
    def test_format_tidak_tersedia(self):
        self.assertIn("Format video", yt._pesan_error(Exception("Requested format is not available")))

    def test_video_tidak_tersedia(self):
        self.assertIn("tidak tersedia", yt._pesan_error(Exception("Video unavailable")))

    def test_video_privat(self):
        self.assertIn("privat", yt._pesan_error(Exception("Private video")))

    def test_perlu_login_umur(self):
        self.assertIn("verifikasi umur", yt._pesan_error(Exception("Sign in to confirm your age")))

    def test_live_tidak_didukung(self):
        self.assertIn("Live stream", yt._pesan_error(Exception("is_live")))

    def test_timeout(self):
        self.assertIn("timeout", yt._pesan_error(Exception("Connection timed out")))

    def test_koneksi_gagal(self):
        self.assertIn("Tidak bisa menghubungi", yt._pesan_error(Exception("urlopen error")))

    def test_diblokir_wilayah(self):
        self.assertIn("diblokir", yt._pesan_error(Exception("blocked in your country")))

    def test_ffmpeg_hilang(self):
        self.assertIn("ffmpeg", yt._pesan_error(Exception("ffmpeg not found")))

    def test_baris_error_dibersihkan_dari_prefix(self):
        e = Exception("ERROR: [youtube] abc123: Something specific broke")
        self.assertEqual(yt._pesan_error(e), "Something specific broke")

    def test_pesan_tak_dikenal_dipotong(self):
        self.assertLessEqual(len(yt._pesan_error(Exception("x" * 500))), 200)

    def test_pesan_kosong_memberi_fallback(self):
        self.assertTrue(yt._pesan_error(Exception("")))


class FormatDurasiTest(unittest.TestCase):
    def test_jam_menit(self):
        self.assertEqual(yt._format_durasi(3725), "1j 2m")

    def test_menit_detik(self):
        self.assertEqual(yt._format_durasi(125), "2m 5d")

    def test_detik_saja(self):
        self.assertEqual(yt._format_durasi(45), "45 detik")

    def test_none_aman(self):
        self.assertEqual(yt._format_durasi(None), "0 detik")


class CariVideoTest(unittest.TestCase):
    def _ydl(self, info):
        instance = mock.MagicMock()
        instance.extract_info.return_value = info
        ctx = mock.MagicMock()
        ctx.__enter__.return_value = instance
        return mock.patch.object(yt.yt_dlp, "YoutubeDL", return_value=ctx), instance

    def test_query_kosong_ditolak(self):
        with self.assertRaises(yt.YouTubeSearchError):
            yt.cari_video("   ")

    def test_hasil_dipetakan(self):
        info = {
            "entries": [
                {
                    "id": "abc",
                    "title": "Judul",
                    "uploader": "Kanal",
                    "duration": 100,
                    "view_count": 5000,
                },
                {"id": None},  # dilewati
                None,          # dilewati
            ]
        }
        patch, _ = self._ydl(info)
        with patch:
            hasil = yt.cari_video("kucing", jumlah=3)

        self.assertEqual(len(hasil), 1)
        self.assertEqual(hasil[0]["url"], "https://www.youtube.com/watch?v=abc")
        self.assertEqual(hasil[0]["durasi"], 100)

    def test_tanpa_hasil_jadi_search_error(self):
        patch, _ = self._ydl({"entries": []})
        with patch:
            with self.assertRaises(yt.YouTubeSearchError) as ctx:
                yt.cari_video("tidak ada")
        self.assertIn("Tidak ada hasil", str(ctx.exception))

    def test_error_ytdlp_diterjemahkan(self):
        instance = mock.MagicMock()
        instance.extract_info.side_effect = Exception("Video unavailable")
        ctx = mock.MagicMock()
        ctx.__enter__.return_value = instance
        with mock.patch.object(yt.yt_dlp, "YoutubeDL", return_value=ctx):
            with self.assertRaises(yt.YouTubeSearchError) as ctx_err:
                yt.cari_video("x")
        self.assertIn("tidak tersedia", str(ctx_err.exception))


class CekDurasiTest(unittest.TestCase):
    def _info(self, durasi=100, live=False):
        instance = mock.MagicMock()
        instance.extract_info.return_value = {
            "duration": durasi,
            "is_live": live,
            "id": "abc",
        }
        ctx = mock.MagicMock()
        ctx.__enter__.return_value = instance
        return mock.patch.object(yt.yt_dlp, "YoutubeDL", return_value=ctx)

    def test_durasi_wajar_lolos(self):
        with self._info(100):
            info = yt._cek_durasi("https://youtu.be/abc")
        self.assertEqual(info["id"], "abc")

    def test_live_ditolak(self):
        with self._info(0, live=True):
            with self.assertRaises(yt.YouTubeDownloadError) as ctx:
                yt._cek_durasi("https://youtu.be/abc")
        self.assertIn("Live stream", str(ctx.exception))

    def test_video_terlalu_panjang_jadi_tautan(self):
        """Video >1 jam bukan error mentah; handler diminta kirim tautan."""
        with self._info(7200):
            with self.assertRaises(MediaTerlaluBesar) as ctx:
                yt._cek_durasi("https://youtu.be/abc")

        self.assertEqual(ctx.exception.url, "https://youtu.be/abc")
        self.assertIn("1 jam", ctx.exception.catatan)


class DownloadVideoTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="chrostt-test-yt-")
        self.patch_ffmpeg = mock.patch.object(yt, "ffmpeg_tersedia", return_value=True)
        self.patch_ffmpeg.start()

    def tearDown(self):
        self.patch_ffmpeg.stop()

    def _siapkan(self, buat_file=True, ukuran=1024):
        """Stub YoutubeDL yang menulis file hasil seperti yt-dlp sungguhan."""
        instance = mock.MagicMock()

        def extract(url, download=False):
            if buat_file:
                path = os.path.join(self.folder, "Judul-abc.mp4")
                with open(path, "wb") as f:
                    f.write(b"x" * ukuran)
            return {"id": "abc", "duration": 100}

        instance.extract_info.side_effect = extract
        ctx = mock.MagicMock()
        ctx.__enter__.return_value = instance
        return mock.patch.object(yt.yt_dlp, "YoutubeDL", return_value=ctx)

    def test_hasil_normal_dikembalikan(self):
        with self._siapkan():
            path = yt.download_youtube_video("https://youtu.be/abc", self.folder)
        self.assertTrue(os.path.exists(path))

    def test_ffmpeg_hilang_ditolak_lebih_awal(self):
        with mock.patch.object(yt, "ffmpeg_tersedia", return_value=False):
            with self.assertRaises(yt.YouTubeDownloadError) as ctx:
                yt.download_youtube_video("https://youtu.be/abc", self.folder)
        self.assertIn("ffmpeg", str(ctx.exception))

    def test_file_tidak_terbentuk_jadi_tautan(self):
        """max_filesize menghentikan unduhan: tidak ada file hasil."""
        with self._siapkan(buat_file=False):
            with self.assertRaises(MediaTerlaluBesar) as ctx:
                yt.download_youtube_video("https://youtu.be/abc", self.folder)

        self.assertEqual(ctx.exception.url, "https://youtu.be/abc")
        self.assertIn("kualitas lebih rendah", ctx.exception.catatan)

    def test_file_terlalu_besar_jadi_tautan(self):
        with self._siapkan(ukuran=yt.MAX_UPLOAD_BYTES + 100):
            with self.assertRaises(MediaTerlaluBesar) as ctx:
                yt.download_youtube_video("https://youtu.be/abc", self.folder)

        self.assertGreater(ctx.exception.ukuran_bytes, yt.MAX_UPLOAD_BYTES)


class DownloadAudioTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="chrostt-test-yta-")
        self.patch_ffmpeg = mock.patch.object(yt, "ffmpeg_tersedia", return_value=True)
        self.patch_ffmpeg.start()

    def tearDown(self):
        self.patch_ffmpeg.stop()

    def _siapkan(self, buat_file=True, ukuran=1024):
        instance = mock.MagicMock()

        def extract(url, download=False):
            if buat_file:
                path = os.path.join(self.folder, "Judul-abc.mp3")
                with open(path, "wb") as f:
                    f.write(b"x" * ukuran)
            return {"id": "abc"}

        instance.extract_info.side_effect = extract
        ctx = mock.MagicMock()
        ctx.__enter__.return_value = instance
        return mock.patch.object(yt.yt_dlp, "YoutubeDL", return_value=ctx)

    def test_mp3_normal(self):
        with self._siapkan():
            path = yt.download_youtube_audio("https://youtu.be/abc", self.folder)
        self.assertTrue(path.endswith(".mp3"))

    def test_audio_tidak_terbentuk_jadi_tautan(self):
        with self._siapkan(buat_file=False):
            with self.assertRaises(MediaTerlaluBesar) as ctx:
                yt.download_youtube_audio("https://youtu.be/abc", self.folder)
        self.assertIn("Audio terlalu panjang", ctx.exception.catatan)

    def test_audio_terlalu_besar_jadi_tautan(self):
        with self._siapkan(ukuran=yt.MAX_UPLOAD_BYTES + 100):
            with self.assertRaises(MediaTerlaluBesar):
                yt.download_youtube_audio("https://youtu.be/abc", self.folder)


class HelperTest(unittest.TestCase):
    def test_cari_file_memilih_terbesar_dan_abaikan_part(self):
        folder = tempfile.mkdtemp(prefix="chrostt-test-cari-")
        for nama, ukuran in (("a-abc.mp4", 10), ("b-abc.mp4", 100), ("c-abc.mp4.part", 999)):
            with open(os.path.join(folder, nama), "wb") as f:
                f.write(b"x" * ukuran)

        hasil = yt._cari_file_hasil(folder, "abc")
        self.assertTrue(hasil.endswith("b-abc.mp4"))

    def test_folder_kosong_menghasilkan_none(self):
        folder = tempfile.mkdtemp(prefix="chrostt-test-kosong-")
        self.assertIsNone(yt._cari_file_hasil(folder, "abc"))

    def test_bersihkan_folder_menghapus_isi(self):
        folder = tempfile.mkdtemp(prefix="chrostt-test-hapus-")
        with open(os.path.join(folder, "x.mp4"), "wb") as f:
            f.write(b"x")
        yt.bersihkan_folder(folder)
        self.assertFalse(os.path.exists(folder))

    def test_bersihkan_folder_tidak_error_kalau_tidak_ada(self):
        yt.bersihkan_folder("folder-yang-tidak-ada-xyz")


if __name__ == "__main__":
    unittest.main()
