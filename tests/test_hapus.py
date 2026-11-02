"""Uji handler /del — jalur destruktif, jadi perilakunya dikunci ketat.

Tidak ada jaringan: deleteMessages / deleteMessage / send_message di-stub.
"""

import types
import unittest
from unittest import mock

from bot.handlers import hapus as h


class _TelegramPalsu:
    """Rekam semua panggilan Telegram, dengan kontrol sukses/gagal per pesan."""

    def __init__(self, gagal_ids=(), bulk_gagal=False):
        self.gagal_ids = set(gagal_ids)
        self.bulk_gagal = bulk_gagal
        self.dihapus = []
        self.dikirim = []

    @staticmethod
    def _error(deskripsi: str):
        return h.ApiTelegramException(
            "Bad Request",
            "Bad Request",
            {"ok": False, "error_code": 400, "description": deskripsi},
        )

    def delete_message(self, chat_id, message_id):
        if message_id in self.gagal_ids:
            raise self._error("Bad Request: message can't be deleted")
        self.dihapus.append(message_id)
        return True

    def delete_messages(self, chat_id, ids):
        if self.bulk_gagal:
            raise self._error("Bad Request: chat not found")
        self.dihapus.extend(ids)
        return True

    def send_message(self, chat_id, teks, **kwargs):
        self.dikirim.append(teks)
        return types.SimpleNamespace(message_id=1)


def _pesan(chat_id=7, message_id=100, teks="/del", reply=None):
    return types.SimpleNamespace(
        chat=types.SimpleNamespace(id=chat_id, type="private"),
        message_id=message_id,
        text=teks,
        reply_to_message=reply,
        from_user=types.SimpleNamespace(id=1),
    )


class DeskripsiErrorTest(unittest.TestCase):
    def _err(self, deskripsi):
        return h.ApiTelegramException(
            "Bad Request",
            f"Bad Request: {deskripsi}",
            {"ok": False, "error_code": 400, "description": f"Bad Request: {deskripsi}"},
        )

    def test_pesan_sudah_tidak_ada(self):
        self.assertIn("sudah tidak ada", h._deskripsi_error(self._err("message to delete not found")))

    def test_batas_48_jam(self):
        self.assertIn("48 jam", h._deskripsi_error(self._err("message can't be deleted")))

    def test_kurang_izin(self):
        self.assertIn("izin", h._deskripsi_error(self._err("not enough rights to delete")))

    def test_chat_tidak_ditemukan(self):
        self.assertIn("chat tidak ditemukan", h._deskripsi_error(self._err("chat not found")))

    def test_error_tak_dikenal_dipotong(self):
        teks = h._deskripsi_error(self._err("sesuatu yang aneh"))
        self.assertLessEqual(len(teks), 120)


class HapusBanyakTest(unittest.TestCase):
    def test_bulk_sukses_tidak_ada_alasan(self):
        palsu = _TelegramPalsu()
        with mock.patch.object(h.tg_bot, "delete_messages", palsu.delete_messages), \
             mock.patch.object(h.tg_bot, "delete_message", palsu.delete_message):
            berhasil, alasan = h._hapus_banyak(7, [1, 2, 3])
        self.assertEqual(berhasil, 3)
        self.assertEqual(alasan, [])

    def test_bulk_gagal_jatuh_ke_per_pesan(self):
        palsu = _TelegramPalsu(bulk_gagal=True)
        with mock.patch.object(h.tg_bot, "delete_messages", palsu.delete_messages), \
             mock.patch.object(h.tg_bot, "delete_message", palsu.delete_message):
            berhasil, alasan = h._hapus_banyak(7, [1, 2, 3])
        # Fallback per pesan tetap menghapus semuanya
        self.assertEqual(berhasil, 3)

    def test_sebagian_pesan_gagal_dilaporkan(self):
        palsu = _TelegramPalsu(gagal_ids={2}, bulk_gagal=True)
        with mock.patch.object(h.tg_bot, "delete_messages", palsu.delete_messages), \
             mock.patch.object(h.tg_bot, "delete_message", palsu.delete_message):
            berhasil, alasan = h._hapus_banyak(7, [1, 2, 3])
        self.assertEqual(berhasil, 2)
        self.assertTrue(alasan, "alasan kegagalan harus dilaporkan")

    def test_alasan_duplikat_tidak_diulang(self):
        palsu = _TelegramPalsu(gagal_ids={1, 2, 3}, bulk_gagal=True)
        with mock.patch.object(h.tg_bot, "delete_messages", palsu.delete_messages), \
             mock.patch.object(h.tg_bot, "delete_message", palsu.delete_message):
            berhasil, alasan = h._hapus_banyak(7, [1, 2, 3])
        self.assertEqual(berhasil, 0)
        self.assertEqual(len(alasan), len(set(alasan)))

    def test_daftar_kosong_aman(self):
        berhasil, alasan = h._hapus_banyak(7, [])
        self.assertEqual((berhasil, alasan), (0, []))


class LaporanTest(unittest.TestCase):
    def test_tanpa_kegagalan_tidak_menyebut_alasan(self):
        teks = h._laporan(3, 0, [])
        self.assertIn("<b>3</b>", teks)
        self.assertNotIn("Alasan", teks)

    def test_kegagalan_dan_alasan_muncul(self):
        teks = h._laporan(1, 2, ["pesan sudah tidak ada"])
        self.assertIn("Dilewati", teks)
        self.assertIn("pesan sudah tidak ada", teks)

    def test_alasan_di_escape(self):
        teks = h._laporan(1, 1, ["<script>alert(1)</script>"])
        self.assertNotIn("<script>", teks)
        self.assertIn("&lt;script&gt;", teks)


class PerintahHapusTest(unittest.TestCase):
    def test_tanpa_argumen_sukses_senyap(self):
        """/del biasa menghapus pesannya sendiri tanpa mengirim laporan."""
        palsu = _TelegramPalsu()
        with mock.patch.object(h.tg_bot, "delete_messages", palsu.delete_messages), \
             mock.patch.object(h.tg_bot, "delete_message", palsu.delete_message), \
             mock.patch.object(h.tg_bot, "send_message", palsu.send_message):
            h.perintah_hapus(_pesan(teks="/del"))

        self.assertIn(100, palsu.dihapus)
        self.assertEqual(palsu.dikirim, [], "tidak boleh ada pesan saat sukses")

    def test_tanpa_argumen_gagal_memberi_cara_pakai(self):
        palsu = _TelegramPalsu(gagal_ids={100}, bulk_gagal=True)
        with mock.patch.object(h.tg_bot, "delete_messages", palsu.delete_messages), \
             mock.patch.object(h.tg_bot, "delete_message", palsu.delete_message), \
             mock.patch.object(h.tg_bot, "send_message", palsu.send_message):
            h.perintah_hapus(_pesan(teks="/del"))

        self.assertEqual(len(palsu.dikirim), 1)
        self.assertIn("Cara pakai /del", palsu.dikirim[0])

    def test_reply_menghapus_target_dan_perintah(self):
        palsu = _TelegramPalsu()
        reply = types.SimpleNamespace(message_id=42)
        with mock.patch.object(h.tg_bot, "delete_messages", palsu.delete_messages), \
             mock.patch.object(h.tg_bot, "delete_message", palsu.delete_message), \
             mock.patch.object(h.tg_bot, "send_message", palsu.send_message):
            h.perintah_hapus(_pesan(message_id=100, teks="/del", reply=reply))

        self.assertIn(42, palsu.dihapus, "pesan yang dibalas harus terhapus")
        self.assertIn(100, palsu.dihapus, "pesan perintah harus terhapus")
        self.assertEqual(palsu.dikirim, [])

    def test_reply_gagal_total_memberi_pesan_gagal(self):
        palsu = _TelegramPalsu(gagal_ids={42, 100}, bulk_gagal=True)
        reply = types.SimpleNamespace(message_id=42)
        with mock.patch.object(h.tg_bot, "delete_messages", palsu.delete_messages), \
             mock.patch.object(h.tg_bot, "delete_message", palsu.delete_message), \
             mock.patch.object(h.tg_bot, "send_message", palsu.send_message):
            h.perintah_hapus(_pesan(message_id=100, teks="/del", reply=reply))

        self.assertEqual(len(palsu.dikirim), 1)
        self.assertIn("GAGAL MENGHAPUS", palsu.dikirim[0])

    def test_jumlah_terhitung_dari_message_id(self):
        palsu = _TelegramPalsu()
        with mock.patch.object(h.tg_bot, "delete_messages", palsu.delete_messages), \
             mock.patch.object(h.tg_bot, "delete_message", palsu.delete_message), \
             mock.patch.object(h.tg_bot, "send_message", palsu.send_message):
            h.perintah_hapus(_pesan(message_id=100, teks="/del 5"))

        self.assertEqual(sorted(palsu.dihapus), [96, 97, 98, 99, 100])

    def test_jumlah_dibatasi_maksimum(self):
        palsu = _TelegramPalsu()
        with mock.patch.object(h.tg_bot, "delete_messages", palsu.delete_messages), \
             mock.patch.object(h.tg_bot, "delete_message", palsu.delete_message), \
             mock.patch.object(h.tg_bot, "send_message", palsu.send_message):
            h.perintah_hapus(_pesan(message_id=1000, teks="/del 999"))

        self.assertEqual(len(palsu.dihapus), min(999, h.MAKS_SEKALI_HAPUS))

    def test_all_memakai_batas_maksimum(self):
        palsu = _TelegramPalsu()
        with mock.patch.object(h.tg_bot, "delete_messages", palsu.delete_messages), \
             mock.patch.object(h.tg_bot, "delete_message", palsu.delete_message), \
             mock.patch.object(h.tg_bot, "send_message", palsu.send_message):
            h.perintah_hapus(_pesan(message_id=500, teks="/del all"))

        self.assertEqual(len(palsu.dihapus), h.MAKS_SEKALI_HAPUS)

    def test_message_id_kecil_tidak_menghasilkan_id_negatif(self):
        palsu = _TelegramPalsu()
        with mock.patch.object(h.tg_bot, "delete_messages", palsu.delete_messages), \
             mock.patch.object(h.tg_bot, "delete_message", palsu.delete_message), \
             mock.patch.object(h.tg_bot, "send_message", palsu.send_message):
            h.perintah_hapus(_pesan(message_id=2, teks="/del 10"))

        self.assertTrue(all(mid >= 1 for mid in palsu.dihapus), palsu.dihapus)

    def test_argumen_bukan_angka_ditolak(self):
        palsu = _TelegramPalsu()
        with mock.patch.object(h.tg_bot, "delete_messages", palsu.delete_messages), \
             mock.patch.object(h.tg_bot, "delete_message", palsu.delete_message), \
             mock.patch.object(h.tg_bot, "send_message", palsu.send_message):
            h.perintah_hapus(_pesan(teks="/del banyak"))

        self.assertEqual(palsu.dihapus, [], "tidak boleh menghapus apa pun")
        self.assertIn("ARGUMEN TIDAK VALID", palsu.dikirim[0])

    def test_argumen_html_di_escape(self):
        palsu = _TelegramPalsu()
        with mock.patch.object(h.tg_bot, "delete_messages", palsu.delete_messages), \
             mock.patch.object(h.tg_bot, "delete_message", palsu.delete_message), \
             mock.patch.object(h.tg_bot, "send_message", palsu.send_message):
            h.perintah_hapus(_pesan(teks="/del <b>x</b>"))

        self.assertNotIn("<b>x</b>", palsu.dikirim[0])
        self.assertIn("&lt;b&gt;", palsu.dikirim[0])

    def test_sebagian_gagal_mengirim_laporan(self):
        palsu = _TelegramPalsu(gagal_ids={98}, bulk_gagal=True)
        with mock.patch.object(h.tg_bot, "delete_messages", palsu.delete_messages), \
             mock.patch.object(h.tg_bot, "delete_message", palsu.delete_message), \
             mock.patch.object(h.tg_bot, "send_message", palsu.send_message):
            h.perintah_hapus(_pesan(message_id=100, teks="/del 3"))

        self.assertEqual(len(palsu.dikirim), 1)
        self.assertIn("HASIL HAPUS", palsu.dikirim[0])


if __name__ == "__main__":
    unittest.main()
