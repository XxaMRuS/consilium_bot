import logging
import re
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from notifications import send_record_notification
from database import (
    add_user, get_exercises, add_workout, get_user_level, get_exercise_by_id,
    get_user_challenges, update_challenge_progress, check_challenge_completion,
    complete_challenge, get_setting, get_challenge_name
)

logger = logging.getLogger(__name__)

EXERCISE, RESULT, VIDEO, COMMENT = range(4)


def get_current_week():
    """Возвращает номер текущей недели (ISO)."""
    return datetime.now().isocalendar()[1]


async def _send_challenge_completion_notification(bot, user_id, challenge_id, bonus):
    """Отправляет уведомление пользователю и в канал о завершении челленджа."""
    # Уведомление пользователю
    try:
        await bot.send_message(
            chat_id=user_id,
            text=f"🎉 Поздравляем! Вы завершили челлендж и получили {bonus} бонусных баллов!"
        )
    except Exception as e:
        logger.error(f"Ошибка уведомления пользователя {user_id}: {e}")

    # Отправка в канал
    channel_id = get_setting("public_channel")
    if channel_id:
        try:
            channel_id_int = int(channel_id)
            challenge_name = get_challenge_name(challenge_id)
            await bot.send_message(
                chat_id=channel_id_int,
                text=f"🏆 Пользователь {user_id} завершил челлендж «{challenge_name}» и получил {bonus} бонусных баллов!"
            )
            logger.info(f"Сообщение о челлендже отправлено в канал {channel_id_int}")
        except Exception as e:
            logger.error(f"Ошибка отправки в канал: {e}")


async def _finalize_workout(update: Update, context: ContextTypes.DEFAULT_TYPE, comment=None):
    """
    Общая логика завершения тренировки:
    - добавляет тренировку в БД,
    - отправляет ачивки,
    - обновляет челленджи,
    - отправляет финальное сообщение.
    """
    user_id = update.effective_user.id
    exercise_id = context.user_data['exercise_id']
    result_value = context.user_data['result_value']
    video_link = context.user_data['video_link']
    user_level = get_user_level(user_id) or 'beginner'
    metric = context.user_data.get('metric')
    bot = update.get_bot()

    # Колбэк для уведомления о новом рекорде
    def notify_record_callback(uid, eid, res, met):
        asyncio.create_task(send_record_notification(bot, uid, eid, res, met))

    # Добавляем тренировку с передачей колбэка
    _, new_achievements = add_workout(
        user_id=user_id,
        exercise_id=exercise_id,
        result_value=result_value,
        video_link=video_link,
        user_level=user_level,
        comment=comment,
        metric=metric,
        notify_record_callback=notify_record_callback
    )

    # Отправляем новые ачивки
    for ach in new_achievements:
        ach_id, name, desc, cond_type, cond_value, icon = ach
        await update.message.reply_text(
            f"{icon} **{name}** — {desc}",
            parse_mode='Markdown'
        )

    # Обновляем прогресс челленджей
    challenges = get_user_challenges(user_id)
    for ch in challenges:
        ch_id, ch_target_type, ch_target_id, ch_target_value, ch_metric, bonus = ch
        if ch_target_type == 'exercise' and ch_target_id == exercise_id:
            update_challenge_progress(user_id, ch_id, result_value)
            if check_challenge_completion(user_id, ch_id, ch_target_value, ch_metric):
                if complete_challenge(user_id, ch_id):
                    await _send_challenge_completion_notification(
                        update.get_bot(), user_id, ch_id, bonus
                    )

    # Финальное сообщение
    await update.message.reply_text(
        "✅ Тренировка успешно записана! Спасибо за честность.\n"
        "Можешь посмотреть свои результаты командой /mystats, а таблицу лидеров — /top."
    )
    context.user_data.clear()


async def workout_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_level = get_user_level(user.id) or 'beginner'
    add_user(user.id, user.first_name, user.last_name, user.username, user_level)

    # Если есть отложенное упражнение (например, из инлайн-кнопки)
    if 'pending_exercise' in context.user_data:
        ex_id = context.user_data.pop('pending_exercise')
        ex = get_exercise_by_id(ex_id)
        if ex:
            context.user_data['exercise_id'] = ex_id
            metric = ex[2]   # metric на индексе 2
            context.user_data['metric'] = metric
            if metric == 'reps':
                await update.message.reply_text("🔢 Введи количество повторений (только число):")
            else:
                await update.message.reply_text("⏱️ Введи время в формате ММ:СС (например, 05:30):")
            return RESULT
        else:
            await update.message.reply_text("❌ Упражнение не найдено. Начните заново командой /workout")
            return ConversationHandler.END

    current_week = get_current_week()
    exercises = get_exercises(active_only=True, week=current_week, difficulty=user_level)
    if not exercises:
        await update.message.reply_text("❌ На этой неделе нет активных упражнений. Загляни позже!")
        return ConversationHandler.END

    keyboard = []
    for ex in exercises:
        ex_id, name, metric, points, week, difficulty = ex
        btn_text = f"{name} ({points} баллов)" if points else name
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"ex_{ex_id}")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🏋️ Выбери упражнение, которое выполнил:", reply_markup=reply_markup)
    return EXERCISE


async def exercise_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "cancel":
        await query.edit_message_text("❌ Запись тренировки отменена.")
        context.user_data.clear()
        return ConversationHandler.END

    ex_id = int(query.data.split("_")[1])
    context.user_data['exercise_id'] = ex_id

    user_level = get_user_level(update.effective_user.id) or 'beginner'
    exercises = get_exercises(active_only=True, week=get_current_week(), difficulty=user_level)
    ex_metric = None
    for ex in exercises:
        if ex[0] == ex_id:
            ex_metric = ex[2]
            break

    if ex_metric is None:
        await query.edit_message_text("❌ Это упражнение больше недоступно. Выберите другое командой /workout.")
        return ConversationHandler.END

    context.user_data['metric'] = ex_metric

    if ex_metric == 'reps':
        prompt = "🔢 Введи количество повторений (только число):"
    else:
        prompt = "⏱️ Введи время в формате ММ:СС (например, 05:30):"

    await query.edit_message_text(prompt)
    return RESULT


async def result_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    metric = context.user_data.get('metric')

    if not metric:
        await update.message.reply_text("⚠️ Ошибка: не определён тип упражнения. Попробуйте начать заново через /workout")
        return ConversationHandler.END

    if metric == 'reps':
        if not text.isdigit():
            await update.message.reply_text("❌ Пожалуйста, введи число (количество повторений).")
            return RESULT
        context.user_data['result_value'] = text
    else:
        if not re.match(r'^\d{1,2}:\d{2}$', text):
            await update.message.reply_text("❌ Неправильный формат. Введи время как ММ:СС (например, 05:30).")
            return RESULT
        context.user_data['result_value'] = text

    await update.message.reply_text("📎 Теперь отправь ссылку на видео с выполнением (Google Drive, YouTube и т.п.)")
    return VIDEO


async def video_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video_link = update.message.text.strip()
    if not video_link.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ Это не похоже на ссылку. Попробуй ещё раз (должно начинаться с http:// или https://)")
        return VIDEO

    context.user_data['video_link'] = video_link
    await update.message.reply_text("💬 Добавь комментарий к тренировке (можно пропустить, нажми /skip или просто отправь сообщение):")
    return COMMENT


async def comment_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _finalize_workout(update, context, comment=None)


async def comment_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    comment = update.message.text
    if comment == '/skip':
        comment = None
    await _finalize_workout(update, context, comment=comment)


async def workout_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Запись тренировки отменена.")
    context.user_data.clear()
    return ConversationHandler.END