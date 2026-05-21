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
    return "🌃 NEON CITY 6.3 ONLINE"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)

# ================= CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не найден в Environment Variables!")

bot = telebot.TeleBot(TOKEN)

# ================= DATABASE =================
conn = sqlite3.connect("game.db", check_same_thread=False)
cur = conn.cursor()

cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        coins INTEGER DEFAULT 800,
        xp INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        last_work INTEGER DEFAULT 0,
        last_daily INTEGER DEFAULT 0,
        vip_until INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        rarity TEXT,
        power INTEGER,
        equipped INTEGER DEFAULT 0
    );
""")
conn.commit()

db_lock = threading.Lock()

# ================= HELPERS =================
def get_user(uid):
    with db_lock:
        cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
        conn.commit()
        cur.execute("SELECT * FROM users WHERE user_id=?", (uid,))
        return cur.fetchone()

def get_power(uid):
    with db_lock:
        cur.execute("SELECT COALESCE(SUM(power),0) FROM inventory WHERE user_id=? AND equipped=1", (uid,))
        return cur.fetchone()[0]

def is_vip(u):
    return u and u[6] > int(time.time())

def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💼 Work", callback_data="work"),
        InlineKeyboardButton("📦 Кейс", callback_data="case"),
        InlineKeyboardButton("🎒 Инвентарь", callback_data="inv"),
        InlineKeyboardButton("👤 Профиль", callback_data="profile")
    )
    return kb

# ================= GAME =================
def work(uid):
    u = get_user(uid)
    now = int(time.time())
    cd = 20 if is_vip(u) else 30
    if now - u[4] < cd:
        return f"⏳ Подожди {cd - (now - u[4])} сек"
    
    reward = random.randint(80, 160) + get_power(uid)
    with db_lock:
        cur.execute("UPDATE users SET coins = coins + ?, last_work = ? WHERE user_id=?", (reward, now, uid))
        conn.commit()
    return f"💼 +{reward} монет"

# ================= HANDLERS =================
@bot.message_handler(commands=['start'])
def start(m):
    get_user(m.from_user.id)
    bot.send_message(m.chat.id, "🌃 <b>NEON CITY 6.3</b>\n\nБот запущен!", 
                     parse_mode='HTML', reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    uid = c.from_user.id
    if c.data == "work":
        text = work(uid)
        bot.answer_callback_query(c.id, text)
    elif c.data == "profile":
        u = get_user(uid)
        power = get_power(uid)
        bot.send_message(c.message.chat.id, 
            f"👤 Профиль\n\nМонеты: {u[1]}\nУровень: {u[3]}\nPower: {power}", parse_mode='HTML')

# ================= RUN (для Render) =================
if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    print("🌃 NEON CITY 6.3 — ЗАПУЩЕН")
    
    while True:
        try:
            bot.infinity_polling(none_stop=True, interval=0.5, timeout=15, skip_pending=True)
        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(5)
