"""Uji logika akses admin tanpa menyentuh Telegram."""

import unittest
from unittest import mock

import config
from bot import admin


class AksesAdminTest(unittest.TestCase):
    def setUp(self):
        self.asli = config.ADMIN_IDS_SET
        config.ADMIN_IDS_SET = frozenset({111, 222})

    def tearDown(self):
        config.ADMIN_IDS_SET = self.asli

    def test_admin_dikenali(self):
        self.assertTrue(admin.apakah_admin(111))

    def test_bukan_admin_ditolak(self):
        self.assertFalse(admin.apakah_admin(999))

    def test_user_id_kosong_ditolak(self):
        self.assertFalse(admin.apakah_admin(None))
        self.assertFalse(admin.apakah_admin(0))

    def test_input_bukan_angka_ditolak(self):
        self.assertFalse(admin.apakah_admin("bukan-angka"))

    def test_memakai_from_user_bukan_chat_id(self):
        """Bot di grup: chat_id grup tidak boleh memberi akses admin."""
        message = mock.Mock()
        message.chat.id = 111  # id grup kebetulan sama dengan id admin
        message.from_user.id = 999  # pengirim bukan admin

        self.assertFalse(admin.pesan_dari_admin(message))

    def test_callback_dari_admin(self):
        call = mock.Mock()
        call.from_user.id = 222
        self.assertTrue(admin.callback_dari_admin(call))


class CatatPenggunaTest(unittest.TestCase):
    def test_pesan_grup_tidak_dicatat(self):
        with mock.patch("bot.admin.RIWAYAT") as riwayat:
            message = mock.Mock()
            message.chat.type = "group"
            message.from_user.id = 5
            message.from_user.is_bot = False

            admin.catat_pengguna(message)

            riwayat.simpan_pengguna.assert_not_called()

    def test_pesan_pribadi_dicatat(self):
        with mock.patch("bot.admin.RIWAYAT") as riwayat:
            message = mock.Mock()
            message.chat.type = "private"
            message.from_user.id = 5
            message.from_user.is_bot = False
            message.from_user.full_name = "Ilham"
            message.from_user.username = "ilham"

            admin.catat_pengguna(message)

            riwayat.simpan_pengguna.assert_called_once_with(5, "Ilham", "ilham")

    def test_bot_tidak_dicatat(self):
        with mock.patch("bot.admin.RIWAYAT") as riwayat:
            message = mock.Mock()
            message.chat.type = "private"
            message.from_user.is_bot = True

            admin.catat_pengguna(message)

            riwayat.simpan_pengguna.assert_not_called()

    def test_database_rusak_tidak_melempar(self):
        with mock.patch("bot.admin.RIWAYAT") as riwayat:
            riwayat.simpan_pengguna.side_effect = RuntimeError("db rusak")

            message = mock.Mock()
            message.chat.type = "private"
            message.from_user.id = 5
            message.from_user.is_bot = False
            message.from_user.full_name = "x"
            message.from_user.username = ""

            admin.catat_pengguna(message)  # tidak boleh raise


if __name__ == "__main__":
    unittest.main()
