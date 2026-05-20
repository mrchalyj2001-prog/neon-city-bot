import random
from database import cursor
from systems.inventory import get_stats_from_inventory, get_equipped


def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    return cursor.fetchone()


def pve_fight(user_id):
    user = get_user(user_id)
    if not user:
        return "❌ User not found"

    level = user[3]
    base_attack = user[4]
    base_defense = user[5]

    # инвентарь
    inv_attack, inv_defense = get_stats_from_inventory(user_id)

    # экипировка
    equipped = get_equipped(user_id)

    equip_attack = 0
    equip_defense = 0

    if equipped:
        items = {
            "knife": {"attack": 5, "defense": 0},
            "armor": {"attack": 0, "defense": 5},
            "pistol": {"attack": 10, "defense": 0},
        }

        if equipped in items:
            equip_attack = items[equipped]["attack"]
            equip_defense = items[equipped]["defense"]

    # итоговые статы
    total_attack = base_attack + inv_attack + equip_attack + level
    total_defense = base_defense + inv_defense + equip_defense + level

    enemy_power = random.randint(10, 25 + level * 3)

    player_power = total_attack + random.randint(0, 10)
    enemy_power_total = enemy_power + random.randint(0, 10)

    if player_power >= enemy_power_total:
        reward = random.randint(60, 160) + level * 10

        cursor.execute("""
            UPDATE users
            SET money = money + ?, xp = xp + 10
            WHERE user_id = ?
        """, (reward, user_id))

        return f"🏆 ПОБЕДА!\n💰 +{reward} монет\n⚔️ ты: {player_power} vs враг: {enemy_power_total}"

    else:
        loss = random.randint(10, 50)

        cursor.execute("""
            UPDATE users
            SET money = money - ?
            WHERE user_id = ?
        """, (loss, user_id))

        return f"💀 ПОРАЖЕНИЕ!\n- {loss} монет\n⚔️ ты: {player_power} vs враг: {enemy_power_total}"
