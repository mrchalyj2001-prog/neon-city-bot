import time
import random
from database import cursor, conn

WORK_COOLDOWN = 30


# получить пользователя
def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    return cursor.fetchone()


# работа
def work(user_id):
    user = get_user(user_id)
    if not user:
        return "User not found"

    money = user[1]
    xp = user[2]
    level = user[3]
    last_work = user[6]

    # cooldown
    if time.time() - last_work < WORK_COOLDOWN:
        return "⏳ Подожди перед следующей работой"

    # доход
    base_money = random.randint(20, 80)
    reward = base_money + (level * 5)

    # XP
    xp_gain = random.randint(5, 15)

    xp += xp_gain
    money += reward

    # level up
    if xp >= level * 100:
        xp = 0
        level += 1

    # save
    cursor.execute("""
        UPDATE users
        SET money = ?, xp = ?, level = ?, last_work = ?
        WHERE user_id = ?
    """, (money, xp, level, time.time(), user_id))

    conn.commit()

    return f"💼 Работа выполнена!\n💰 +{reward} монет\n⭐ +{xp_gain} XP\n📊 Level: {level}"
