import telebot
from config import TELEGRAM_TOKEN

# Rename dari 'bot' jadi 'tg_bot' untuk hindari konflik namespace
tg_bot = telebot.TeleBot(TELEGRAM_TOKEN)