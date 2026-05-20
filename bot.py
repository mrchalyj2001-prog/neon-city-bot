import telebot
import sqlite3
import random
import time
import os
import threading
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = os.getenv("BOT_TOKEN")

bot = telebot.TeleBot(TOKEN)

conn = sqlite3.connect("game.db", check_same_thread=False)
cur = conn.cursor()
lock = threading.Lock()

# ================= DB =================
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    coins INTEGER DEFAULT 100,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    last_work INTEGER DEFAULT 0,
    last_daily INTEGER DEFAULT 0,
    strength INTEGER DEFAULT 1,
    defense INTEGER DEFAULT 1,
    luck INTEGER DEFAULT 1,
    house INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    user_id INTEGER,
    name TEXT,
    type TEXT,
    power INTEGER
)
""")

conn.commit()

# ================= CORE =================
def user(uid):
    with lock:
        cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
        conn.commit()
        cur.execute("SELECT * FROM users WHERE user_id=?", (uid,))
        return cur.fetchone()

def update(q, p):
    with lock:
        cur.execute(q, p)
        conn.commit()

# ================= STATS =================
def stats(uid):
    u = user(uid)

    with lock:
        cur.execute("SELECT type, power FROM inventory WHERE user_id=?", (uid,))
        items = cur.fetchall()

    atk = sum(p for t, p in items if t == "weapon")
    df = sum(p for t, p in items if t == "armor")

    return u[6] + atk, u[7] + df, u[8]

# ================= GAME =================
def work(uid):
    u = user(uid)
    now = int(time.time())

    if now - u[4] < 20:
        return "⏳ cooldown"

    reward = random.randint(30, 90) + stats(uid)[0]
    update("UPDATE users SET coins = coins + ?, last_work=? WHERE user_id=?",
           (reward, now, uid))
    return f"+{reward}"

def daily(uid):
    u = user(uid)
    now = int(time.time())

    if now - u[5] < 86400:
        return "❌ daily used"

    reward = random.randint(120, 300)
    update("UPDATE users SET coins = coins + ?, last_daily=? WHERE user_id=?",
           (reward, now, uid))
    return f"+{reward}"

# ================= CASE =================
def case(uid):
    r = random.random()

    if r < 0.5:
        v = random.randint(20, 120)
        update("UPDATE users SET coins = coins + ? WHERE user_id=?", (v, uid))
        return f"💰 +{v}"

    elif r < 0.8:
        t = random.choice(["weapon", "armor"])
        p = random.randint(1, 10)
        name = "Blade" if t == "weapon" else "Armor"

        with lock:
            cur.execute("INSERT INTO inventory VALUES (?,?,?,?)",
                        (uid, name, t, p))
            conn.commit()

        return f"🎒 {name}+{p}"

    return "💀 empty"

# ================= HOUSE =================
def buy_house(uid):
    u = user(uid)

    if u[1] < 500:
        return "❌ need 500 coins"

    update("UPDATE users SET coins = coins - 500, house = house + 1 WHERE user_id=?", (uid,))
    return "🏠 house bought"

def house_income(uid):
    u = user(uid)

    if u[9] <= 0:
        return 0

    income = u[9] * 5
    update("UPDATE users SET coins = coins + ? WHERE user_id=?", (income, uid))
    return income

# ================= PVE =================
def pve(uid):
    u = user(uid)
    enemy = random.randint(20, 120)

    s, d, l = stats(uid)

    player = s + d + random.randint(0, l)

    if player > enemy:
        reward = random.randint(30, 150)
        update("UPDATE users SET coins = coins + ? WHERE user_id=?", (reward, uid))
        return f"⚔ WIN +{reward}"
    else:
        loss = random.randint(10, 40)
        update("UPDATE users SET coins = coins - ? WHERE user_id=?", (loss, uid))
        return f"💀 LOSE -{loss}"

# ================= MENU =================
def menu():
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("💼 Work", callback_data="work"),
        InlineKeyboardButton("🎁 Daily", callback_data="daily"),
        InlineKeyboardButton("📦 Case", callback_data="case"),
        InlineKeyboardButton("⚔ PvE", callback_data="pve"),
    )
    kb.add(
        InlineKeyboardButton("🏠 House", callback_data="house"),
        InlineKeyboardButton("👤 Profile", callback_data="profile")
    )
    return kb

# ================= HANDLERS =================
@bot.message_handler(commands=['start'])
def start(m):
    user(m.from_user.id)
    bot.send_message(m.chat.id, "🎮 NEON CITY v8", reply_markup=menu())

@bot.callback_query_handler(func=lambda c: True)
def cb(c):
    uid = c.from_user.id

    if c.data == "work":
        bot.answer_callback_query(c.id, work(uid))

    elif c.data == "daily":
        bot.answer_callback_query(c.id, daily(uid))

    elif c.data == "case":
        bot.answer_callback_query(c.id, case(uid))

    elif c.data == "pve":
        bot.answer_callback_query(c.id, pve(uid))

    elif c.data == "house":
        msg = buy_house(uid)
        income = house_income(uid)
        bot.answer_callback_query(c.id, f"{msg} | +{income}/tick")

    elif c.data == "profile":
        u = user(uid)
        s, d, l = stats(uid)

        bot.send_message(c.message.chat.id,
            f"💰 {u[1]}\n"
            f"⭐ XP {u[2]}\n"
            f"📊 LVL {u[3]}\n\n"
            f"💪 {s}\n🛡 {d}\n🍀 {l}\n"
            f"🏠 houses {u[9]}"
        )

# ================= RUN =================
print("NEON CITY v8 RUNNING")
bot.infinity_polling()
