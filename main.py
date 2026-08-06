import bot.handlers  # noqa: F401

from bot import bot


if __name__ == "__main__":
    print("[SYSTEM] Super App Bot sedang berjalan. Silakan buka Telegram Anda!")
    bot.infinity_polling()