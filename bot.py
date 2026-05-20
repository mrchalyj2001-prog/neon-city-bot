import telebot
import sqlite3
import random
import time
import os
import threading
import sys
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "KingAVIV").strip("@")

if not TOKEN:
    raise ValueError("BOT_TOKEN not found in environment variables!")

bot = telebot.TeleBot(TOKEN)

# ================= DB =================
conn = sqlite3.connect("game.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    coins INTEGER DEFAULT 100,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    last_work INTEGER DEFAULT 0,
    last_daily INTEGER DEFAULT 0,
    vip_until INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    user_id INTEGER,
    item TEXT,
    power INTEGER DEFAULT 0
)
""")
conn.commit()

db_lock = threading.Lock()

# ================= SAFE DB =================
def user(uid):
    with db_lock:
        cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
        conn.commit()
        cur.execute("SELECT * FROM users WHERE user_id=?", (uid,))
        return cur.fetchone()

def update(q, p):
    with db_lock:
        cur.execute(q, p)
        conn.commit()

def power(uid):
    with db_lock:
        cur.execute("SELECT COALESCE(SUM(power),0) FROM inventory WHERE user_id=?", (uid,))
        val = cur.fetchone()[0]
        return val or 0

def vip(u):
    return u and u[6] > int(time.time())

# ================= GAME =================
def work(uid):
    u = user(uid)
    now = int(time.time())
    if now - u[4] < 30:
        return None, "⏳ Работать можно раз в 30 секунд!"

    base = random.randint(40, 120)
    reward = base + power(uid)
    if vip(u):
        reward = int(reward * 1.4)

    update("UPDATE users SET coins = coins + ?, last_work=? WHERE user_id=?", 
           (reward, now, uid))
    return reward, f"💼 +{reward} монет"

def daily(uid):
    u = user(uid)
    now = int(time.time())
    if now - u[5] < 86400:
        return None, "🎁 Daily уже получен сегодня!"

    reward = random.randint(120, 350)
    update("UPDATE users SET coins = coins + ?, last_daily=? WHERE user_id=?", 
           (reward, now, uid))
    return reward, f"🎁 +{reward} монет"

def case(uid):
    r = random.random()
    if r < 0.6:
        val = random.randint(20, 150)
        update("UPDATE users SET coins = coins + ? WHERE user_id=?", (val, uid))
        return f"💰 +{val} монет"
    elif r < 0.85:
        p = random.randint(1, 12)
        with db_lock:
            cur.execute("INSERT INTO inventory VALUES (?,?,?)", (uid, "blade", p))
            conn.commit()
        return f"🔪 Blade +{p} power"
    elif r < 0.95:
        val = random.randint(200, 500)
        update("UPDATE users SET coins = coins + ? WHERE user_id=?", (val, uid))
        return f"🔥 JACKPOT +{val} монет"
    return "💀 Пусто..."

def pvp(a, b):
    if a == b:
        return "❌ Нельзя атаковать себя!"
    ua = user(a)
    ub = user(b)
    if not ub:
        return "❌ Игрок не найден"

    pa = ua[3] * 2 + power(a)
    pb = ub[3] * 2 + power(b)

    if pa + pb == 0:
        return "⚖️ Оба без силы"

    roll = random.randint(1, pa + pb)
    if roll <= pa:
        steal = max(1, int(ub[1] * 0.1))
        update("UPDATE users SET coins = coins + ? WHERE user_id=?", (steal, a))
        update("UPDATE users SET coins = coins - ? WHERE user_id=?", (steal, b))
        return f"⚔️ ПОБЕДА! +{steal} монет"
    return "🛡️ Поражение"

# ================= UI =================
def menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💼 Work", callback_data="work"),
        InlineKeyboardButton("🎁 Daily", callback_data="daily"),
        InlineKeyboardButton("📦 Case", callback_data="case"),
        InlineKeyboardButton("👤 Profile", callback_data="profile"),
        InlineKeyboardButton("⚔ PvP", callback_data="pvp"),
        InlineKeyboardButton("🛒 Shop", callback_data="shop"),
    )
    return kb

# ================= HANDLERS =================
@bot.message_handler(commands=['start'])
def start(m):
    user(m.from_user.id)
    bot.send_message(m.chat.id, "🎮 <b>NEON CITY 4.5</b>\nДобро пожаловать в игру!", 
                     parse_mode='HTML', reply_markup=menu())

@bot.callback_query_handler(func=lambda c: True)
def cb(c):
    uid = c.from_user.id
    u = user(uid)

    if c.data == "work":
        reward, text = work(uid)
        bot.answer_callback_query(c.id, text if reward is None else f"+{reward}")

    elif c.data == "daily":
        reward, text = daily(uid)
        bot.answer_callback_query(c.id, text if reward is None else f"+{reward}")

    elif c.data == "case":
        bot.answer_callback_query(c.id, case(uid))

    elif c.data == "profile":
        p = power(uid)
        bot.send_message(c.message.chat.id,
            f"👤 <b>ПРОФИЛЬ</b>\n"
            f"💰 Монеты: {u[1]}\n"
            f"⭐ XP: {u[2]}\n"
            f"📊 Уровень: {u[3]}\n"
            f"⚡ Power: {p}\n"
            f"👑 VIP: {'✅ Активен' if vip(u) else '❌ Нет'}",
            parse_mode='HTML'
        )

    elif c.data == "shop":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Купить VIP", url=f"https://t.me/{ADMIN_USERNAME}"))
        bot.send_message(c.message.chat.id, "🛒 <b>МАГАЗИН</b>", parse_mode='HTML', reply_markup=kb)

    elif c.data == "pvp":
        bot.send_message(c.message.chat.id, "⚔️ PvP пока через команду:\n/pvp ID")

# ================= RUN =================
if __name__ == "__main__":
    print("🚀 NEON CITY 4.5 ЗАПУЩЕН")
    while True:
        try:
            bot.infinity_polling(none_stop=True, interval=0, timeout=20, long_polling_timeout=60)
        except Exception as e:
            print(f"⚠️ Ошибка: {e}")
            time.sleep(5)
