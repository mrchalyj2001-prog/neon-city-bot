from database import cursor, conn

# пример предметов (пока без БД таблицы предметов — упрощённая версия)
ITEMS = {
    "knife": {"attack": 5, "defense": 0},
    "armor": {"attack": 0, "defense": 5},
    "pistol": {"attack": 10, "defense": 0},
}


def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    return cursor.fetchone()


def add_item(user_id, item_name):
    # инвентарь пока храним в виде строки (упрощение)
    user = get_user(user_id)
    if not user:
        return

    cursor.execute("SELECT inventory FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    inventory = row[0] if row and row[0] else ""

    inventory += item_name + ","

    cursor.execute("""
        UPDATE users
        SET inventory = ?
        WHERE user_id = ?
    """, (inventory, user_id))

    conn.commit()


def get_inventory(user_id):
    cursor.execute("SELECT inventory FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if not row or not row[0]:
        return []

    return row[0].split(",")[:-1]


def get_stats_from_inventory(user_id):
    items = get_inventory(user_id)

    attack = 0
    defense = 0

    for item in items:
        if item in ITEMS:
            attack += ITEMS[item]["attack"]
            defense += ITEMS[item]["defense"]

    return attack, defense
