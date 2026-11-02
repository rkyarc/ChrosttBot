"""Uji retry flood limit tanpa menunggu waktu nyata."""

import unittest
from unittest import mock

from bot import telegram_io as tg_io


class _FloodError(Exception):
    def __init__(self, retry_after=None, pesan="Too Many Requests: retry after 7"):
        super().__init__(pesan)
        if retry_after is not None:
            self.retry_after = retry_after


class RetryFloodTest(unittest.TestCase):
    def test_retry_after_dari_atribut(self):
        self.assertEqual(tg_io._retry_after(_FloodError(retry_after=12)), 12)

    def test_retry_after_dari_teks(self):
        self.assertEqual(tg_io._retry_after(_FloodError()), 7)

    def test_bukan_flood_menghasilkan_none(self):
        self.assertIsNone(tg_io._retry_after(ValueError("beda")))

    def test_kena_flood_mengenali_beberapa_bentuk(self):
        self.assertTrue(tg_io._kena_flood(Exception("Flood control exceeded")))
        self.assertTrue(tg_io._kena_flood(Exception("Too Many Requests")))
        self.assertTrue(tg_io._kena_flood(Exception("retry after 5")))
        self.assertFalse(tg_io._kena_flood(Exception("chat not found")))

    @mock.patch.object(tg_io.time, "sleep", return_value=None)
    def test_ulang_setelah_flood_lalu_sukses(self, tidur):
        panggilan = {"n": 0}

        def fungsi():
            panggilan["n"] += 1
            if panggilan["n"] == 1:
                raise _FloodError(retry_after=2)
            return "ok"

        self.assertEqual(tg_io._ulang(fungsi), "ok")
        self.assertEqual(panggilan["n"], 2)
        tidur.assert_called_once_with(2)

    @mock.patch.object(tg_io.time, "sleep", return_value=None)
    def test_menyerah_setelah_maks_ulang(self, _tidur):
        def selalu_flood():
            raise _FloodError(retry_after=1)

        with self.assertRaises(_FloodError):
            tg_io._ulang(selalu_flood)

    def test_error_biasa_tidak_diulang(self):
        panggilan = {"n": 0}

        def fungsi():
            panggilan["n"] += 1
            raise ValueError("beda")

        with self.assertRaises(ValueError):
            tg_io._ulang(fungsi)
        self.assertEqual(panggilan["n"], 1)


if __name__ == "__main__":
    unittest.main()
