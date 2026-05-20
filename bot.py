import telebot
import sqlite3
import random
import time
import os
import threading

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
    job_level INTEGER DEFAULT 1,
    strength INTEGER DEFAULT 1,
    defense INTEGER DEFAULT 1,
    luck INTEGER DEFAULT 1,
    house INTEGER DEFAULT 0,
    last_work INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    user_id INTEGER,
    name TEXT,
    type TEXT,
    rarity TEXT,
    power INTEGER,
    equipped INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS market (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller INTEGER,
    name TEXT,
    price INTEGER,
    type TEXT,
    rarity TEXT,
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
        cur.execute("""
            SELECT type, power, rarity FROM inventory
            WHERE user_id=? AND equipped=1
        """, (uid,))
        items = cur.fetchall()

    atk = sum(p for t, p, r in items if t == "weapon")
    df = sum(p for t, p, r in items if t == "armor")

    rarity_bonus = sum({"common":1,"rare":2,"epic":4}.get(r,1) for t,p,r in items)

    return u[5] + atk + rarity_bonus, u[6] + df + rarity_bonus, u[7]

# ================= CASE =================
def case(uid):
    r = random.random()

    if r < 0.55:
        v = random.randint(20, 150)
        update("UPDATE users SET coins = coins + ? WHERE user_id=?", (v, uid))
        return f"💰 +{v}"

    if r < 0.85:
        rarity = random.choice(["common", "rare", "epic"])
        t = random.choice(["weapon", "armor"])
        p = random.randint(1, 12)

        with lock:
            cur.execute("INSERT INTO inventory VALUES (?,?,?,?,?,0)",
                        (uid, t, t, rarity, p))
            conn.commit()

        return f"🎒 {rarity.upper()} {t}+{p}"

    loss = random.randint(20, 80)
    update("UPDATE users SET coins = coins - ? WHERE user_id=?", (loss, uid))

    return f"💀 CURSE -{loss}"

# ================= INVENTORY =================
def inventory(uid):
    with lock:
        cur.execute("SELECT rowid, name, type, rarity, power, equipped FROM inventory WHERE user_id=?", (uid,))
        items = cur.fetchall()

    if not items:
        return "📭 empty inventory"

    text = "🎒 INVENTORY:\n"
    for i in items:
        eq = "🟢" if i[5] else "⚪"
        text += f"{eq} [{i[0]}] {i[3]} {i[2]} +{i[4]}\n"

    return text

# ================= EQUIP =================
def equip(uid, item_id):
    with lock:
        cur.execute("SELECT type, equipped FROM inventory WHERE rowid=? AND user_id=?", (item_id, uid))
        item = cur.fetchone()

        if not item:
            return "❌ not found"

        # unequip same type
        cur.execute("""
            UPDATE inventory SET equipped=0
            WHERE user_id=? AND type=?
        """, (uid, item[0]))

        cur.execute("UPDATE inventory SET equipped=1 WHERE rowid=?", (item_id,))
        conn.commit()

    return f"⚔ equipped {item[0]}"

# ================= MARKET =================
def sell(uid, item_id, price):
    with lock:
        cur.execute("""
            SELECT name,type,rarity,power FROM inventory
            WHERE rowid=? AND user_id=?
        """, (item_id, uid))
        item = cur.fetchone()

        if not item:
            return "❌ no item"

        cur.execute("""
            INSERT INTO market (seller,name,price,type,rarity,power)
            VALUES (?,?,?,?,?,?)
        """, (uid, item[0], price, item[1], item[2], item[3]))

        cur.execute("DELETE FROM inventory WHERE rowid=?", (item_id,))
        conn.commit()

    return f"🏪 listed for {price}"

def buy(uid, market_id):
    with lock:
        cur.execute("SELECT seller,price,type,rarity,power FROM market WHERE id=?", (market_id,))
        item = cur.fetchone()

        if not item:
            return "❌ not found"

        if user(uid)[1] < item[1]:
            return "❌ no money"

        update("UPDATE users SET coins = coins - ? WHERE user_id=?", (item[1], uid))
        update("UPDATE users SET coins = coins + ? WHERE user_id=?", (item[1], item[0]))

        cur.execute("""
            INSERT INTO inventory VALUES (?,?,?,?,?,0)
        """, (uid, item[2], item[2], item[3], item[4]))

        cur.execute("DELETE FROM market WHERE id=?", (market_id,))
        conn.commit()

    return "🛒 purchased"

# ================= WORK =================
def work(uid):
    u = user(uid)
    now = int(time.time())

    if now - u[9] < 3:
        return "⏳ cooldown"

    reward = 10 * u[4] + random.randint(1, 20) + stats(uid)[0]

    update("UPDATE users SET coins = coins + ?, last_work=? WHERE user_id=?",
           (reward, now, uid))

    return f"💼 +{reward}"

# ================= MENU =================
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

def menu():
    kb = InlineKeyboardMarkup()

    kb.add(
        InlineKeyboardButton("💼 Work", callback_data="work"),
        InlineKeyboardButton("📦 Case", callback_data="case")
    )

    kb.add(
        InlineKeyboardButton("🎒 Inv", callback_data="inv"),
        InlineKeyboardButton("⚔ Equip 1", callback_data="equip1")
    )

    return kb

# ================= HANDLER =================
@bot.message_handler(commands=['start'])
def start(m):
    user(m.from_user.id)
    bot.send_message(m.chat.id, "🎮 NEON CITY v13 RPG DEPTH", reply_markup=menu())

@bot.callback_query_handler(func=lambda c: True)
def cb(c):
    uid = c.from_user.id

    if c.data == "work":
        bot.answer_callback_query(c.id, work(uid))

    elif c.data == "case":
        bot.answer_callback_query(c.id, case(uid))

    elif c.data == "inv":
        bot.send_message(c.message.chat.id, inventory(uid))

    elif c.data == "equip1":
        bot.answer_callback_query(c.id, equip(uid, 1))

# ================= RUN =================
print("NEON CITY v13 RUNNING")
bot.infinity_polling()
