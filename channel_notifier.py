import logging
from telegram import Bot
from config import NOTIFICATION_CHANNEL_ID

logger = logging.getLogger(__name__)


async def send_to_channel(bot: Bot, message: str):
    """Отправка сообщения в канал"""
    try:
        await bot.send_message(
            chat_id=NOTIFICATION_CHANNEL_ID,
            text=message,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        logger.info("Уведомление отправлено в канал")
        return True
    except Exception as e:
        logger.error("Ошибка отправки в канал: %s", e)
        return False


async def notify_exercise_complete(bot, user_name, exercise_name, result, is_record=False):
    """Уведомление о выполнении упражнения"""
    if is_record:
        message = "🎉 *РЕКОРД!* 🎉\n\n"
        message += f"👤 *{user_name}*\n"
        message += f"💪 *{exercise_name}*\n"
        message += f"📊 *НОВЫЙ РЕКОРД:* {result}\n\n"
        message += "🔥 Отличный результат! Поздравляем!\n"
        message += "💬 *Оставьте комментарий* (ответьте на это сообщение)"
    else:
        message = "✅ *Выполнено упражнение*\n\n"
        message += f"👤 *{user_name}*\n"
        message += f"💪 *{exercise_name}*\n"
        message += f"📊 *Результат:* {result}\n\n"
        message += "Продолжай в том же духе! 💪\n"
        message += "💬 *Обсудить:* ответьте на это сообщение"

    await send_to_channel(bot, message)


async def notify_challenge_update(bot, user_name, challenge_name, action, message_text):
    """Уведомление о действии в челлендже"""
    emoji = "🏆" if action == "started" else "📈"

    text = f"{emoji} *Челлендж* {emoji}\n\n"
    text += f"👤 *{user_name}*\n"
    text += f"🎯 *{challenge_name}*\n"
    text += f"📌 {message_text}\n\n"
    text += "💬 *Поддержи участника в комментариях!* 👇"

    await send_to_channel(bot, text)


async def notify_challenge_complete(bot, user_name, challenge_name, days, bonus):
    """Уведомление о завершении челленджа (days может быть None)."""
    message = "🏆🏆🏆 *ЧЕЛЛЕНДЖ ВЫПОЛНЕН!* 🏆🏆🏆\n\n"
    message += f"👤 *{user_name}*\n"
    message += f"🎯 *{challenge_name}*\n"
    message += "✅ Выполнено!\n"
    if days is not None:
        message += f"📅 Дней: {days}\n"
    message += f"🎁 Получено {bonus} бонусных баллов!\n\n"
    message += "🎉 Грандиозное достижение! Поздравляем!\n"
    message += "💬 *Оставьте свои поздравления в комментариях*"

    await send_to_channel(bot, message)
