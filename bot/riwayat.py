"""Penyimpanan permanen riwayat obrolan AI per chat (SQLite).

SQLite dipilih karena ringan: bagian dari pustaka standar Python, tanpa server,
tanpa dependency tambahan, dan tetap aman untuk penulisan paralel berkat mode
WAL. File database dibuat otomatis di ``data/riwayat-ai.db``.

Setiap chat punya satu baris di tabel ``chat`` dan pesan-pesannya di tabel
``pesan``. Konteks yang dikirim ke model tetap dipotong oleh handler AI, jadi
simpanan di disk boleh lebih panjang daripada yang dipakai model.
"""

import logging
import os
import sqlite3
import threading
import time

log = logging.getLogger("chrosttbot.riwayat")

# Batas penyimpanan per chat (bukan batas konteks model)
MAKS_PESAN_SIMPAN = 300

# Batas jumlah chat yang disimpan; chat paling lama dibuang saat penuh
MAKS_CHAT = 1000

_SKEMA = """
CREATE TABLE IF NOT EXISTS chat (
    chat_id     INTEGER PRIMARY KEY,
    user_id     INTEGER,
    nama        TEXT NOT NULL DEFAULT '',
    username    TEXT NOT NULL DEFAULT '',
    tipe        TEXT NOT NULL DEFAULT '',
    akses       TEXT NOT NULL DEFAULT 'user',
    diperbarui  REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pesan (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    role    TEXT NOT NULL,
    konten  TEXT NOT NULL,
    waktu   REAL NOT NULL,
    FOREIGN KEY (chat_id) REFERENCES chat(chat_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pesan_chat ON pesan(chat_id, id);
CREATE INDEX IF NOT EXISTS idx_chat_update ON chat(diperbarui);

CREATE TABLE IF NOT EXISTS state (
    kunci  TEXT PRIMARY KEY,
    nilai  TEXT NOT NULL,
    waktu  REAL NOT NULL DEFAULT 0
);
"""


class RiwayatStore:
    """Riwayat obrolan per chat di SQLite dengan API kecil dan aman-thread."""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None

    # ================== KONEKSI ==================

    def _koneksi(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn

        if self.path != ":memory:":
            folder = os.path.dirname(self.path)
            if folder:
                os.makedirs(folder, exist_ok=True)

        try:
            conn = sqlite3.connect(
                self.path,
                check_same_thread=False,
                timeout=10,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.executescript(_SKEMA)
            conn.commit()
        except sqlite3.Error as e:
            log.error("Gagal membuka database riwayat %s: %s", self.path, e)
            raise

        self._conn = conn
        return conn

    # ================== BACA ==================

    def ambil(self, chat_id: int) -> list[dict]:
        """Seluruh riwayat chat, urut dari paling lama."""
        with self._lock:
            conn = self._koneksi()
            baris = conn.execute(
                "SELECT role, konten FROM pesan WHERE chat_id = ? ORDER BY id",
                (int(chat_id),),
            ).fetchall()
            return [
                {"role": r["role"], "content": r["konten"]}
                for r in baris
                if r["konten"]
            ]

    def info(self, chat_id: int) -> dict | None:
        """Metadata satu chat tanpa isi percakapan."""
        with self._lock:
            conn = self._koneksi()
            baris = conn.execute(
                "SELECT c.*, "
                "  (SELECT COUNT(*) FROM pesan p WHERE p.chat_id = c.chat_id) AS jumlah "
                "FROM chat c WHERE c.chat_id = ?",
                (int(chat_id),),
            ).fetchone()

            return self._ke_dict(baris) if baris else None

    def punya(self, chat_id: int) -> bool:
        with self._lock:
            conn = self._koneksi()
            baris = conn.execute(
                "SELECT 1 FROM chat WHERE chat_id = ?", (int(chat_id),)
            ).fetchone()
            return baris is not None

    def daftar(self) -> list[dict]:
        """Ringkasan semua chat, terbaru dulu. Tanpa isi pesan."""
        with self._lock:
            conn = self._koneksi()
            baris = conn.execute(
                "SELECT c.*, "
                "  (SELECT COUNT(*) FROM pesan p WHERE p.chat_id = c.chat_id) AS jumlah "
                "FROM chat c ORDER BY c.diperbarui DESC"
            ).fetchall()
            return [self._ke_dict(r) for r in baris]

    def statistik(self) -> dict:
        with self._lock:
            conn = self._koneksi()
            jumlah_chat = conn.execute("SELECT COUNT(*) FROM chat").fetchone()[0]
            jumlah_pesan = conn.execute("SELECT COUNT(*) FROM pesan").fetchone()[0]

        ukuran = 0
        if self.path != ":memory:":
            try:
                ukuran = os.path.getsize(self.path)
            except OSError:
                pass

        return {
            "jumlah_chat": jumlah_chat,
            "jumlah_pesan": jumlah_pesan,
            "ukuran_byte": ukuran,
        }

    # ================== TULIS ==================

    def siapkan(
        self,
        chat_id: int,
        akses: str = "user",
        user_id: int | None = None,
        info: dict | None = None,
    ) -> list[dict]:
        """Siapkan riwayat untuk percakapan baru di chat ini.

        Kalau tingkat akses tersimpan berbeda (admin ↔ user) di chat yang sama,
        riwayat dikosongkan supaya konteks admin tidak terbawa ke pengguna.
        """
        with self._lock:
            conn = self._koneksi()
            kunci = int(chat_id)
            baris = conn.execute(
                "SELECT akses FROM chat WHERE chat_id = ?", (kunci,)
            ).fetchone()

            if baris is not None:
                if baris["akses"] != akses:
                    conn.execute("DELETE FROM pesan WHERE chat_id = ?", (kunci,))
                self._sentuh(conn, kunci, akses, user_id, info)
                conn.commit()
            else:
                self._buat_chat(conn, kunci, akses, user_id, info)
                conn.commit()
                return []

            return self.ambil(chat_id)

    def catat(
        self,
        chat_id: int,
        role: str,
        konten: str,
        akses: str = "user",
        user_id: int | None = None,
        info: dict | None = None,
    ) -> None:
        """Tambahkan satu pesan ke riwayat chat lalu simpan ke disk."""
        konten = (konten or "").strip()
        if not konten:
            return

        with self._lock:
            conn = self._koneksi()
            kunci = int(chat_id)
            baris = conn.execute(
                "SELECT akses FROM chat WHERE chat_id = ?", (kunci,)
            ).fetchone()

            if baris is None:
                self._buat_chat(conn, kunci, akses, user_id, info)
            elif baris["akses"] != akses:
                conn.execute("DELETE FROM pesan WHERE chat_id = ?", (kunci,))
                self._sentuh(conn, kunci, akses, user_id, info)
            else:
                self._sentuh(conn, kunci, akses, user_id, info)

            conn.execute(
                "INSERT INTO pesan (chat_id, role, konten, waktu) VALUES (?, ?, ?, ?)",
                (kunci, role, konten, time.time()),
            )
            self._pangkas(conn, kunci)
            self._buang_kelebihan(conn)
            conn.commit()

    def hapus(self, chat_id: int) -> bool:
        """Hapus riwayat satu chat. Return True kalau ada yang dihapus."""
        with self._lock:
            conn = self._koneksi()
            kunci = int(chat_id)
            ada = conn.execute(
                "SELECT 1 FROM chat WHERE chat_id = ?", (kunci,)
            ).fetchone()
            if not ada:
                return False

            conn.execute("DELETE FROM pesan WHERE chat_id = ?", (kunci,))
            conn.execute("DELETE FROM chat WHERE chat_id = ?", (kunci,))
            conn.commit()
            return True

    def hapus_semua(self) -> int:
        """Hapus seluruh riwayat. Return jumlah chat yang dihapus."""
        with self._lock:
            conn = self._koneksi()
            jumlah = conn.execute("SELECT COUNT(*) FROM chat").fetchone()[0]
            conn.execute("DELETE FROM pesan")
            conn.execute("DELETE FROM chat")
            conn.commit()
            return jumlah

    # ================== STATE KECIL ==================
    # Dipakai untuk menyimpan hal yang harus bertahan setelah restart,
    # misalnya ID pesan prompt /play yang perlu dihapus.

    def simpan_state(self, kunci: str, nilai: str) -> None:
        with self._lock:
            conn = self._koneksi()
            conn.execute(
                "INSERT INTO state (kunci, nilai, waktu) VALUES (?, ?, ?) "
                "ON CONFLICT(kunci) DO UPDATE SET nilai = excluded.nilai, "
                "waktu = excluded.waktu",
                (kunci, str(nilai), time.time()),
            )
            conn.commit()

    def ambil_state(self, kunci: str) -> str | None:
        with self._lock:
            conn = self._koneksi()
            baris = conn.execute(
                "SELECT nilai FROM state WHERE kunci = ?", (kunci,)
            ).fetchone()
            return baris["nilai"] if baris else None

    def hapus_state(self, kunci: str) -> None:
        with self._lock:
            conn = self._koneksi()
            conn.execute("DELETE FROM state WHERE kunci = ?", (kunci,))
            conn.commit()

    def state_dengan_prefix(self, prefix: str) -> list[tuple[str, str]]:
        with self._lock:
            conn = self._koneksi()
            baris = conn.execute(
                "SELECT kunci, nilai FROM state WHERE kunci LIKE ?",
                (f"{prefix}%",),
            ).fetchall()
            return [(r["kunci"], r["nilai"]) for r in baris]

    # ================== HELPER ==================

    @staticmethod
    def _ke_dict(baris: sqlite3.Row) -> dict:
        return {
            "chat_id": baris["chat_id"],
            "user_id": baris["user_id"],
            "nama": baris["nama"] or "",
            "username": baris["username"] or "",
            "tipe": baris["tipe"] or "",
            "akses": baris["akses"] or "user",
            "jumlah_pesan": baris["jumlah"] if "jumlah" in baris.keys() else 0,
            "diperbarui": baris["diperbarui"] or 0,
        }

    def _buat_chat(
        self,
        conn: sqlite3.Connection,
        chat_id: int,
        akses: str,
        user_id: int | None,
        info: dict | None,
    ) -> None:
        nama, username, tipe = self._info_bersih(info)
        conn.execute(
            "INSERT INTO chat "
            "(chat_id, user_id, nama, username, tipe, akses, diperbarui) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (chat_id, user_id, nama, username, tipe, akses, time.time()),
        )

    def _sentuh(
        self,
        conn: sqlite3.Connection,
        chat_id: int,
        akses: str,
        user_id: int | None,
        info: dict | None,
    ) -> None:
        """Perbarui metadata chat tanpa menghapus isi riwayat."""
        nama, username, tipe = self._info_bersih(info)

        conn.execute(
            "UPDATE chat SET "
            "  akses = ?, "
            "  user_id = COALESCE(?, user_id), "
            "  nama = CASE WHEN ? <> '' THEN ? ELSE nama END, "
            "  username = CASE WHEN ? <> '' THEN ? ELSE username END, "
            "  tipe = CASE WHEN ? <> '' THEN ? ELSE tipe END, "
            "  diperbarui = ? "
            "WHERE chat_id = ?",
            (
                akses,
                user_id,
                nama, nama,
                username, username,
                tipe, tipe,
                time.time(),
                chat_id,
            ),
        )

    @staticmethod
    def _info_bersih(info: dict | None) -> tuple[str, str, str]:
        info = info or {}
        return (
            str(info.get("nama") or "").strip()[:80],
            str(info.get("username") or "").strip()[:40],
            str(info.get("tipe") or "").strip()[:20],
        )

    @staticmethod
    def _pangkas(conn: sqlite3.Connection, chat_id: int) -> None:
        """Sisakan MAKS_PESAN_SIMPAN pesan terakhir per chat."""
        conn.execute(
            "DELETE FROM pesan WHERE chat_id = ? AND id NOT IN ("
            "  SELECT id FROM pesan WHERE chat_id = ? ORDER BY id DESC LIMIT ?"
            ")",
            (chat_id, chat_id, MAKS_PESAN_SIMPAN),
        )

    @staticmethod
    def _buang_kelebihan(conn: sqlite3.Connection) -> None:
        """Buang chat paling lama kalau jumlahnya melewati batas."""
        jumlah = conn.execute("SELECT COUNT(*) FROM chat").fetchone()[0]
        if jumlah <= MAKS_CHAT:
            return

        conn.execute(
            "DELETE FROM chat WHERE chat_id IN ("
            "  SELECT chat_id FROM chat ORDER BY diperbarui ASC LIMIT ?"
            ")",
            (jumlah - MAKS_CHAT,),
        )


def _buat_store() -> RiwayatStore:
    """Buat store sesuai konfigurasi.

    Kalau RIWAYAT_AKTIF=false, database memakai mode in-memory: riwayat tetap
    bekerja selama bot hidup, tetapi tidak menulis apa pun ke disk.
    """
    import config

    lokasi = config.RIWAYAT_DB
    if not config.RIWAYAT_AKTIF:
        log.info("Penyimpanan riwayat AI dimatikan; memakai database in-memory")
        lokasi = ":memory:"

    return RiwayatStore(lokasi)


RIWAYAT = _buat_store()
