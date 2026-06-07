import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# ================= KONFIGURASI UTAMA =================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
REMOVE_BG_API_KEY = os.getenv('REMOVE_BG_API_KEY')

bot = telebot.TeleBot(TELEGRAM_TOKEN)
# =====================================================

@bot.message_handler(commands=['start', 'menu'])
def tampilkan_menu(message):
    markup = InlineKeyboardMarkup()
    
    btn1 = InlineKeyboardButton("✂️ Hapus Background Foto", callback_data="menu_bg")
    btn2 = InlineKeyboardButton("ℹ️ Info Bot", callback_data="menu_info")
    
    markup.add(btn1, btn2)
    
    teks_sambutan = (
        "🤖 <b>Selamat datang di Chrostt Bot!</b>\n\n"
        "Silakan pilih menu layanan yang Anda butuhkan hari ini:"
    )
    
    bot.send_message(message.chat.id, teks_sambutan, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def tanggapi_tombol(call):
    chat_id = call.message.chat.id
    
    if call.data == "menu_bg":
        bot.send_message(chat_id, "📸 <b>Mode Hapus Background Aktif!</b>\nSilakan kirimkan satu foto (kirim sebagai foto biasa, bukan sebagai file dokumen).", parse_mode="HTML")
        
    elif call.data == "menu_info":
        bot.send_message(chat_id, "Bot ini dibangun menggunakan Python dan pyTelegramBotAPI. Dirancang khusus untuk efisiensi keseharian.")

@bot.message_handler(content_types=['photo'])
def proses_hapus_background(message):
    chat_id = message.chat.id
    pesan_loading = bot.reply_to(message, "⏳ Sedang memproses... Mohon tunggu sebentar.")
    
    try:
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_info.file_path}"
        gambar_mentah = requests.get(file_url).content
        
        response = requests.post(
            'https://api.remove.bg/v1.0/removebg',
            files={'image_file': ('gambar.jpg', gambar_mentah)},
            data={'size': 'auto'},
            headers={'X-Api-Key': REMOVE_BG_API_KEY},
            timeout=20
        )
        
        if response.status_code == requests.codes.ok:
            bot.send_document(chat_id, response.content, visible_file_name="tanpa_background.png")
            bot.delete_message(chat_id, pesan_loading.message_id)
        else:
            bot.edit_message_text("❌ Gagal. Pastikan API Key benar dan kuota bulan ini masih ada.", chat_id, pesan_loading.message_id)
            
    except Exception as e:
        bot.edit_message_text("❌ Terjadi kesalahan jaringan.", chat_id, pesan_loading.message_id)

if __name__ == "__main__":
    print("[SYSTEM] Super App Bot sedang berjalan. Silakan buka Telegram Anda!")
    bot.infinity_polling()