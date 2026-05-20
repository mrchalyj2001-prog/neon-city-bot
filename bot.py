import telebot
import sqlite3
import random
import time
import os
import threading
from flask import Flask
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= WEB SERVER =================
app = Flask(__name__)

@app.route('/')
def home():
    return "NEON CITY ONLINE"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ================= CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "KingAVIV").strip("@")

if not TOKEN:
    raise ValueError("BOT_TOKEN not found!")

bot = telebot.TeleBot(TOKEN)

# ================= DATABASE =================
conn = sqlite3.connect("game.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    coins INTEGER DEFAULT 500,
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

# ================= USER SYSTEM =================
def user(uid):
    with db_lock:
        cur.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
            (uid,)
        )

        conn.commit()

        cur.execute(
            "SELECT * FROM users WHERE user_id=?",
            (uid,)
        )

        return cur.fetchone()

def update(q, p):
    with db_lock:
        cur.execute(q, p)
        conn.commit()

def power(uid):
    with db_lock:
        cur.execute(
            "SELECT COALESCE(SUM(power),0) FROM inventory WHERE user_id=?",
            (uid,)
        )

        val = cur.fetchone()[0]
        return val or 0

def vip(u):
    return u and u[6] > int(time.time())

# ================= XP SYSTEM =================
def add_xp(uid, amount):

    u = user(uid)

    xp = u[2] + amount
    level = u[3]

    need = level * 100

    while xp >= need:
        xp -= need
        level += 1
        need = level * 100

    update(
        "UPDATE users SET xp=?, level=? WHERE user_id=?",
        (xp, level, uid)
    )

# ================= GAME =================
def work(uid):

    u = user(uid)

    now = int(time.time())

    cooldown = 20 if vip(u) else 30

    if now - u[4] < cooldown:
        left = cooldown - (now - u[4])
        return None, f"⏳ Подожди {left} сек."

    base = random.randint(40, 120)

    reward = base + power(uid)

    if vip(u):
        reward = int(reward * 1.5)

    update(
        "UPDATE users SET coins = coins + ?, last_work=? WHERE user_id=?",
        (reward, now, uid)
    )

    add_xp(uid, 10)

    return reward, f"💼 +{reward} монет"

def daily(uid):

    u = user(uid)

    now = int(time.time())

    if now - u[5] < 86400:
        return None, "🎁 Daily уже получен"

    reward = random.randint(150, 500)

    if vip(u):
        reward += 200

    update(
        "UPDATE users SET coins = coins + ?, last_daily=? WHERE user_id=?",
        (reward, now, uid)
    )

    add_xp(uid, 25)

    return reward, f"🎁 +{reward} монет"

def case(uid):

    u = user(uid)

    case_price = 150

    if u[1] < case_price:
        return "❌ Нужно 150 монет"

    update(
        "UPDATE users SET coins = coins - ? WHERE user_id=?",
        (case_price, uid)
    )

    roll = random.random()

    if roll < 0.50:

        val = random.randint(50, 200)

        update(
            "UPDATE users SET coins = coins + ? WHERE user_id=?",
            (val, uid)
        )

        return f"💰 Выпало {val} монет"

    elif roll < 0.80:

        rarity_roll = random.random()

        if rarity_roll < 0.6:
            rarity = "⚪ Common"
            p = random.randint(1, 4)

        elif rarity_roll < 0.9:
            rarity = "🟣 Epic"
            p = random.randint(5, 10)

        else:
            rarity = "🟡 Legendary"
            p = random.randint(11, 20)

        with db_lock:
            cur.execute(
                "INSERT INTO inventory VALUES (?,?,?)",
                (uid, rarity, p)
            )

            conn.commit()

        return f"{rarity} предмет +{p} power"

    elif roll < 0.95:

        val = random.randint(300, 1000)

        update(
            "UPDATE users SET coins = coins + ? WHERE user_id=?",
            (val, uid)
        )

        return f"🔥 JACKPOT +{val}"

    return "💀 Пустой кейс"

def pvp(a, b):

    if a == b:
        return "❌ Нельзя атаковать себя"

    ua = user(a)
    ub = user(b)

    pa = ua[3] * 2 + power(a)
    pb = ub[3] * 2 + power(b)

    roll = random.randint(1, pa + pb)

    if roll <= pa:

        steal = max(1, int(ub[1] * 0.12))

        update(
            "UPDATE users SET coins = coins + ? WHERE user_id=?",
            (steal, a)
        )

        update(
            "UPDATE users SET coins = coins - ? WHERE user_id=?",
            (steal, b)
        )

        add_xp(a, 15)

        return f"⚔️ Победа! +{steal} монет"

    return "🛡️ Поражение"

# ================= UI =================
def menu():

    kb = InlineKeyboardMarkup(row_width=2)

    kb.add(
        InlineKeyboardButton("💼 Work", callback_data="work"),
        InlineKeyboardButton("🎁 Daily", callback_data="daily"),
        InlineKeyboardButton("📦 Case", callback_data="case"),
        InlineKeyboardButton("🎒 Inventory", callback_data="inventory"),
        InlineKeyboardButton("👤 Profile", callback_data="profile"),
        InlineKeyboardButton("🏆 Top", callback_data="top"),
        InlineKeyboardButton("⚔ PvP", callback_data="pvp"),
        InlineKeyboardButton("🛒 Shop", callback_data="shop")
    )

    return kb

# ================= START =================
@bot.message_handler(commands=['start'])
def start(m):

    user(m.from_user.id)

    bot.send_message(
        m.chat.id,
        "🌃 <b>NEON CITY 6.0</b>\n\n"
        "Добро пожаловать в неоновый город.",
        parse_mode='HTML',
        reply_markup=menu()
    )

# ================= BUTTONS =================
@bot.callback_query_handler(func=lambda c: True)
def callback(c):

    uid = c.from_user.id

    if c.data == "work":

        reward, text = work(uid)

        bot.answer_callback_query(c.id, text)

    elif c.data == "daily":

        reward, text = daily(uid)

        bot.answer_callback_query(c.id, text)

    elif c.data == "case":

        bot.answer_callback_query(c.id, case(uid))

    elif c.data == "inventory":

        with db_lock:
            cur.execute(
                "SELECT item, power FROM inventory WHERE user_id=?",
                (uid,)
            )

            items = cur.fetchall()

        if not items:

            bot.send_message(
                c.message.chat.id,
                "🎒 Инвентарь пуст"
            )

            return

        text = "🎒 <b>ИНВЕНТАРЬ</b>\n\n"

        for item, p in items[-15:]:
            text += f"{item} | ⚡ {p}\n"

        bot.send_message(
            c.message.chat.id,
            text,
            parse_mode='HTML'
        )

    elif c.data == "profile":

        u = user(uid)

        p = power(uid)

        bot.send_message(
            c.message.chat.id,
            f"👤 <b>ПРОФИЛЬ</b>\n\n"
            f"💰 Монеты: {u[1]}\n"
            f"⭐ XP: {u[2]}\n"
            f"📊 Уровень: {u[3]}\n"
            f"⚡ Power: {p}\n"
            f"👑 VIP: {'✅ Да' if vip(u) else '❌ Нет'}",
            parse_mode='HTML'
        )

    elif c.data == "top":

        with db_lock:

            cur.execute(
                "SELECT user_id, coins, level FROM users ORDER BY coins DESC LIMIT 10"
            )

            top_players = cur.fetchall()

        text = "🏆 <b>ТОП ИГРОКОВ</b>\n\n"

        for i, pl in enumerate(top_players, start=1):
            text += f"{i}. ID {pl[0]} | 💰 {pl[1]} | 📊 LVL {pl[2]}\n"

        bot.send_message(
            c.message.chat.id,
            text,
            parse_mode='HTML'
        )

    elif c.data == "shop":

        kb = InlineKeyboardMarkup()

        kb.add(
            InlineKeyboardButton(
                "💎 Купить VIP",
                url=f"https://t.me/{ADMIN_USERNAME}"
            )
        )

        bot.send_message(
            c.message.chat.id,
            "🛒 <b>VIP МАГАЗИН</b>\n\n"
            "✨ VIP даёт:\n"
            "• +50% монет\n"
            "• Быстрый cooldown\n"
            "• Бонусы\n",
            parse_mode='HTML',
            reply_markup=kb
        )

    elif c.data == "pvp":

        bot.send_message(
            c.message.chat.id,
            "⚔️ Используй команду:\n/pvp ID"
        )

# ================= RUN =================
if __name__ == "__main__":

    threading.Thread(target=run_web).start()

    print("🚀 NEON CITY 6.0 ONLINE")

    while True:

        try:

            bot.infinity_polling(
                none_stop=True,
                interval=0,
                timeout=30,
                long_polling_timeout=30
            )

        except Exception as e:

            print(f"⚠️ ERROR: {e}")

            time.sleep(5)
