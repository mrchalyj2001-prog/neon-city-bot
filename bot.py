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
    return "🌃 NEON CITY 6.3 — ONLINE"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)

# ================= CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не найден! Добавь его в Environment Variables.")

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
        last_quest INTEGER DEFAULT 0,
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

    CREATE TABLE IF NOT EXISTS market (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        seller_id INTEGER,
        item_id INTEGER UNIQUE,
        price INTEGER,
        time INTEGER
    );

    CREATE TABLE IF NOT EXISTS businesses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        income INTEGER,
        last_collect INTEGER DEFAULT 0
    );
""")
conn.commit()

db_lock = threading.Lock()
awaiting_price = {}

# ================= RARITIES =================
RARITIES = {
    "⚪ Common": (1, 15, 0.45),
    "🟢 Rare": (16, 35, 0.30),
    "🔵 Epic": (36, 70, 0.17),
    "🟡 Legendary": (71, 110, 0.06),
    "🔴 Mythic": (120, 200, 0.02)
}

def generate_item():
    roll = random.random()
    cum = 0
    for rarity, (minp, maxp, chance) in RARITIES.items():
        cum += chance
        if roll <= cum:
            power = random.randint(minp, maxp)
            name = f"{random.choice(['Неоновый','Кибер','Квантовый','Нейро','Плазменный','Теневой','Аркановый'])} " \
                   f"{random.choice(['Клинок','Имплант','Броня','Процессор','Ядро','Корона','Костюм'])}"
            return name, rarity, power
    return "Неоновый Клинок", "⚪ Common", 10

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
    return u and u[7] > int(time.time())

def add_xp(uid, amount):
    u = get_user(uid)
    xp, level = u[2] + amount, u[3]
    while xp >= level * 120:
        xp -= level * 120
        level += 1
    with db_lock:
        cur.execute("UPDATE users SET xp=?, level=? WHERE user_id=?", (xp, level, uid))
        conn.commit()

# ================= BUSINESSES =================
BUSINESSES = {
    "Неоновая Лавка": {"cost": 3500, "income": 90},
    "Кибер-Такси": {"cost": 9000, "income": 250},
    "Подпольный Клуб": {"cost": 18000, "income": 520},
    "ShadowTech Corp": {"cost": 50000, "income": 1350}
}

def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💼 Work", callback_data="work"),
        InlineKeyboardButton("📦 Кейс 180💰", callback_data="case"),
        InlineKeyboardButton("🏪 Рынок", callback_data="market"),
        InlineKeyboardButton("🏢 Бизнесы", callback_data="biz"),
        InlineKeyboardButton("🎒 Инвентарь", callback_data="inv"),
        InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        InlineKeyboardButton("🏆 Топ", callback_data="top")
    )
    return kb

# ================= GAME FUNCTIONS =================
def work(uid):
    u = get_user(uid)
    now = int(time.time())
    cd = 20 if is_vip(u) else 30
    if now - u[4] < cd:
        return f"⏳ Ещё {cd - (now - u[4])} сек."
    
    reward = random.randint(70, 170) + get_power(uid)
    if is_vip(u): reward = int(reward * 1.6)
    
    with db_lock:
        cur.execute("UPDATE users SET coins=coins+?, last_work=? WHERE user_id=?", (reward, now, uid))
        conn.commit()
    add_xp(uid, 15)
    return f"💼 +{reward} монет"

def open_case(uid):
    u = get_user(uid)
    if u[1] < 180:
        return "❌ Нужно 180 монет"
    
    with db_lock:
        cur.execute("UPDATE users SET coins=coins-180 WHERE user_id=?", (uid,))
        conn.commit()

    if random.random() < 0.02:
        name, rarity, power = "🔴 Артефакт Бездны", "🔴 Mythic", random.randint(140, 200)
    else:
        name, rarity, power = generate_item()

    with db_lock:
        cur.execute("INSERT INTO inventory (user_id, name, rarity, power) VALUES (?,?,?,?)",
                    (uid, name, rarity, power))
        conn.commit()
    return f"{rarity} {name}\n⚡ +{power} power"

# ================= MARKET =================
def list_on_market(uid, item_id, price):
    with db_lock:
        cur.execute("SELECT name, rarity FROM inventory WHERE id=? AND user_id=?", (item_id, uid))
        item = cur.fetchone()
        if not item: return "❌ Предмет не найден"
        
        cur.execute("DELETE FROM market WHERE item_id=?", (item_id,))
        cur.execute("INSERT INTO market (seller_id, item_id, price, time) VALUES (?,?,?,?)",
                    (uid, item_id, price, int(time.time())))
        cur.execute("UPDATE inventory SET equipped=0 WHERE id=?", (item_id,))
        conn.commit()
    return f"✅ {item[1]} {item[0]} выставлен за {price}💰"

def buy_from_market(buyer_id, lot_id):
    with db_lock:
        cur.execute("""SELECT m.seller_id, m.item_id, m.price, i.name, i.rarity 
                       FROM market m JOIN inventory i ON m.item_id = i.id 
                       WHERE m.id=?""", (lot_id,))
        lot = cur.fetchone()
        if not lot: return "❌ Лот уже продан"
        
        seller_id, item_id, price, name, rarity = lot
        buyer = get_user(buyer_id)
        if buyer[1] < price: return "❌ Недостаточно монет"
        
        cur.execute("UPDATE users SET coins = coins - ? WHERE user_id=?", (price, buyer_id))
        cur.execute("UPDATE users SET coins = coins + ? WHERE user_id=?", (price, seller_id))
        cur.execute("UPDATE inventory SET user_id=? WHERE id=?", (buyer_id, item_id))
        cur.execute("DELETE FROM market WHERE id=?", (lot_id,))
        conn.commit()
    return f"🎉 Куплено: {rarity} {name}"

# ================= CALLBACKS =================
@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    uid = c.from_user.id
    data = c.data

    if data == "work":
        bot.answer_callback_query(c.id, work(uid))
    elif data == "case":
        bot.answer_callback_query(c.id, open_case(uid), show_alert=True)
    elif data == "profile":
        u = get_user(uid)
        power = get_power(uid)
        vip_text = "✅ Активен" if is_vip(u) else "❌ Нет"
        bot.send_message(c.message.chat.id,
            f"👤 <b>ПРОФИЛЬ</b>\n\n"
            f"💰 Монеты: {u[1]:,}\n"
            f"📊 Уровень: {u[3]}\n"
            f"⚡ Power: {power}\n"
            f"👑 VIP: {vip_text}", parse_mode='HTML')
    # ... (остальные кнопки можно добавить позже)

    elif data.startswith("sell_"):
        iid = int(data[5:])
        awaiting_price[uid] = iid
        bot.send_message(c.message.chat.id, "💰 Напиши цену продажи:")

# ================= TEXT HANDLER =================
@bot.message_handler(content_types=['text'])
def text_handler(m):
    uid = m.from_user.id
    if uid in awaiting_price:
        try:
            price = int(m.text)
            if price < 100 or price > 100000:
                bot.reply_to(m, "❌ Цена от 100 до 100000")
                return
            item_id = awaiting_price.pop(uid)
            result = list_on_market(uid, item_id, price)
            bot.reply_to(m, result)
        except:
            bot.reply_to(m, "❌ Введи только число")

@bot.message_handler(commands=['start'])
def start(m):
    get_user(m.from_user.id)
    bot.send_message(m.chat.id,
        "🌃 <b>NEON CITY 6.3</b>\n\n"
        "Бот перезапущен.\nНажимай кнопки и проверяй работу.",
        parse_mode='HTML', reply_markup=main_menu())

# ================= RUN (Стабильная версия для Render) =================
if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    
    print("🌃 NEON CITY 6.3 FINAL — ЗАПУЩЕН")
    print("Flask сервер работает, запускаем бота...")
    
    time.sleep(5)
    
    while True:
        try:
            print("✅ Polling запущен...")
            bot.infinity_polling(
                none_stop=True,
                interval=0.5,
                timeout=15,
                long_polling_timeout=15,
                skip_pending=True,
                allowed_updates=["message", "callback_query"]
            )
        except Exception as e:
            print(f"⚠️ Ошибка polling: {e}")
            time.sleep(8)
