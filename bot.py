import telebot
import time
import random
import sqlite3
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

# ---------------- DB ----------------

conn = sqlite3.connect("game.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    money INTEGER DEFAULT 0,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    attack INTEGER DEFAULT 1,
    defense INTEGER DEFAULT 1,
    inventory TEXT DEFAULT "",
    equipped TEXT DEFAULT "",
    last_work REAL DEFAULT 0
)
""")
conn.commit()

# ---------------- BOT ----------------

TOKEN = "PASTE_YOUR_TOKEN_HERE"
bot = telebot.TeleBot(TOKEN)

# ---------------- DATA ----------------

ITEMS = {
    "knife": {"attack": 5, "defense": 0},
    "armor": {"attack": 0, "defense": 5},
    "pistol": {"attack": 10, "defense": 0},
}

# ---------------- HELPERS ----------------

def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    return cursor.fetchone()

def create_user(user_id):
    if not get_user(user_id):
        cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()

def get_inventory(user_id):
    cursor.execute("SELECT inventory FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row[0].split(",")[:-1] if row and row[0] else []

def get_equipped(user_id):
    cursor.execute("SELECT equipped FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row and row[0] else None

def equip_item(user_id, item):
    cursor.execute("UPDATE users SET equipped = ? WHERE user_id = ?", (item, user_id))
    conn.commit()
    return f"Equipped {item}"

# ---------------- ECONOMY ----------------

def work(user_id):
    user = get_user(user_id)
    if not user:
        return

    if time.time() - user[7] < 10:
        return "Cooldown"

    money = user[1]
    xp = user[2]
    level = user[3]

    reward = random.randint(20, 80) + level * 5
    xp += 10

    if xp >= level * 100:
        xp = 0
        level += 1

    cursor.execute("""
        UPDATE users
        SET money=?, xp=?, level=?, last_work=?
        WHERE user_id=?
    """, (money + reward, xp, level, time.time(), user_id))
    conn.commit()

    return f"+{reward} coins | lvl {level}"

# ---------------- PVE ----------------

def pve(user_id):
    user = get_user(user_id)
    if not user:
        return

    level = user[3]
    base_attack = user[4]
    base_defense = user[5]

    inv_attack = sum(ITEMS[i]["attack"] for i in get_inventory(user_id) if i in ITEMS)

    eq = get_equipped(user_id)
    eq_attack = ITEMS[eq]["attack"] if eq in ITEMS else 0

    player = base_attack + inv_attack + eq_attack + level
    enemy = random.randint(10, 30 + level * 3)

    if player > enemy:
        reward = random.randint(50, 120)
        cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (reward, user_id))
        conn.commit()
        return f"WIN +{reward}"
    else:
        return "LOSE"

# ---------------- UI ----------------

kb = ReplyKeyboardMarkup(resize_keyboard=True)
kb.add(KeyboardButton("WORK"))
kb.add(KeyboardButton("PVE"))
kb.add(KeyboardButton("INV"))
kb.add(KeyboardButton("EQUIP"))

# ---------------- HANDLERS ----------------

@bot.message_handler(commands=["start"])
def start(m):
    create_user(m.from_user.id)
    bot.send_message(m.chat.id, "Game started", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "WORK")
def h1(m):
    bot.send_message(m.chat.id, work(m.from_user.id))

@bot.message_handler(func=lambda m: m.text == "PVE")
def h2(m):
    bot.send_message(m.chat.id, pve(m.from_user.id))

@bot.message_handler(func=lambda m: m.text == "INV")
def h3(m):
    items = get_inventory(m.from_user.id)
    bot.send_message(m.chat.id, str(items))

@bot.message_handler(func=lambda m: m.text.startswith("EQUIP"))
def h4(m):
    parts = m.text.split()
    if len(parts) < 2:
        bot.send_message(m.chat.id, "EQUIP knife")
        return
    bot.send_message(m.chat.id, equip_item(m.from_user.id, parts[1]))

# ---------------- RUN ----------------

bot.infinity_polling()
