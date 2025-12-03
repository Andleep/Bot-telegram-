import telebot
import os

TOKEN = os.getenv("BOT_TOKEN")

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "البوت اشتغل بنجاح 🔥🔥 على Render")

@bot.message_handler(func=lambda m: True)
def echo(message):
    bot.reply_to(message, f"انت قلت: {message.text}")

bot.infinity_polling()
