import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import os
from dotenv import load_dotenv
import yfinance as yf

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
    btn2 = InlineKeyboardButton("📈 Cek Saham", callback_data="menu_saham")
    btn3 = InlineKeyboardButton("ℹ️ Info Bot", callback_data="menu_info")
    
    markup.add(btn1)
    markup.add(btn2)
    markup.add(btn3)
    
    teks_sambutan = (
        "🤖 <b>Selamat datang di Chrostt Bot!</b>\n\n"
        "Silakan pilih menu layanan yang Anda butuhkan hari ini:"
    )
    
    bot.send_message(message.chat.id, teks_sambutan, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def tanggapi_tombol(call):
    chat_id = call.message.chat.id
    
    if call.data == "menu_utama":
        markup = InlineKeyboardMarkup()
        btn1 = InlineKeyboardButton("✂️ Hapus Background Foto", callback_data="menu_bg")
        btn2 = InlineKeyboardButton("📈 Cek Saham", callback_data="menu_saham")
        btn3 = InlineKeyboardButton("ℹ️ Info Bot", callback_data="menu_info")
        markup.add(btn1)
        markup.add(btn2)
        markup.add(btn3)
        
        teks_sambutan = (
            "🤖 <b>Selamat datang di Chrostt Bot!</b>\n\n"
            "Silakan pilih menu layanan yang Anda butuhkan hari ini:"
        )
        bot.edit_message_text(teks_sambutan, chat_id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    elif call.data == "menu_bg":
        bot.send_message(chat_id, "📸 <b>Mode Hapus Background Aktif!</b>\nSilakan kirimkan satu foto (kirim sebagai foto biasa, bukan file dokumen).", parse_mode="HTML")
        
    elif call.data == "menu_saham":
        markup = InlineKeyboardMarkup()
        
        btn_ihsg = InlineKeyboardButton("📊 IHSG", callback_data="cek_^JKSE")
        btn_cari = InlineKeyboardButton("🔍 Cari Emiten Manual", callback_data="cari_saham")
        btn_kembali = InlineKeyboardButton("🔙 Kembali ke Menu Utama", callback_data="menu_utama")
        
        markup.add(btn_ihsg)
        markup.add(btn_cari)
        markup.add(btn_kembali)
        
        bot.edit_message_text(
            "📈 <b>Pusat Data Market</b>\n\nSilakan pilih indeks atau cari emiten:", 
            chat_id, 
            call.message.message_id, 
            parse_mode="HTML", 
            reply_markup=markup
        )
    
    elif call.data == "menu_info":
        bot.send_message(chat_id, "Bot ini dibangun menggunakan Python dan pyTelegramBotAPI. Dirancang khusus untuk efisiensi keseharian.")

    elif call.data.startswith("cek_"):
        kode_emiten = call.data.split("_")[1] 
        pesan_loading = bot.send_message(chat_id, f"🔍 <i>Menarik data {kode_emiten} dari bursa...</i>", parse_mode="HTML")
        
        try:
            target = yf.Ticker(kode_emiten)
            data_market = target.history(period="1d")
            harga_terakhir = data_market['Close'].iloc[-1]
            
            if kode_emiten == "^JKSE":
                harga_formatted = f"{harga_terakhir:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                nama_tampilan = "IHSG"
            else:
                harga_formatted = f"{int(harga_terakhir):,}".replace(",", "X").replace(".", ",").replace("X", ".")
                nama_tampilan = kode_emiten.replace(".JK", "")
            
            teks_balasan = (
                f"📊 <b>Update: {nama_tampilan}</b>\n"
                f"Harga Terakhir: <b>Rp {harga_formatted}</b>\n\n"
                "<i>*Data ditarik secara real-time via yfinance</i>"
            )
            
            bot.edit_message_text(teks_balasan, chat_id, pesan_loading.message_id, parse_mode="HTML")
            
        except Exception as e:
            bot.edit_message_text(f"❌ Gagal menarik data {kode_emiten}. Pastikan kode benar.", chat_id, pesan_loading.message_id)

    elif call.data == "cari_saham":
        pesan_instruksi = bot.send_message(
            chat_id, 
            "🔍 <b>Mode Pencarian Saham</b>\n\n"
            "Silakan ketik 4 huruf kode saham yang ingin Anda cari (contoh: <code>ASII</code>, <code>GOTO</code>, atau <code>BBCA</code>):", 
            parse_mode="HTML"
        )
        bot.register_next_step_handler(pesan_instruksi, proses_cari_saham)

def proses_cari_saham(message):
    chat_id = message.chat.id
    
    kode_input = message.text.upper().strip() 
    kode_emiten = f"{kode_input}.JK"
    
    pesan_loading = bot.send_message(chat_id, f"⏳ <i>Mencari data {kode_input} di server bursa...</i>", parse_mode="HTML")
    
    try:
        target = yf.Ticker(kode_emiten)
        data_market = target.history(period="1d")
        
        if data_market.empty:
            markup_error = InlineKeyboardMarkup()
            btn_coba_lagi = InlineKeyboardButton("🔄 Coba Cari Lagi", callback_data="cari_saham")
            btn_kembali = InlineKeyboardButton("🔙 Kembali ke Menu Saham", callback_data="menu_saham")
            markup_error.add(btn_coba_lagi)
            markup_error.add(btn_kembali)
            
            bot.edit_message_text(
                f"❌ Saham <b>{kode_input}</b> tidak ditemukan atau tidak terdaftar di BEI.\n\nSilakan periksa kembali kode emitennya.", 
                chat_id, pesan_loading.message_id, parse_mode="HTML", reply_markup=markup_error
            )
            return 
            
        harga_terakhir = int(data_market['Close'].iloc[-1])
        harga_formatted = f"{harga_terakhir:,}".replace(",", "X").replace(".", ",").replace("X", ".")
        
        markup_sukses = InlineKeyboardMarkup()
        btn_cari_lain = InlineKeyboardButton("🔍 Cari Saham Lain", callback_data="cari_saham")
        btn_kembali = InlineKeyboardButton("🔙 Kembali ke Menu Saham", callback_data="menu_saham")
        markup_sukses.add(btn_cari_lain)
        markup_sukses.add(btn_kembali)
        
        teks_balasan = (
            f"📊 <b>Hasil Pencarian: {kode_input}</b>\n"
            f"Harga Terakhir: <b>Rp {harga_formatted}</b>\n\n"
            "<i>*Data ditarik secara real-time via yfinance</i>"
        )
        
        bot.edit_message_text(teks_balasan, chat_id, pesan_loading.message_id, parse_mode="HTML", reply_markup=markup_sukses)
        
    except Exception as e:
        markup_error = InlineKeyboardMarkup()
        btn_coba_lagi = InlineKeyboardButton("🔄 Coba Lagi", callback_data="cari_saham")
        markup_error.add(btn_coba_lagi)
        
        bot.edit_message_text(f"❌ Terjadi kesalahan saat mencari {kode_input}. Coba lagi.", chat_id, pesan_loading.message_id, reply_markup=markup_error)

# SISTEM
if __name__ == "__main__":
    print("[SYSTEM] Super App Bot sedang berjalan. Silakan buka Telegram Anda!")
    bot.infinity_polling()