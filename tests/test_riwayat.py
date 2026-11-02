import tempfile
import unittest

from bot.riwayat import RiwayatStore


class RiwayatStoreTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="chrostt-test-")
        self.store = RiwayatStore(f"{self.folder}/riwayat.db")

    def tearDown(self):
        try:
            self.store._conn.close()
        except Exception:
            pass

    def test_chat_baru_kosong(self):
        self.assertEqual(self.store.siapkan(1, "user"), [])

    def test_catat_lalu_ambil(self):
        self.store.catat(1, "user", "halo")
        self.store.catat(1, "assistant", "hai")
        self.assertEqual(
            self.store.ambil(1),
            [
                {"role": "user", "content": "halo"},
                {"role": "assistant", "content": "hai"},
            ],
        )

    def test_konten_kosong_tidak_disimpan(self):
        self.store.catat(1, "user", "   ")
        self.assertEqual(self.store.ambil(1), [])

    def test_ganti_akses_mengosongkan_riwayat(self):
        self.store.catat(1, "user", "pesan admin", akses="admin")
        self.store.siapkan(1, "user")
        self.assertEqual(self.store.ambil(1), [])

    def test_hapus_satu_chat(self):
        self.store.catat(1, "user", "x")
        self.assertTrue(self.store.hapus(1))
        self.assertEqual(self.store.ambil(1), [])
        self.assertFalse(self.store.hapus(1))

    def test_hapus_semua(self):
        self.store.catat(1, "user", "x")
        self.store.catat(2, "user", "y")
        self.assertEqual(self.store.hapus_semua(), 2)
        self.assertEqual(self.store.statistik()["jumlah_chat"], 0)

    def test_pemangkasan_per_chat(self):
        import bot.riwayat as modul

        asli = modul.MAKS_PESAN_SIMPAN
        modul.MAKS_PESAN_SIMPAN = 5
        try:
            for i in range(10):
                self.store.catat(1, "user", f"pesan {i}")
            isi = self.store.ambil(1)
        finally:
            modul.MAKS_PESAN_SIMPAN = asli

        self.assertEqual(len(isi), 5)
        self.assertEqual(isi[-1]["content"], "pesan 9")

    def test_state_disimpan_dan_dihapus(self):
        self.store.simpan_state("kunci", "nilai")
        self.assertEqual(self.store.ambil_state("kunci"), "nilai")

        self.store.hapus_state("kunci")
        self.assertIsNone(self.store.ambil_state("kunci"))

    def test_state_dengan_prefix(self):
        self.store.simpan_state("play_prompt:1", "10")
        self.store.simpan_state("play_prompt:2", "20")
        self.store.simpan_state("lain", "x")

        hasil = dict(self.store.state_dengan_prefix("play_prompt:"))
        self.assertEqual(hasil, {"play_prompt:1": "10", "play_prompt:2": "20"})

    def test_pengguna_tersimpan_dan_diperbarui(self):
        self.store.simpan_pengguna(10, "Ilham", "ilham")
        self.store.simpan_pengguna(20, "Ricky", "rkyarc")

        self.assertEqual(self.store.jumlah_pengguna(), 2)

        # Update tanpa username: username lama harus dipertahankan
        self.store.simpan_pengguna(10, "Ilham Baru", "")
        data = {u["id"]: u for u in self.store.daftar_pengguna()}
        self.assertEqual(data[10]["nama"], "Ilham Baru")
        self.assertEqual(data[10]["username"], "ilham")
        self.assertEqual(self.store.jumlah_pengguna(), 2)

    def test_info_tanpa_isi_pesan(self):
        self.store.catat(1, "user", "rahasia")
        info = self.store.info(1)

        self.assertEqual(info["jumlah_pesan"], 1)
        self.assertNotIn("rahasia", str(info))


if __name__ == "__main__":
    unittest.main()
