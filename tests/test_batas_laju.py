import unittest

from bot import batas_laju


class BatasLajuTest(unittest.TestCase):
    def setUp(self):
        batas_laju.reset()

    def tearDown(self):
        batas_laju.reset()

    def test_aksi_di_bawah_batas_lolos(self):
        for _ in range(3):
            batas_laju.cek(1, "unduh")  # tidak boleh melempar

    def test_melewati_batas_ditolak(self):
        batas, _ = batas_laju.BATAS_UNDUH
        for _ in range(batas):
            batas_laju.cek(1, "unduh")

        with self.assertRaises(batas_laju.BatasTerlampaui) as ctx:
            batas_laju.cek(1, "unduh")

        self.assertGreaterEqual(ctx.exception.detik, 1)
        self.assertTrue(ctx.exception.pesan)

    def test_pengguna_lain_tidak_terpengaruh(self):
        batas, _ = batas_laju.BATAS_UNDUH
        for _ in range(batas):
            batas_laju.cek(1, "unduh")

        # User 2 masih punya kuota sendiri
        batas_laju.cek(2, "unduh")

    def test_jenis_aksi_punya_kuota_terpisah(self):
        batas, _ = batas_laju.BATAS_UNDUH
        for _ in range(batas):
            batas_laju.cek(1, "unduh")

        batas_laju.cek(1, "stiker")  # kuota stiker masih utuh

    def test_user_kosong_selalu_lolos(self):
        for _ in range(100):
            batas_laju.cek(None, "umum")

    def test_periksa_tidak_menambah_jejak(self):
        batas, _ = batas_laju.BATAS_UNDUH
        for _ in range(batas):
            self.assertTrue(batas_laju.periksa(1, "unduh"))

        # periksa() berulang tetap True karena tidak mencatat aksi
        self.assertTrue(batas_laju.periksa(1, "unduh"))
        self.assertFalse(batas_laju.periksa(1, "unduh") is None)

    def test_setelah_ditolak_tetap_ditolak(self):
        batas, _ = batas_laju.BATAS_UNDUH
        for _ in range(batas):
            batas_laju.cek(1, "unduh")

        with self.assertRaises(batas_laju.BatasTerlampaui):
            batas_laju.cek(1, "unduh")
        with self.assertRaises(batas_laju.BatasTerlampaui):
            batas_laju.cek(1, "unduh")


if __name__ == "__main__":
    unittest.main()
