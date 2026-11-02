"""Uji siklus mode tunggu /play: prompt ForceReply harus selalu bersih.

Bug paling mahal di sini adalah prompt yang menggantung di chat pengguna,
jadi test-nya menekankan pembersihan dan kepemilikan mode.
"""

import types as pytypes
import unittest
from unittest import mock

from telebot import types as tg_types

from bot import play_mode, tg_bot


class _TelegramPalsu:
    def __init__(self):
        self.dikirim = []
        self.dihapus = []
        self.gagal_kirim = False

    def send_message(self, chat_id, teks, **kwargs):
        if self.gagal_kirim:
            raise RuntimeError("jaringan mati")
        self.dikirim.append({"chat_id": chat_id, "teks": teks, "kwargs": kwargs})
        return pytypes.SimpleNamespace(message_id=900 + len(self.dikirim))

    def delete_message(self, chat_id, message_id):
        self.dihapus.append((chat_id, message_id))
        return True


class DasarPlayTest(unittest.TestCase):
    def setUp(self):
        play_mode._STATE._data.clear()
        self.palsu = _TelegramPalsu()
        self.patch_kirim = mock.patch.object(tg_bot, "send_message", self.palsu.send_message)
        self.patch_hapus = mock.patch.object(tg_bot, "delete_message", self.palsu.delete_message)
        self.patch_kirim.start()
        self.patch_hapus.start()
        # State prompt disimpan di SQLite; pakai store in-memory agar test bersih
        self.patch_state = mock.patch.multiple(
            play_mode.RIWAYAT,
            simpan_state=mock.DEFAULT,
            ambil_state=mock.DEFAULT,
            hapus_state=mock.DEFAULT,
            state_dengan_prefix=mock.DEFAULT,
        )
        self.state = self.patch_state.start()
        self.state["simpan_state"].return_value = None
        self.state["ambil_state"].return_value = None
        self.state["hapus_state"].return_value = None
        self.state["state_dengan_prefix"].return_value = []

    def tearDown(self):
        self.patch_state.stop()
        self.patch_kirim.stop()
        self.patch_hapus.stop()
        play_mode._STATE._data.clear()


class StatusTest(DasarPlayTest):
    def test_belum_aktif(self):
        self.assertFalse(play_mode.aktif(1))
        self.assertFalse(play_mode.sedang_menunggu(1, 5))

    def test_aktif_setelah_minta_judul(self):
        play_mode.minta_judul(1, user_id=5)
        self.assertTrue(play_mode.aktif(1))
        self.assertTrue(play_mode.sedang_menunggu(1, 5))

    def test_pengguna_lain_tidak_boleh_mengisi(self):
        play_mode.minta_judul(1, user_id=5)
        self.assertFalse(play_mode.sedang_menunggu(1, 99))

    def test_tanpa_user_id_mode_tetap_diterima(self):
        play_mode.minta_judul(1)
        self.assertTrue(play_mode.sedang_menunggu(1, 99))


class MintaJudulTest(DasarPlayTest):
    def test_mengirim_prompt_force_reply(self):
        play_mode.minta_judul(1, user_id=5)
        self.assertEqual(len(self.palsu.dikirim), 1)
        kiriman = self.palsu.dikirim[0]
        self.assertIsInstance(kiriman["kwargs"]["reply_markup"], tg_types.ForceReply)
        self.assertEqual(kiriman["kwargs"]["parse_mode"], "HTML")

    def test_di_grup_prompt_selective_dan_membalas(self):
        play_mode.minta_judul(1, user_id=5, balas_pesan_id=77)
        markup = self.palsu.dikirim[0]["kwargs"]["reply_markup"]
        self.assertTrue(markup.selective)
        self.assertEqual(self.palsu.dikirim[0]["kwargs"]["reply_parameters"].message_id, 77)

    def test_prompt_lama_dihapus_dulu(self):
        play_mode.minta_judul(1, user_id=5)
        prompt_lama = self.palsu.dikirim[0]["kwargs"]
        play_mode.minta_judul(1, user_id=5)
        self.assertTrue(self.palsu.dihapus, "prompt lama harus dihapus saat minta ulang")
        self.assertTrue(prompt_lama)  # memakai prompt pertama sebagai pembanding

    def test_id_prompt_disimpan_ke_database(self):
        play_mode.minta_judul(1, user_id=5)
        self.state["simpan_state"].assert_called_once()

    def test_gagal_kirim_prompt_tidak_mengaktifkan_mode(self):
        self.palsu.gagal_kirim = True
        play_mode.minta_judul(1, user_id=5)
        self.assertFalse(play_mode.aktif(1), "mode tidak boleh aktif kalau prompt gagal")

    def test_chat_berbeda_tidak_saling_mengganggu(self):
        play_mode.minta_judul(1, user_id=5)
        play_mode.minta_judul(2, user_id=6)
        self.assertTrue(play_mode.aktif(1))
        self.assertTrue(play_mode.aktif(2))
        self.assertTrue(play_mode.sedang_menunggu(1, 5))
        self.assertTrue(play_mode.sedang_menunggu(2, 6))


class LepasPromptTest(DasarPlayTest):
    def test_prompt_dihapus_tapi_mode_tetap_aktif(self):
        play_mode.minta_judul(1, user_id=5)
        prompt_id = play_mode._STATE.get(1)["prompt_id"]
        self.palsu.dihapus.clear()

        play_mode.lepas_prompt(1)

        self.assertIn((1, prompt_id), self.palsu.dihapus)
        self.assertTrue(play_mode.aktif(1), "mode harus tetap aktif")
        self.assertIsNone(play_mode._STATE.get(1)["prompt_id"])

    def test_lepas_prompt_tanpa_mode_tidak_error(self):
        play_mode.lepas_prompt(999)  # tidak boleh melempar


class TutupTest(DasarPlayTest):
    def test_menutup_mode_dan_menghapus_prompt(self):
        play_mode.minta_judul(1, user_id=5)
        prompt_id = play_mode._STATE.get(1)["prompt_id"]
        self.palsu.dihapus.clear()

        play_mode.tutup(1)

        self.assertFalse(play_mode.aktif(1))
        self.assertIn((1, prompt_id), self.palsu.dihapus)

    def test_tutup_tanpa_mode_tidak_error(self):
        play_mode.tutup(999)

    def test_prompt_dari_database_ikut_dihapus(self):
        """Setelah restart, prompt lama hanya tercatat di SQLite."""
        self.state["ambil_state"].return_value = "555"
        play_mode.tutup(1)
        self.assertIn((1, 555), self.palsu.dihapus)

    def test_state_database_dilupakan(self):
        play_mode.minta_judul(1, user_id=5)
        play_mode.tutup(1)
        self.state["hapus_state"].assert_called()


class BersihkanSisaTest(DasarPlayTest):
    def test_prompt_sisa_dihapus(self):
        self.state["state_dengan_prefix"].return_value = [("play_prompt:42", "777")]
        play_mode.bersihkan_sisa()
        self.assertIn((42, 777), self.palsu.dihapus)
        self.state["hapus_state"].assert_any_call("play_prompt:42")

    def test_mode_yang_masih_aktif_tidak_diganggu(self):
        play_mode.minta_judul(42, user_id=5)
        self.palsu.dihapus.clear()
        self.state["state_dengan_prefix"].return_value = [("play_prompt:42", "777")]

        play_mode.bersihkan_sisa()

        self.assertEqual(self.palsu.dihapus, [], "prompt yang masih dipakai jangan dihapus")

    def test_kunci_rusak_dibersihkan_tanpa_error(self):
        self.state["state_dengan_prefix"].return_value = [("play_prompt:bukan-angka", "x")]
        play_mode.bersihkan_sisa()  # tidak boleh melempar
        self.state["hapus_state"].assert_called_with("play_prompt:bukan-angka")

    def test_database_error_tidak_melempar(self):
        self.state["state_dengan_prefix"].side_effect = RuntimeError("db rusak")
        play_mode.bersihkan_sisa()  # tidak boleh melempar


class TutupSemuaTest(DasarPlayTest):
    def test_semua_prompt_dihapus(self):
        play_mode.minta_judul(1, user_id=5)
        play_mode.minta_judul(2, user_id=6)
        self.palsu.dihapus.clear()

        play_mode.tutup_semua()

        self.assertTrue(play_mode._STATE.get(1) is None)
        self.assertTrue(play_mode._STATE.get(2) is None)
        self.assertEqual(len(self.palsu.dihapus), 2)


if __name__ == "__main__":
    unittest.main()
