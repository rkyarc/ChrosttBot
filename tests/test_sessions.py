import time
import unittest

from bot.sessions import SessionStore


class SessionStoreTest(unittest.TestCase):
    def test_set_lalu_get(self):
        store = SessionStore()
        store.set(1, {"a": 1})
        self.assertEqual(store.get(1), {"a": 1})

    def test_chat_lain_tidak_tercampur(self):
        store = SessionStore()
        store.set(1, "satu")
        store.set(2, "dua")
        self.assertEqual(store.get(1), "satu")
        self.assertEqual(store.get(2), "dua")

    def test_clear_menghapus(self):
        store = SessionStore()
        store.set(1, "x")
        store.clear(1)
        self.assertIsNone(store.get(1))

    def test_chat_tidak_dikenal_menghasilkan_none(self):
        self.assertIsNone(SessionStore().get(999))

    def test_ttl_kedaluwarsa(self):
        store = SessionStore(ttl=1)
        store.set(1, "x")
        # Majukan waktu tanpa sleep lama
        store._data[1] = (time.time() - 5, "x")
        self.assertIsNone(store.get(1))

    def test_max_entries_membuang_yang_paling_lama(self):
        store = SessionStore(ttl=3600, max_entries=3)
        for i in range(5):
            store.set(i, i)
            store._data[i] = (time.time() + i, i)

        store.set(99, 99)  # memicu pembersihan
        self.assertLessEqual(len(store._data), 3)
        self.assertIsNotNone(store.get(99))

    def test_items_hanya_yang_masih_berlaku(self):
        store = SessionStore(ttl=1)
        store.set(1, "baru")
        store.set(2, "lama")
        store._data[2] = (time.time() - 10, "lama")

        kunci = [chat_id for chat_id, _ in store.items()]
        self.assertIn(1, kunci)
        self.assertNotIn(2, kunci)


if __name__ == "__main__":
    unittest.main()
