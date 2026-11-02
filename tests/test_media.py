"""Uji jalur "file >50MB dikirim sebagai tautan" dengan Telegram di-stub."""

import types
import unittest

from bot import tg_bot
from bot.services.media import BATAS_UPLOAD_BYTES, MediaTerlaluBesar, ukuran_mb


class MediaTest(unittest.TestCase):
    def test_batas_lima_puluh_mb(self):
        self.assertEqual(BATAS_UPLOAD_BYTES, 50 * 1024 * 1024)

    def test_ukuran_mb_membulatkan_satu_desimal(self):
        self.assertEqual(ukuran_mb(50 * 1024 * 1024), "50.0 MB")

    def test_ukuran_tidak_diketahui(self):
        self.assertEqual(ukuran_mb(None), "tidak diketahui")

    def test_exception_membawa_url_dan_ukuran(self):
        e = MediaTerlaluBesar("https://contoh/v.mp4", 60 * 1024 * 1024)
        self.assertEqual(e.url, "https://contoh/v.mp4")
        self.assertEqual(e.ukuran_bytes, 60 * 1024 * 1024)
        self.assertIn("60.0 MB", str(e))


class _Palsu:
    """Pengganti objek bot: merekam semua panggilan."""

    def __init__(self):
        self.rekam = []

    def __getattr__(self, nama):
        def fn(*args, **kwargs):
            self.rekam.append((nama, args, kwargs))
            return types.SimpleNamespace(message_id=999)

        return fn

    def pesan(self, kata_kunci):
        return [
            r for r in self.rekam
            if r[0] == "send_message" and kata_kunci in str(r[1][1])
        ]


class TautanUnduhTest(unittest.TestCase):
    def setUp(self):
        self.palsu = _Palsu()
        self.asli = {}
        for nama in (
            "send_message",
            "send_video",
            "send_audio",
            "send_photo",
            "send_media_group",
            "delete_message",
            "edit_message_text",
            "answer_callback_query",
        ):
            self.asli[nama] = getattr(tg_bot, nama, None)
            setattr(tg_bot, nama, getattr(self.palsu, nama))

    def tearDown(self):
        for nama, nilai in self.asli.items():
            setattr(tg_bot, nama, nilai)

    def test_kirim_tautan_tanpa_url_menghasilkan_false(self):
        from bot.handlers.unduhan import kirim_tautan_unduh

        self.assertFalse(kirim_tautan_unduh(1, ""))
        self.assertEqual(self.palsu.rekam, [])

    def test_kirim_tautan_memuat_ukuran_dan_url(self):
        from bot.handlers.unduhan import kirim_tautan_unduh

        ok = kirim_tautan_unduh(
            1,
            "https://contoh/v.mp4",
            ukuran=60 * 1024 * 1024,
            jenis="video",
            judul="Judul Video",
            alternatif=[("🔗 Cadangan", "https://contoh/cadangan.mp4")],
        )
        self.assertTrue(ok)

        pesan = self.palsu.pesan("LINK UNDUHAN")
        self.assertEqual(len(pesan), 1)
        teks = pesan[0][1][1]
        self.assertIn("60.0 MB", teks)
        self.assertIn("https://contoh/v.mp4", teks)
        self.assertIn("Judul Video", teks)

        tombol = [
            b.url
            for baris in pesan[0][2]["reply_markup"].keyboard
            for b in baris
        ]
        self.assertIn("https://contoh/v.mp4", tombol)
        self.assertIn("https://contoh/cadangan.mp4", tombol)

    def test_url_berisi_karakter_html_di_escape(self):
        from bot.handlers.unduhan import kirim_tautan_unduh

        kirim_tautan_unduh(1, "https://contoh/a?b=1&c=<x>", ukuran=1024)
        teks = self.palsu.pesan("LINK UNDUHAN")[0][1][1]
        self.assertIn("&amp;", teks)
        self.assertIn("&lt;x&gt;", teks)

    def test_handler_tiktok_mengirim_tautan_bukan_error(self):
        import bot.handlers.tiktok as h

        h.TIKTOK_SESSIONS.set(
            7,
            {
                "author": {"username": "u", "full_name": "U"},
                "content": {
                    "title": "judul",
                    "video_no_wm": "https://cdn/v.mp4",
                    "video_wm": "",
                    "images": [],
                },
                "music": {"url": "", "title": "", "author": ""},
            },
        )

        asli = h.unduh_media
        h.unduh_media = lambda url, timeout=None: (_ for _ in ()).throw(
            MediaTerlaluBesar(url, 70 * 1024 * 1024)
        )
        try:
            call = types.SimpleNamespace(
                id="cb",
                data="tiktok_nowm",
                from_user=types.SimpleNamespace(id=1),
                message=types.SimpleNamespace(
                    chat=types.SimpleNamespace(id=7), message_id=5
                ),
            )
            h.aksi_download_tiktok(call)
        finally:
            h.unduh_media = asli

        pesan = self.palsu.pesan("LINK UNDUHAN")
        self.assertEqual(len(pesan), 1)
        self.assertIn("70.0 MB", pesan[0][1][1])
        self.assertNotIn("❌", pesan[0][1][1])


if __name__ == "__main__":
    unittest.main()
