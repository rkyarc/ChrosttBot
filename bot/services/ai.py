import json
import time

import requests

import config
from bot.services import diagnostik, websearch


class AIError(Exception):
    """Error yang aman ditampilkan ke pengguna."""


_last_request: dict[int, float] = {}
MIN_INTERVAL = 1.5  # detik antar request per chat

# Batas putaran tool-calling, supaya model tidak bisa berputar tanpa henti.
# 2 putaran tool + 1 putaran jawaban final = maksimal 3 request ke model.
MAKS_PUTARAN_TOOL = 2
# Admin boleh riset lebih dalam, tapi tetap dibatasi supaya biaya & waktu wajar.
MAKS_PUTARAN_TOOL_ADMIN = 4

# Batas jumlah tool yang dieksekusi per putaran (model kadang minta banyak sekaligus)
MAKS_TOOL_PER_PUTARAN = 2
MAKS_TOOL_PER_PUTARAN_ADMIN = 3

# Kedalaman riset per tool
HASIL_WEB = 5
HASIL_WEB_ADMIN = 8
MAKS_KARAKTER_HALAMAN = 2500
MAKS_KARAKTER_HALAMAN_ADMIN = 6000

# Tool tambahan yang hanya diberikan ke admin. Semuanya read-only.
TOOL_ADMIN = (diagnostik.SKEMA_STATUS_BOT,)

# Nama tool admin, dipakai untuk menampilkan batas akses di /ai_status
TOOL_ADMIN_NAMA = tuple(t["function"]["name"] for t in TOOL_ADMIN)


def tersedia() -> bool:

    return config.AI_ENABLED


def model_aktif() -> str:
    return config.AI_MODEL


def web_aktif() -> bool:
    """Web search hanya jalan kalau diaktifkan dan AI-nya siap."""
    return config.AI_ENABLED and config.AI_WEB_SEARCH


def daftar_tool(admin: bool = False) -> list[dict]:
    """Tool yang boleh dipakai model. Admin mendapat tool diagnostik tambahan."""
    tools = []
    if web_aktif():
        tools += [websearch.SKEMA_WEB_SEARCH, websearch.SKEMA_BACA_HALAMAN]
    if admin:
        tools += list(TOOL_ADMIN)
    return tools


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


def _muat_json(teks: str):
    """Parse JSON dari gateway.

    Gateway kadang menambahkan sisa SSE (`data: [DONE]`) setelah JSON utama,
    sehingga json.loads() gagal dengan "Extra data". Ambil objek JSON pertama.
    """
    teks = (teks or "").strip()
    if not teks:
        raise ValueError("Body kosong.")

    try:
        return json.loads(teks)
    except ValueError:
        pass

    dekoder = json.JSONDecoder()
    try:
        objek, _ = dekoder.raw_decode(teks)
        return objek
    except ValueError:
        raise ValueError("Body bukan JSON yang valid.")


def _detail_error(body: str) -> tuple[str, str]:
    """Ambil (code, message) dari body error gateway."""
    try:
        data = _muat_json(body)
    except ValueError:
        return "", ""

    err = data.get("error") or {}
    if not isinstance(err, dict):
        return "", ""
    return str(err.get("code") or ""), str(err.get("message") or "")


def _pesan_error(status: int, body: str) -> str:
    kode, pesan = _detail_error(body)
    pesan_rendah = pesan.lower()

    # Gateway memakai 403 + code "insufficient_quota" untuk model yang tidak
    # diizinkan, jadi kode error saja tidak cukup; cek isi pesannya dulu.
    model_ditolak = "not allowed to use model" in pesan_rendah
    model_hilang = "model not found" in pesan_rendah or "unknown model" in pesan_rendah

    if model_ditolak or model_hilang:
        return (
            f"Model '{model_aktif()}' tidak tersedia untuk API key ini.\n"
            "Cek AI_MODEL di .env, atau pakai model lain dari gateway."
        )

    if status == 401 or kode == "invalid_api_key":
        return "API key AI tidak valid. Cek AI_API_KEY di file .env."

    if status == 429 or kode == "rate_limit_exceeded":
        return "Terlalu banyak permintaan ke AI. Tunggu sebentar lalu coba lagi."

    if status == 402 or kode == "insufficient_balance":
        return "Saldo AI habis. Top up dulu di dashboard penyedia model."

    if status == 404:
        if kode == "not_found" and "endpoint" in pesan_rendah:
            return "Endpoint AI tidak ditemukan. Cek AI_BASE_URL di .env."
        return f"Model '{model_aktif()}' tidak ditemukan di gateway."

    if status == 403 or kode == "permission_error":
        return "API key tidak punya izin untuk permintaan ini. Cek paket/limit akun."

    if status >= 500:
        return "Server AI sedang bermasalah. Coba lagi beberapa saat."

    return f"Permintaan AI gagal (HTTP {status})."


def model_tersedia() -> list[str]:
    """Daftar model yang bisa dipakai API key ini (best effort)."""
    try:
        response = requests.get(
            f"{config.AI_BASE_URL}/models",
            headers={"Authorization": f"Bearer {config.AI_API_KEY}"},
            timeout=20,
        )
        if response.status_code != 200:
            return []
        data = _muat_json(response.text)
    except (requests.RequestException, ValueError):
        return []

    return [m.get("id", "") for m in data.get("data", []) if m.get("id")]


def _post(payload: dict) -> dict:
    """POST ke /chat/completions dengan error handling seragam."""
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

    # Jangan pakai response.json(): gateway menempelkan sisa SSE di belakang JSON
    try:
        return _muat_json(response.text)
    except ValueError:
        raise AIError("Respons AI bukan JSON yang valid.")


def _rapikan_tool_calls(calls: list[dict]) -> list[dict]:
    """Gateway bisa memberi id duplikat; beri id unik agar round-trip valid."""
    rapikan = []
    for i, call in enumerate(calls):
        fungsi = call.get("function") or {}
        rapikan.append(
            {
                "id": f"call_{i}",
                "type": "function",
                "function": {
                    "name": fungsi.get("name") or "",
                    "arguments": fungsi.get("arguments") or "{}",
                },
            }
        )
    return rapikan


def _jalankan_tool_calls(
    calls: list[dict],
    sudah_dicari: set[str],
    admin: bool = False,
) -> list[str]:
    """Eksekusi semua tool yang diminta model, kembalikan catatan sumber.

    Query yang sudah pernah dicari di percakapan ini dilewati, karena model
    kadang mengulang query yang sama dan itu hanya membakar token.
    """
    jumlah_hasil = HASIL_WEB_ADMIN if admin else HASIL_WEB
    maks_halaman = (
        MAKS_KARAKTER_HALAMAN_ADMIN if admin else MAKS_KARAKTER_HALAMAN
    )

    catatan = []
    for call in calls:
        nama = call["function"]["name"]
        mentah = call["function"]["arguments"]

        # Tool admin ditolak untuk pengguna biasa, walau model tetap memintanya.
        if nama in TOOL_ADMIN_NAMA and not admin:
            call["_hasil"] = (
                f"Tool '{nama}' hanya tersedia untuk admin. Jawab tanpa tool ini."
            )
            continue

        try:
            argumen = json.loads(mentah) if isinstance(mentah, str) else dict(mentah or {})
        except ValueError:
            argumen = {}

        if nama == "web_search":
            query = str(argumen.get("query") or "").strip()
            kunci = query.lower()
            if not query:
                call["_hasil"] = "Query kosong."
                continue
            if kunci in sudah_dicari:
                call["_hasil"] = (
                    f"Query '{query}' sudah dicari sebelumnya. Pakai hasil itu, "
                    "jangan mengulang. Kalau kurang, pakai kata kunci berbeda."
                )
                continue
            sudah_dicari.add(kunci)

        if nama in ("web_search", "baca_halaman"):
            call["_hasil"] = websearch.jalankan_tool(
                nama, argumen, jumlah=jumlah_hasil, maks_karakter=maks_halaman
            )
        else:
            # Termasuk tool admin (read-only) dan nama tak dikenal
            call["_hasil"] = diagnostik.jalankan_tool(nama, argumen)

        if nama == "web_search":
            query = str(argumen.get("query") or "").strip()
            if query:
                catatan.append(f"🔎 {query}")
        elif nama == "baca_halaman":
            url = str(argumen.get("url") or "").strip()
            if url:
                domain = url.split("//", 1)[-1].split("/", 1)[0]
                catatan.append(f"📄 {domain}")
        elif nama == "status_bot":
            catatan.append("🩺 status bot")

    return catatan


def tanya(chat_id: int, riwayat: list[dict], admin: bool = False) -> dict:
    """
    Kirim percakapan ke endpoint OpenAI-compatible, dengan dukungan web search.

    Kalau model meminta tool, tool dijalankan lalu hasilnya dikirim balik
    sampai model memberi jawaban final (maksimal MAKS_PUTARAN_TOOL putaran;
    admin mendapat MAKS_PUTARAN_TOOL_ADMIN).

    Args:
        chat_id: dipakai untuk rate limit per chat.
        riwayat: daftar pesan OpenAI (system + history + user).
        admin: kalau True, batas token, jumlah putaran, kedalaman riset, dan
            tool diagnostik read-only ikut dinaikkan.

    Returns:
        {"teks": str, "model": str, "total_tokens": int, "sumber": list[str]}
    """
    if not config.AI_ENABLED:
        raise AIError(
            "Fitur AI belum aktif. Isi AI_API_KEY di file .env lalu restart bot."
        )

    _batasi_rate(chat_id)

    batas_token = config.AI_MAX_TOKENS_ADMIN if admin else config.AI_MAX_TOKENS
    tools = daftar_tool(admin)
    maks_putaran = MAKS_PUTARAN_TOOL_ADMIN if admin else MAKS_PUTARAN_TOOL
    maks_tool = (
        MAKS_TOOL_PER_PUTARAN_ADMIN if admin else MAKS_TOOL_PER_PUTARAN
    )

    pesan = list(riwayat)
    sumber: list[str] = []
    sudah_dicari: set[str] = set()
    total_tokens = 0
    model_dipakai = config.AI_MODEL

    for putaran in range(maks_putaran + 1):
        # Putaran terakhir dikirim tanpa tool, supaya model wajib menjawab
        putaran_terakhir = putaran >= maks_putaran

        payload = {
            "model": config.AI_MODEL,
            "messages": pesan,
            "temperature": config.AI_TEMPERATURE,
            "max_tokens": batas_token,
        }
        if tools and not putaran_terakhir:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        elif tools:
            # Putaran penutup: tool dimatikan total supaya model tidak menulis
            # tool call sebagai teks mentah. Instruksinya dikirim sebagai
            # pesan user (bukan system) agar tidak menimpa system prompt.
            payload["tools"] = tools
            payload["tool_choice"] = "none"
            payload["messages"] = pesan + [
                {
                    "role": "user",
                    "content": (
                        "Pencarian ditutup. Jawab sekarang HANYA memakai hasil yang "
                        "sudah didapat di atas, tanpa memanggil tool apa pun. "
                        "Kalau data kurang, katakan apa adanya dan sebutkan sumber "
                        "yang sudah ditemukan."
                    ),
                }
            ]

        data = _post(payload)
        model_dipakai = data.get("model") or model_dipakai

        usage = data.get("usage") or {}
        token = usage.get("total_tokens")
        if isinstance(token, int):
            total_tokens += token

        pilihan = data.get("choices") or []
        if not pilihan:
            raise AIError("AI tidak mengembalikan jawaban.")

        message = pilihan[0].get("message") or {}
        calls_mentah = message.get("tool_calls") or []

        if calls_mentah and not putaran_terakhir:
            calls = _rapikan_tool_calls(calls_mentah[:maks_tool])

            pesan.append(
                {
                    "role": "assistant",
                    "content": _normalisasi_konten(message.get("content")) or "",
                    "tool_calls": calls,
                }
            )

            sumber.extend(_jalankan_tool_calls(calls, sudah_dicari, admin))

            for call in calls:
                pesan.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": call.get("_hasil", ""),
                    }
                )
            continue

        # Tidak ada tool call (atau sudah mentok batas) -> ini jawaban final
        teks = _normalisasi_konten(message.get("content")).strip()

        if not teks and calls_mentah:
            teks = (
                "Aku sudah mencari di web, tapi belum dapat jawaban yang bisa "
                "disimpulkan. Coba perjelas pertanyaannya."
            )

        if not teks:
            raise AIError("AI mengembalikan jawaban kosong.")

        return {
            "teks": teks,
            "model": model_dipakai,
            "total_tokens": total_tokens,
            "sumber": list(dict.fromkeys(sumber)),
        }

    raise AIError("AI terlalu banyak mencari. Coba pertanyaan yang lebih spesifik.")


def cek_koneksi() -> tuple[bool, str]:
    """Cek base URL, key, dan apakah AI_MODEL benar-benar bisa dipakai."""
    try:
        response = requests.get(
            f"{config.AI_BASE_URL}/models",
            headers={"Authorization": f"Bearer {config.AI_API_KEY}"},
            timeout=20,
        )
    except requests.exceptions.RequestException as e:
        return False, f"Tidak bisa reach server AI: {e}"

    if response.status_code != 200:
        return False, _pesan_error(response.status_code, response.text)

    try:
        data = _muat_json(response.text)
    except ValueError:
        return False, "Daftar model dari server bukan JSON yang valid."

    daftar = [m.get("id", "") for m in data.get("data", []) if m.get("id")]
    if not daftar:
        return False, "Server tidak mengembalikan model apa pun untuk key ini."

    if config.AI_MODEL not in daftar:
        tersedia = ", ".join(daftar[:5])
        return False, (
            f"Model '{config.AI_MODEL}' tidak ada di gateway.\n"
            f"Model yang tersedia: {tersedia}.\n"
            "Perbaiki AI_MODEL di .env."
        )

    return True, "OK"
