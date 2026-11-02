"""Pastikan `pyproject.toml` dan `requirements.txt` tidak menyimpang.

Dua daftar dependency yang berbeda isi adalah sumber bug yang tenang: CI
memasang satu hal, developer memasang hal lain. Test ini mengunci keduanya
agar selalu sinkron.
"""

import pathlib
import re
import unittest

AKAR = pathlib.Path(__file__).resolve().parent.parent

# Paket yang memang hanya untuk development, jadi boleh ada di requirements.txt
# tanpa muncul sebagai dependency runtime di pyproject.toml.
KHUSUS_DEV = {"watchfiles"}


def _blok_dependency_runtime() -> list[str]:
    teks = (AKAR / "pyproject.toml").read_text(encoding="utf-8")

    # Ambil blok "dependencies = [ ... ]" milik tabel [project]
    awal = teks.index("\n[project]")
    mulai = teks.index("dependencies = [", awal)
    akhir = teks.index("]", mulai)

    isi = teks[mulai + len("dependencies = [") : akhir]
    return [baris.strip().strip('",') for baris in isi.splitlines() if baris.strip()]


def _normalisasi(spek: str) -> tuple[str, str]:
    """Pisahkan nama paket dari batas versi, abaikan spasi dan huruf besar."""
    cocok = re.match(r"^([A-Za-z0-9_.-]+)\s*(.*)$", spek.strip())
    nama = cocok.group(1).lower().replace("_", "-")
    batas = cocok.group(2).replace(" ", "").replace("(", "").replace(")", "")
    return nama, batas


def _dependency_requirements() -> list[str]:
    hasil = []
    for baris in (AKAR / "requirements.txt").read_text(encoding="utf-8").splitlines():
        baris = baris.split("#")[0].strip()
        if baris and not baris.startswith("-"):
            hasil.append(baris)
    return hasil


class DependencySinkronTest(unittest.TestCase):
    def setUp(self):
        self.pyproject = dict(_normalisasi(s) for s in _blok_dependency_runtime())
        self.requirements = dict(_normalisasi(s) for s in _dependency_requirements())

    def test_semua_dependency_runtime_ada_di_requirements(self):
        hilang = [
            nama
            for nama in self.pyproject
            if nama not in self.requirements
        ]
        self.assertEqual(hilang, [], f"Paket ini hilang dari requirements.txt: {hilang}")

    def test_batas_versi_sama(self):
        beda = {
            nama: (batas, self.requirements[nama])
            for nama, batas in self.pyproject.items()
            if nama in self.requirements and self.requirements[nama] != batas
        }
        self.assertEqual(beda, {}, f"Batas versi berbeda (pyproject, requirements): {beda}")

    def test_requirements_tidak_punya_paket_liar(self):
        liar = [
            nama
            for nama in self.requirements
            if nama not in self.pyproject and nama not in KHUSUS_DEV
        ]
        self.assertEqual(
            liar,
            [],
            f"Paket di requirements.txt tidak ada di pyproject.toml: {liar}",
        )

    def test_yt_dlp_tanpa_batas_versi(self):
        # yt-dlp sering berubah mengikuti perubahan YouTube; dibiarkan mengikuti rilis.
        self.assertEqual(self.pyproject["yt-dlp"], "")
        self.assertEqual(self.requirements["yt-dlp"], "")


if __name__ == "__main__":
    unittest.main()
