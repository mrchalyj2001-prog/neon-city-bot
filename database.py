import sqlite3

conn = sqlite3.connect("game.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,

    money INTEGER DEFAULT 0,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,

    attack INTEGER DEFAULT 1,
    defense INTEGER DEFAULT 1,

    inventory TEXT DEFAULT "",
    equipped TEXT DEFAULT "",

    last_work REAL DEFAULT 0,
    last_daily REAL DEFAULT 0
)
""")

conn.commit()


def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    return cursor.fetchone()


def create_user(user_id):
    if not get_user(user_id):
        cursor.execute(
            "INSERT INTO users (user_id) VALUES (?)",
            (user_id,)
        )
        conn.commit()


def update_user(user_id, field, value):
    cursor.execute(f"""
        UPDATE users SET {field} = ? WHERE user_id = ?
    """, (value, user_id))
    conn.commit()
