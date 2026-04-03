import asyncio
import logging
import re
from datetime import datetime
from functools import wraps
from database import get_complex_by_id, get_complex_exercises
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import (
    add_user, get_exercises, add_workout, get_user_level, get_exercise_by_id,
    get_user_challenges, update_challenge_progress, check_challenge_completion,
    complete_challenge, get_challenge_name
)
from channel_notifier import notify_exercise_complete

# ==================== ДЕБАГ-РЕЖИМ ====================
from debug_utils import debug_print, log_call, log_user_data, log_state_change, log_callback, log_message, DEBUG_MODE

# ==================== НАСТРОЙКА ЛОГИРОВАНИЯ ====================
logger = logging.getLogger(__name__)

EXERCISE = 60
RESULT = 61
VIDEO = 62
COMMENT = 63
COMPLEX_EXERCISE = 64


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
@log_call
def get_current_week():
    debug_print(f"🔥 get_current_week: возвращает {datetime.now().isocalendar()[1]}")
    return datetime.now().isocalendar()[1]


@log_call
def _reply_anchor_message(update: Update):
    debug_print(f"🔥 _reply_anchor_message: update.message={update.message}")
    debug_print(f"🔥 _reply_anchor_message: update.callback_query={update.callback_query}")
    if update.message:
        return update.message
    if update.callback_query and update.callback_query.message:
        return update.callback_query.message
    return None


@log_call
async def _send_challenge_completion_notification(bot, user_id, challenge_id, bonus):
    debug_print(f"🔥 _send_challenge_completion_notification: user_id={user_id}")
    debug_print(f"🔥 _send_challenge_completion_notification: challenge_id={challenge_id}")
    debug_print(f"🔥 _send_challenge_completion_notification: bonus={bonus}")
    try:
        user = await bot.get_chat(user_id)
        user_name = user.first_name or user.username or f"User{user_id}"
    except Exception:
        user_name = f"User{user_id}"

    challenge_name = get_challenge_name(challenge_id) or f"Челлендж {challenge_id}"

    try:
        from channel_notifier import notify_challenge_complete
        await notify_challenge_complete(
            bot=bot,
            user_name=user_name,
            challenge_name=challenge_name,
            days=None,
            bonus=bonus
        )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления в канал: {e}")

    try:
        await bot.send_message(
            chat_id=user_id,
            text=f"🎉 Поздравляем! Вы завершили челлендж «{challenge_name}» и получили {bonus} бонусных баллов!"
        )
    except Exception as e:
        logger.error(f"Ошибка уведомления пользователя {user_id}: {e}")

    debug_print(f"🔥 _send_challenge_completion_notification: ВОЗВРАТ None")
    return None


# ==================== ОСНОВНЫЕ ФУНКЦИИ ====================
@log_call
async def _finalize_workout(update: Update, context: ContextTypes.DEFAULT_TYPE, comment=None):
    """
    Финализация тренировки: сохранение в БД, отправка уведомлений, очистка данных.
    Содержит многоуровневую защиту от дублирования.
    Поддерживает как упражнения, так и комплексы.
    """
    # === НАЧАЛО ЛОГИРОВАНИЯ ===
    log_user_data(update, context, "_finalize_workout")
    debug_print("=" * 60)
    debug_print("🔥 _finalize_workout: НАЧАЛО ВЫПОЛНЕНИЯ")
    debug_print(f"👤 user_id: {update.effective_user.id}")
    debug_print(f"💬 comment: {comment}")
    debug_print(f"📦 user_data ключи: {list(context.user_data.keys())}")

    # === УРОВЕНЬ 1: ЗАЩИТА ОТ ПОВТОРНОГО ВЫЗОВА ===
    if context.user_data.get('_finalizing'):
        debug_print("⚠️ [ЗАЩИТА] _finalize_workout уже выполняется, пропускаем повторный вызов")
        debug_print(f"📊 Текущий _finalizing = {context.user_data.get('_finalizing')}")
        debug_print("=" * 60)
        return ConversationHandler.END

    # === УРОВЕНЬ 2: ЗАЩИТА ОТ ПОВТОРНОГО СОХРАНЕНИЯ ===
    if context.user_data.get('_already_saved'):
        debug_print("⚠️ [ЗАЩИТА] Тренировка уже сохранена, пропускаем повторное сохранение")
        debug_print(f"📊 _already_saved = {context.user_data.get('_already_saved')}")
        debug_print("=" * 60)
        return ConversationHandler.END

    # === ПРОВЕРКА: ЭТО УПРАЖНЕНИЕ ИЛИ КОМПЛЕКС? ===
    exercise_id = context.user_data.get('exercise_id')
    complex_id = context.user_data.get('current_complex_id')
    result_value = context.user_data.get('result_value')

    # Для комплекса может быть также complex_reps (количество повторений для упражнения в комплексе)
    complex_reps = context.user_data.get('complex_reps')

    debug_print(f"🔍 [ПРОВЕРКА] exercise_id={exercise_id}, complex_id={complex_id}, complex_reps={complex_reps}")

    # === УРОВЕНЬ 3: ПРОВЕРКА ОБЯЗАТЕЛЬНЫХ ПОЛЕЙ ===
    if not exercise_id:
        debug_print("❌ [ОШИБКА] Отсутствует exercise_id в user_data")
        debug_print(f"📊 user_data: {dict(context.user_data)}")
        debug_print("=" * 60)
        try:
            await update.message.reply_text("❌ Ошибка: не найдено упражнение. Попробуйте начать заново.")
        except:
            pass
        return ConversationHandler.END

    if not result_value:
        debug_print("❌ [ОШИБКА] Отсутствует result_value в user_data")
        debug_print(f"📊 user_data: {dict(context.user_data)}")
        debug_print("=" * 60)
        try:
            await update.message.reply_text("❌ Ошибка: не найден результат. Попробуйте начать заново.")
        except:
            pass
        return ConversationHandler.END

    debug_print("✅ [ПРОВЕРКА] Все обязательные поля присутствуют")
    debug_print(f"💪 exercise_id: {exercise_id}")
    debug_print(f"📊 result_value: {result_value}")
    if complex_id:
        debug_print(f"📦 complex_id: {complex_id}")
        debug_print(f"🔢 complex_reps: {complex_reps}")

    # === УСТАНОВКА ФЛАГОВ ===
    context.user_data['_finalizing'] = True
    debug_print("🔒 Установлен флаг _finalizing = True")

    # === ИНИЦИАЛИЗАЦИЯ ПЕРЕМЕННЫХ ===
    anchor = None
    new_achievements = None

    try:
        # === ПОЛУЧЕНИЕ ДАННЫХ ИЗ user_data ===
        user_id = update.effective_user.id
        video_link = context.user_data.get('video_link', '')
        user_level = get_user_level(user_id) or 'beginner'
        metric = context.user_data.get('metric')
        bot = update.get_bot()

        debug_print(f"📹 video_link: {video_link[:50] if video_link else 'None'}...")
        debug_print(f"⭐ user_level: {user_level}")
        debug_print(f"📏 metric: {metric}")

        # === ПОЛУЧЕНИЕ ИНФОРМАЦИИ ОБ УПРАЖНЕНИИ ===
        exercise = get_exercise_by_id(exercise_id)
        if not exercise:
            debug_print(f"❌ [ОШИБКА] Упражнение с ID {exercise_id} не найдено в БД")
            debug_print("=" * 60)
            await update.message.reply_text("❌ Упражнение не найдено. Попробуйте начать заново.")
            return ConversationHandler.END

        exercise_name = exercise[1]
        debug_print(f"📋 Упражнение найдено: '{exercise_name}'")

        # === ПОЛУЧЕНИЕ ИНФОРМАЦИИ О ПОЛЬЗОВАТЕЛЕ ===
        user = update.effective_user
        user_name = user.first_name or user.username or f"User{user_id}"
        debug_print(f"👤 user_name: {user_name}")

        # === CALLBACK ДЛЯ УВЕДОМЛЕНИЙ ===
        def notify_record_callback(uid, eid, res, met):
            debug_print(f"📢 notify_record_callback вызван: user={uid}, exercise={eid}, result={res}")

        # === СОХРАНЕНИЕ ТРЕНИРОВКИ В БД ===
        debug_print("💾 [БД] Начинаем сохранение тренировки...")
        debug_print(f"   - user_id: {user_id}")
        debug_print(f"   - exercise_id: {exercise_id}")
        debug_print(f"   - complex_id: {complex_id}")
        debug_print(f"   - result_value: {result_value}")
        debug_print(f"   - video_link: {video_link[:50] if video_link else 'None'}...")
        debug_print(f"   - user_level: {user_level}")
        debug_print(f"   - comment: {comment}")
        debug_print(f"   - metric: {metric}")

        # Если это часть комплекса, передаём complex_id
        if complex_id:
            _, new_achievements = add_workout(
                user_id=user_id,
                exercise_id=exercise_id,
                complex_id=complex_id,
                result_value=result_value,
                video_link=video_link,
                user_level=user_level,
                comment=comment,
                metric=metric,
                notify_record_callback=notify_record_callback
            )
        else:
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

        # === ПОМЕЧАЕМ, ЧТО ТРЕНИРОВКА СОХРАНЕНА ===
        context.user_data['_already_saved'] = True
        debug_print("✅ [БД] Тренировка успешно сохранена")
        debug_print(f"🏆 new_achievements: {new_achievements if new_achievements else 'None'}")
        debug_print("🔒 Установлен флаг _already_saved = True")

        # === ОТПРАВКА УВЕДОМЛЕНИЯ В КАНАЛ ===
        try:
            debug_print("📢 [КАНАЛ] Отправка уведомления о завершении упражнения...")
            await notify_exercise_complete(
                bot=bot,
                user_name=user_name,
                exercise_name=exercise_name,
                result=result_value,
                is_record=False
            )
            debug_print("✅ [КАНАЛ] Уведомление успешно отправлено")
        except Exception as e:
            logger.error(f"❌ [КАНАЛ] Ошибка отправки уведомления: {e}")
            debug_print(f"❌ [КАНАЛ] Ошибка: {e}")

        # === ПОЛУЧЕНИЕ ЯКОРЯ ДЛЯ ОТВЕТА ===
        anchor = _reply_anchor_message(update)
        debug_print(f"📌 anchor: {type(anchor).__name__ if anchor else 'None'}")

        # === ОТПРАВКА ДОСТИЖЕНИЙ ===
        if new_achievements:
            debug_print(f"🏆 [ДОСТИЖЕНИЯ] Найдено {len(new_achievements)} достижений")
            for idx, ach in enumerate(new_achievements, 1):
                try:
                    ach_text = f"{ach[5]} **{ach[1]}** — {ach[2]}"
                    debug_print(f"   {idx}. Отправка: {ach[1]}")

                    if anchor:
                        await anchor.reply_text(ach_text, parse_mode='Markdown')
                    else:
                        await bot.send_message(chat_id=user_id, text=ach_text, parse_mode='Markdown')

                    debug_print(f"   ✅ Достижение отправлено: {ach[1]}")
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки достижения {ach[1]}: {e}")
                    debug_print(f"   ❌ Ошибка: {e}")
        else:
            debug_print("🏆 [ДОСТИЖЕНИЯ] Новых достижений нет")

        # === ПРОВЕРКА ЧЕЛЛЕНДЖЕЙ ===
        challenges = get_user_challenges(user_id)
        debug_print(f"🏆 [ЧЕЛЛЕНДЖИ] Найдено активных: {len(challenges) if challenges else 0}")

        if challenges:
            for idx, ch in enumerate(challenges, 1):
                ch_id, ch_target_type, ch_target_id, ch_target_value, ch_metric, bonus = ch
                debug_print(f"   {idx}. Челлендж ID={ch_id}, тип={ch_target_type}, цель={ch_target_value}")

                if ch_target_type == 'exercise' and ch_target_id == exercise_id:
                    debug_print(f"   ✅ Совпадение! Обновляем прогресс челленджа {ch_id}")
                    update_challenge_progress(user_id, ch_id, result_value)
                    debug_print(f"   📊 Прогресс обновлён")

                    if check_challenge_completion(user_id, ch_id, ch_target_value, ch_metric):
                        debug_print(f"   🎉 Челлендж {ch_id} выполнен!")
                        if complete_challenge(user_id, ch_id):
                            debug_print(f"   ✅ Челлендж {ch_id} завершён, бонус={bonus}")
                            await _send_challenge_completion_notification(bot, user_id, ch_id, bonus)
                        else:
                            debug_print(f"   ❌ Ошибка завершения челленджа {ch_id}")
                    else:
                        debug_print(f"   📊 Прогресс челленджа {ch_id}: цель ещё не достигнута")
                elif ch_target_type == 'complex' and complex_id and ch_target_id == complex_id:
                    # Если челлендж на комплекс, используем complex_reps для прогресса
                    debug_print(f"   ✅ Совпадение с комплексом! Обновляем прогресс челленджа {ch_id}")
                    progress_value = complex_reps if complex_reps else result_value
                    update_challenge_progress(user_id, ch_id, progress_value)
                    debug_print(f"   📊 Прогресс обновлён (значение={progress_value})")

                    if check_challenge_completion(user_id, ch_id, ch_target_value, ch_metric):
                        debug_print(f"   🎉 Челлендж {ch_id} выполнен!")
                        if complete_challenge(user_id, ch_id):
                            debug_print(f"   ✅ Челлендж {ch_id} завершён, бонус={bonus}")
                            await _send_challenge_completion_notification(bot, user_id, ch_id, bonus)
                        else:
                            debug_print(f"   ❌ Ошибка завершения челленджа {ch_id}")
                    else:
                        debug_print(f"   📊 Прогресс челленджа {ch_id}: цель ещё не достигнута")
                else:
                    debug_print(f"   ⏭️ Челлендж {ch_id} не подходит")

        # === ОТПРАВКА ФИНАЛЬНОГО СООБЩЕНИЯ ===
        if complex_id:
            done_text = (
                f"✅ Упражнение из комплекса успешно записано! Спасибо за честность.\n"
                f"Можешь посмотреть свои результаты командой /mystats, а таблицу лидеров — /top."
            )
        else:
            done_text = (
                "✅ Тренировка успешно записана! Спасибо за честность.\n"
                "Можешь посмотреть свои результаты командой /mystats, а таблицу лидеров — /top."
            )
        debug_print("📨 [СООБЩЕНИЕ] Отправка финального уведомления пользователю...")

        try:
            if anchor:
                await anchor.reply_text(done_text)
                debug_print("✅ [СООБЩЕНИЕ] Отправлено через anchor.reply_text")
            else:
                await bot.send_message(chat_id=user_id, text=done_text)
                debug_print("✅ [СООБЩЕНИЕ] Отправлено через bot.send_message")
        except Exception as e:
            logger.error(f"❌ [СООБЩЕНИЕ] Ошибка отправки: {e}")
            debug_print(f"❌ [СООБЩЕНИЕ] Ошибка: {e}")

        debug_print("✅ _finalize_workout: ВСЕ ОПЕРАЦИИ ВЫПОЛНЕНЫ УСПЕШНО")

    except Exception as e:
        # === ОБРАБОТКА КРИТИЧЕСКИХ ОШИБОК ===
        logger.error(f"❌ [КРИТИЧЕСКАЯ ОШИБКА] _finalize_workout: {e}", exc_info=True)
        debug_print(f"❌ [КРИТИЧЕСКАЯ ОШИБКА] {type(e).__name__}: {e}")

        # Отправляем сообщение об ошибке пользователю
        error_text = "❌ Произошла ошибка при сохранении тренировки. Пожалуйста, попробуйте ещё раз."

        try:
            if anchor:
                await anchor.reply_text(error_text)
                debug_print("📨 Отправлено сообщение об ошибке через anchor")
            elif update.callback_query:
                await update.callback_query.edit_message_text(error_text)
                debug_print("📨 Отправлено сообщение об ошибке через callback")
            elif update.message:
                await update.message.reply_text(error_text)
                debug_print("📨 Отправлено сообщение об ошибке через message")
            else:
                await update.get_bot().send_message(
                    chat_id=update.effective_user.id,
                    text=error_text
                )
                debug_print("📨 Отправлено сообщение об ошибке через bot")
        except Exception as send_error:
            logger.error(f"❌ Не удалось отправить сообщение об ошибке: {send_error}")
            debug_print(f"❌ Не удалось отправить сообщение об ошибке: {send_error}")

        return ConversationHandler.END

    finally:
        # === ОЧИСТКА ФЛАГОВ И ДАННЫХ ===
        debug_print("🧹 [ОЧИСТКА] Начинаем очистку данных...")

        # Удаляем флаг финализации
        if context.user_data.pop('_finalizing', None):
            debug_print("   ✅ Флаг '_finalizing' удалён")
        else:
            debug_print("   ⚠️ Флаг '_finalizing' не найден")

        # Небольшая задержка для гарантии отправки сообщений
        debug_print("   ⏳ Задержка 0.5 секунды перед очисткой user_data...")
        await asyncio.sleep(0.5)

        # Полная очистка user_data
        old_keys = list(context.user_data.keys())
        context.user_data.clear()
        debug_print(f"   ✅ user_data полностью очищен (было ключей: {len(old_keys)})")
        debug_print(f"   📋 Удалённые ключи: {old_keys}")

        debug_print("=" * 60)
        debug_print("🔥 _finalize_workout: ЗАВЕРШЕНИЕ (успешно)")
        debug_print("=" * 60)

    return ConversationHandler.END


@log_call
async def workout_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_data(update, context, "workout_start")
    debug_print(f"workout_start вызвана, pending_exercise={context.user_data.get('pending_exercise')}")
    debug_print(f"🔥 workout_start: pending_exercise={context.user_data.get('pending_exercise')}")
    debug_print(f"🔥 workout_start: pending_complex={context.user_data.get('pending_complex')}")
    debug_print(f"user_data в начале workout_start: {dict(context.user_data)}")

    if update.callback_query:
        user = update.callback_query.from_user
        reply_func = update.callback_query.message.reply_text
    else:
        user = update.effective_user
        reply_func = update.message.reply_text

    debug_print(f"🔥 workout_start: reply_func определена")

    user_level = get_user_level(user.id) or 'beginner'
    debug_print(f"🔥 workout_start: user_level={user_level}")
    add_user(user.id, user.first_name, user.last_name, user.username, user_level)

    # Если есть pending_complex — показываем упражнения комплекса
    if 'pending_complex' in context.user_data:
        debug_print(f"🔥 workout_start: ветка 'pending_complex'")
        complex_id = context.user_data.pop('pending_complex')

        # СОХРАНЯЕМ ИНФОРМАЦИЮ О КОМПЛЕКСЕ
        complex_data = get_complex_by_id(complex_id)
        if not complex_data:
            await reply_func("❌ Комплекс не найден.")
            debug_print(f"🔥 workout_start: ВОЗВРАТ {ConversationHandler.END}")
            return ConversationHandler.END

        # Сохраняем ID и тип комплекса в user_data
        context.user_data['current_complex_id'] = complex_id
        context.user_data['current_complex_type'] = complex_data[3]  # 'reps' или 'time'
        context.user_data['current_complex_name'] = complex_data[1]
        context.user_data['current_complex_points'] = complex_data[4]
        debug_print(
            f"🔥 workout_start: сохранён комплекс: id={complex_id}, type={complex_data[3]}, name={complex_data[1]}")

        exercises = get_complex_exercises(complex_id)
        if not exercises:
            await reply_func("❌ В этом комплексе нет упражнений.")
            debug_print(f"🔥 workout_start: ВОЗВРАТ {ConversationHandler.END}")
            return ConversationHandler.END

        text = f"🏋️ **{complex_data[1]}**\n{complex_data[2]}\n\nВыбери упражнение для выполнения:\n\n(Чтобы отменить, нажми '❌ Отмена' в главном меню)"
        keyboard = []
        for ex in exercises:
            ex_id = ex[2]
            ex_name = ex[3]
            reps = ex[4]
            keyboard.append([InlineKeyboardButton(f"💪 {ex_name} ({reps} раз)",
                                                  callback_data=f"complex_ex_{ex_id}_{complex_id}_{reps}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await reply_func(text, parse_mode='Markdown', reply_markup=reply_markup)
        debug_print(f"🔥 workout_start: ВОЗВРАТ {COMPLEX_EXERCISE}")
        return COMPLEX_EXERCISE

    # Если есть pending_exercise — сразу запрашиваем результат
    if 'pending_exercise' in context.user_data:
        debug_print(f"🔥 workout_start: ветка 'pending_exercise'")
        ex_id = context.user_data.pop('pending_exercise')
        ex = get_exercise_by_id(ex_id)
        if ex:
            context.user_data['exercise_id'] = ex_id
            metric = ex[3]
            context.user_data['metric'] = metric
            cancel_keyboard = ReplyKeyboardMarkup([["❌ Отмена"]], resize_keyboard=True)
            if metric == 'reps':
                await reply_func(
                    "🔢 Введи количество повторений (только число):\n\n(Чтобы отменить, нажми '❌ Отмена' в главном меню)",
                    reply_markup=cancel_keyboard)
            else:
                await reply_func(
                    "⏱️ Введи время в формате ММ:СС (например, 05:30):\n\n(Чтобы отменить, нажми '❌ Отмена' в главном меню)",
                    reply_markup=cancel_keyboard)
            debug_print(f"🔥 workout_start: ВОЗВРАТ {RESULT}")
            return RESULT
        else:
            await reply_func("❌ Упражнение не найдено. Начните заново командой /workout")
            debug_print(f"🔥 workout_start: ВОЗВРАТ {ConversationHandler.END}")
            return ConversationHandler.END

    # Обычный старт тренировки через /wod
    current_week = get_current_week()
    exercises = get_exercises(active_only=True, week=current_week, difficulty=user_level)
    if not exercises:
        await reply_func("❌ На этой неделе нет активных упражнений. Загляни позже!")
        debug_print(f"🔥 workout_start: ВОЗВРАТ {ConversationHandler.END}")
        return ConversationHandler.END

    keyboard = []
    for ex in exercises:
        ex_id, name, metric, points, week, difficulty = ex
        btn_text = f"{name} ({points} баллов)" if points else name
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"ex_{ex_id}")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])

    debug_print(f"🔥 workout_start: создана клавиатура с {len(keyboard)} кнопками")

    reply_markup = InlineKeyboardMarkup(keyboard)
    await reply_func("🏋️ Выбери упражнение, которое выполнил:", reply_markup=reply_markup)
    debug_print(f"🔥 workout_start: ВОЗВРАТ {EXERCISE}")
    return EXERCISE

@log_call
async def exercise_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_data(update, context, "exercise_choice")
    query = update.callback_query
    await query.answer()
    data = query.data

    debug_print(f"🔥 exercise_choice: ВЫЗВАНА, data={data}")
    debug_print(f"🔥 exercise_choice: data={data}")

    if data == "cancel":
        debug_print(f"🔥 exercise_choice: ветка 'cancel'")
        await query.edit_message_text("❌ Запись тренировки отменена.")
        context.user_data.clear()
        debug_print(f"🔥 exercise_choice: ВОЗВРАТ {ConversationHandler.END}")
        return ConversationHandler.END

    ex_id = int(data.split("_")[1])
    debug_print(f"🔥 exercise_choice: выбран ex_id={ex_id}")
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
        debug_print(f"🔥 exercise_choice: ВОЗВРАТ {ConversationHandler.END}")
        return ConversationHandler.END

    debug_print(f"🔥 exercise_choice: ex_metric={ex_metric}")
    context.user_data['metric'] = ex_metric
    prompt = "🔢 Введи количество повторений (только число):" if ex_metric == 'reps' else "⏱️ Введи время в формате ММ:СС (например, 05:30):"
    await query.edit_message_text(prompt)
    debug_print(f"🔥 exercise_choice: ВОЗВРАТ {RESULT}")
    return RESULT


@log_call
async def result_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_data(update, context, "result_input")
    text = update.message.text.strip()
    metric = context.user_data.get('metric')

    debug_print(f"🔥 result_input: text='{text}'")
    debug_print(f"🔥 result_input: metric='{metric}'")

    if not metric:
        await update.message.reply_text(
            "⚠️ Ошибка: не определён тип упражнения. Попробуйте начать заново через /workout")
        debug_print(f"🔥 result_input: ВОЗВРАТ {ConversationHandler.END}")
        return ConversationHandler.END

    if metric == 'reps':
        debug_print(f"🔥 result_input: text.isdigit()={text.isdigit()}")
        if not text.isdigit():
            await update.message.reply_text("❌ Пожалуйста, введи число (количество повторений).")
            debug_print(f"🔥 result_input: ВОЗВРАТ {RESULT}")
            return RESULT
        context.user_data['result_value'] = text
        debug_print(f"🔥 result_input: сохранено result_value={context.user_data.get('result_value')}")
    else:
        if not re.match(r'^\d{1,2}:\d{2}$', text):
            await update.message.reply_text("❌ Неправильный формат. Введи время как ММ:СС (например, 05:30).")
            debug_print(f"🔥 result_input: ВОЗВРАТ {RESULT}")
            return RESULT
        context.user_data['result_value'] = text
        debug_print(f"🔥 result_input: сохранено result_value={context.user_data.get('result_value')}")

    await update.message.reply_text("📎 Теперь отправь ссылку на видео с выполнением (Google Drive, YouTube и т.п.)")
    debug_print(f"🔥 result_input: ВОЗВРАТ {VIDEO}")
    return VIDEO


@log_call
async def video_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video_link = update.message.text.strip()
    debug_print(f"🔥 video_input: video_link='{video_link[:50]}...'")
    if not video_link.startswith(('http://', 'https://')):
        await update.message.reply_text(
            "❌ Это не похоже на ссылку. Попробуй ещё раз (должно начинаться с http:// или https://)")
        debug_print(f"🔥 video_input: ВОЗВРАТ {VIDEO}")
        return VIDEO
    debug_print(f"🔥 video_input: проверка ссылки прошла")
    context.user_data['video_link'] = video_link
    keyboard = [[InlineKeyboardButton("⏩ Пропустить", callback_data="skip_comment")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("💬 Добавь комментарий (или нажми кнопку):", reply_markup=reply_markup)
    debug_print(f"🔥 video_input: ВОЗВРАТ {COMMENT}")
    return COMMENT


@log_call
async def comment_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 comment_input: comment='{update.message.text}'")

    # Если нет активной тренировки, не продолжаем
    if not context.user_data.get('exercise_id'):
        debug_print("🔥 comment_input: нет exercise_id, игнорируем")
        await update.message.reply_text("❌ Нет активной тренировки. Начните новую командой /wod")
        return ConversationHandler.END

    debug_print(f"🔥 comment_input: ВОЗВРАТ {await _finalize_workout(update, context, comment=update.message.text)}")
    return await _finalize_workout(update, context, comment=update.message.text)


@log_call
async def comment_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 comment_skip: пропуск комментария")
    debug_print(f"🔥 comment_skip: ВОЗВРАТ {await _finalize_workout(update, context, comment=None)}")
    return await _finalize_workout(update, context, comment=None)


@log_call
async def comment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    debug_print(f"🔥 comment_handler: text='{text}'")

    # Если нет активной тренировки в user_data, просто игнорируем
    if not context.user_data.get('exercise_id'):
        debug_print("🔥 comment_handler: нет активной тренировки, игнорируем")
        await update.message.reply_text(
            "❌ Нет активной тренировки для добавления комментария. Начните новую тренировкой командой /wod")
        return ConversationHandler.END

    if text.lower() == '/skip':
        return await comment_skip(update, context)
    if text in ("🏋️ Спорт", "Спорт"):
        context.user_data.clear()
        from menu_handlers import sport_menu
        await sport_menu(update, context)
        debug_print(f"🔥 comment_handler: ВОЗВРАТ {ConversationHandler.END}")
        return ConversationHandler.END
    debug_print(f"🔥 comment_handler: ВОЗВРАТ {await comment_input(update, context)}")
    return await comment_input(update, context)


@log_call
async def skip_comment_finalize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 skip_comment_finalize: вызвана")
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✅ Тренировка сохранена без комментария.")
    debug_print(f"🔥 skip_comment_finalize: ВОЗВРАТ {await _finalize_workout(update, context, comment=None)}")
    return await _finalize_workout(update, context, comment=None)


@log_call
async def workout_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 workout_cancel: user_data до очистки: {context.user_data}")
    context.user_data.clear()
    debug_print(f"🔥 workout_cancel: user_data очищен")
    em = update.effective_message
    if em:
        await em.reply_text("❌ Запись тренировки отменена.")
    debug_print(f"🔥 workout_cancel: ВОЗВРАТ {ConversationHandler.END}")
    return ConversationHandler.END


@log_call
async def skip_comment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback для кнопки пропуска (обёртка)"""
    debug_print(f"🔥 skip_comment_callback: вызвана")
    return await skip_comment_finalize(update, context)