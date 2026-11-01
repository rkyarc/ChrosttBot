import time


class SessionStore:
    """Cache sementara per chat dengan TTL dan batas jumlah entri.

    Dipakai supaya hasil ekstraksi (TikTok/Facebook) tidak menumpuk di memori
    dan tidak "nyangkut" selamanya setelah sesi selesai.
    """

    def __init__(self, ttl: int = 1800, max_entries: int = 500):
        self.ttl = ttl
        self.max_entries = max_entries
        self._data: dict[int, tuple[float, object]] = {}

    def _bersihkan(self, now: float) -> None:
        kedaluwarsa = [chat_id for chat_id, (waktu, _) in self._data.items()
                       if now - waktu > self.ttl]
        for chat_id in kedaluwarsa:
            self._data.pop(chat_id, None)

        if len(self._data) >= self.max_entries:
            urut = sorted(self._data.items(), key=lambda item: item[1][0])
            for chat_id, _ in urut[: len(self._data) - self.max_entries + 1]:
                self._data.pop(chat_id, None)

    def set(self, chat_id: int, nilai: object) -> None:
        now = time.time()
        self._bersihkan(now)
        self._data[chat_id] = (now, nilai)

    def get(self, chat_id: int):
        item = self._data.get(chat_id)
        if not item:
            return None

        waktu, nilai = item
        if time.time() - waktu > self.ttl:
            self._data.pop(chat_id, None)
            return None

        return nilai

    def clear(self, chat_id: int) -> None:
        self._data.pop(chat_id, None)

    def items(self) -> list[tuple[int, object]]:
        """Pasangan (chat_id, nilai) yang masih berlaku, untuk pembersihan."""
        self._bersihkan(time.time())
        return [(chat_id, nilai) for chat_id, (_, nilai) in self._data.items()]
