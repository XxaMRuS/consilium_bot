import logging
import sqlite3
from database import DB_NAME, get_setting

logger = logging.getLogger(__name__)

async def send_record_notification(bot, user_id, exercise_id, new_result, metric_type):
    """Отправляет в канал уведомление о новом рекорде."""
    channel_id = get_setting("public_channel")
    if not channel_id:
        return
    try:
        channel_id_int = int(channel_id)
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT first_name, username FROM users WHERE user_id = ?", (user_id,))
        user_row = cur.fetchone()
        cur.execute("SELECT name FROM exercises WHERE id = ?", (exercise_id,))
        ex_row = cur.fetchone()
        conn.close()

        if not user_row:
            user_name = f"Пользователь {user_id}"
        else:
            first_name = user_row[0] or ""
            username = user_row[1]
            user_name = first_name if first_name else (username if username else f"User{user_id}")

        ex_name = ex_row[0] if ex_row else f"упражнение {exercise_id}"

        if metric_type == 'reps':
            result_text = f"{new_result} повторений"
        else:
            result_text = f"{new_result}"

        message = f"🏆 *Новый рекорд!*\nПользователь {user_name} установил рекорд в упражнении «{ex_name}»: {result_text}!"

        await bot.send_message(chat_id=channel_id_int, text=message, parse_mode='Markdown')
        logger.info(f"Уведомление о рекорде отправлено в канал {channel_id_int}")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о рекорде: {e}")