import telebot
import time
import random
import sqlite3
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

# ================= DB =================

conn = sqlite3.connect("game.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    money INTEGER DEFAULT 0,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    career TEXT DEFAULT 'worker',
    attack INTEGER DEFAULT 1,
    defense INTEGER DEFAULT 1,
    inventory TEXT DEFAULT '',
    equipped TEXT DEFAULT '',
    last_work REAL DEFAULT 0
)
""")
conn.commit()

# ================= BOT =================

TOKEN = "PASTE_YOUR_TOKEN_HERE"
bot = telebot.TeleBot(TOKEN)

# ================= GAME DATA =================

ITEMS = {
    "knife": {"type": "weapon", "attack": 5, "defense": 0, "rarity": "common"},
    "armor": {"type": "armor", "attack": 0, "defense": 5, "rarity": "common"},
    "pistol": {"type": "weapon", "attack": 10, "defense": 0, "rarity": "rare"},
    "rifle": {"type": "weapon", "attack": 18, "defense": 0, "rarity": "epic"},
}

ENEMIES = ["thug", "bandit", "mutant"]

# ================= HELPERS =================

def get_user(uid):
    cur.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    return cur.fetchone()

def create_user(uid):
    if not get_user(uid):
        cur.execute("INSERT INTO users (user_id) VALUES (?)", (uid,))
        conn.commit()

def update_user(uid, **kwargs):
    keys = ", ".join([f"{k}=?" for k in kwargs])
    values = list(kwargs.values())
    values.append(uid)
    cur.execute(f"UPDATE users SET {keys} WHERE user_id=?", values)
    conn.commit()

def inv(uid):
    u = get_user(uid)
    return u[7].split(",") if u and u[7] else []

def equip(uid, item):
    update_user(uid, equipped=item)

def stats(uid):
    u = get_user(uid)
    if not u:
        return 0,0

    base_a = u[5]
    base_d = u[6]

    items = inv(uid)
    eq = u[8]

    bonus_a = sum(ITEMS[i]["attack"] for i in items if i in ITEMS)
    bonus_d = sum(ITEMS[i]["defense"] for i in items if i in ITEMS)

    if eq in ITEMS:
        bonus_a += ITEMS[eq]["attack"]
        bonus_d += ITEMS[eq]["defense"]

    level_bonus = u[3]

    return base_a + bonus_a + level_bonus, base_d + bonus_d + level_bonus

# ================= ECONOMY =================

def work(uid):
    u = get_user(uid)
    if time.time() - u[9] < 10:
        return "⏳ cooldown"

    money = u[1]
    xp = u[2]
    lvl = u[3]

    gain = random.randint(20, 60) + lvl * 5
    xp += 15

    if xp >= lvl * 100:
        xp = 0
        lvl += 1

    update_user(uid,
        money=money + gain,
        xp=xp,
        level=lvl,
        last_work=time.time()
    )

    return f"💼 +{gain}$ | XP +15 | LVL {lvl}"

# ================= PvE =================

def pve(uid):
    u = get_user(uid)
    if not u:
        return

    player_a, player_d = stats(uid)

    enemy_power = random.randint(10, 25 + u[3] * 3)

    enemy = random.choice(ENEMIES)

    if player_a > enemy_power:
        reward = random.randint(50, 120)
        update_user(uid, money=u[1] + reward)
        drop = random.choice(list(ITEMS.keys()))
        update_user(uid, inventory=u[7] + drop + ",")

        return f"⚔️ WIN vs {enemy}\n💰 +{reward}$\n🎁 loot: {drop}"

    return f"💀 LOST vs {enemy}"

# ================= UI =================

kb = ReplyKeyboardMarkup(resize_keyboard=True)
kb.add(KeyboardButton("WORK"))
kb.add(KeyboardButton("PVE"))
kb.add(KeyboardButton("INV"))
kb.add(KeyboardButton("EQUIP"))

# ================= HANDLERS =================

@bot.message_handler(commands=["start"])
def start(m):
    create_user(m.from_user.id)
    bot.send_message(m.chat.id, "🔥 RPG STARTED", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "WORK")
def h1(m):
    bot.send_message(m.chat.id, work(m.from_user.id))

@bot.message_handler(func=lambda m: m.text == "PVE")
def h2(m):
    bot.send_message(m.chat.id, pve(m.from_user.id))

@bot.message_handler(func=lambda m: m.text == "INV")
def h3(m):
    items = inv(m.from_user.id)
    bot.send_message(m.chat.id, f"🎒 {items}")

@bot.message_handler(func=lambda m: m.text.startswith("EQUIP"))
def h4(m):
    parts = m.text.split()
    if len(parts) < 2:
        bot.send_message(m.chat.id, "EQUIP knife")
        return
    equip(m.from_user.id, parts[1])
    bot.send_message(m.chat.id, f"🧥 equipped {parts[1]}")

# ================= RUN =================

bot.infinity_polling()
