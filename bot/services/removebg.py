from io import BytesIO

import requests


# URL API gratis rembg.com (tanpa API key)
URL_API = "https://api.rembg.com/rmbg"

# Header wajib ada agar tidak diblokir server (disangka bot/scrapper)
HEADERS = {
    "accept": "application/json, text/plain, */*",
    "Referer": "https://www.rembg.com/",
    "Origin": "https://www.rembg.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
}

# Batas ukuran gambar yang masuk akal untuk API gratis
MAX_IMAGE_BYTES = 12 * 1024 * 1024


class RemoveBgError(Exception):
    pass


def hapus_background(file_bytes):
    """
    Mengirim byte gambar ke API rembg.com dan menghapus background-nya.

    Args:
        file_bytes: byte gambar dari Telegram (hasil download_file)

    Returns:
        byte PNG hasil hapus background.

    Raises:
        RemoveBgError: kalau ukuran terlalu besar atau API gagal.
    """
    if not file_bytes:
        raise RemoveBgError("File gambar kosong.")

    if len(file_bytes) > MAX_IMAGE_BYTES:
        raise RemoveBgError("Ukuran gambar melebihi 12MB. Kirim foto dengan ukuran lebih kecil.")

    file_obj = BytesIO(file_bytes)

    files = {"image": ("image.jpg", file_obj, "image/jpeg")}
    data = {"return_type": "binary"}

    try:
        response = requests.post(
            URL_API,
            headers=HEADERS,
            files=files,
            data=data,
            timeout=90,
        )
    except requests.exceptions.Timeout:
        raise RemoveBgError("Server rembg.com timeout (>90 detik). Coba lagi.")
    except requests.exceptions.ConnectionError:
        raise RemoveBgError("Gagal koneksi ke server rembg.com.")
    except requests.exceptions.RequestException as e:
        raise RemoveBgError(f"Request gagal: {e}")

    if response.status_code != 200:
        raise RemoveBgError(f"API menolak permintaan (Status: {response.status_code}).")

    content_type = response.headers.get("content-type", "")
    if "image" not in content_type:
        raise RemoveBgError("Server tidak mengembalikan gambar. Kuota API mungkin habis.")

    return response.content
