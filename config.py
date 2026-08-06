from dotenv import load_dotenv
import os


load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
REMOVE_BG_API_KEY = os.getenv("REMOVE_BG_API_KEY")

if not TELEGRAM_TOKEN:
	raise RuntimeError("TELEGRAM_TOKEN belum diisi. Cek file .env kamu.")
