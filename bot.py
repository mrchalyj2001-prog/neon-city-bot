import telebot
import random
import time
import sqlite3
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

# ================= DB =================

conn = sqlite3.connect("game.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    money INTEGER DEFAULT 0,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    career TEXT DEFAULT 'worker',
    attack INTEGER DEFAULT 1,
    defense INTEGER DEFAULT 1,
    inventory TEXT DEFAULT '',
    equipped TEXT DEFAULT '',
    last_work REAL DEFAULT 0
)
""")

conn.commit()

# ================= BOT =================

TOKEN = "8848414252:AAEx3uSwOma9V_VSnnxJVECPBarhKNk6Xv4"
bot = telebot.TeleBot(TOKEN)

# ================= WORLD STATE =================

WORLD = {
    "inflation": 1.0
}

# ================= DATA =================

ITEMS = {
    "knife": {"atk": 5, "def": 0, "price": 50},
    "armor": {"atk": 0, "def": 5, "price": 70},
    "pistol": {"atk": 10, "def": 1, "price": 150},
    "rifle": {"atk": 18, "def": 3, "price": 300},
}

ENEMIES = ["wolf", "bandit", "mutant", "raider"]

QUESTS = ["hunt", "kill", "survive", "raid"]

clans = {}
market = {}

# ================= HELPERS =================

def get(uid):
    cur.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    return cur.fetchone()

def create(uid):
    if not get(uid):
        cur.execute("INSERT INTO users (user_id) VALUES (?)", (uid,))
        conn.commit()

def update(uid, **kwargs):
    keys = ",".join([f"{k}=?" for k in kwargs])
    vals = list(kwargs.values()) + [uid]
    cur.execute(f"UPDATE users SET {keys} WHERE user_id=?", vals)
    conn.commit()

def inv(uid):
    u = get(uid)
    return u[7].split(",") if u and u[7] else []

def equip(uid, item):
    update(uid, equipped=item)

def stats(uid):
    u = get(uid)

    base_a = u[5]
    base_d = u[6]

    items = inv(uid)
    eq = u[8]

    bonus_a = sum(ITEMS[i]["atk"] for i in items if i in ITEMS)
    bonus_d = sum(ITEMS[i]["def"] for i in items if i in ITEMS)

    if eq in ITEMS:
        bonus_a += ITEMS[eq]["atk"]
        bonus_d += ITEMS[eq]["def"]

    return base_a + bonus_a + u[3], base_d + bonus_d + u[3]

# ================= PROFILE =================

def profile(uid):
    u = get(uid)
    a,d = stats(uid)

    return f"""
👤 PROFILE
💰 Money: {u[1]}
⭐ XP: {u[2]}
📊 Level: {u[3]}
💼 Career: {u[4]}

⚔️ ATK: {a}
🛡 DEF: {d}

🎒 Inventory: {inv(uid)}
🧥 Equipped: {u[8]}
"""

# ================= WORK =================

def work(uid):
    u = get(uid)

    if time.time() - u[9] < 10:
        return "⏳ cooldown"

    gain = random.randint(20, 80) + u[3]*5
    xp = u[2] + 20
    lvl = u[3]

    if xp >= lvl * 100:
        xp = 0
        lvl += 1

    update(uid,
        money=u[1] + gain,
        xp=xp,
        level=lvl,
        last_work=time.time()
    )

    return f"💼 +{gain}$ | XP +20 | LVL {lvl}"

# ================= PvE =================

def pve(uid):
    u = get(uid)
    a,d = stats(uid)

    enemy = random.choice(ENEMIES)
    power = random.randint(10, 30 + u[3]*5)

    if a > power:
        reward = random.randint(50, 200)
        drop = random.choice(list(ITEMS.keys()))

        update(uid,
            money=u[1] + reward,
            inventory=u[7] + drop + ","
        )

        return f"⚔️ WIN vs {enemy}\n💰 +{reward}$\n🎁 {drop}"

    return f"💀 LOST vs {enemy}"

# ================= PvP =================

def pvp(uid, target):
    u1 = get(uid)
    u2 = get(target)

    if not u2:
        return "❌ no player"

    p1 = stats(uid)[0]
    p2 = stats(target)[0]

    if p1 > p2:
        win = 100
        update(uid, money=u1[1] + win)
        return f"⚔️ WIN PvP +{win}$"

    loss = 50
    update(uid, money=max(0, u1[1] - loss))
    return f"💀 LOST PvP -{loss}$"

# ================= QUEST =================

def quest(uid):
    u = get(uid)

    reward = random.randint(60, 150)
    xp = random.randint(20, 60)

    update(uid,
        money=u[1] + reward,
        xp=u[2] + xp
    )

    return f"📜 QUEST DONE +{reward}$ +{xp}XP"

# ================= MARKET =================

def shop():
    t = "🛒 SHOP\n"
    for i,v in ITEMS.items():
        t += f"{i} - {v['price']}$\n"
    return t

def buy(uid, item):
    u = get(uid)

    if item not in ITEMS:
        return "❌ no item"

    price = ITEMS[item]["price"]

    if u[1] < price:
        return "❌ no money"

    update(uid,
        money=u[1] - price,
        inventory=u[7] + item + ","
    )

    return f"✅ bought {item}"

# ================= CLANS =================

def create_clan(uid, name):
    clans[name] = {"leader": uid, "members": [uid]}
    return f"🏴 clan {name} created"

def join_clan(uid, name):
    if name not in clans:
        return "❌ no clan"

    clans[name]["members"].append(uid)
    return f"👥 joined {name}"

# ================= BUSINESS =================

def business(uid):
    income = random.randint(20, 100)
    u = get(uid)
    update(uid, money=u[1] + income)
    return f"🏢 +{income}$ passive"

# ================= UI =================

kb = ReplyKeyboardMarkup(resize_keyboard=True)
kb.add(KeyboardButton("PROFILE"))
kb.add(KeyboardButton("WORK"))
kb.add(KeyboardButton("PVE"))
kb.add(KeyboardButton("PVP"))
kb.add(KeyboardButton("QUEST"))
kb.add(KeyboardButton("SHOP"))
kb.add(KeyboardButton("INV"))
kb.add(KeyboardButton("BUSINESS"))

# ================= HANDLERS =================

@bot.message_handler(commands=["start"])
def start(m):
    create(m.from_user.id)
    bot.send_message(m.chat.id, "🔥 FULL RPG WORLD STARTED", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "PROFILE")
def h1(m):
    bot.send_message(m.chat.id, profile(m.from_user.id))

@bot.message_handler(func=lambda m: m.text == "WORK")
def h2(m):
    bot.send_message(m.chat.id, work(m.from_user.id))

@bot.message_handler(func=lambda m: m.text == "PVE")
def h3(m):
    bot.send_message(m.chat.id, pve(m.from_user.id))

@bot.message_handler(func=lambda m: m.text == "PVP")
def h4(m):
    bot.send_message(m.chat.id, pvp(m.from_user.id, m.from_user.id))

@bot.message_handler(func=lambda m: m.text == "QUEST")
def h5(m):
    bot.send_message(m.chat.id, quest(m.from_user.id))

@bot.message_handler(func=lambda m: m.text == "SHOP")
def h6(m):
    bot.send_message(m.chat.id, shop())

@bot.message_handler(func=lambda m: m.text.startswith("BUY"))
def h7(m):
    bot.send_message(m.chat.id, buy(m.from_user.id, m.text.split()[-1]))

@bot.message_handler(func=lambda m: m.text == "INV")
def h8(m):
    bot.send_message(m.chat.id, str(inv(m.from_user.id)))

@bot.message_handler(func=lambda m: m.text == "BUSINESS")
def h9(m):
    bot.send_message(m.chat.id, business(m.from_user.id))

# ================= RUN =================

bot.infinity_polling()
