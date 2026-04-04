import logging
import re
from database_backup import get_complex_exercises
import sqlite3
from datetime import datetime
from functools import wraps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import ContextTypes
from database import DB_NAME, get_complex_by_id, get_exercise_by_id, get_challenge_by_id, add_workout, get_user_level, get_setting

# ==================== ДЕБАГ-РЕЖИМ ====================
from debug_utils import debug_print, log_call, log_user_data, log_state_change, log_callback, log_message, DEBUG_MODE

# ==================== НАСТРОЙКА ЛОГИРОВАНИЯ ====================
logger = logging.getLogger(__name__)

_last_comment = None

AWAIT_SUBMIT_RESULT = 61
AWAIT_SUBMIT_VIDEO = 62
AWAIT_SUBMIT_COMMENT = 63


# ==================== ОСНОВНЫЕ ФУНКЦИИ ====================
@log_call
async def submit_complex_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Сдать результат' для комплекса"""
    log_user_data(update, context, "submit_complex_callback")
    debug_print(f"🔥 submit_complex_callback: ВЫЗВАНА")
    debug_print(f"📦 user_data на входе: {context.user_data if context else 'Нет context'}")

    query = update.callback_query
    data = query.data
    debug_print(f"🔥 submit_complex_callback: data={data}")
    await query.answer()

    try:
        complex_id = int(query.data.split('_')[2])
        debug_print(f"🔥 submit_complex_callback: complex_id={complex_id}")
    except (ValueError, IndexError):
        debug_print(f"🔥 submit_complex_callback: ОШИБКА - некорректные данные")
        await query.edit_message_text("❌ Некорректные данные кнопки.")
        debug_print(f"🔥 submit_complex_callback: ВОЗВРАТ None")
        return

    context.user_data['submit_entity_type'] = 'complex'
    context.user_data['submit_entity_id'] = complex_id
    context.user_data['submit_channel_post_id'] = query.message.message_id
    context.user_data['submit_channel_id'] = query.message.chat_id
    context.user_data['conversation_state'] = AWAIT_SUBMIT_RESULT

    debug_print(f"🔥 submit_complex_callback: user_data={dict(context.user_data)}")

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_submit")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await update.effective_user.send_message(
            "📊 Введите результат:\n- повторения: просто число (например, 10)\n- время: в формате ММ:СС (например, 05:30)",
            reply_markup=reply_markup
        )
        debug_print(f"🔥 submit_complex_callback: запрос результата отправлен")
    except TelegramError as e:
        logger.error("Не удалось отправить запрос результата: %s", e)
        debug_print(f"🔥 submit_complex_callback: ОШИБКА - {e}")
        await query.edit_message_text("❌ Не удалось начать ввод. Напишите боту в личку и попробуйте снова.")
        debug_print(f"🔥 submit_complex_callback: ВОЗВРАТ None")
        return
    logger.info(f"Комплекс {complex_id}: запрос результата отправлен")
    debug_print(f"🔥 submit_complex_callback: ВОЗВРАТ None")


@log_call
async def submit_exercise_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Сдать результат' для упражнения"""
    log_user_data(update, context, "submit_exercise_callback")
    debug_print(f"🔥 submit_exercise_callback: ВЫЗВАНА")
    debug_print(f"📦 user_data на входе: {context.user_data if context else 'Нет context'}")

    query = update.callback_query
    data = query.data
    debug_print(f"🔥 submit_exercise_callback: data={data}")
    await query.answer()

    try:
        exercise_id = int(query.data.split('_')[2])
        debug_print(f"🔥 submit_exercise_callback: exercise_id={exercise_id}")
    except (ValueError, IndexError):
        debug_print(f"🔥 submit_exercise_callback: ОШИБКА - некорректные данные")
        await query.edit_message_text("❌ Некорректные данные кнопки.")
        debug_print(f"🔥 submit_exercise_callback: ВОЗВРАТ None")
        return

    context.user_data['submit_entity_type'] = 'exercise'
    context.user_data['submit_entity_id'] = exercise_id
    context.user_data['submit_channel_post_id'] = query.message.message_id
    context.user_data['submit_channel_id'] = query.message.chat_id
    context.user_data['conversation_state'] = AWAIT_SUBMIT_RESULT

    exercise = get_exercise_by_id(exercise_id)
    exercise_name = exercise[1] if exercise else "упражнения"
    metric = exercise[3] if exercise else None
    context.user_data['metric'] = metric

    debug_print(f"🔥 submit_exercise_callback: user_data={dict(context.user_data)}")
    debug_print(f"🔥 submit_exercise_callback: metric={metric}, name={exercise_name}")

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
        debug_print(f"🔥 submit_exercise_callback: запрос результата отправлен")
    except TelegramError as e:
        logger.error("submit_exercise_callback edit_message: %s", e)
        debug_print(f"🔥 submit_exercise_callback: ОШИБКА - {e}")
        await query.edit_message_text("❌ Ошибка отображения. Попробуйте снова.")
        debug_print(f"🔥 submit_exercise_callback: ВОЗВРАТ None")
        return
    logger.info(f"Упражнение {exercise_id}: запрос результата отправлен")
    debug_print(f"🔥 submit_exercise_callback: ВОЗВРАТ None")


@log_call
async def submit_challenge_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Сдать результат' для челленджа"""
    log_user_data(update, context, "submit_challenge_callback")
    debug_print(f"🔥 submit_challenge_callback: ВЫЗВАНА")
    debug_print(f"📦 user_data на входе: {context.user_data if context else 'Нет context'}")

    query = update.callback_query
    data = query.data
    debug_print(f"🔥 submit_challenge_callback: data={data}")
    await query.answer()

    try:
        challenge_id = int(query.data.split('_')[2])
        debug_print(f"🔥 submit_challenge_callback: challenge_id={challenge_id}")
    except (ValueError, IndexError):
        debug_print(f"🔥 submit_challenge_callback: ОШИБКА - некорректные данные")
        await query.edit_message_text("❌ Некорректные данные кнопки.")
        debug_print(f"🔥 submit_challenge_callback: ВОЗВРАТ None")
        return

    context.user_data['submit_entity_type'] = 'challenge'
    context.user_data['submit_entity_id'] = challenge_id
    context.user_data['submit_channel_post_id'] = query.message.message_id
    context.user_data['submit_channel_id'] = query.message.chat_id
    context.user_data['conversation_state'] = AWAIT_SUBMIT_RESULT

    challenge = get_challenge_by_id(challenge_id)
    challenge_name = challenge[1] if challenge else "челленджа"
    metric = challenge[5] if challenge else None
    context.user_data['metric'] = metric

    debug_print(f"🔥 submit_challenge_callback: user_data={dict(context.user_data)}")
    debug_print(f"🔥 submit_challenge_callback: metric={metric}, name={challenge_name}")

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
        debug_print(f"🔥 submit_challenge_callback: запрос результата отправлен")
    except TelegramError as e:
        logger.error("submit_challenge_callback edit_message: %s", e)
        debug_print(f"🔥 submit_challenge_callback: ОШИБКА - {e}")
        await query.edit_message_text("❌ Ошибка отображения. Попробуйте снова.")
        debug_print(f"🔥 submit_challenge_callback: ВОЗВРАТ None")
        return
    logger.info(f"Челлендж {challenge_id}: запрос результата отправлен")
    debug_print(f"🔥 submit_challenge_callback: ВОЗВРАТ None")


@log_call
async def submit_result_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка введённого результата"""
    log_user_data(update, context, "submit_result_input")
    debug_print(f"🔥 submit_result_input: ВЫЗВАНА")
    debug_print(f"📦 user_data на входе: {context.user_data if context else 'Нет context'}")
    debug_print(f"🔥 submit_result_input: text='{update.message.text}'")

    if update.message.text and update.message.text.strip() == "❌ Отмена":
        debug_print(f"🔥 submit_result_input: получена Отмена")
        from utils import handle_cancel
        debug_print(f"🔥 submit_result_input: ВОЗВРАТ из handle_cancel")
        return await handle_cancel(update, context)

    metric_type = context.user_data.get('metric')
    debug_print(f"🔥 submit_result_input: metric_type='{metric_type}'")

    if context.user_data.get('conversation_state') != AWAIT_SUBMIT_RESULT:
        logger.warning("submit_result_input: состояние не AWAIT_SUBMIT_RESULT")
        debug_print(f"🔥 submit_result_input: состояние не AWAIT_SUBMIT_RESULT, ВОЗВРАТ")
        return

    user_input = update.message.text.strip()
    entity_type = context.user_data.get('submit_entity_type')
    debug_print(f"🔥 submit_result_input: user_input='{user_input}'")
    debug_print(f"🔥 submit_result_input: entity_type='{entity_type}'")
    entity_id = context.user_data.get('submit_entity_id')
    debug_print(f"🔥 submit_result_input: entity_id={entity_id}")

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
        debug_print(f"🔥 submit_result_input: неизвестный тип")
        await update.message.reply_text("❌ Неизвестный тип.")
        debug_print(f"🔥 submit_result_input: ВОЗВРАТ")
        return

    context.user_data['submit_entity_name'] = name
    context.user_data['metric'] = metric_type
    debug_print(f"🔥 submit_result_input: name='{name}'")
    debug_print(f"🔥 submit_result_input: metric_type='{metric_type}'")

    # Проверяем формат
    debug_print(f"🔥 submit_result_input: проверка формата")
    if metric_type in ('for_reps', 'reps'):
        debug_print(f"🔥 submit_result_input: проверка metric_type = {metric_type}")
        if not user_input.isdigit():
            debug_print(f"🔥 submit_result_input: не число - ВОЗВРАТ")
            await update.message.reply_text("❌ Введите целое число повторений.")
            return
        context.user_data['submit_result'] = user_input
    else:
        if not re.match(r'^\d{1,2}:\d{2}$', user_input):
            debug_print(f"🔥 submit_result_input: неверный формат времени - ВОЗВРАТ")
            await update.message.reply_text("❌ Введите время в формате ММ:СС, например 05:30.")
            return
        context.user_data['submit_result'] = user_input

    debug_print(f"🔥 submit_result_input: результат сохранён: {context.user_data.get('submit_result')}")

    context.user_data['conversation_state'] = AWAIT_SUBMIT_VIDEO
    debug_print(f"🔥 submit_result_input: переход к AWAIT_SUBMIT_VIDEO")
    debug_print(f"📦 user_data на выходе: {context.user_data}")
    await update.message.reply_text("📎 Теперь отправьте ссылку на видео (YouTube, Google Drive и т.п.):")
    logger.info("Переход к AWAIT_SUBMIT_VIDEO")
    debug_print(f"🔥 submit_result_input: ВОЗВРАТ None")


@log_call
async def submit_video_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ссылки на видео"""
    log_user_data(update, context, "submit_video_input")
    debug_print(
        f"submit_video_input вызвана, video={update.message.text[:50] if update.message.text else 'None'}, user_data={dict(context.user_data)}")
    logger.info(f"submit_video_input: {update.message.text[:50]}...")

    # Обработка отмены
    if update.message.text and update.message.text.strip() == "❌ Отмена":
        from utils import handle_cancel
        return await handle_cancel(update, context)

    if context.user_data.get('conversation_state') != AWAIT_SUBMIT_VIDEO:
        logger.warning("submit_video_input: состояние не AWAIT_SUBMIT_VIDEO")
        return

    video_link = update.message.text.strip()
    if not video_link.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ Ссылка должна начинаться с http:// или https://.")
        return

    context.user_data['submit_video'] = video_link
    debug_print(f"submit_video_input: ссылка сохранена: {video_link}")

    # Переключаем состояние на ожидание комментария
    context.user_data['conversation_state'] = AWAIT_SUBMIT_COMMENT

    # Отправляем сообщение с запросом комментария и кнопкой "Пропустить"
    keyboard = [[InlineKeyboardButton("⏩ Пропустить", callback_data="skip_comment")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "💬 Добавьте комментарий (или нажмите кнопку):",
        reply_markup=reply_markup
    )
    logger.info("Переход к AWAIT_SUBMIT_COMMENT")
    # НЕ вызываем submit_comment_input здесь!
    return


@log_call
async def submit_comment_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка комментария"""
    log_user_data(update, context, "submit_comment_input")

    debug_print(f"🔥 submit_comment_input: ВЫЗВАНА")
    debug_print(f"📦 user_data на входе: {context.user_data if context else 'Нет context'}")
    debug_print(f"🔥 submit_comment_input: comment='{update.message.text}'")

    if update.message.text and update.message.text.strip() == "❌ Отмена":
        debug_print(f"🔥 submit_comment_input: получена Отмена")
        from utils import handle_cancel
        debug_print(f"🔥 submit_comment_input: ВОЗВРАТ из handle_cancel")
        return await handle_cancel(update, context)

    # Проверка на дубликат комментария для ЭТОГО пользователя в ЭТОМ диалоге
    last_comment = context.user_data.get('_last_comment')
    if last_comment == update.message.text:
        debug_print("🔥 submit_comment_input: дубликат комментария, игнорируем")
        debug_print(f"🔥 submit_comment_input: ВОЗВРАТ None")
        return
    context.user_data['_last_comment'] = update.message.text

    if context.user_data.get('submit_completed'):
        debug_print("🔥 submit_comment_input: submit_completed=True, игнорируем")
        debug_print(f"🔥 submit_comment_input: ВОЗВРАТ None")
        return
    context.user_data['submit_completed'] = True

    logger.info(f"submit_comment_input: {update.message.text}")
    print(f"🔥🔥🔥 submit_result_input: ПОЛУЧЕН ТЕКСТ: '{update.message.text}'")

    if context.user_data.get('conversation_state') != AWAIT_SUBMIT_COMMENT:
        logger.warning("submit_comment_input: состояние не AWAIT_SUBMIT_COMMENT")
        debug_print(f"🔥 submit_comment_input: состояние не AWAIT_SUBMIT_COMMENT, ВОЗВРАТ")
        return

    comment = update.message.text
    debug_print(f"🔥 submit_comment_input: проверка на /skip")
    if comment == '/skip':
        comment = None
        logger.info("Комментарий пропущен")
        debug_print(f"🔥 submit_comment_input: comment пропущен")

    debug_print(f"🔥 submit_comment_input: comment сохранён: {comment}")
    debug_print(f"🔥 submit_comment_input: вызов finalize_submit")
    await finalize_submit(update, context, comment)
    context.user_data['conversation_state'] = None
    debug_print(f"🔥 submit_comment_input: ВОЗВРАТ None")


@log_call
async def submit_comment_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропуск комментария"""
    log_user_data(update, context, "submit_comment_skip")
    debug_print(f"🔥 submit_comment_skip: ВЫЗВАНА")
    debug_print(f"📦 user_data на входе: {context.user_data if context else 'Нет context'}")

    if context.user_data.get('conversation_state') != AWAIT_SUBMIT_COMMENT:
        debug_print(f"🔥 submit_comment_skip: состояние не AWAIT_SUBMIT_COMMENT, ВОЗВРАТ")
        return

    debug_print(f"🔥 submit_comment_skip: comment пропущен")
    await finalize_submit(update, context, None)
    debug_print(f"🔥 submit_comment_skip: ВОЗВРАТ None")


@log_call
async def finalize_submit(update: Update, context: ContextTypes.DEFAULT_TYPE, comment):
    debug_print(f"🔥 FINALIZE: user_data = {context.user_data}")
    """Сохранение результата и публикация в канал"""
    log_user_data(update, context, "finalize_submit")
    debug_print(f"🔥 finalize_submit: ВЫЗВАНА")
    debug_print(f"📦 user_data на входе: {context.user_data if context else 'Нет context'}")

    user_id = update.effective_user.id
    debug_print(f"🔥 finalize_submit: user_id={user_id}")

    entity_type = context.user_data.get('submit_entity_type')
    debug_print(f"🔥 finalize_submit: entity_type={entity_type}")

    entity_id = context.user_data.get('submit_entity_id')
    debug_print(f"🔥 finalize_submit: entity_id={entity_id}")

    entity_name = context.user_data.get('submit_entity_name')
    result_value = context.user_data.get('submit_result')
    debug_print(f"🔥 finalize_submit: result_value={result_value}")

    video_link = context.user_data.get('submit_video')
    debug_print(f"🔥 finalize_submit: video_link={video_link}")

    debug_print(f"🔥 finalize_submit: comment={comment}")

    channel_id = context.user_data.get('submit_channel_id')
    channel_post_id = context.user_data.get('submit_channel_post_id')

    # ПРИНУДИТЕЛЬНО берём channel_id из настроек
    from database import get_setting
    channel_id_str = get_setting("public_channel")
    if channel_id_str:
        channel_id = int(channel_id_str)
    else:
        channel_id = None

    # Всегда берём channel_id из настроек, игнорируя submit_channel_id
    from database import get_setting
    channel_id_str = get_setting("public_channel")
    if channel_id_str:
        channel_id = int(channel_id_str)
        debug_print(f"🔥 finalize_submit: channel_id принудительно взят из настроек: {channel_id}")
    else:
        channel_id = None
        debug_print(f"🔥 finalize_submit: channel_id не найден в настройках")
    # Проверка: если это упражнение из комплекса
    if 'current_complex_id' in context.user_data and entity_type == 'exercise':
        from workout_handlers import get_complex_exercises
        total_exercises = len(get_complex_exercises(context.user_data['current_complex_id']))
        completed = len(context.user_data.get('completed_exercises', []))

        if completed < total_exercises:
            # Не все упражнения выполнены — не очищаем user_data
            debug_print(
                f"🔥 finalize_submit: выполнено {completed} из {total_exercises} упражнений комплекса. Продолжаем.")
            # Очищаем только временные данные, но сохраняем прогресс комплекса
            context.user_data.pop('submit_entity_name', None)
            context.user_data.pop('submit_result', None)
            context.user_data.pop('submit_video', None)
            context.user_data.pop('_last_comment', None)
            context.user_data.pop('submit_completed', None)
            context.user_data.pop('conversation_state', None)
            return
        else:
            # ВСЕ УПРАЖНЕНИЯ ВЫПОЛНЕНЫ!
            debug_print(f"🔥 finalize_submit: ВЫПОЛНЕН ВЕСЬ КОМПЛЕКС! {completed} из {total_exercises}")

            # Распределяем бонусы комплекса между топ-3
            from database import distribute_bonus_for_entity
            complex_id = context.user_data.get('current_complex_id')
            if complex_id:
                distribute_bonus_for_entity('complex', complex_id)
                debug_print(f"🔥 finalize_submit: бонусы комплекса {complex_id} распределены")

            # Отправляем поздравление пользователю
            complex_name = context.user_data.get('current_complex_name', 'комплекс')
            await update.message.reply_text(
                f"🎉 ПОЗДРАВЛЯЮ! Вы выполнили комплекс *{complex_name}*!\n\n"
                f"🔥 Отличная работа! Так держать!",
                parse_mode='Markdown'
            )

            # Отправляем в канал
            if channel_id:
                try:
                    await context.bot.send_message(
                        chat_id=channel_id,
                        text=f"🏆 *{user_name}* выполнил(а) комплекс *{complex_name}*! 🔥",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    debug_print(f"🔥 finalize_submit: ошибка отправки в канал: {e}")

            # Очищаем данные комплекса
            context.user_data.pop('current_complex_id', None)
            context.user_data.pop('current_complex_type', None)
            context.user_data.pop('current_complex_name', None)
            context.user_data.pop('current_complex_points', None)
            context.user_data.pop('completed_exercises', None)
            context.user_data.pop('complex_reps', None)

    context.user_data.pop('conversation_state', None)

    debug_print(
        f"🔥 finalize_submit: user_id={user_id}, entity_type={entity_type}, entity_id={entity_id}, result={result_value}")

    # Получаем имя пользователя
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT first_name, username FROM users WHERE id = ?", (user_id,))
    user_row = cur.fetchone()
    conn.close()
    user_name = user_row[0] if user_row and user_row[0] else (user_row[1] if user_row else f"User{user_id}")
    debug_print(f"🔥 finalize_submit: user_name={user_name}")

    # Сохраняем в БД
    try:
        user_level = get_user_level(user_id) or 'beginner'
        debug_print(f"🔥 finalize_submit: add_workout вызвана")

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
        debug_print(f"🔥 finalize_submit: тренировка сохранена")
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")
        debug_print(f"🔥 finalize_submit: ОШИБКА сохранения: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")
        context.user_data.clear()
        debug_print(f"🔥 finalize_submit: user_data очищен (после ошибки)")
        debug_print(f"🔥 finalize_submit: ВОЗВРАТ None")
        return

    if channel_id:
        emoji = "💪" if entity_type == 'exercise' else "🏋️" if entity_type == 'complex' else "🏆"
        type_text = "упражнение" if entity_type == 'exercise' else "комплекс" if entity_type == 'complex' else "челлендж"

        publish_text = f"{emoji} *{user_name}* сдал(а) результат для *{type_text}*: *{entity_name}*\n\n"
        publish_text += f"📊 *Результат:* {result_value}\n"
        publish_text += f"📹 *Видео:* [Ссылка]({video_link})\n"
        if comment:
            publish_text += f"💬 *Комментарий:* {comment}\n"
        publish_text += f"\n🔥 Отличная работа!"

        try:
            # Отправляем в канал (убрал reply_to_message_id)
            sent = await context.bot.send_message(
                chat_id=channel_id,
                text=publish_text,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            logger.info(f"Результат опубликован в канале, message_id={sent.message_id}")
            debug_print(f"🔥 finalize_submit: результат опубликован в канале {channel_id}")

            if update.message:
                await update.message.reply_text(f"✅ Результат *{entity_name}* сохранён и опубликован в канале!",
                                                parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Ошибка публикации: {e}")
            debug_print(f"🔥 finalize_submit: ОШИБКА публикации: {e}")
            if update.message:
                await update.message.reply_text("✅ Результат сохранён, но не опубликован в канале.")

@log_call
async def cancel_submit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена ввода результата"""
    log_user_data(update, context, "cancel_submit_callback")
    debug_print(f"🔥 cancel_submit_callback: ВЫЗВАНА")
    debug_print(f"📦 user_data на входе: {context.user_data if context else 'Нет context'}")

    query = update.callback_query
    data = query.data
    debug_print(f"🔥 cancel_submit_callback: data={data}")
    await query.answer()

    context.user_data.clear()
    debug_print(f"🔥 cancel_submit_callback: user_data очищен")
    await query.edit_message_text("❌ Ввод результата отменён.")
    logger.info("Ввод результата отменён")
    debug_print(f"🔥 cancel_submit_callback: ВОЗВРАТ None")


@log_call
async def skip_comment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback для кнопки пропуска комментария"""
    debug_print(f"🔥 skip_comment_callback: ВЫЗВАНА")

    query = update.callback_query
    await query.answer()

    debug_print(f"🔥 skip_comment_callback: пропуск комментария")
    await finalize_submit(update, context, None)

    debug_print(f"🔥 skip_comment_callback: ВОЗВРАТ")