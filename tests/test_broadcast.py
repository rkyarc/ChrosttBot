"""Uji broadcast admin: berjalan di thread, menghitung hasil dengan benar."""

import types
import unittest
from unittest import mock

from bot import telegram_io as tg_io
from bot.handlers import admin as h_admin


class JalankanBroadcastTest(unittest.TestCase):
    def setUp(self):
        self.penerima = [
            {"id": 1, "nama": "A", "username": "a", "terakhir": 0},
            {"id": 2, "nama": "B", "username": "b", "terakhir": 0},
            {"id": 3, "nama": "C", "username": "c", "terakhir": 0},
        ]
        h_admin._broadcast_aktif.clear()

    def tearDown(self):
        h_admin._broadcast_aktif.clear()

    def test_menghitung_sukses_dan_gagal(self):
        status = types.SimpleNamespace(message_id=555)
        editan = []

        def kirim(chat_id, teks, **kwargs):
            if chat_id == 999:  # chat admin: pesan status
                return status
            if chat_id == 2:
                return None  # simulasi gagal kirim
            return types.SimpleNamespace(message_id=1)

        with mock.patch.object(tg_io, "kirim", side_effect=kirim), \
             mock.patch.object(
                 tg_io, "edit", side_effect=lambda *a, **k: editan.append(a)
             ), \
             mock.patch.object(h_admin.time, "sleep", return_value=None):
            h_admin._jalankan_broadcast(999, "halo", self.penerima)

        laporan = [a[2] for a in editan if "BROADCAST SELESAI" in str(a[2])]
        self.assertTrue(laporan, "harus ada laporan akhir")
        teks = laporan[0]
        self.assertIn("<b>2</b>", teks)  # 2 terkirim
        self.assertIn("<b>1</b>", teks)  # 1 gagal

    def test_flag_aktif_dibersihkan_setelah_selesai(self):
        h_admin._broadcast_aktif.add(999)

        with mock.patch.object(tg_io, "kirim", return_value=None), \
             mock.patch.object(h_admin.time, "sleep", return_value=None):
            h_admin._jalankan_broadcast(999, "halo", self.penerima)

        self.assertNotIn(999, h_admin._broadcast_aktif)

    def test_kegagalan_total_tetap_membersihkan_flag(self):
        h_admin._broadcast_aktif.add(999)

        with mock.patch.object(
            h_admin, "_kirim_ke_semua", side_effect=RuntimeError("meledak")
        ), mock.patch.object(tg_io, "kirim", return_value=None):
            h_admin._jalankan_broadcast(999, "halo", self.penerima)

        self.assertNotIn(999, h_admin._broadcast_aktif)

    def test_handler_tidak_menahan_worker(self):
        """kirim_broadcast harus langsung kembali, bukan menunggu loop selesai."""
        call = types.SimpleNamespace(
            id="cb",
            data="admin_kirim",
            from_user=types.SimpleNamespace(id=42),
            message=types.SimpleNamespace(
                chat=types.SimpleNamespace(id=999, type="private"), message_id=5
            ),
        )

        dibuat = []

        class ThreadPalsu:
            def __init__(self, *a, **k):
                dibuat.append((a, k))

            def start(self):
                pass  # jangan benar-benar jalan di test

        with mock.patch.object(h_admin, "_admin_call", return_value=True), \
             mock.patch.object(h_admin, "_draft_valid", return_value={"teks": "x"}), \
             mock.patch.object(h_admin, "daftar_pengguna", return_value=self.penerima), \
             mock.patch.object(h_admin.threading, "Thread", ThreadPalsu), \
             mock.patch.object(h_admin.tg_bot, "answer_callback_query", return_value=None):
            h_admin.kirim_broadcast(call)

        self.assertEqual(len(dibuat), 1, "broadcast harus dijalankan di thread")
        _, kwargs = dibuat[0]
        self.assertTrue(kwargs.get("daemon"), "thread harus daemon agar tidak menahan exit")

    def test_broadcast_ganda_ditolak(self):
        call = types.SimpleNamespace(
            id="cb",
            data="admin_kirim",
            from_user=types.SimpleNamespace(id=42),
            message=types.SimpleNamespace(
                chat=types.SimpleNamespace(id=999, type="private"), message_id=5
            ),
        )

        dibuat = []

        class ThreadPalsu:
            def __init__(self, *a, **k):
                dibuat.append(a)

            def start(self):
                pass

        pesan = []
        h_admin._broadcast_aktif.add(999)

        with mock.patch.object(h_admin, "_admin_call", return_value=True), \
             mock.patch.object(h_admin, "_draft_valid", return_value={"teks": "x"}), \
             mock.patch.object(h_admin, "daftar_pengguna", return_value=self.penerima), \
             mock.patch.object(h_admin.threading, "Thread", ThreadPalsu), \
             mock.patch.object(
                 h_admin.tg_bot,
                 "send_message",
                 side_effect=lambda *a, **k: pesan.append(a),
             ), \
             mock.patch.object(h_admin.tg_bot, "answer_callback_query", return_value=None):
            h_admin.kirim_broadcast(call)

        self.assertEqual(dibuat, [], "broadcast kedua tidak boleh dijalankan")
        self.assertTrue(
            any("masih berjalan" in str(p) for p in pesan),
            "admin harus diberi tahu kenapa ditolak",
        )


if __name__ == "__main__":
    unittest.main()
