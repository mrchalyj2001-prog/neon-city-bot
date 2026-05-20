import telebot
import sqlite3
import random
import time
import os
import threading

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# =========================================================
# NEON CITY FULL MMORPG BUILD
# =========================================================

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise Exception("BOT_TOKEN not found")

bot = telebot.TeleBot(TOKEN)

# =========================================================
# DATABASE
# =========================================================

conn = sqlite3.connect("game.db", check_same_thread=False)
cur = conn.cursor()
lock = threading.Lock()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,

    coins INTEGER DEFAULT 100,
    bank INTEGER DEFAULT 0,

    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,

    job TEXT DEFAULT 'Дворник',
    job_level INTEGER DEFAULT 1,

    strength INTEGER DEFAULT 1,
    defense INTEGER DEFAULT 1,
    luck INTEGER DEFAULT 1,

    house_level INTEGER DEFAULT 0,
    business_level INTEGER DEFAULT 0,

    crime_rating INTEGER DEFAULT 0,
    jail_until INTEGER DEFAULT 0,

    last_work INTEGER DEFAULT 0,
    last_daily INTEGER DEFAULT 0,
    last_crime INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER,

    item_name TEXT,
    item_type TEXT,
    rarity TEXT,

    power INTEGER DEFAULT 1,

    equipped INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS market (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    seller_id INTEGER,

    item_name TEXT,
    item_type TEXT,
    rarity TEXT,
    power INTEGER,

    price INTEGER
)
""")

conn.commit()

# =========================================================
# CORE
# =========================================================

def user(uid):
    with lock:
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

def update(q, p=()):
    with lock:
        cur.execute(q, p)
        conn.commit()

# =========================================================
# STATS
# =========================================================

RARITY_BONUS = {
    "common": 1,
    "rare": 3,
    "epic": 6,
    "legendary": 10
}

def get_stats(uid):
    u = user(uid)

    with lock:
        cur.execute("""
            SELECT item_type, power, rarity
            FROM inventory
            WHERE user_id=? AND equipped=1
        """, (uid,))

        items = cur.fetchall()

    atk = 0
    df = 0

    for t, p, r in items:
        bonus = RARITY_BONUS.get(r, 1)

        if t == "weapon":
            atk += p + bonus

        elif t == "armor":
            df += p + bonus

    atk += u[7]
    df += u[8]

    return atk, df, u[9]

# =========================================================
# XP / LEVEL
# =========================================================

def add_xp(uid, amount):
    u = user(uid)

    xp = u[3] + amount
    lvl = u[4]

    need = lvl * 100

    if xp >= need:
        xp -= need
        lvl += 1

        update("""
            UPDATE users
            SET level=?,
                strength=strength+1,
                defense=defense+1,
                luck=luck+1
            WHERE user_id=?
        """, (lvl, uid))

    update("""
        UPDATE users
        SET xp=?
        WHERE user_id=?
    """, (xp, uid))

# =========================================================
# JOBS
# =========================================================

JOBS = {
    "Дворник": 15,
    "Курьер": 35,
    "Таксист": 60,
    "Хакер": 120,
    "Бизнесмен": 250
}

JOB_ORDER = list(JOBS.keys())

def work(uid):
    u = user(uid)

    now = int(time.time())

    if now - u[14] < 3:
        return "⏳ Подожди"

    atk, df, luck = get_stats(uid)

    base = JOBS[u[5]]

    reward = (
        base +
        (u[6] * 8) +
        atk +
        random.randint(1, 20)
    )

    reward += (u[11] * 30)
    reward += (u[12] * 60)

    update("""
        UPDATE users
        SET coins = coins + ?,
            last_work = ?
        WHERE user_id=?
    """, (reward, now, uid))

    add_xp(uid, 15)

    return f"💼 +{reward} монет"

def upgrade_job(uid):
    u = user(uid)

    current = u[5]

    idx = JOB_ORDER.index(current)

    if idx >= len(JOB_ORDER) - 1:
        return "🏆 Максимальная работа"

    next_job = JOB_ORDER[idx + 1]

    cost = (idx + 1) * 1500

    if u[1] < cost:
        return f"❌ Нужно {cost}"

    update("""
        UPDATE users
        SET coins = coins - ?,
            job = ?
        WHERE user_id=?
    """, (cost, next_job, uid))

    return f"⬆ Новая работа: {next_job}"

# =========================================================
# DAILY
# =========================================================

def daily(uid):
    u = user(uid)

    now = int(time.time())

    if now - u[15] < 86400:
        return "🎁 Уже забрал"

    reward = random.randint(300, 1000)

    update("""
        UPDATE users
        SET coins = coins + ?,
            last_daily = ?
        WHERE user_id=?
    """, (reward, now, uid))

    return f"🎁 +{reward}"

# =========================================================
# CASE SYSTEM
# =========================================================

WEAPONS = [
    "Нож",
    "Бита",
    "Катана",
    "Пистолет",
    "Лазер"
]

ARMORS = [
    "Куртка",
    "Бронежилет",
    "Киберброня"
]

RARITIES = ["common", "rare", "epic", "legendary"]

def open_case(uid):
    u = user(uid)

    roll = random.random()

    if roll < 0.50:
        coins = random.randint(50, 300)

        update("""
            UPDATE users
            SET coins = coins + ?
            WHERE user_id=?
        """, (coins, uid))

        return f"💰 +{coins}"

    elif roll < 0.85:

        rarity = random.choices(
            RARITIES,
            weights=[60, 25, 10, 5]
        )[0]

        item_type = random.choice(["weapon", "armor"])

        if item_type == "weapon":
            name = random.choice(WEAPONS)
        else:
            name = random.choice(ARMORS)

        power = random.randint(1, 12)

        with lock:
            cur.execute("""
                INSERT INTO inventory (
                    user_id,
                    item_name,
                    item_type,
                    rarity,
                    power
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                uid,
                name,
                item_type,
                rarity,
                power
            ))

            conn.commit()

        return f"🎒 {rarity.upper()} {name} +{power}"

    else:
        loss = random.randint(50, 200)

        update("""
            UPDATE users
            SET coins = MAX(0, coins - ?)
            WHERE user_id=?
        """, (loss, uid))

        return f"💀 Ты потерял {loss}"

# =========================================================
# INVENTORY
# =========================================================

def inventory(uid):
    with lock:
        cur.execute("""
            SELECT
                id,
                item_name,
                item_type,
                rarity,
                power,
                equipped
            FROM inventory
            WHERE user_id=?
        """, (uid,))

        items = cur.fetchall()

    if not items:
        return "🎒 Инвентарь пуст"

    txt = "🎒 ИНВЕНТАРЬ\n\n"

    for i in items:
        eq = "🟢" if i[5] else "⚪"

        txt += (
            f"{eq} ID:{i[0]} | "
            f"{i[1]} | "
            f"{i[3]} | "
            f"+{i[4]}\n"
        )

    return txt

# =========================================================
# EQUIP
# =========================================================

def equip(uid, item_id):
    with lock:
        cur.execute("""
            SELECT item_type
            FROM inventory
            WHERE id=? AND user_id=?
        """, (item_id, uid))

        item = cur.fetchone()

        if not item:
            return "❌ Предмет не найден"

        t = item[0]

        cur.execute("""
            UPDATE inventory
            SET equipped=0
            WHERE user_id=? AND item_type=?
        """, (uid, t))

        cur.execute("""
            UPDATE inventory
            SET equipped=1
            WHERE id=?
        """, (item_id,))

        conn.commit()

    return "⚔ Экипировано"

# =========================================================
# HOUSES / BUSINESS
# =========================================================

def buy_house(uid):
    u = user(uid)

    cost = (u[11] + 1) * 2500

    if u[1] < cost:
        return f"❌ Нужно {cost}"

    update("""
        UPDATE users
        SET coins = coins - ?,
            house_level = house_level + 1
        WHERE user_id=?
    """, (cost, uid))

    return "🏠 Недвижимость улучшена"

def buy_business(uid):
    u = user(uid)

    cost = (u[12] + 1) * 7000

    if u[1] < cost:
        return f"❌ Нужно {cost}"

    update("""
        UPDATE users
        SET coins = coins - ?,
            business_level = business_level + 1
        WHERE user_id=?
    """, (cost, uid))

    return "🏢 Бизнес улучшен"

# =========================================================
# CRIME
# =========================================================

def crime(uid):
    u = user(uid)

    now = int(time.time())

    if now - u[16] < 20:
        return "🚔 Слишком опасно"

    if u[13] > now:
        return "⛓ Ты в тюрьме"

    success = random.randint(1, 100)

    if success <= 65:

        reward = random.randint(200, 800)

        update("""
            UPDATE users
            SET coins = coins + ?,
                crime_rating = crime_rating + 1,
                last_crime = ?
            WHERE user_id=?
        """, (reward, now, uid))

        return f"🔫 Успешно +{reward}"

    else:

        jail = now + 60

        update("""
            UPDATE users
            SET jail_until=?,
                last_crime=?
            WHERE user_id=?
        """, (jail, now, uid))

        return "🚔 Тебя посадили на 60 сек"

# =========================================================
# PVP
# =========================================================

def pvp(a, b):
    if a == b:
        return "❌ Нельзя"

    ua = user(a)
    ub = user(b)

    if not ub:
        return "❌ Игрок не найден"

    sa, da, la = get_stats(a)
    sb, db, lb = get_stats(b)

    pa = sa + da + random.randint(0, la)
    pb = sb + db + random.randint(0, lb)

    if pa > pb:

        steal = max(50, int(ub[1] * 0.10))

        update("""
            UPDATE users
            SET coins = coins + ?
            WHERE user_id=?
        """, (steal, a))

        update("""
            UPDATE users
            SET coins = MAX(0, coins - ?)
            WHERE user_id=?
        """, (steal, b))

        return f"⚔ Победа +{steal}"

    return "🛡 Поражение"

# =========================================================
# MARKET
# =========================================================

def market_list():
    with lock:
        cur.execute("""
            SELECT
                id,
                item_name,
                rarity,
                power,
                price
            FROM market
            ORDER BY price ASC
            LIMIT 15
        """)

        items = cur.fetchall()

    if not items:
        return "🏪 Рынок пуст"

    txt = "🏪 РЫНОК\n\n"

    for i in items:
        txt += (
            f"ID:{i[0]} | "
            f"{i[1]} | "
            f"{i[2]} | "
            f"+{i[3]} | "
            f"{i[4]}💰\n"
        )

    return txt

# =========================================================
# PROFILE
# =========================================================

def profile(uid):
    u = user(uid)

    atk, df, luck = get_stats(uid)

    return (
        f"👤 ПРОФИЛЬ\n\n"

        f"💰 Монеты: {u[1]}\n"
        f"🏦 Банк: {u[2]}\n\n"

        f"⭐ XP: {u[3]}\n"
        f"📊 LVL: {u[4]}\n\n"

        f"💼 Работа: {u[5]}\n\n"

        f"💪 Сила: {atk}\n"
        f"🛡 Защита: {df}\n"
        f"🍀 Удача: {luck}\n\n"

        f"🏠 Дом: {u[11]}\n"
        f"🏢 Бизнес: {u[12]}\n\n"

        f"🚔 Crime: {u[13]}"
    )

# =========================================================
# MENU
# =========================================================

def menu():
    kb = InlineKeyboardMarkup(row_width=2)

    kb.add(
        InlineKeyboardButton("💼 Работа", callback_data="work"),
        InlineKeyboardButton("⬆ Карьера", callback_data="job")
    )

    kb.add(
        InlineKeyboardButton("🎁 Daily", callback_data="daily"),
        InlineKeyboardButton("📦 Кейсы", callback_data="case")
    )

    kb.add(
        InlineKeyboardButton("🔫 Криминал", callback_data="crime"),
        InlineKeyboardButton("⚔ PvP", callback_data="pvp")
    )

    kb.add(
        InlineKeyboardButton("🎒 Инвентарь", callback_data="inv"),
        InlineKeyboardButton("🏪 Рынок", callback_data="market")
    )

    kb.add(
        InlineKeyboardButton("🏠 Дом", callback_data="house"),
        InlineKeyboardButton("🏢 Бизнес", callback_data="biz")
    )

    kb.add(
        InlineKeyboardButton("👤 Профиль", callback_data="profile")
    )

    return kb

# =========================================================
# COMMANDS
# =========================================================

@bot.message_handler(commands=['start'])
def start(m):
    user(m.from_user.id)

    bot.send_message(
        m.chat.id,
        "🌆 NEON CITY MMORPG",
        reply_markup=menu()
    )

@bot.message_handler(commands=['inv'])
def inv_cmd(m):
    bot.send_message(
        m.chat.id,
        inventory(m.from_user.id)
    )

@bot.message_handler(commands=['equip'])
def equip_cmd(m):
    try:
        item_id = int(m.text.split()[1])

        bot.reply_to(
            m,
            equip(m.from_user.id, item_id)
        )

    except:
        bot.reply_to(m, "Используй: /equip ID")

@bot.message_handler(commands=['pvp'])
def pvp_cmd(m):
    try:
        target = int(m.text.split()[1])

        bot.reply_to(
            m,
            pvp(m.from_user.id, target)
        )

    except:
        bot.reply_to(m, "Используй: /pvp ID")

# =========================================================
# CALLBACKS
# =========================================================

@bot.callback_query_handler(func=lambda c: True)
def cb(c):
    uid = c.from_user.id

    if c.data == "work":
        bot.answer_callback_query(c.id, work(uid))

    elif c.data == "job":
        bot.answer_callback_query(c.id, upgrade_job(uid))

    elif c.data == "daily":
        bot.answer_callback_query(c.id, daily(uid))

    elif c.data == "case":
        bot.answer_callback_query(c.id, open_case(uid))

    elif c.data == "crime":
        bot.answer_callback_query(c.id, crime(uid))

    elif c.data == "inv":
        bot.send_message(
            c.message.chat.id,
            inventory(uid)
        )

    elif c.data == "market":
        bot.send_message(
            c.message.chat.id,
            market_list()
        )

    elif c.data == "house":
        bot.answer_callback_query(
            c.id,
            buy_house(uid)
        )

    elif c.data == "biz":
        bot.answer_callback_query(
            c.id,
            buy_business(uid)
        )

    elif c.data == "profile":
        bot.send_message(
            c.message.chat.id,
            profile(uid)
        )

    elif c.data == "pvp":
        bot.send_message(
            c.message.chat.id,
            "⚔ Используй:\n/pvp ID"
        )

# =========================================================
# RUN
# =========================================================

print("NEON CITY MMORPG RUNNING")

while True:
    try:
        bot.infinity_polling(
            timeout=20,
            long_polling_timeout=20
        )

    except Exception as e:
        print(f"ERROR: {e}")
        time.sleep(5)
