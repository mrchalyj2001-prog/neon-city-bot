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
awaiting_price = {}   # Для продажи предметов

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
            name = f"{random.choice(['Неоновый','Кибер','Квантовый','Нейро','Плазменный','Теневой','Аркановый','Хромированный'])} " \
                   f"{random.choice(['Клинок','Имплант','Броня','Процессор','Ядро','Корона','Костюм','Перчатки'])}"
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
    return u[7] > int(time.time()) if u else False

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

# ================= MAIN MENU =================
def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💼 Work", callback_data="work"),
        InlineKeyboardButton("📦 Кейс 180💰", callback_data="case"),
        InlineKeyboardButton("🏪 Рынок", callback_data="market"),
        InlineKeyboardButton("🏢 Бизнесы", callback_data="biz"),
        InlineKeyboardButton("📋 Задания", callback_data="quests"),
        InlineKeyboardButton("🎒 Инвентарь", callback_data="inv"),
        InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        InlineKeyboardButton("🏆 Топ", callback_data="top")
    )
    return kb

# ================= CORE FUNCTIONS =================
def work(uid):
    u = get_user(uid)
    now = int(time.time())
    cd = 20 if is_vip(u) else 30
    if now - u[4] < cd:
        return f"⏳ Ещё {cd - (now - u[4])} сек."
    
    reward = random.randint(70, 170) + get_power(uid)
    if is_vip(u):
        reward = int(reward * 1.6)
    
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

    if random.random() < 0.018:  # Очень редкий Mythic
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
        if not item:
            return "❌ Предмет не найден"
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
        if not lot:
            return "❌ Лот уже продан"

        seller_id, item_id, price, name, rarity = lot
        buyer = get_user(buyer_id)
        if buyer[1] < price:
            return "❌ Недостаточно монет"

        cur.execute("UPDATE users SET coins = coins - ? WHERE user_id=?", (price, buyer_id))
        cur.execute("UPDATE users SET coins = coins + ? WHERE user_id=?", (price, seller_id))
        cur.execute("UPDATE inventory SET user_id=? WHERE id=?", (buyer_id, item_id))
        cur.execute("DELETE FROM market WHERE id=?", (lot_id,))
        conn.commit()
    return f"🎉 Куплено: {rarity} {name}"

# ================= QUESTS =================
def get_quests(uid):
    now = int(time.time())
    u = get_user(uid)
    if now - u[6] < 86400:
        return None  # уже брал сегодня

    quests = [
        ("Сделай Work 8 раз", 8, 450),
        ("Открой 3 кейса", 3, 600),
        ("Набери 800 XP", 800, 700)
    ]
    return quests

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

    elif data == "inv":
        with db_lock:
            cur.execute("SELECT id, name, rarity, power, equipped FROM inventory WHERE user_id=? ORDER BY power DESC", (uid,))
            items = cur.fetchall()
        if not items:
            bot.send_message(c.message.chat.id, "🎒 Инвентарь пуст")
            return
        text = "🎒 <b>ИНВЕНТАРЬ</b>\n\n"
        kb = InlineKeyboardMarkup(row_width=1)
        for iid, name, rarity, power, eq in items[:12]:
            status = " [🟢 Надето]" if eq else ""
            text += f"{rarity} {name} ⚡{power}{status}\n"
            kb.add(InlineKeyboardButton(f"{'Снять' if eq else 'Надеть'}", callback_data=f"eq_{iid}"))
            kb.add(InlineKeyboardButton("📌 Выставить на рынок", callback_data=f"sell_{iid}"))
        bot.send_message(c.message.chat.id, text, parse_mode='HTML', reply_markup=kb)

    elif data.startswith("eq_"):
        iid = int(data[3:])
        with db_lock:
            cur.execute("SELECT equipped FROM inventory WHERE id=?", (iid,))
            eq = cur.fetchone()[0]
            new = 0 if eq else 1
            if new == 1:
                cur.execute("SELECT COUNT(*) FROM inventory WHERE user_id=? AND equipped=1", (uid,))
                if cur.fetchone()[0] >= 5:
                    bot.answer_callback_query(c.id, "❌ Макс. 5 предметов!", show_alert=True)
                    return
            cur.execute("UPDATE inventory SET equipped=? WHERE id=?", (new, iid))
            conn.commit()
        bot.answer_callback_query(c.id, "✅ Готово")

    elif data.startswith("sell_"):
        iid = int(data[5:])
        awaiting_price[uid] = iid
        bot.send_message(c.message.chat.id, "💰 Напиши цену продажи (от 100 до 100000):")

    elif data == "market":
        with db_lock:
            cur.execute("""SELECT m.id, m.price, i.name, i.rarity, i.power 
                           FROM market m JOIN inventory i ON m.item_id = i.id 
                           ORDER BY m.time DESC LIMIT 10""")
            lots = cur.fetchall()
        if not lots:
            bot.send_message(c.message.chat.id, "🏪 Рынок пуст. Выставь свои вещи!")
            return
        text = "🏪 <b>РЫНОК</b>\n\n"
        kb = InlineKeyboardMarkup(row_width=1)
        for lid, price, name, rarity, power in lots:
            text += f"{rarity} {name} ⚡{power} — {price}💰\n"
            kb.add(InlineKeyboardButton(f"Купить за {price}", callback_data=f"buy_{lid}"))
        bot.send_message(c.message.chat.id, text, parse_mode='HTML', reply_markup=kb)

    elif data.startswith("buy_"):
        lot_id = int(data[4:])
        result = buy_from_market(uid, lot_id)
        bot.answer_callback_query(c.id, result, show_alert=True)

    elif data == "biz":
        text = "🏢 <b>БИЗНЕСЫ</b>\n\n"
        kb = InlineKeyboardMarkup(row_width=1)
        for name, info in BUSINESSES.items():
            text += f"{name} — {info['cost']}💰 (+{info['income']}/10мин)\n"
            kb.add(InlineKeyboardButton(f"Купить {name}", callback_data=f"buybiz_{name}"))
        bot.send_message(c.message.chat.id, text, parse_mode='HTML', reply_markup=kb)

    elif data.startswith("buybiz_"):
        name = data[7:]
        u = get_user(uid)
        biz = BUSINESSES[name]
        if u[1] < biz["cost"]:
            bot.answer_callback_query(c.id, "❌ Недостаточно монет", show_alert=True)
            return
        with db_lock:
            cur.execute("UPDATE users SET coins=coins-? WHERE user_id=?", (biz["cost"], uid))
            cur.execute("INSERT INTO businesses (user_id, name, income, last_collect) VALUES (?,?,?,?)",
                        (uid, name, biz["income"], int(time.time())))
            conn.commit()
        bot.answer_callback_query(c.id, f"✅ Куплен {name}!", show_alert=True)

    elif data == "quests":
        quests = get_quests(uid)
        if not quests:
            bot.answer_callback_query(c.id, "🎁 Задания обновятся завтра", show_alert=True)
            return
        # Здесь можно расширить логику выполнения заданий позже

# ================= TEXT HANDLER (для цены) =================
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

    elif m.text == "/start" or m.text.startswith("/start "):
        pass
    else:
        bot.reply_to(m, "Используй кнопки меню 👇")

# ================= START =================
@bot.message_handler(commands=['start'])
def start(m):
    get_user(m.from_user.id)
    bot.send_message(m.chat.id,
        "🌃 <b>NEON CITY 6.3</b>\n\n"
        "Полноценная игра:\n"
        "• Фарм • Редкий лут • Бизнесы • Рынок • Задания",
        parse_mode='HTML', reply_markup=main_menu())

# ================= RUN =================
if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    print("🌃 NEON CITY 6.3 FINAL — ЗАПУЩЕН")
    
    while True:
        try:
            bot.infinity_polling(none_stop=True, interval=0, timeout=30)
        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(5)
