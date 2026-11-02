"""Uji websearch tanpa jaringan.

Fokus pada bagian yang dulu salah: pemilihan backend, parsing tanggal,
peringkat kesegaran, dan format hasil untuk model.
"""

import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from bot.services import websearch


class BackendTersediaTest(unittest.TestCase):
    def test_membuang_backend_yang_tidak_terpasang(self):
        # google sudah tidak ada di ddgs 9.16; permintaan ke sana hanya
        # menghasilkan peringatan, jadi harus disaring.
        with mock.patch.dict(
            websearch._DDGS_ENGINES,
            {"text": {"duckduckgo": object(), "yahoo": object()}},
            clear=True,
        ):
            hasil = websearch._backend_tersedia(
                "text", ("google", "duckduckgo", "yahoo")
            )
        self.assertEqual(hasil, "duckduckgo, yahoo")

    def test_semua_kandidat_hilang_menghasilkan_none(self):
        with mock.patch.dict(websearch._DDGS_ENGINES, {"text": {}}, clear=True):
            self.assertIsNone(websearch._backend_tersedia("text", ("google",)))

    def test_kategori_tidak_dikenal_menghasilkan_none(self):
        with mock.patch.dict(websearch._DDGS_ENGINES, {}, clear=True):
            self.assertIsNone(websearch._backend_tersedia("video", ("bing",)))


class ParseTanggalTest(unittest.TestCase):
    def test_iso_dengan_offset(self):
        hasil = websearch._parse_tanggal("2026-10-31T02:29:22+00:00")
        self.assertEqual(hasil.year, 2026)
        self.assertEqual(hasil.month, 10)
        self.assertEqual(hasil.day, 31)

    def test_iso_dengan_z(self):
        hasil = websearch._parse_tanggal("2026-10-16T02:27:00Z")
        self.assertEqual(hasil.day, 16)
        self.assertIsNotNone(hasil.tzinfo)

    def test_rfc822_dari_rss(self):
        hasil = websearch._parse_tanggal("Mon, 02 Nov 2026 08:00:00 GMT")
        self.assertEqual((hasil.year, hasil.month, hasil.day), (2026, 11, 2))

    def test_tanggal_saja(self):
        hasil = websearch._parse_tanggal("2026-11-01")
        self.assertEqual((hasil.month, hasil.day), (11, 1))

    def test_relatif_dihitung_dari_sekarang(self):
        hasil = websearch._parse_tanggal("2 jam yang lalu")
        selisih = datetime.now(timezone.utc) - hasil
        self.assertGreater(selisih.total_seconds(), 7000)
        self.assertLess(selisih.total_seconds(), 7400)

    def test_nilai_tidak_dikenal_menghasilkan_none(self):
        for nilai in (None, "", "kemarin lusa sore", "bukan tanggal"):
            self.assertIsNone(websearch._parse_tanggal(nilai), nilai)


class FormatTanggalTest(unittest.TestCase):
    def test_tanpa_tanggal_menghasilkan_kosong(self):
        self.assertEqual(websearch._format_tanggal({"waktu": None}), "")

    def test_tanggal_relatif_tidak_menampilkan_jam_palsu(self):
        # Tanggal dari teks relatif dikonversi memakai jam sekarang, jadi
        # jamnya tidak bermakna. Yang ditampilkan hanya tanggalnya.
        hasil = {
            "waktu": datetime.now(timezone.utc) - timedelta(days=2),
            "waktu_dari_halaman": False,
        }
        teks = websearch._format_tanggal(hasil)
        self.assertIn("hari lalu", teks)
        self.assertNotIn("UTC", teks)

    def test_tanggal_dari_halaman_menampilkan_jam(self):
        hasil = {
            "waktu": datetime.now(timezone.utc) - timedelta(hours=2),
            "waktu_dari_halaman": True,
        }
        teks = websearch._format_tanggal(hasil)
        self.assertIn("UTC", teks)
        self.assertIn("dari halaman", teks)

    def test_tanggal_masa_depan_ditandai_tidak_wajar(self):
        hasil = {"waktu": datetime.now(timezone.utc) + timedelta(days=30)}
        teks = websearch._format_tanggal(hasil)
        self.assertIn("tidak wajar", teks)


class TanggalDariHtmlTest(unittest.TestCase):
    def test_meta_published_time(self):
        html = (
            '<head><meta property="article:published_time" '
            'content="2026-11-02T01:00:00+00:00"></head>'
        )
        hasil = websearch._tanggal_dari_html(html)
        self.assertEqual((hasil.month, hasil.day), (11, 2))

    def test_urutan_atribut_dibalik(self):
        html = (
            '<meta content="2026-10-05T10:00:00Z" '
            'property="article:published_time">'
        )
        self.assertEqual(websearch._tanggal_dari_html(html).day, 5)

    def test_json_ld(self):
        html = '<script>{"datePublished": "2026-09-01T08:00:00Z"}</script>'
        self.assertEqual(websearch._tanggal_dari_html(html).month, 9)

    def test_tag_time(self):
        html = '<time datetime="2026-08-17T12:00:00Z">17 Agustus</time>'
        self.assertEqual(websearch._tanggal_dari_html(html).day, 17)

    def test_tanpa_tanggal_menghasilkan_none(self):
        self.assertIsNone(websearch._tanggal_dari_html("<html><body>halo</body></html>"))
        self.assertIsNone(websearch._tanggal_dari_html(""))


class ButuhTerkiniTest(unittest.TestCase):
    def test_kata_waktu_dikenali(self):
        for q in (
            "cuaca Tuban hari ini",
            "harga emas antam hari ini",
            "skor Liverpool tadi malam",
            "jadwal kereta besok",
        ):
            self.assertTrue(websearch._butuh_terkini(q), q)

    def test_pertanyaan_konseptual_bukan_terkini(self):
        for q in ("apa itu vector database", "sejarah majapahit", "cara kerja diesel"):
            self.assertFalse(websearch._butuh_terkini(q), q)


class GabungTest(unittest.TestCase):
    def _hasil(self, url, judul, skor, menit_lalu=None, sumber="web"):
        waktu = (
            datetime.now(timezone.utc) - timedelta(minutes=menit_lalu)
            if menit_lalu is not None
            else None
        )
        return {"url": url, "judul": judul, "ringkas": "", "sumber": sumber,
                "waktu": waktu, "_skor": skor}

    def test_dedup_url_sama(self):
        kumpulan = [
            self._hasil("https://a.com/x", "A", 5),
            self._hasil("https://a.com/x/", "A lagi", 3),
        ]
        hasil = websearch._gabung(kumpulan, 10, False)
        self.assertEqual(len(hasil), 1)

    def test_maksimal_dua_per_domain(self):
        kumpulan = [
            self._hasil(f"https://a.com/{i}", f"A{i}", 5 - i) for i in range(5)
        ]
        hasil = websearch._gabung(kumpulan, 10, False)
        self.assertEqual(len(hasil), 2)

    def test_hasil_baru_naik_saat_query_terkini(self):
        kumpulan = [
            self._hasil("https://lama.com/a", "Lama", 6, menit_lalu=60 * 24 * 30),
            self._hasil("https://baru.com/b", "Baru", 4, menit_lalu=30),
        ]
        terkini = websearch._gabung(kumpulan, 2, terkini=True)
        self.assertEqual(terkini[0]["url"], "https://baru.com/b")

    def test_bonus_kesegaran_lebih_kecil_untuk_query_biasa(self):
        kumpulan = [
            self._hasil("https://lama.com/a", "Lama", 6, menit_lalu=60 * 24 * 30),
            self._hasil("https://baru.com/b", "Baru", 4, menit_lalu=30),
        ]
        biasa = websearch._gabung(kumpulan, 2, terkini=False)
        # Skor 6 melawan 4+1 masih menang saat tidak butuh yang terbaru
        self.assertEqual(biasa[0]["url"], "https://lama.com/a")

    def test_skor_internal_dibersihkan(self):
        hasil = websearch._gabung([self._hasil("https://a.com/x", "A", 5)], 5, False)
        self.assertNotIn("_skor", hasil[0])

    def test_artikel_bulanan_tidak_menang_untuk_query_terkini(self):
        """Judul lama sering memuat frasa identik ("... Hari Ini")."""
        kumpulan = [
            self._hasil(
                "https://lama.com/cuaca",
                "Prakiraan Cuaca Tuban Hari Ini",
                12,
                menit_lalu=60 * 24 * 45,
            ),
            self._hasil(
                "https://bmkg.go.id/cuaca/tuban",
                "Prakiraan Cuaca Kabupaten Tuban",
                6,
                menit_lalu=None,
            ),
        ]
        hasil = websearch._gabung(kumpulan, 2, terkini=True)
        self.assertEqual(hasil[0]["url"], "https://bmkg.go.id/cuaca/tuban")

    def test_artikel_lama_tetap_menang_untuk_query_biasa(self):
        kumpulan = [
            self._hasil(
                "https://lama.com/konsep",
                "Penjelasan Konsep",
                12,
                menit_lalu=60 * 24 * 400,
            ),
            self._hasil("https://baru.com/x", "Sekilas", 3, menit_lalu=30),
        ]
        hasil = websearch._gabung(kumpulan, 2, terkini=False)
        self.assertEqual(hasil[0]["url"], "https://lama.com/konsep")



class CariFallbackTest(unittest.TestCase):
    def setUp(self):
        websearch._kosongkan_cache()

    def tearDown(self):
        websearch._kosongkan_cache()

    def test_tetap_ada_hasil_saat_engine_teks_gagal(self):
        """Wikipedia harus jadi jaring terakhir, bukan dilewati."""
        wiki = [
            {
                "judul": "Basis data vektor",
                "url": "https://id.wikipedia.org/wiki/Basis_data_vektor",
                "ringkas": "Basis data vektor menyimpan embedding.",
                "sumber": "wiki",
                "waktu": None,
            }
        ]
        with mock.patch.object(websearch, "_cari_ddgs", return_value=[]), \
             mock.patch.object(websearch, "_cari_berita_ddgs", return_value=[]), \
             mock.patch.object(websearch, "_cari_berita_rss", return_value=[]), \
             mock.patch.object(websearch, "_cari_wikipedia", return_value=wiki), \
             mock.patch.object(websearch, "_lengkapi_tanggal"):
            hasil = websearch.cari("basis data vektor", jumlah=5)

        self.assertTrue(hasil, "harus ada hasil dari Wikipedia")
        self.assertEqual(hasil[0]["sumber"], "wiki")

    def test_pengayaan_tanggal_dilewati_untuk_query_konseptual(self):
        hasil_web = [
            {
                "judul": "Apa itu vector database",
                "url": "https://contoh.com/a",
                "ringkas": "penjelasan vector database",
                "sumber": "web",
                "waktu": None,
            }
        ]
        with mock.patch.object(websearch, "_cari_ddgs", return_value=hasil_web), \
             mock.patch.object(websearch, "_cari_wikipedia", return_value=[]), \
             mock.patch.object(websearch, "_cari_berita_ddgs", return_value=[]), \
             mock.patch.object(websearch, "_cari_berita_rss", return_value=[]), \
             mock.patch.object(websearch, "_lengkapi_tanggal") as lengkapi:
            websearch.cari("apa itu vector database", jumlah=5)

        # Dipanggil, tetapi dengan terkini=False sehingga langsung kembali
        lengkapi.assert_called_once()
        self.assertFalse(lengkapi.call_args.args[1])

    def test_query_kosong(self):
        self.assertEqual(websearch.cari("   "), [])

    def test_hasil_di_cache(self):
        panggilan = {"n": 0}

        def pencari(query, jumlah):
            panggilan["n"] += 1
            return [{
                "judul": "hasil",
                "url": "https://contoh.com/x",
                "ringkas": "isi",
                "sumber": "web",
                "waktu": None,
            }]

        with mock.patch.object(websearch, "_cari_ddgs", side_effect=pencari), \
             mock.patch.object(websearch, "_cari_wikipedia", return_value=[]), \
             mock.patch.object(websearch, "_cari_berita_ddgs", return_value=[]), \
             mock.patch.object(websearch, "_cari_berita_rss", return_value=[]), \
             mock.patch.object(websearch, "_lengkapi_tanggal"):
            websearch.cari("contoh", jumlah=5)
            websearch.cari("contoh", jumlah=5)

        self.assertEqual(panggilan["n"], 1, "panggilan kedua harus dari cache")


class JalankanToolTest(unittest.TestCase):
    def test_tampilan_memuat_tanggal_dan_instruksi_kesegaran(self):
        hasil = [{
            "judul": "Harga emas hari ini",
            "url": "https://contoh.com/emas",
            "ringkas": "harga emas turun",
            "sumber": "berita",
            "waktu": datetime.now(timezone.utc) - timedelta(hours=3),
        }]
        with mock.patch.object(websearch, "cari", return_value=hasil):
            teks = websearch.jalankan_tool("web_search", {"query": "harga emas hari ini"})

        self.assertIn("Waktu pencarian", teks)
        self.assertIn("Tanggal:", teks)
        self.assertIn("jam lalu", teks)
        self.assertIn("Sumber: contoh.com", teks)

    def test_query_kosong(self):
        self.assertEqual(
            websearch.jalankan_tool("web_search", {"query": "  "}), "Query kosong."
        )

    def test_tanpa_hasil_memberi_saran(self):
        with mock.patch.object(websearch, "cari", return_value=[]):
            teks = websearch.jalankan_tool("web_search", {"query": "xyz"})
        self.assertIn("Tidak ada hasil", teks)

    def test_tool_tidak_dikenal(self):
        self.assertIn("tidak dikenal", websearch.jalankan_tool("hapus_file", {}))


if __name__ == "__main__":
    unittest.main()
