import random
from database import cursor
from systems.inventory import get_stats_from_inventory


def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    return cursor.fetchone()


def pve_fight(user_id):
    user = get_user(user_id)
    if not user:
        return "User not found"

    level = user[3]
    attack_base = user[4]
    defense_base = user[5]

    # статы от экипировки
    gear_attack, gear_defense = get_stats_from_inventory(user_id)

    total_attack = attack_base + gear_attack + level
    total_defense = defense_base + gear_defense + level

    enemy_power = random.randint(5, 20 + level * 3)

    player_power = total_attack + random.randint(0, 10)
    enemy_power_total = enemy_power + random.randint(0, 10)

    if player_power >= enemy_power_total:
        reward = random.randint(50, 150) + level * 10

        cursor.execute("""
            UPDATE users
            SET money = money + ?, xp = xp + 10
            WHERE user_id = ?
        """, (reward, user_id))

        return f"🏆 Победа!\n💰 +{reward} монет\n⚔️ враг: {enemy_power_total} vs ты: {player_power}"

    else:
        penalty = random.randint(10, 40)

        cursor.execute("""
            UPDATE users
            SET money = money - ?
            WHERE user_id = ?
        """, (penalty, user_id))

        return f"💀 Поражение!\n- {penalty} монет\n⚔️ враг был сильнее: {enemy_power_total}"
