import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

from database import create_user
from systems.economy import work
from systems.combat import pve_fight
from systems.inventory import add_item, get_inventory, equip_item

TOKEN = "8848414252:AAEx3uSwOma9V_VSnnxJVECPBarhKNk6Xv4"

bot = telebot.TeleBot(TOKEN)


# ---------------- UI ----------------

def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("💼 Work"))
    kb.add(KeyboardButton("⚔️ PvE"))
    kb.add(KeyboardButton("🎒 Inventory"))
    kb.add(KeyboardButton("🧥 Equip"))
    return kb


# ---------------- START ----------------

@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.from_user.id
    create_user(user_id)

    bot.send_message(
        user_id,
        "🎮 Добро пожаловать в RPG игру!\nВыбери действие:",
        reply_markup=main_menu()
    )


# ---------------- WORK ----------------

@bot.message_handler(func=lambda m: m.text == "💼 Work")
def work_handler(message):
    result = work(message.from_user.id)
    bot.send_message(message.chat.id, result)


# ---------------- PVE ----------------

@bot.message_handler(func=lambda m: m.text == "⚔️ PvE")
def pve_handler(message):
    result = pve_fight(message.from_user.id)
    bot.send_message(message.chat.id, result)


# ---------------- INVENTORY ----------------

@bot.message_handler(func=lambda m: m.text == "🎒 Inventory")
def inventory_handler(message):
    items = get_inventory(message.from_user.id)

    if not items:
        bot.send_message(message.chat.id, "🎒 Инвентарь пуст")
        return

    text = "🎒 Твой инвентарь:\n"
    for i in items:
        text += f"- {i}\n"

    bot.send_message(message.chat.id, text)


# ---------------- EQUIP ----------------

@bot.message_handler(func=lambda m: m.text.startswith("🧥 Equip"))
def equip_handler(message):
    parts = message.text.split(" ")

    if len(parts) < 2:
        bot.send_message(message.chat.id, "Напиши: 🧥 Equip knife")
        return

    item = parts[1]
    result = equip_item(message.from_user.id, item)

    bot.send_message(message.chat.id, result)


# ---------------- RUN ----------------

bot.infinity_polling()
