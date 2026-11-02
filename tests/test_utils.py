import unittest

from bot.utils import (
    escape_html,
    ke_telegram_html,
    potong_html,
    potong_teks,
    strip_html,
)


class EscapeHtmlTest(unittest.TestCase):
    def test_mengamankan_karakter_html(self):
        self.assertEqual(escape_html("<b>&\"</b>"), "&lt;b&gt;&amp;&quot;&lt;/b&gt;")

    def test_none_menjadi_string_kosong(self):
        self.assertEqual(escape_html(None), "")

    def test_teks_biasa_tidak_berubah(self):
        self.assertEqual(escape_html("BBCA naik 1,2%"), "BBCA naik 1,2%")


class PotongTeksTest(unittest.TestCase):
    def test_teks_pendek_dikembalikan_utuh(self):
        self.assertEqual(potong_teks("halo"), ["halo"])

    def test_teks_kosong_menjadi_list_kosong(self):
        self.assertEqual(potong_teks("   "), [])

    def test_teks_panjang_dipecah_di_batas_kata(self):
        teks = "kata " * 1000
        bagian = potong_teks(teks, batas=100)

        self.assertGreater(len(bagian), 1)
        for potongan in bagian:
            self.assertLessEqual(len(potongan), 100)
            # Tidak boleh memotong di tengah kata
            self.assertFalse(potongan.endswith("kat"))

    def test_tidak_ada_isi_yang_hilang(self):
        teks = " ".join(str(i) for i in range(500))
        bagian = potong_teks(teks, batas=80)
        gabungan = " ".join(bagian).split()

        self.assertEqual(gabungan, teks.split())


class PotongHtmlTest(unittest.TestCase):
    def test_tag_selalu_seimbang_per_bagian(self):
        teks = "<b>" + ("kata " * 500) + "</b>"
        bagian = potong_html(teks, batas=120)

        self.assertGreater(len(bagian), 1)
        for potongan in bagian:
            self.assertEqual(
                potongan.count("<b>"),
                potongan.count("</b>"),
                f"tag tidak seimbang: {potongan[:60]}",
            )

    def test_tidak_memotong_di_tengah_tag(self):
        teks = "<i>" + ("panjang " * 300) + "</i>"
        for potongan in potong_html(teks, batas=100):
            self.assertNotIn("<i", potongan.replace("<i>", ""))
            self.assertNotIn("</i", potongan.replace("</i>", ""))

    def test_teks_pendek_tidak_diubah(self):
        teks = "<b>halo</b>"
        self.assertEqual(potong_html(teks), [teks])


class KeTelegramHtmlTest(unittest.TestCase):
    def test_bold_markdown_menjadi_tag_b(self):
        self.assertEqual(ke_telegram_html("**tebal**"), "<b>tebal</b>")

    def test_code_block_menjadi_pre(self):
        hasil = ke_telegram_html("```python\nprint(1)\n```")
        self.assertEqual(hasil, "<pre>print(1)</pre>")

    def test_inline_code_menjadi_code(self):
        self.assertEqual(ke_telegram_html("pakai `pip`"), "pakai <code>pip</code>")

    def test_kurung_siku_tidak_merusak_html(self):
        hasil = ke_telegram_html("nilai <script>alert(1)</script>")
        self.assertNotIn("<script>", hasil)
        self.assertIn("&lt;script&gt;", hasil)


class StripHtmlTest(unittest.TestCase):
    def test_membuang_tag_dan_unescape_entitas(self):
        self.assertEqual(strip_html("<b>a</b> &amp; b"), "a & b")

    def test_none_aman(self):
        self.assertEqual(strip_html(None), "")


if __name__ == "__main__":
    unittest.main()
