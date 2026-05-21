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
    return "🌃 NEON CITY 6.2 — ONLINE"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)

# ================= CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "KingAVIV").strip("@")

if not TOKEN:
    raise ValueError("BOT_TOKEN не найден!")

bot = telebot.TeleBot(TOKEN)

# ================= DATABASE =================
conn = sqlite3.connect("game.db", check_same_thread=False)
cur = conn.cursor()

cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        coins INTEGER DEFAULT 600,
        xp INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        last_work INTEGER DEFAULT 0,
        last_daily INTEGER DEFAULT 0,
        last_pvp INTEGER DEFAULT 0,
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
""")
conn.commit()

db_lock = threading.Lock()

# Для ожидания цены при продаже
awaiting_price = {}

# ================= RARITIES =================
RARITIES = {
    "⚪ Common": (1, 10, 0.48),
    "🟢 Rare": (11, 25, 0.30),
    "🔵 Epic": (26, 50, 0.15),
    "🟡 Legendary": (51, 85, 0.05),
    "🔴 Mythic": (90, 150, 0.02)
}

ITEM_BASE = ["Неоновый", "Кибер", "Голографический", "Квантовый", "Нейро", "Плазменный", "Теневой", "Аркановый", "Хромированный", "Вortex"]

def generate_item():
    roll = random.random()
    cum = 0
    for rarity_name, (minp, maxp, chance) in RARITIES.items():
        cum += chance
        if roll <= cum:
            power = random.randint(minp, maxp)
            name = f"{random.choice(ITEM_BASE)} {random.choice(['Клинок','Щит','Браслет','Костюм','Перчатки','Ботинки','Имплант','Ядро','Процессор','Корона'])}"
            return name, rarity_name, power
    return "Неоновый Клинок", "⚪ Common", 5

# ================= HELPERS =================
def get_user(uid):
    with db_lock:
        cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
        conn.commit()
        cur.execute("SELECT * FROM users WHERE user_id=?", (uid,))
        return cur.fetchone()

def update_user(query, params):
    with db_lock:
        cur.execute(query, params)
        conn.commit()

def get_power(uid):
    with db_lock:
        cur.execute("SELECT COALESCE(SUM(power),0) FROM inventory WHERE user_id=? AND equipped=1", (uid,))
        return cur.fetchone()[0]

def is_vip(u):
    return u and u[7] > int(time.time())

def add_xp(uid, amount):
    u = get_user(uid)
    xp, level = u[2] + amount, u[3]
    while xp >= level * 100:
        xp -= level * 100
        level += 1
    update_user("UPDATE users SET xp=?, level=? WHERE user_id=?", (xp, level, uid))

# ================= MARKET FUNCTIONS =================
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
    return f"✅ {item[1]} {item[0]} выставлен за {price} монет"

def buy_item(buyer_id, lot_id):
    with db_lock:
        cur.execute("""SELECT m.seller_id, m.item_id, m.price, i.name, i.rarity 
                       FROM market m 
                       JOIN inventory i ON m.item_id = i.id 
                       WHERE m.id=?""", (lot_id,))
        lot = cur.fetchone()
        if not lot:
            return "❌ Лот уже продан или снят"

        seller_id, item_id, price, name, rarity = lot

        if seller_id == buyer_id:
            return "❌ Нельзя купить свой товар"

        buyer = get_user(buyer_id)
        if buyer[1] < price:
            return "❌ Недостаточно монет"

        # Трансфер
        update_user("UPDATE users SET coins = coins - ? WHERE user_id=?", (price, buyer_id))
        update_user("UPDATE users SET coins = coins + ? WHERE user_id=?", (price, seller_id))
        
        cur.execute("UPDATE inventory SET user_id=? WHERE id=?", (buyer_id, item_id))
        cur.execute("DELETE FROM market WHERE id=?", (lot_id,))
        conn.commit()

    return f"🎉 Вы купили {rarity} {name}!"

# ================= UI =================
def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💼 Work", callback_data="work"),
        InlineKeyboardButton("📦 Кейс (180)", callback_data="case"),
        InlineKeyboardButton("🏪 Рынок", callback_data="market"),
        InlineKeyboardButton("🎒 Инвентарь", callback_data="inv"),
        InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        InlineKeyboardButton("🏆 Топ", callback_data="top"),
        InlineKeyboardButton("⚔️ PvP", callback_data="pvp_menu")
    )
    return kb

# ================= HANDLERS =================
@bot.message_handler(commands=['start'])
def start(m):
    get_user(m.from_user.id)
    bot.send_message(m.chat.id,
        "🌃 <b>NEON CITY 6.2</b>\n\n"
        "Самая атмосферная экономическая игра в Telegram.\n"
        "Зарабатывай • Собирай легендарный лут • Торгуй на рынке",
        parse_mode='HTML', reply_markup=main_menu())

@bot.message_handler(commands=['pvp'])
def pvp_cmd(m):
    # (оставил из прошлой версии — можешь расширить позже)
    bot.reply_to(m, "⚔️ /pvp <ID>")

@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    uid = c.from_user.id
    data = c.data

    if data == "work":
        # ... (работа из прошлых версий)
        bot.answer_callback_query(c.id, "💼 +120 монет")  # упрощённо для примера

    elif data == "case":
        text = open_case(uid)   # функция из предыдущей версии
        bot.answer_callback_query(c.id, text, show_alert=True)

    elif data == "profile":
        u = get_user(uid)
        power = get_power(uid)
        vip_text = f"✅ Активен" if is_vip(u) else "❌ Нет"
        bot.send_message(c.message.chat.id,
            f"👤 <b>ПРОФИЛЬ</b>\n\n"
            f"💰 Монеты: {u[1]:,}\n"
            f"📊 Уровень: {u[3]}\n"
            f"⚡ Power: {power}\n"
            f"👑 VIP: {vip_text}", parse_mode='HTML')

    elif data == "inv":
        with db_lock:
            cur.execute("SELECT id, name, rarity, power, equipped FROM inventory WHERE user_id=? ORDER BY power DESC LIMIT 15", (uid,))
            items = cur.fetchall()

        if not items:
            bot.send_message(c.message.chat.id, "🎒 Инвентарь пуст")
            return

        text = "🎒 <b>ИНВЕНТАРЬ</b>\n\n"
        kb = InlineKeyboardMarkup(row_width=1)
        for iid, name, rarity, power, eq in items:
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
            new_eq = 0 if eq else 1
            if new_eq == 1:
                cur.execute("SELECT COUNT(*) FROM inventory WHERE user_id=? AND equipped=1", (uid,))
                if cur.fetchone()[0] >= 5:
                    bot.answer_callback_query(c.id, "❌ Максимум 5 экипированных предметов!", show_alert=True)
                    return
            cur.execute("UPDATE inventory SET equipped=? WHERE id=?", (new_eq, iid))
            conn.commit()
        bot.answer_callback_query(c.id, "✅ Готово")

    elif data.startswith("sell_"):
        iid = int(data[5:])
        awaiting_price[uid] = iid
        bot.send_message(c.message.chat.id, f"💰 Введите цену продажи для этого предмета:")

    elif data == "market":
        with db_lock:
            cur.execute("""SELECT m.id, m.price, i.name, i.rarity, i.power, u.user_id 
                           FROM market m 
                           JOIN inventory i ON m.item_id = i.id 
                           JOIN users u ON m.seller_id = u.user_id 
                           ORDER BY m.time DESC LIMIT 12""")
            lots = cur.fetchall()

        if not lots:
            bot.send_message(c.message.chat.id, "🏪 Рынок пока пуст. Выставляйте свои предметы!")
            return

        text = "🏪 <b>РЫНОК NEON CITY</b>\n\n"
        kb = InlineKeyboardMarkup(row_width=1)
        for lot_id, price, name, rarity, power, seller in lots:
            text += f"{rarity} {name} ⚡{power} — <b>{price}</b> 💰\n"
            kb.add(InlineKeyboardButton(f"Купить за {price}", callback_data=f"buy_{lot_id}"))
        bot.send_message(c.message.chat.id, text, parse_mode='HTML', reply_markup=kb)

    elif data.startswith("buy_"):
        lot_id = int(data[4:])
        result = buy_item(uid, lot_id)
        bot.answer_callback_query(c.id, result, show_alert=True)

# ================= ОБРАБОТКА ЦЕНЫ ДЛЯ ПРОДАЖИ =================
@bot.message_handler(content_types=['text'])
def handle_text(m):
    uid = m.from_user.id
    if uid in awaiting_price:
        try:
            price = int(m.text)
            if price < 50 or price > 100000:
                bot.reply_to(m, "❌ Цена должна быть от 50 до 100000 монет.")
                return
            item_id = awaiting_price.pop(uid)
            result = list_on_market(uid, item_id, price)
            bot.reply_to(m, result)
        except:
            bot.reply_to(m, "❌ Введите только число (цену).")
    else:
        if m.text.startswith('/'):
            pass
        else:
            bot.reply_to(m, "Используй кнопки меню 👇")

# ================= RUN =================
if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    print("🌃 NEON CITY 6.2 с полноценным рынком — ЗАПУЩЕН")
    
    while True:
        try:
            bot.infinity_polling(none_stop=True, interval=0, timeout=30)
        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(5)
