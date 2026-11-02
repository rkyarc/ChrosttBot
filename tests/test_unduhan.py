"""Uji ujung-ke-ujung jalur "file besar" untuk keempat downloader.

Semua panggilan Telegram dan layanan luar diganti stub, jadi test ini tidak
menyentuh jaringan dan bisa dijalankan di CI.
"""

import types
import unittest

from bot import tg_bot
from bot.services.media import MediaTerlaluBesar


class _BotPalsu:
    def __init__(self):
        self.rekam = []

    def __getattr__(self, nama):
        def fn(*args, **kwargs):
            self.rekam.append((nama, args, kwargs))
            return types.SimpleNamespace(message_id=999)

        return fn

    def bersih(self):
        self.rekam.clear()

    def tautan(self):
        """Semua pesan/teks yang berisi LINK UNDUHAN."""
        hasil = []
        for nama, args, _kwargs in self.rekam:
            teks = args[1] if nama == "send_message" and len(args) > 1 else None
            if teks is None and nama == "edit_message_text" and args:
                teks = args[0]
            if teks and "LINK UNDUHAN" in str(teks):
                hasil.append((nama, str(teks)))
        return hasil

    def error_teks(self):
        hasil = []
        for nama, args, _kwargs in self.rekam:
            teks = args[1] if nama == "send_message" and len(args) > 1 else None
            if teks is None and nama == "edit_message_text" and args:
                teks = args[0]
            if teks and ("❌" in str(teks) or "GAGAL" in str(teks)):
                hasil.append(str(teks))
        return hasil


class _DasarStub(unittest.TestCase):
    def setUp(self):
        from bot import batas_laju

        batas_laju.reset()
        self.palsu = _BotPalsu()
        self.asli = {}
        for nama in (
            "send_message",
            "send_video",
            "send_audio",
            "send_photo",
            "send_document",
            "send_sticker",
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

    @staticmethod
    def call(data, chat_id=7):
        return types.SimpleNamespace(
            id="cb",
            data=data,
            from_user=types.SimpleNamespace(id=1),
            message=types.SimpleNamespace(
                chat=types.SimpleNamespace(id=chat_id, type="private"),
                message_id=5,
            ),
        )

    @staticmethod
    def pesan(chat_id=7, text="halo"):
        return types.SimpleNamespace(
            text=text,
            chat=types.SimpleNamespace(id=chat_id, type="private"),
            from_user=types.SimpleNamespace(id=1),
            message_id=5,
        )


class UnduhanBesarTest(_DasarStub):
    def test_youtube_video_besar_menampilkan_tautan(self):
        import bot.handlers.youtube as h

        h.YT_SESSIONS.set(7, {"url": "https://youtu.be/abc", "judul": "lagu"})

        def gagal(url, output_path=None):
            raise MediaTerlaluBesar(url, 95 * 1024 * 1024)

        asli = h.YT.download_youtube_video
        h.YT.download_youtube_video = gagal
        try:
            h.unduh_youtube(self.call("yt_video"))
        finally:
            h.YT.download_youtube_video = asli

        tautan = self.palsu.tautan()
        self.assertTrue(tautan, "harus ada pesan tautan")
        self.assertIn("https://youtu.be/abc", tautan[0][1])
        self.assertEqual(self.palsu.error_teks(), [])

    def test_facebook_besar_menawarkan_kualitas_lain(self):
        import bot.handlers.facebook as h

        h.FB_SESSIONS.set(
            7, {"sdlink": "https://fb/sd.mp4", "hdlink": "https://fb/hd.mp4"}
        )

        def gagal(url, max_bytes, timeout=60):
            raise MediaTerlaluBesar(url, 80 * 1024 * 1024)

        asli = h.unduh_video
        h.unduh_video = gagal
        try:
            h.aksi_download_facebook(self.call("fb_hd"))
        finally:
            h.unduh_video = asli

        tautan = self.palsu.tautan()
        self.assertTrue(tautan)
        self.assertIn("https://fb/hd.mp4", tautan[0][1])
        self.assertIn("https://fb/sd.mp4", tautan[0][1])  # tombol alternatif

    def test_instagram_foto_besar_mengirim_tautan(self):
        import bot.handlers.instagram as h

        class ScraperPalsu:
            def unduh_media(self, url, max_bytes=None):
                raise MediaTerlaluBesar(url, 55 * 1024 * 1024)

        # Album berbasis URL gagal -> jalur fallback unduh manual diuji
        def gagal_album(*a, **k):
            raise RuntimeError("Telegram menolak fetch URL")

        asli = tg_bot.send_media_group
        tg_bot.send_media_group = gagal_album
        try:
            h.kirim_foto_instagram(7, ScraperPalsu(), ["https://ig/f.jpg"])
        finally:
            tg_bot.send_media_group = asli

        tautan = self.palsu.tautan()
        self.assertTrue(tautan)
        self.assertIn("https://ig/f.jpg", tautan[0][1])


class BatasLajuHandlerTest(_DasarStub):
    def test_unduh_berulang_dibatasi(self):
        import bot.handlers.youtube as h

        h.YT_SESSIONS.set(
            7,
            {"url": "https://youtu.be/abc", "judul": "lagu"},
        )

        dipanggil = {"n": 0}

        def sukses(url, output_path=None):
            dipanggil["n"] += 1
            raise h.YT.YouTubeDownloadError("berhenti di sini")

        asli = h.YT.download_youtube_video
        h.YT.download_youtube_video = sukses
        try:
            batas, _ = __import__("bot.batas_laju", fromlist=["x"]).BATAS_UNDUH
            for _ in range(batas + 3):
                h.unduh_youtube(self.call("yt_video"))
        finally:
            h.YT.download_youtube_video = asli

        # Unduhan sungguhan tidak boleh dipanggil melebihi kuota
        self.assertEqual(dipanggil["n"], batas)
        self.assertTrue(
            any("Batas tercapai" in str(t) for _, t in self._semua_teks()),
            "pengguna harus diberi tahu batasnya",
        )

    def _semua_teks(self):
        hasil = []
        for nama, args, _kwargs in self.palsu.rekam:
            if nama == "send_message" and len(args) > 1:
                hasil.append((nama, str(args[1])))
            elif nama == "edit_message_text" and args:
                hasil.append((nama, str(args[0])))
        return hasil


if __name__ == "__main__":
    unittest.main()
