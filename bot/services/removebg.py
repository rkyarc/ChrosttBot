from io import BytesIO

import requests


# URL API gratis rembg.com (tanpa API key)
URL_API = "https://api.rembg.com/rmbg"

# Header wajib ada agar tidak diblokir server (disangka bot/scrapper)
HEADERS = {
    "accept": "application/json, text/plain, */*",
    "Referer": "https://www.rembg.com/",
    "Origin": "https://www.rembg.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
}


def hapus_background(file_bytes):
    """
    Mengirim byte gambar ke API rembg.com dan menghapus background-nya.
    
    Args:
        file_bytes: byte gambar dari Telegram (hasil download_file)
    
    Returns:
        Response object dari requests, atau None jika gagal
    """
    # Bungkus byte dalam BytesIO agar bisa dikirim sebagai file
    file_obj = BytesIO(file_bytes)
    file_obj.seek(0)

    # Parameter request
    files = {
        "image": ("image.jpg", file_obj, "image/jpeg")
    }
    data = {
        "return_type": "binary"
    }

    try:
        response = requests.post(
            URL_API,
            headers=HEADERS,
            files=files,
            data=data,
            timeout=60  # timeout 60 detik biar tidak menggantung selamanya
        )
        return response

    except requests.exceptions.Timeout:
        print("❌ Request ke rembg.com timeout (>60 detik)")
        return None
    except requests.exceptions.ConnectionError:
        print("❌ Gagal koneksi ke server rembg.com")
        return None
    except Exception as e:
        print(f"❌ Error tidak terduga: {e}")
        return None