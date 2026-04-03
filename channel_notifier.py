import logging
import traceback
from telegram import Bot
from config import NOTIFICATION_CHANNEL_ID

# ==================== ДЕБАГ-РЕЖИМ ====================
from debug_utils import debug_print, log_call, log_user_data, DEBUG_MODE

logger = logging.getLogger(__name__)


@log_call
async def send_to_channel(bot: Bot, message: str):
    """Отправка сообщения в канал"""
    debug_print(f"🔥 channel_notifier: send_to_channel: ВЫЗВАНА")
    debug_print(f"📥 Аргументы: bot={bot}, message={message[:100] if message else 'None'}...")

    if DEBUG_MODE:
        debug_print(f"🔹 channel_notifier: send_to_channel вызвана, message={message[:100]}...")

    debug_print(f"🔥 channel_notifier: send_to_channel: message={message[:100] if message else 'None'}...")
    debug_print(f"🔥 channel_notifier: send_to_channel: NOTIFICATION_CHANNEL_ID={NOTIFICATION_CHANNEL_ID}")

    try:
        debug_print(f"🔥 channel_notifier: send_to_channel: отправка в канал...")
        await bot.send_message(
            chat_id=NOTIFICATION_CHANNEL_ID,
            text=message,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        logger.info("Уведомление отправлено в канал")
        if DEBUG_MODE:
            debug_print("✅ send_to_channel: сообщение отправлено")
        debug_print(f"🔥 channel_notifier: send_to_channel: успешно отправлено")
        debug_print(f"🔥 channel_notifier: send_to_channel: ВОЗВРАТ True")
        return True
    except Exception as e:
        logger.error("Ошибка отправки в канал: %s", e)
        if DEBUG_MODE:
            debug_print(f"❌ send_to_channel: ошибка - {e}")
        debug_print(f"🔥 channel_notifier: ОШИБКА: {e}")
        debug_print(f"🔥 channel_notifier: traceback: {traceback.format_exc()}")
        debug_print(f"🔥 channel_notifier: send_to_channel: ошибка: {e}")
        debug_print(f"🔥 channel_notifier: send_to_channel: ВОЗВРАТ False")
        return False


@log_call
async def notify_exercise_complete(bot, user_name, exercise_name, result, is_record=False):
    """Уведомление о выполнении упражнения"""
    debug_print(f"🔥 channel_notifier: notify_exercise_complete: ВЫЗВАНА")
    debug_print(
        f"📥 Аргументы: bot={bot}, user_name={user_name}, exercise_name={exercise_name}, result={result}, is_record={is_record}")

    if DEBUG_MODE:
        debug_print(
            f"🔹 channel_notifier: notify_exercise_complete вызвана с user_name={user_name}, exercise_name={exercise_name}, result={result}, is_record={is_record}")

    debug_print(f"🔥 channel_notifier: notify_exercise_complete: user_name={user_name}")
    debug_print(f"🔥 channel_notifier: notify_exercise_complete: exercise_name={exercise_name}")
    debug_print(f"🔥 channel_notifier: notify_exercise_complete: result={result}")
    debug_print(f"🔥 channel_notifier: notify_exercise_complete: is_record={is_record}")
    debug_print(f"🔥 channel_notifier: notify_exercise_complete: формирование сообщения")

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

    debug_print(f"🔥 channel_notifier: notify_exercise_complete: сообщение: {message[:100] if message else 'None'}...")
    debug_print(f"🔥 channel_notifier: notify_exercise_complete: вызов send_to_channel")

    result_send = await send_to_channel(bot, message)

    debug_print(f"🔥 channel_notifier: notify_exercise_complete: ВОЗВРАТ {result_send}")
    return result_send


@log_call
async def notify_challenge_update(bot, user_name, challenge_name, action, message_text):
    """Уведомление о действии в челлендже"""
    debug_print(f"🔥 channel_notifier: notify_challenge_update: ВЫЗВАНА")
    debug_print(
        f"📥 Аргументы: bot={bot}, user_name={user_name}, challenge_name={challenge_name}, action={action}, message_text={message_text[:100] if message_text else 'None'}...")

    if DEBUG_MODE:
        debug_print(
            f"🔹 channel_notifier: notify_challenge_update вызвана с user_name={user_name}, challenge_name={challenge_name}, action={action}, message_text={message_text}")

    debug_print(f"🔥 channel_notifier: notify_challenge_update: user_name={user_name}")
    debug_print(f"🔥 channel_notifier: notify_challenge_update: challenge_name={challenge_name}")
    debug_print(f"🔥 channel_notifier: notify_challenge_update: action={action}")
    debug_print(
        f"🔥 channel_notifier: notify_challenge_update: message_text={message_text[:100] if message_text else 'None'}...")
    debug_print(f"🔥 channel_notifier: notify_challenge_update: формирование сообщения")

    emoji = "🏆" if action == "started" else "📈"

    text = f"{emoji} *Челлендж* {emoji}\n\n"
    text += f"👤 *{user_name}*\n"
    text += f"🎯 *{challenge_name}*\n"
    text += f"📌 {message_text}\n\n"
    text += "💬 *Поддержи участника в комментариях!* 👇"

    debug_print(f"🔥 channel_notifier: notify_challenge_update: вызов send_to_channel")

    result_send = await send_to_channel(bot, text)

    debug_print(f"🔥 channel_notifier: notify_challenge_update: ВОЗВРАТ {result_send}")
    return result_send


@log_call
async def notify_challenge_complete(bot, user_name, challenge_name, days, bonus):
    """Уведомление о завершении челленджа (days может быть None)."""
    debug_print(f"🔥 channel_notifier: notify_challenge_complete: ВЫЗВАНА")
    debug_print(
        f"📥 Аргументы: bot={bot}, user_name={user_name}, challenge_name={challenge_name}, days={days}, bonus={bonus}")

    if DEBUG_MODE:
        debug_print(
            f"🔹 channel_notifier: notify_challenge_complete вызвана с user_name={user_name}, challenge_name={challenge_name}, days={days}, bonus={bonus}")

    debug_print(f"🔥 channel_notifier: notify_challenge_complete: user_name={user_name}")
    debug_print(f"🔥 channel_notifier: notify_challenge_complete: challenge_name={challenge_name}")
    debug_print(f"🔥 channel_notifier: notify_challenge_complete: days={days}")
    debug_print(f"🔥 channel_notifier: notify_challenge_complete: bonus={bonus}")
    debug_print(f"🔥 channel_notifier: notify_challenge_complete: формирование сообщения")

    message = "🏆🏆🏆 *ЧЕЛЛЕНДЖ ВЫПОЛНЕН!* 🏆🏆🏆\n\n"
    message += f"👤 *{user_name}*\n"
    message += f"🎯 *{challenge_name}*\n"
    message += "✅ Выполнено!\n"
    if days is not None:
        message += f"📅 Дней: {days}\n"
    message += f"🎁 Получено {bonus} бонусных баллов!\n\n"
    message += "🎉 Грандиозное достижение! Поздравляем!\n"
    message += "💬 *Оставьте свои поздравления в комментариях*"

    debug_print(f"🔥 channel_notifier: notify_challenge_complete: сообщение: {message[:100] if message else 'None'}...")
    debug_print(f"🔥 channel_notifier: notify_challenge_complete: вызов send_to_channel")

    result_send = await send_to_channel(bot, message)

    debug_print(f"🔥 channel_notifier: notify_challenge_complete: ВОЗВРАТ {result_send}")
    return result_send