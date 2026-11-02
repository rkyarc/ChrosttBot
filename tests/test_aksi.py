"""Uji tool aksi bot untuk Chrostt AI.

Yang dikunci: tool terdaftar, routing dari service AI, pengiriman hasil ke
chat, pesan saat media tidak ada, dan batas laju yang tetap berlaku walau
aksinya dipicu model (bukan perintah langsung).
"""

import os
import tempfile
import types
import unittest
from unittest import mock

import config
from bot import batas_laju, tg_bot
from bot.services import aksi


class _BotPalsu:
    def __init__(self):
        self.dokumen = []
        self.audio = []
        self.stiker = []
        self.pesan = []

    def get_file(self, file_id):
        return types.SimpleNamespace(file_path="media.bin")

    def download_file(self, file_path):
        return b"data-media"

    def send_document(self, chat_id, file_obj, **kwargs):
        self.dokumen.append((chat_id, kwargs))
        return types.SimpleNamespace(message_id=1)

    def send_audio(self, chat_id, file_obj, **kwargs):
        self.audio.append((chat_id, kwargs))
        return types.SimpleNamespace(message_id=2)

    def send_sticker(self, chat_id, file_obj, **kwargs):
        self.stiker.append((chat_id, kwargs))
        return types.SimpleNamespace(message_id=3)

    def send_message(self, chat_id, teks, **kwargs):
        self.pesan.append((chat_id, teks))
        return types.SimpleNamespace(message_id=4)


class _DasarAksi(unittest.TestCase):
    def setUp(self):
        batas_laju.reset()
        self.palsu = _BotPalsu()
        self.asli = {}
        for nama in ("get_file", "download_file", "send_document", "send_audio", "send_sticker"):
            self.asli[nama] = getattr(tg_bot, nama)
            setattr(tg_bot, nama, getattr(self.palsu, nama))
        aksi._MEDIA._data.clear()

    def tearDown(self):
        for nama, nilai in self.asli.items():
            setattr(tg_bot, nama, nilai)
        aksi._MEDIA._data.clear()
        batas_laju.reset()

    @staticmethod
    def konteks(media=None, user_id=2):
        return aksi.Konteks(chat_id=7, user_id=user_id, media=media)


class RegistrasiTest(unittest.TestCase):
    def setUp(self):
        self.asli = (config.AI_ENABLED, config.AI_AKSI_BOT)
        config.AI_ENABLED = True
        config.AI_AKSI_BOT = True

    def tearDown(self):
        config.AI_ENABLED, config.AI_AKSI_BOT = self.asli

    def test_tool_aksi_terdaftar(self):
        nama = {t["function"]["name"] for t in aksi.SKEMA_AKSI}
        self.assertEqual(
            nama,
            {"hapus_background", "buat_stiker", "putar_lagu", "cek_saham", "berita_idx"},
        )
        self.assertEqual(set(aksi.NAMA_TOOL), nama)

    def test_ai_memberi_tool_aksi_ke_pengguna_biasa(self):
        from bot.services import ai

        nama = [t["function"]["name"] for t in ai.daftar_tool(admin=False)]
        self.assertIn("hapus_background", nama)
        self.assertIn("putar_lagu", nama)

    def test_ai_aksi_bisa_dimatikan(self):
        from bot.services import ai

        config.AI_AKSI_BOT = False
        nama = [t["function"]["name"] for t in ai.daftar_tool(admin=False)]
        self.assertNotIn("hapus_background", nama)

    def test_semua_skema_punya_deskripsi(self):
        for skema in aksi.SKEMA_AKSI:
            fungsi = skema["function"]
            self.assertTrue(fungsi["description"].strip(), fungsi["name"])
            self.assertEqual(fungsi["parameters"]["type"], "object")


class HapusBackgroundTest(_DasarAksi):
    def test_mengirim_png_hasil(self):
        with mock.patch.object(aksi.removebg, "hapus_background", return_value=b"png"):
            hasil = aksi.jalankan(
                "hapus_background",
                {},
                self.konteks({"jenis": "foto", "file_id": "f1", "ukuran": 10}),
            )

        self.assertIn("berhasil", hasil.lower())
        self.assertEqual(len(self.palsu.dokumen), 1)
        self.assertEqual(self.palsu.dokumen[0][1]["visible_file_name"], "hasil_nobg.png")

    def test_tanpa_media_memberi_pesan_jelas(self):
        hasil = aksi.jalankan("hapus_background", {}, self.konteks())
        self.assertIn("foto", hasil.lower())
        self.assertEqual(self.palsu.dokumen, [])

    def test_media_tersimpan_dipakai_untuk_permintaan_berikutnya(self):
        aksi.simpan_media(7, "foto", "f9", 10)
        with mock.patch.object(aksi.removebg, "hapus_background", return_value=b"png"):
            hasil = aksi.jalankan("hapus_background", {}, self.konteks())
        self.assertIn("berhasil", hasil.lower())
        self.assertEqual(len(self.palsu.dokumen), 1)

    def test_error_api_diterjemahkan_tanpa_melempar(self):
        with mock.patch.object(
            aksi.removebg, "hapus_background", side_effect=aksi.removebg.RemoveBgError("kuota habis")
        ):
            hasil = aksi.jalankan(
                "hapus_background",
                {},
                self.konteks({"jenis": "foto", "file_id": "f1", "ukuran": 10}),
            )
        self.assertIn("GAGAL", hasil)
        self.assertIn("kuota habis", hasil)

    def test_foto_terlalu_besar_ditolak_sebelum_diunduh(self):
        besar = aksi.removebg.MAX_IMAGE_BYTES + 1
        with mock.patch.object(aksi.removebg, "hapus_background") as proses:
            hasil = aksi.jalankan(
                "hapus_background",
                {},
                self.konteks({"jenis": "foto", "file_id": "f1", "ukuran": besar}),
            )
        proses.assert_not_called()
        self.assertEqual(self.palsu.dokumen, [])
        self.assertIn("12MB", hasil)

    def test_ekstensi_ditebak_dari_isi_file(self):
        self.assertEqual(aksi._ekstensi_gambar(b"\x89PNG\r\n"), ".png")
        self.assertEqual(aksi._ekstensi_gambar(b"\xff\xd8\xff\xe0"), ".jpg")
        self.assertEqual(aksi._ekstensi_gambar(b"RIFF0000WEBPVP8 "), ".webp")
        self.assertEqual(aksi._ekstensi_gambar(b"GIF89a"), ".gif")
        self.assertEqual(aksi._ekstensi_gambar(b"???"), ".jpg")


class PutarLaguTest(_DasarAksi):
    def _video(self):
        return {
            "id": "abc",
            "url": "https://youtu.be/abc",
            "judul": "Lagu Uji",
            "channel": "Kanal",
            "durasi": 200,
        }

    def test_audio_dikirim_ke_chat(self):
        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        try:
            with mock.patch.object(aksi.YT, "ffmpeg_tersedia", return_value=True), \
                 mock.patch.object(aksi.YT, "cari_video", return_value=[self._video()]), \
                 mock.patch.object(aksi.YT, "download_youtube_audio", return_value=path), \
                 mock.patch.object(aksi.YT, "bersihkan_folder"):
                hasil = aksi.jalankan("putar_lagu", {"judul": "lagu uji"}, self.konteks())
        finally:
            os.path.exists(path) and os.remove(path)

        self.assertIn("berhasil", hasil.lower())
        self.assertEqual(len(self.palsu.audio), 1)
        self.assertEqual(self.palsu.audio[0][1]["title"], "Lagu Uji")

    def test_mode_cari_tidak_mengunduh(self):
        with mock.patch.object(aksi.YT, "ffmpeg_tersedia", return_value=True), \
             mock.patch.object(aksi.YT, "cari_video", return_value=[self._video()]) as cari, \
             mock.patch.object(aksi.YT, "download_youtube_audio") as unduh:
            hasil = aksi.jalankan(
                "putar_lagu", {"judul": "lagu", "format": "cari"}, self.konteks()
            )

        unduh.assert_not_called()
        self.assertIn("Lagu Uji", hasil)
        self.assertEqual(cari.call_args.kwargs["jumlah"], 5)

    def test_batas_laju_tetap_berlaku(self):
        from bot.batas_laju import BATAS_UNDUH

        for _ in range(BATAS_UNDUH[0]):
            batas_laju.cek(2, "unduh")

        with mock.patch.object(aksi.YT, "ffmpeg_tersedia", return_value=True), \
             mock.patch.object(aksi.YT, "cari_video") as cari:
            hasil = aksi.jalankan("putar_lagu", {"judul": "lagu"}, self.konteks())

        cari.assert_not_called()
        self.assertIn("Batas", hasil)


class SahamBeritaTest(_DasarAksi):
    class _DataPalsu:
        empty = False

        def __contains__(self, kunci):
            return kunci == "Close"

        def __getitem__(self, kunci):
            return self if kunci == "Close" else 9000

        @property
        def iloc(self):
            return self

    def test_saham_ihsg(self):
        with mock.patch.object(aksi, "ambil_data_saham", return_value=self._DataPalsu()):
            hasil = aksi.jalankan("cek_saham", {"kode": "IHSG"}, self.konteks())
        self.assertIn("IHSG", hasil)
        self.assertIn("9.000", hasil)

    def test_kode_saham_tidak_valid(self):
        hasil = aksi.jalankan("cek_saham", {"kode": "BBCA123456"}, self.konteks())
        self.assertIn("tidak valid", hasil.lower())

    def test_berita_idx(self):
        berita = [
            {"tanggal": "2 Nov", "judul": "IHSG menguat", "sumber": "Kompas", "link": "https://x"},
        ]
        with mock.patch.object(aksi.idx_news, "ambil_berita_terbaru", return_value=berita):
            hasil = aksi.jalankan("berita_idx", {"jumlah": 1}, self.konteks())
        self.assertIn("IHSG menguat", hasil)
        self.assertIn("Kompas", hasil)


class RoutingServiceTest(unittest.TestCase):
    def test_tool_aksi_dirutekan_ke_aksi(self):
        from bot.services import ai

        calls = [
            {
                "id": "call_0",
                "type": "function",
                "function": {"name": "putar_lagu", "arguments": '{"judul": "x"}'},
            }
        ]
        konteks = aksi.Konteks(chat_id=7, user_id=2)
        with mock.patch.object(aksi, "jalankan", return_value="ok") as jalankan:
            ai._jalankan_tool_calls(calls, set(), konteks=konteks)

        jalankan.assert_called_once_with("putar_lagu", {"judul": "x"}, konteks)
        self.assertEqual(calls[0]["_hasil"], "ok")

    def test_tool_aksi_tanpa_konteks_ditolak(self):
        from bot.services import ai

        calls = [
            {
                "id": "call_0",
                "type": "function",
                "function": {"name": "hapus_background", "arguments": "{}"},
            }
        ]
        with mock.patch.object(aksi, "jalankan") as jalankan:
            ai._jalankan_tool_calls(calls, set())

        jalankan.assert_not_called()
        self.assertIn("konteks", calls[0]["_hasil"])

    def test_aksi_dijalankan_lalu_model_menjawab(self):
        from bot.services import ai

        asli = (config.AI_ENABLED, config.AI_API_KEY, config.AI_WEB_SEARCH)
        config.AI_ENABLED = True
        config.AI_API_KEY = "kunci-uji"
        config.AI_WEB_SEARCH = False
        ai._last_request._data.clear()
        konteks = aksi.Konteks(chat_id=7, user_id=2)
        panggilan = {"n": 0}

        def post(_payload):
            panggilan["n"] += 1
            if panggilan["n"] == 1:
                return {
                    "choices": [
                        {
                            "message": {
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": "c1",
                                        "function": {
                                            "name": "hapus_background",
                                            "arguments": "{}",
                                        },
                                    }
                                ],
                            }
                        }
                    ],
                    "usage": {"total_tokens": 5},
                }
            return {"choices": [{"message": {"content": "sudah ya"}}], "usage": {}}

        try:
            with mock.patch.object(ai, "_post", side_effect=post), \
                 mock.patch.object(aksi, "jalankan", return_value="Berhasil") as jalankan:
                hasil = ai.tanya(7, [{"role": "user", "content": "hapus bg"}], konteks=konteks)
        finally:
            config.AI_ENABLED, config.AI_API_KEY, config.AI_WEB_SEARCH = asli
            ai._last_request._data.clear()

        jalankan.assert_called_once_with("hapus_background", {}, konteks)
        self.assertEqual(hasil["teks"], "sudah ya")
        self.assertIn("✂️ hapus background", hasil["sumber"])


class HandlerTest(unittest.TestCase):
    def setUp(self):
        from bot.handlers import ai as h

        self.h = h
        h.AI_SESSIONS.clear(7)
        h.play_mode.tutup(7)

    def tearDown(self):
        self.h.AI_SESSIONS.clear(7)
        self.h.play_mode.tutup(7)

    @staticmethod
    def _pesan(caption):
        return types.SimpleNamespace(
            chat=types.SimpleNamespace(id=7),
            caption=caption,
            photo=[types.SimpleNamespace(file_id="f1", file_size=100)],
        )

    def test_foto_dengan_caption_direbut_saat_mode_ai_aktif(self):
        self.h.AI_SESSIONS.set(7, {"riwayat": [], "akses": "user"})
        self.assertTrue(self.h.direbut_ai(self._pesan("hapus background ini")))

    def test_foto_tanpa_caption_tetap_ke_handler_otomatis(self):
        self.h.AI_SESSIONS.set(7, {"riwayat": [], "akses": "user"})
        self.assertFalse(self.h.direbut_ai(self._pesan("")))

    def test_mode_ai_nonaktif_tidak_merebut(self):
        self.assertFalse(self.h.direbut_ai(self._pesan("hapus background")))

    def test_caption_ai_direbut_walau_mode_belum_aktif(self):
        self.assertTrue(self.h.direbut_ai(self._pesan("/ai hapus background-nya")))

    def test_caption_perintah_lain_tidak_direbut(self):
        self.assertFalse(self.h.direbut_ai(self._pesan("/play lofi")))

    def test_alur_stiker_tidak_direbut(self):
        from bot.handlers.sticker import STIKER_SESSIONS

        STIKER_SESSIONS.set(7, {"mode": "buat"})
        try:
            self.assertFalse(self.h.direbut_ai(self._pesan("buat stiker ini")))
        finally:
            STIKER_SESSIONS.clear(7)

    def test_stiker_yang_sudah_selesai_tidak_menghalangi_ai(self):
        from bot.handlers.sticker import STIKER_SESSIONS

        STIKER_SESSIONS.set(7, {"mode": "buat", "path": "C:/tmp/x.jpg"})
        self.h.AI_SESSIONS.set(7, {"riwayat": [], "akses": "user"})
        try:
            self.assertTrue(self.h.direbut_ai(self._pesan("hapus background ini")))
        finally:
            STIKER_SESSIONS.clear(7)

    def test_caption_ai_tanpa_pertanyaan_hanya_menyapa(self):
        self.assertTrue(self.h._perintah_ai("/ai"))
        self.assertTrue(self.h._perintah_ai("/ai@chrosttbot"))
        self.assertEqual(self.h._pertanyaan_media("/ai"), "")
        self.assertEqual(
            self.h._pertanyaan_media("/ai hapus background"), "hapus background"
        )

    def test_caption_biasa_bukan_perintah(self):
        self.assertFalse(self.h._perintah_ai("/play lofi"))
        self.assertFalse(self.h._perintah_ai("tanya ai soal ini"))
        self.assertEqual(self.h._pertanyaan_media("buat stiker"), "buat stiker")

    def test_media_disimpan_saat_caption_diterima(self):
        self.h.AI_SESSIONS.set(7, {"riwayat": [], "akses": "user"})
        pesan = self._pesan("buat stiker dari foto ini")
        pesan.from_user = types.SimpleNamespace(id=2)
        pesan.message_id = 11

        with mock.patch.object(self.h, "direbut_ai", return_value=True), \
             mock.patch.object(self.h, "_jawab") as jawab:
            self.h.tangkap_media_ai.__wrapped__(pesan)

        media = aksi.ambil_media(7, 2)
        self.assertEqual(media["file_id"], "f1")
        jawab.assert_called_once()
        self.assertEqual(jawab.call_args.kwargs["media"]["file_id"], "f1")

    def test_foto_orang_lain_di_grup_tidak_dipakai(self):
        aksi.simpan_media(7, "foto", "punya-a", 100, user_id=1)
        self.assertIsNone(aksi.ambil_media(7, 2))
        self.assertIsNotNone(aksi.ambil_media(7, 1))


if __name__ == "__main__":
    unittest.main()
