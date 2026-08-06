from io import BytesIO

import requests

from config import REMOVE_BG_API_KEY


def hapus_background(file_bytes):
	if not REMOVE_BG_API_KEY:
		raise RuntimeError("REMOVE_BG_API_KEY belum diisi. Cek file .env kamu.")

	file_obj = BytesIO(file_bytes)
	file_obj.seek(0)

	return requests.post(
		"https://api.remove.bg/v1.0/removebg",
		files={"image_file": ("image.png", file_obj, "image/png")},
		data={"size": "auto"},
		headers={"X-Api-Key": REMOVE_BG_API_KEY},
	)
