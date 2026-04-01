import logging
import re
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import ContextTypes
from database_backup import DB_NAME, get_complex_by_id, get_exercise_by_id, get_challenge_by_id, add_workout, \
    get_user_level

logger = logging.getLogger(__name__)

AWAIT_SUBMIT_RESULT = 60
AWAIT_SUBMIT_VIDEO = 61
AWAIT_SUBMIT_COMMENT = 62
DEBUG = True


async def submit_complex_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Сдать результат' для комплекса"""
    logger.info("submit_complex_callback вызвана")
    query = update.callback_query
    await query.answer()

    try:
        complex_id = int(query.data.split('_')[2])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Некорректные данные кнопки.")
        return
    context.user_data['submit_entity_type'] = 'complex'
    context.user_data['submit_entity_id'] = complex_id
    context.user_data['submit_channel_post_id'] = query.message.message_id
    context.user_data['submit_channel_id'] = query.message.chat_id
    context.user_data['conversation_state'] = AWAIT_SUBMIT_RESULT

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_submit")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await update.effective_user.send_message(
            "📊 Введите результат:\n- повторения: просто число (например, 10)\n- время: в формате ММ:СС (например, 05:30)",
            reply_markup=reply_markup
        )
    except TelegramError as e:
        logger.error("Не удалось отправить запрос результата: %s", e)
        await query.edit_message_text("❌ Не удалось начать ввод. Напишите боту в личку и попробуйте снова.")
        return
    logger.info(f"Комплекс {complex_id}: запрос результата отправлен")


async def submit_exercise_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Сдать результат' для упражнения"""
    logger.info("submit_exercise_callback вызвана")
    query = update.callback_query
    await query.answer()

    try:
        exercise_id = int(query.data.split('_')[2])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Некорректные данные кнопки.")
        return

    context.user_data['submit_entity_type'] = 'exercise'
    context.user_data['submit_entity_id'] = exercise_id
    context.user_data['submit_channel_post_id'] = query.message.message_id
    context.user_data['submit_channel_id'] = query.message.chat_id
    context.user_data['conversation_state'] = AWAIT_SUBMIT_RESULT

    exercise = get_exercise_by_id(exercise_id)
    exercise_name = exercise[1] if exercise else "упражнения"
    metric = exercise[3] if exercise else None

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_submit")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        if metric == 'reps':
            await query.edit_message_text(
                f"📊 Введите количество повторений для *{exercise_name}*:",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text(
                f"⏱️ Введите время в формате ММ:СС для *{exercise_name}*:",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
    except TelegramError as e:
        logger.error("submit_exercise_callback edit_message: %s", e)
        await query.edit_message_text("❌ Ошибка отображения. Попробуйте снова.")
        return
    logger.info(f"Упражнение {exercise_id}: запрос результата отправлен")


async def submit_challenge_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Сдать результат' для челленджа"""
    logger.info("submit_challenge_callback вызвана")
    query = update.callback_query
    await query.answer()

    try:
        challenge_id = int(query.data.split('_')[2])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Некорректные данные кнопки.")
        return
    context.user_data['submit_entity_type'] = 'challenge'
    context.user_data['submit_entity_id'] = challenge_id
    context.user_data['submit_channel_post_id'] = query.message.message_id
    context.user_data['submit_channel_id'] = query.message.chat_id
    context.user_data['conversation_state'] = AWAIT_SUBMIT_RESULT

    challenge = get_challenge_by_id(challenge_id)
    challenge_name = challenge[1] if challenge else "челленджа"
    metric = challenge[5] if challenge else None

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_submit")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        if metric == 'reps':
            await query.edit_message_text(
                f"📊 Введите количество повторений для челленджа *{challenge_name}*:",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text(
                f"⏱️ Введите время в формате ММ:СС для челленджа *{challenge_name}*:",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
    except TelegramError as e:
        logger.error("submit_challenge_callback edit_message: %s", e)
        await query.edit_message_text("❌ Ошибка отображения. Попробуйте снова.")
        return
    logger.info(f"Челлендж {challenge_id}: запрос результата отправлен")


async def submit_result_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка введённого результата"""
    logger.info(f"submit_result_input: {update.message.text}")

    if context.user_data.get('conversation_state') != AWAIT_SUBMIT_RESULT:
        logger.warning("submit_result_input: состояние не AWAIT_SUBMIT_RESULT")
        return

    user_input = update.message.text.strip()
    entity_type = context.user_data.get('submit_entity_type')
    entity_id = context.user_data.get('submit_entity_id')

    # Получаем тип метрики
    if entity_type == 'complex':
        data = get_complex_by_id(entity_id)
        metric_type = data[3] if data else None
        name = data[1] if data else "комплекс"
    elif entity_type == 'exercise':
        data = get_exercise_by_id(entity_id)
        metric_type = data[3] if data else None
        name = data[1] if data else "упражнение"
    elif entity_type == 'challenge':
        data = get_challenge_by_id(entity_id)
        metric_type = data[5] if data else None
        name = data[1] if data else "челлендж"
    else:
        await update.message.reply_text("❌ Неизвестный тип.")
        return

    context.user_data['submit_entity_name'] = name

    # Проверяем формат
    if metric_type in ('for_reps', 'reps'):
        if not user_input.isdigit():
            await update.message.reply_text("❌ Введите целое число повторений.")
            return
        context.user_data['submit_result'] = user_input
    else:
        if not re.match(r'^\d{1,2}:\d{2}$', user_input):
            await update.message.reply_text("❌ Введите время в формате ММ:СС, например 05:30.")
            return
        context.user_data['submit_result'] = user_input

    context.user_data['conversation_state'] = AWAIT_SUBMIT_VIDEO
    await update.message.reply_text("📎 Теперь отправьте ссылку на видео (YouTube, Google Drive и т.п.):")
    logger.info("Переход к AWAIT_SUBMIT_VIDEO")


async def submit_video_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ссылки на видео"""
    logger.info(f"submit_video_input: {update.message.text[:50]}...")

    if context.user_data.get('conversation_state') != AWAIT_SUBMIT_VIDEO:
        logger.warning("submit_video_input: состояние не AWAIT_SUBMIT_VIDEO")
        return

    video_link = update.message.text.strip()
    if not video_link.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ Ссылка должна начинаться с http:// или https://.")
        return

    context.user_data['submit_video'] = video_link
    context.user_data['conversation_state'] = AWAIT_SUBMIT_COMMENT
    await update.message.reply_text("💬 Добавьте комментарий (или нажмите /skip):")
    logger.info("Переход к AWAIT_SUBMIT_COMMENT")


async def submit_comment_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка комментария"""
    logger.info(f"submit_comment_input: {update.message.text}")

    if context.user_data.get('conversation_state') != AWAIT_SUBMIT_COMMENT:
        logger.warning("submit_comment_input: состояние не AWAIT_SUBMIT_COMMENT")
        return

    comment = update.message.text
    if comment == '/skip':
        comment = None
        logger.info("Комментарий пропущен")

    await finalize_submit(update, context, comment)


async def submit_comment_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропуск комментария"""
    if context.user_data.get('conversation_state') != AWAIT_SUBMIT_COMMENT:
        return
    await finalize_submit(update, context, None)


async def finalize_submit(update: Update, context: ContextTypes.DEFAULT_TYPE, comment):
    """Сохранение результата и публикация в канал"""
    logger.info("finalize_submit начата")

    user_id = update.effective_user.id
    entity_type = context.user_data.get('submit_entity_type')
    entity_id = context.user_data.get('submit_entity_id')
    entity_name = context.user_data.get('submit_entity_name')
    result_value = context.user_data.get('submit_result')
    video_link = context.user_data.get('submit_video')
    channel_post_id = context.user_data.get('submit_channel_post_id')
    channel_id = context.user_data.get('submit_channel_id')

    # Получаем имя пользователя
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT first_name, username FROM users WHERE id = ?", (user_id,))
    user_row = cur.fetchone()
    conn.close()
    user_name = user_row[0] if user_row and user_row[0] else (user_row[1] if user_row else f"User{user_id}")

    # Сохраняем в БД
    try:
        user_level = get_user_level(user_id) or 'beginner'

        if entity_type == 'exercise':
            add_workout(user_id=user_id, exercise_id=entity_id, result_value=result_value,
                        video_link=video_link, user_level=user_level, comment=comment, metric=None)
        elif entity_type == 'complex':
            add_workout(user_id=user_id, complex_id=entity_id, result_value=result_value,
                        video_link=video_link, user_level=user_level, comment=comment, metric=None)
        elif entity_type == 'challenge':
            add_workout(user_id=user_id, challenge_id=entity_id, result_value=result_value,
                        video_link=video_link, user_level=user_level, comment=comment, metric=None)

        logger.info(f"Результат {entity_type} сохранён для {user_name}")
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")
        context.user_data.clear()
        return

    # Публикуем в канал
    emoji = "💪" if entity_type == 'exercise' else "🏋️" if entity_type == 'complex' else "🏆"
    type_text = "упражнение" if entity_type == 'exercise' else "комплекс" if entity_type == 'complex' else "челлендж"

    publish_text = f"{emoji} *{user_name}* сдал(а) результат для *{type_text}*: *{entity_name}*\n\n"
    publish_text += f"📊 *Результат:* {result_value}\n"
    publish_text += f"📹 *Видео:* [Ссылка]({video_link})\n"
    if comment:
        publish_text += f"💬 *Комментарий:* {comment}\n"
    publish_text += f"\n🔥 Отличная работа!"

    try:
        sent = await context.bot.send_message(
            chat_id=channel_id,
            text=publish_text,
            parse_mode='Markdown',
            reply_to_message_id=channel_post_id,
            disable_web_page_preview=True
        )
        logger.info(f"Результат опубликован в канале, message_id={sent.message_id}")

        await update.message.reply_text(f"✅ Результат *{entity_name}* сохранён и опубликован в канале!",
                                        parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Ошибка публикации: {e}")
        await update.message.reply_text("✅ Результат сохранён, но не опубликован в канале.")

    context.user_data.clear()
    logger.info("finalize_submit завершена")


async def cancel_submit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена ввода результата"""
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("❌ Ввод результата отменён.")
    logger.info("Ввод результата отменён")