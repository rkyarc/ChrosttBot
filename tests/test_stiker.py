"""Uji fitur stiker: alur menu, /toimg, /tomp4, dan pembersihan file.

ffmpeg tidak dipanggil: fungsi konversi di service di-stub supaya test tetap
cepat dan jalan di CI yang tidak punya ffmpeg. Yang dikunci adalah logika
handler — bug nyata yang pernah terjadi:

1. Tombol "Jadi PNG/MP4" setelah membuat stiker mengonversi media ASLI, bukan
   stiker hasil konversi (path sesi tidak pernah diperbarui).
2. Folder sementara menumpuk karena file sumber tidak pernah dibersihkan.
3. Stiker statis -> MP4 menghasilkan video 0,04 detik (frame tunggal di-encode
   apa adanya) sehingga di Telegram tampak rusak.
"""

import os
import shutil
import tempfile
import types
import unittest
from unittest import mock

from bot import batas_laju, tg_bot
from bot.handlers import sticker as h


class BotPalsu:
    """Pengganti bot Telegram: merekam panggilan, tanpa jaringan."""

    def __init__(self):
        self.terkirim = []
        self.file = {}

    def send_message(self, chat_id, teks, **kwargs):
        self.terkirim.append(("message", teks))
        return types.SimpleNamespace(message_id=len(self.terkirim))

    def edit_message_text(self, teks, chat_id, message_id, **kwargs):
        self.terkirim.append(("edit", teks))
        return types.SimpleNamespace(message_id=message_id)

    def send_sticker(self, chat_id, berkas, **kwargs):
        self.terkirim.append(("sticker", os.path.basename(getattr(berkas, "name", ""))))
        return types.SimpleNamespace(message_id=90)

    def send_document(self, chat_id, berkas, **kwargs):
        self.terkirim.append(("document", kwargs.get("visible_file_name")))
        return types.SimpleNamespace(message_id=91)

    def send_video(self, chat_id, berkas, **kwargs):
        self.terkirim.append(("video", kwargs.get("caption", "")))
        return types.SimpleNamespace(message_id=92)

    def answer_callback_query(self, *args, **kwargs):
        return True

    def get_file(self, file_id):
        return types.SimpleNamespace(file_path=self.file[file_id])

    def download_file(self, file_path):
        with open(file_path, "rb") as f:
            return f.read()

    def jenis(self, sejak=0):
        return [j for j, _ in self.terkirim[sejak:]]

    def teks(self, sejak=0):
        return " ".join(t for _, t in self.terkirim[sejak:])


class _DasarStiker(unittest.TestCase):
    def setUp(self):
        batas_laju.reset()
        self.palsu = BotPalsu()
        self.asli = {}
        for nama in (
            "send_message",
            "edit_message_text",
            "send_sticker",
            "send_document",
            "send_video",
            "answer_callback_query",
            "get_file",
            "download_file",
        ):
            self.asli[nama] = getattr(tg_bot, nama)
            setattr(tg_bot, nama, getattr(self.palsu, nama))

        self.tmp = tempfile.mkdtemp(prefix="uji-stiker-")
        self.chat = 11
        h.STIKER_SESSIONS.clear(self.chat)

    def tearDown(self):
        for nama, nilai in self.asli.items():
            setattr(tg_bot, nama, nilai)
        h.STIKER_SESSIONS.clear(self.chat)
        shutil.rmtree(self.tmp, ignore_errors=True)
        batas_laju.reset()

    # ---------- helper ----------

    def siapkan_file(self, nama="sumber.jpg", isi=b"data"):
        path = os.path.join(self.tmp, nama)
        with open(path, "wb") as f:
            f.write(isi)
        self.palsu.file[nama] = path
        return path

    def pesan_media(self, file_id="sumber.jpg", jenis="foto"):
        pesan = types.SimpleNamespace(
            chat=types.SimpleNamespace(id=self.chat),
            from_user=types.SimpleNamespace(id=2),
            caption=None,
            photo=None, video=None, animation=None, sticker=None, document=None,
        )
        if jenis == "foto":
            pesan.photo = [types.SimpleNamespace(file_id=file_id, file_size=100)]
        elif jenis == "video":
            pesan.video = types.SimpleNamespace(file_id=file_id)
        else:
            pesan.sticker = types.SimpleNamespace(
                file_id=file_id, is_video=(jenis == "webm"), is_animated=False
            )
        return pesan

    def callback(self, data="stiker_buat"):
        return types.SimpleNamespace(
            id="cb",
            data=data,
            from_user=types.SimpleNamespace(id=2),
            message=types.SimpleNamespace(
                chat=types.SimpleNamespace(id=self.chat), message_id=5
            ),
        )

    def perintah(self, teks, balasan):
        return types.SimpleNamespace(
            chat=types.SimpleNamespace(id=self.chat),
            from_user=types.SimpleNamespace(id=2),
            text=teks,
            reply_to_message=balasan,
        )


class AlurTombolTest(_DasarStiker):
    """Bug #1: tombol PNG/MP4 harus memakai stiker hasil konversi."""

    def _buat_stiker_palsu(self):
        hasil_stiker = os.path.join(self.tmp, "stiker.webp")
        with open(hasil_stiker, "wb") as f:
            f.write(b"stiker")
        return hasil_stiker

    def test_path_sesi_diubah_ke_stiker_hasil_konversi(self):
        self.siapkan_file("sumber.jpg")
        h.aksi_stiker.__wrapped__(self.callback("stiker_buat"))
        hasil_stiker = self._buat_stiker_palsu()

        def palsu_buat(sumber, tujuan_dir, mulai=0.0):
            return hasil_stiker, "statis"

        with mock.patch.object(h, "buat_stiker", side_effect=palsu_buat), \
                mock.patch.object(h, "folder_sementara", return_value=tempfile.mkdtemp()):
            h.proses_media_stiker.__wrapped__(self.pesan_media())

        sesi = h.STIKER_SESSIONS.get(self.chat) or {}
        self.assertTrue(str(sesi.get("path", "")).endswith((".webp", ".webm")))
        self.assertIn("sticker", self.palsu.jenis())

    def test_status_sukses_mengingatkan_simpan_ke_favorit(self):
        self.siapkan_file("sumber.jpg")
        h.aksi_stiker.__wrapped__(self.callback("stiker_buat"))
        hasil_stiker = self._buat_stiker_palsu()

        with mock.patch.object(h, "buat_stiker", return_value=(hasil_stiker, "statis")), \
                mock.patch.object(h, "folder_sementara", return_value=tempfile.mkdtemp()):
            h.proses_media_stiker.__wrapped__(self.pesan_media())

        self.assertIn("favorit", self.palsu.teks().lower())


class TombolKonversiTest(_DasarStiker):
    def test_png_mengirim_dokumen(self):
        path = self.siapkan_file("stiker.webp")
        h.STIKER_SESSIONS.set(self.chat, {"path": path, "folder": self.tmp})

        hasil = self.siapkan_file("hasil.png")
        with mock.patch.object(h, "stiker_ke_png", return_value=hasil), \
                mock.patch.object(h, "folder_sementara", return_value=tempfile.mkdtemp()):
            h._ubah_stiker(self.callback("stiker_ke_png"), "png")

        self.assertIn("document", self.palsu.jenis())

    def test_mp4_mengirim_video(self):
        path = self.siapkan_file("stiker.webp")
        h.STIKER_SESSIONS.set(self.chat, {"path": path, "folder": self.tmp})

        hasil = self.siapkan_file("hasil.mp4")
        with mock.patch.object(h, "stiker_ke_mp4", return_value=hasil), \
                mock.patch.object(h, "folder_sementara", return_value=tempfile.mkdtemp()):
            h._ubah_stiker(self.callback("stiker_ke_mp4"), "mp4")

        self.assertIn("video", self.palsu.jenis())

    def test_sesi_ditutup_setelah_konversi(self):
        path = self.siapkan_file("stiker.webp")
        h.STIKER_SESSIONS.set(self.chat, {"path": path, "folder": self.tmp})

        hasil = self.siapkan_file("hasil.png")
        with mock.patch.object(h, "stiker_ke_png", return_value=hasil), \
                mock.patch.object(h, "folder_sementara", return_value=tempfile.mkdtemp()):
            h._ubah_stiker(self.callback("stiker_ke_png"), "png")

        self.assertIsNone(h.STIKER_SESSIONS.get(self.chat))


class PerintahReplyTest(_DasarStiker):
    """/toimg & /tomp4: jalur tanpa menu, tidak bergantung sesi."""

    def test_toimg_membalas_stiker_mengirim_png(self):
        self.siapkan_file("stiker.webp")
        hasil = self.siapkan_file("hasil.png")

        with mock.patch.object(h, "stiker_ke_png", return_value=hasil), \
                mock.patch.object(h, "folder_sementara", return_value=tempfile.mkdtemp()):
            h.perintah_toimg.__wrapped__(
                self.perintah("/toimg", self.pesan_media("stiker.webp", "statis"))
            )

        self.assertIn("document", self.palsu.jenis())

    def test_tomp4_membalas_stiker_mengirim_video(self):
        self.siapkan_file("stiker.webm")
        hasil = self.siapkan_file("hasil.mp4")

        with mock.patch.object(h, "stiker_ke_mp4", return_value=hasil), \
                mock.patch.object(h, "folder_sementara", return_value=tempfile.mkdtemp()):
            h.perintah_tomp4.__wrapped__(
                self.perintah("/tomp4", self.pesan_media("stiker.webm", "webm"))
            )

        self.assertIn("video", self.palsu.jenis())

    def test_tanpa_reply_memberi_petunjuk(self):
        h.perintah_toimg.__wrapped__(self.perintah("/toimg", None))
        self.assertIn("BALAS STIKERNYA", self.palsu.teks())

    def test_balas_foto_ditolak(self):
        self.siapkan_file("foto.jpg")
        h.perintah_tomp4.__wrapped__(
            self.perintah("/tomp4", self.pesan_media("foto.jpg", "foto"))
        )
        self.assertIn("BUKAN STIKER", self.palsu.teks())


class KebersihanFileTest(_DasarStiker):
    """Bug #2: folder temp tidak boleh menumpuk."""

    def test_media_baru_membuang_folder_media_lama(self):
        lama = tempfile.mkdtemp(prefix="lama-", dir=self.tmp)
        self.siapkan_file("baru.jpg")
        h.aksi_stiker.__wrapped__(self.callback("stiker_buat"))
        h.STIKER_SESSIONS.set(self.chat, {"mode": "buat", "folder": lama})

        hasil = os.path.join(self.tmp, "stiker2.webp")
        with open(hasil, "wb") as f:
            f.write(b"x")

        with mock.patch.object(h, "buat_stiker", return_value=(hasil, "statis")), \
                mock.patch.object(h, "folder_sementara", return_value=tempfile.mkdtemp()):
            h.proses_media_stiker.__wrapped__(self.pesan_media("baru.jpg"))

        self.assertFalse(os.path.exists(lama))

    def test_bersihkan_sesi_menghapus_folder_dan_entri(self):
        folder = tempfile.mkdtemp(prefix="sesi-", dir=self.tmp)
        h.STIKER_SESSIONS.set(self.chat, {"mode": "buat", "folder": folder})
        h._bersihkan_sesi(self.chat)
        self.assertFalse(os.path.exists(folder))
        self.assertIsNone(h.STIKER_SESSIONS.get(self.chat))

    def test_batal_membersihkan_folder(self):
        folder = tempfile.mkdtemp(prefix="batal-", dir=self.tmp)
        h.STIKER_SESSIONS.set(self.chat, {"mode": "buat", "folder": folder})
        h.aksi_stiker.__wrapped__(self.callback("stiker_batal"))
        self.assertFalse(os.path.exists(folder))
        self.assertIsNone(h.STIKER_SESSIONS.get(self.chat))


if __name__ == "__main__":
    unittest.main()
