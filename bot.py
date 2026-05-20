import telebot
import sqlite3
import random
import time
import os
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "@KingAVIV")

if not TOKEN:
    raise ValueError("BOT_TOKEN not found")

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

# ================= SAFE =================
def user(uid):
    cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
    conn.commit()
    cur.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    return cur.fetchone()

def update(q, p):
    cur.execute(q, p)
    conn.commit()

def power(uid):
    cur.execute("SELECT COALESCE(SUM(power),0) FROM inventory WHERE user_id=?", (uid,))
    val = cur.fetchone()[0]
    return val if val else 0

def vip(u):
    return u and u[6] > int(time.time())

# ================= GAME =================
def work(uid):
    u = user(uid)
    now = int(time.time())

    if now - u[4] < 30:
        return None

    base = random.randint(40, 120)
    reward = base + power(uid)

    if vip(u):
        reward = int(reward * 1.4)

    update("UPDATE users SET coins = coins + ?, last_work=? WHERE user_id=?",
           (reward, now, uid))
    return reward

def daily(uid):
    u = user(uid)
    now = int(time.time())

    if now - u[5] < 86400:
        return None

    reward = random.randint(120, 350)

    update("UPDATE users SET coins = coins + ?, last_daily=? WHERE user_id=?",
           (reward, now, uid))
    return reward

def case(uid):
    r = random.random()

    if r < 0.6:
        val = random.randint(20, 150)
        update("UPDATE users SET coins = coins + ? WHERE user_id=?", (val, uid))
        return f"💰 +{val}"

    if r < 0.85:
        p = random.randint(1, 12)
        cur.execute("INSERT INTO inventory VALUES (?,?,?)", (uid, "blade", p))
        conn.commit()
        return f"🔪 item +{p}"

    if r < 0.95:
        val = random.randint(200, 500)
        update("UPDATE users SET coins = coins + ? WHERE user_id=?", (val, uid))
        return f"🔥 JACKPOT +{val}"

    return "💀 empty"

def pvp(a, b):
    if a == b:
        return "❌ self attack blocked"

    ua = user(a)
    ub = user(b)

    if not ub:
        return "❌ player not found"

    pa = ua[3]*2 + power(a)
    pb = ub[3]*2 + power(b)

    if pa + pb == 0:
        return "⚖️ no power"

    roll = random.randint(1, pa + pb)

    if roll <= pa:
        steal = max(1, int(ub[1]*0.1))
        update("UPDATE users SET coins = coins + ? WHERE user_id=?", (steal, a))
        update("UPDATE users SET coins = coins - ? WHERE user_id=?", (steal, b))
        return f"⚔ WIN +{steal}"

    return "🛡 LOSE"

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

# ================= START =================
@bot.message_handler(commands=['start'])
def start(m):
    user(m.from_user.id)
    bot.send_message(m.chat.id, "🎮 NEON CITY 4.5", reply_markup=menu())

# ================= CALLBACK =================
@bot.callback_query_handler(func=lambda c: True)
def cb(c):
    uid = c.from_user.id
    u = user(uid)

    if c.data == "work":
        r = work(uid)
        bot.answer_callback_query(c.id, f"+{r}" if r else "cooldown")

    elif c.data == "daily":
        r = daily(uid)
        bot.answer_callback_query(c.id, f"+{r}" if r else "already")

    elif c.data == "case":
        bot.answer_callback_query(c.id, case(uid))

    elif c.data == "profile":
        p = power(uid)
        bot.send_message(c.message.chat.id,
            f"👤 PROFILE\n💰 {u[1]}\n⭐ {u[2]}\n📊 {u[3]}\n⚡ {p}"
        )

    elif c.data == "shop":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("VIP", url=f"https://t.me/{ADMIN_USERNAME.strip('@')}"))
        bot.send_message(c.message.chat.id, "🛒 SHOP", reply_markup=kb)

    elif c.data == "pvp":
        bot.send_message(c.message.chat.id, "⚔ PvP: /pvp ID (next update UI)")

# ================= RUN =================
print("NEON CITY 4.5 RUNNING")
bot.infinity_polling()
