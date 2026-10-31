import json
import time

import requests

import config


class AIError(Exception):
    """Error yang aman ditampilkan ke pengguna."""


_last_request: dict[int, float] = {}
MIN_INTERVAL = 1.5  # detik antar request per chat


def tersedia() -> bool:
    return config.AI_ENABLED


def model_aktif() -> str:
    return config.AI_MODEL


def _batasi_rate(chat_id: int) -> None:
    sekarang = time.time()
    terakhir = _last_request.get(chat_id, 0.0)
    sisa = MIN_INTERVAL - (sekarang - terakhir)
    if sisa > 0:
        time.sleep(min(sisa, MIN_INTERVAL))
    _last_request[chat_id] = time.time()


def _normalisasi_konten(konten) -> str:
    """Beberapa gateway mengembalikan list part, bukan string."""
    if isinstance(konten, str):
        return konten
    if isinstance(konten, list):
        bagian = []
        for item in konten:
            if isinstance(item, dict):
                bagian.append(item.get("text") or "")
            else:
                bagian.append(str(item))
        return "".join(bagian)
    return str(konten or "")


def _pesan_error(status: int, body: str) -> str:
    kode = ""
    try:
        data = json.loads(body)
        err = data.get("error") or {}
        kode = str(err.get("code") or "")
    except (ValueError, AttributeError):
        pass

    if status == 401 or kode == "invalid_api_key":
        return "API key AI tidak valid. Cek AI_API_KEY di file .env."
    if status == 402 or kode in ("insufficient_balance", "insufficient_quota"):
        return "Saldo/kuota AI habis. Top up dulu di dashboard penyedia model."
    if status == 429 or kode == "rate_limit_exceeded":
        return "Terlalu banyak permintaan ke AI. Tunggu sebentar lalu coba lagi."
    if status == 404:
        return f"Model tidak ditemukan: {model_aktif()}."
    if status >= 500:
        return "Server AI sedang bermasalah. Coba lagi beberapa saat."
    return f"Permintaan AI gagal (HTTP {status})."


def tanya(chat_id: int, riwayat: list[dict]) -> dict:
    """
    Kirim percakapan ke endpoint OpenAI-compatible.

    Returns:
        {"teks": str, "model": str, "total_tokens": int}
    """
    if not config.AI_ENABLED:
        raise AIError(
            "Fitur AI belum aktif. Isi AI_API_KEY di file .env lalu restart bot."
        )

    _batasi_rate(chat_id)

    payload = {
        "model": config.AI_MODEL,
        "messages": riwayat,
        "temperature": config.AI_TEMPERATURE,
        "max_tokens": config.AI_MAX_TOKENS,
    }
    headers = {
        "Authorization": f"Bearer {config.AI_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        response = requests.post(
            f"{config.AI_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120,
        )
    except requests.exceptions.Timeout:
        raise AIError("AI tidak merespons dalam 120 detik. Coba pertanyaan lebih pendek.")
    except requests.exceptions.ConnectionError:
        raise AIError("Gagal terhubung ke server AI. Cek koneksi internet.")
    except requests.exceptions.RequestException as e:
        raise AIError(f"Request ke AI gagal: {e}")

    if response.status_code != 200:
        raise AIError(_pesan_error(response.status_code, response.text))

    try:
        data = response.json()
    except ValueError:
        raise AIError("Respons AI bukan JSON yang valid.")

    pilihan = data.get("choices") or []
    if not pilihan:
        raise AIError("AI tidak mengembalikan jawaban.")

    teks = _normalisasi_konten(pilihan[0].get("message", {}).get("content")).strip()
    if not teks:
        raise AIError("AI mengembalikan jawaban kosong.")

    usage = data.get("usage") or {}
    total = usage.get("total_tokens")

    return {
        "teks": teks,
        "model": data.get("model") or config.AI_MODEL,
        "total_tokens": int(total) if isinstance(total, int) else 0,
    }


def cek_koneksi() -> tuple[bool, str]:
    """Cek cepat apakah base URL dan key bisa dipakai."""
    try:
        response = requests.get(
            f"{config.AI_BASE_URL}/models",
            headers={"Authorization": f"Bearer {config.AI_API_KEY}"},
            timeout=20,
        )
    except requests.exceptions.RequestException as e:
        return False, f"Tidak bisa reach server AI: {e}"

    if response.status_code == 200:
        return True, "OK"
    return False, _pesan_error(response.status_code, response.text)
