import logging
import re
from datetime import datetime
from functools import wraps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import get_all_exercises, get_setting
from database_backup import add_exercise

# ==================== ДЕБАГ-РЕЖИМ ====================
from debug_utils import debug_print, log_call, log_user_data, log_state_change, log_callback, log_message, DEBUG_MODE

# ==================== НАСТРОЙКА ЛОГИРОВАНИЯ ====================
logger = logging.getLogger(__name__)

# Состояния для добавления упражнения
EXERCISE_NAME, EXERCISE_DESC, EXERCISE_METRIC, EXERCISE_POINTS, EXERCISE_WEEK, EXERCISE_DIFF = range(10, 16)


# ==================== ОСНОВНЫЕ ФУНКЦИИ ====================
@log_call
async def send_or_edit(update: Update, text: str, **kwargs):
    log_user_data(update, None, "send_or_edit")
    debug_print(f"🔥 send_or_edit: text={text[:100] if text else 'None'}")
    debug_print(f"🔥 send_or_edit: kwargs={kwargs}")
    if update.callback_query:
        debug_print(f"🔥 send_or_edit: это callback_query, редактируем сообщение")
        await update.callback_query.edit_message_text(text, **kwargs)
    else:
        debug_print(f"🔥 send_or_edit: это обычное сообщение, отправляем новое")
        await update.message.reply_text(text, **kwargs)
    debug_print(f"🔥 send_or_edit: ВОЗВРАТ None")


@log_call
async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_data(update, context, "admin_menu")
    debug_print(f"🔥 admin_menu: вызвана")
    debug_print(f"🔥 admin_menu: user_id={update.effective_user.id}")
    debug_print(f"📦 user_data на входе: {context.user_data if context else 'Нет context'}")

    keyboard = [
        [InlineKeyboardButton("🏋️ Управление упражнениями", callback_data="admin_exercises")],
        [InlineKeyboardButton("🏋️‍♂️ Управление комплексами", callback_data="admin_complexes")],
        [InlineKeyboardButton("🏆 Управление челленджами", callback_data="admin_challenges")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    debug_print(f"🔥 admin_menu: отправка клавиатуры")

    if update.callback_query:
        await update.callback_query.edit_message_text("⚙️ **Админ-панель**\n\nВыберите раздел:", parse_mode='Markdown',
                                                      reply_markup=reply_markup)
    else:
        await update.message.reply_text("⚙️ **Админ-панель**\n\nВыберите раздел:", parse_mode='Markdown',
                                        reply_markup=reply_markup)

    debug_print(f"🔥 admin_menu: ВОЗВРАТ None")


@log_call
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_data(update, context, f"admin_callback: {update.callback_query.data if update.callback_query else 'None'}")
    query = update.callback_query
    await query.answer()
    data = query.data

    debug_print(f"🔥 admin_callback: data={data}")
    debug_print(f"🔥 admin_callback: user_id={update.effective_user.id}")
    debug_print(f"🔥 admin_callback: is_admin={True}")  # Предполагаем, что админ, т.к. функция доступна только админам
    debug_print(f"🔥 admin_callback: user_data={context.user_data}")
    debug_print(f"📦 user_data на входе: {context.user_data if context else 'Нет context'}")

    if data == "back_to_main":
        debug_print(f"🔥 admin_callback: ветка back_to_main")
        from bot import start
        await start(update, context)
        debug_print(f"🔥 admin_callback: ВОЗВРАТ None")
        return

    elif data == "admin_exercises":
        debug_print(f"🔥 admin_callback: ветка admin_exercises")
        await admin_exercises_menu(update, context)
        debug_print(f"🔥 admin_callback: ВОЗВРАТ None")
        return

    elif data == "admin_complexes":
        debug_print(f"🔥 admin_callback: ветка admin_complexes")
        await admin_complexes_menu(update, context)
        debug_print(f"🔥 admin_callback: ВОЗВРАТ None")
        return

    elif data == "admin_challenges":
        debug_print(f"🔥 admin_callback: ветка admin_challenges")
        await admin_challenges_menu(update, context)
        debug_print(f"🔥 admin_callback: ВОЗВРАТ None")
        return

    elif data == "admin_stats":
        debug_print(f"🔥 admin_callback: ветка admin_stats")
        await admin_stats_menu(update, context)
        debug_print(f"🔥 admin_callback: ВОЗВРАТ None")
        return

    elif data == "admin_settings":
        debug_print(f"🔥 admin_callback: ветка admin_settings")
        await admin_settings_menu(update, context)
        debug_print(f"🔥 admin_callback: ВОЗВРАТ None")
        return

    elif data == "admin_back":
        debug_print(f"🔥 admin_callback: ветка admin_back")
        await admin_menu(update, context)
        debug_print(f"🔥 admin_callback: ВОЗВРАТ None")
        return

    elif data == "admin_ex_list":
        debug_print(f"🔥 admin_callback: ветка admin_ex_list")
        await admin_exercise_list(update, context)
        debug_print(f"🔥 admin_callback: ВОЗВРАТ None")
        return

    elif data == "admin_ex_add":
        debug_print(f"🔥 admin_callback: ветка admin_ex_add")
        await admin_exercise_add_start(update, context)
        debug_print(f"🔥 admin_callback: ВОЗВРАТ None")
        return

    elif data == "admin_ex_edit":
        debug_print(f"🔥 admin_callback: ветка admin_ex_edit")
        await send_or_edit(update, "✏️ Редактирование упражнений:\n\nИспользуйте команду `/editexercise <id>`",
                           parse_mode='Markdown')
        debug_print(f"🔥 admin_callback: ВОЗВРАТ None")
        return

    elif data == "admin_ex_delete":
        debug_print(f"🔥 admin_callback: ветка admin_ex_delete")
        await send_or_edit(update, "🗑️ Удаление упражнения:\n\nИспользуйте команду `/delexercise <id>`",
                           parse_mode='Markdown')
        debug_print(f"🔥 admin_callback: ВОЗВРАТ None")
        return

    elif data == "admin_cx_list":
        debug_print(f"🔥 admin_callback: ветка admin_cx_list")
        from bot import complexes_command
        await complexes_command(update, context)
        debug_print(f"🔥 admin_callback: ВОЗВРАТ None")
        return

    elif data == "admin_cx_add":
        debug_print(f"🔥 admin_callback: ветка admin_cx_add")
        from bot import newcomplex_start
        await newcomplex_start(update, context)
        debug_print(f"🔥 admin_callback: ВОЗВРАТ None")
        return

    elif data == "admin_cx_edit":
        debug_print(f"🔥 admin_callback: ветка admin_cx_edit")
        await send_or_edit(update, "✏️ Редактирование комплекса:\n\nИспользуйте команду `/editcomplex <id>`",
                           parse_mode='Markdown')
        debug_print(f"🔥 admin_callback: ВОЗВРАТ None")
        return

    elif data == "admin_cx_delete":
        debug_print(f"🔥 admin_callback: ветка admin_cx_delete")
        await send_or_edit(update, "🗑️ Удаление комплекса:\n\nИспользуйте команду `/deletecomplex <id>`",
                           parse_mode='Markdown')
        debug_print(f"🔥 admin_callback: ВОЗВРАТ None")
        return

    elif data == "admin_ch_list":
        debug_print(f"🔥 admin_callback: ветка admin_ch_list")
        from bot import challenges_command
        await challenges_command(update, context)
        debug_print(f"🔥 admin_callback: ВОЗВРАТ None")
        return

    elif data == "admin_ch_add":
        debug_print(f"🔥 admin_callback: ветка admin_ch_add")
        from bot import addchallenge_start
        await addchallenge_start(update, context)
        debug_print(f"🔥 admin_callback: ВОЗВРАТ None")
        return

    elif data == "admin_ch_edit":
        debug_print(f"🔥 admin_callback: ветка admin_ch_edit")
        await send_or_edit(update, "✏️ Редактирование челленджа:\n\nИспользуйте команду `/editchallenge <id>`",
                           parse_mode='Markdown')
        debug_print(f"🔥 admin_callback: ВОЗВРАТ None")
        return

    elif data == "admin_ch_delete":
        debug_print(f"🔥 admin_callback: ветка admin_ch_delete")
        await send_or_edit(update, "🗑️ Удаление челленджа:\n\nИспользуйте команду `/deletechallenge <id>`",
                           parse_mode='Markdown')
        debug_print(f"🔥 admin_callback: ВОЗВРАТ None")
        return

    elif data == "admin_stats_bot":
        debug_print(f"🔥 admin_callback: ветка admin_stats_bot")
        from bot import config_command
        await config_command(update, context)
        debug_print(f"🔥 admin_callback: ВОЗВРАТ None")
        return

    elif data == "admin_stats_top":
        debug_print(f"🔥 admin_callback: ветка admin_stats_top")
        from bot import top_command
        await top_command(update, context)
        debug_print(f"🔥 admin_callback: ВОЗВРАТ None")
        return

    elif data == "admin_stats_challenges":
        debug_print(f"🔥 admin_callback: ветка admin_stats_challenges")
        from bot import challenges_command
        await challenges_command(update, context)
        debug_print(f"🔥 admin_callback: ВОЗВРАТ None")
        return

    elif data == "admin_stats_workouts":
        debug_print(f"🔥 admin_callback: ветка admin_stats_workouts")
        from bot import mystats_command
        await mystats_command(update, context)
        debug_print(f"🔥 admin_callback: ВОЗВРАТ None")
        return

    elif data == "admin_settings_channel":
        debug_print(f"🔥 admin_callback: ветка admin_settings_channel")
        channel = get_setting("public_channel")
        await send_or_edit(update,
                           f"📢 Текущий канал: {channel if channel else 'не установлен'}\n\nИспользуйте команду `/set_channel <id>`",
                           parse_mode='Markdown')
        debug_print(f"🔥 admin_callback: ВОЗВРАТ None")
        return

    elif data == "admin_settings_ai":
        debug_print(f"🔥 admin_callback: ветка admin_settings_ai")
        from bot import config_command
        await config_command(update, context)
        debug_print(f"🔥 admin_callback: ВОЗВРАТ None")
        return

    elif data == "admin_settings_recalc":
        debug_print(f"🔥 admin_callback: ветка admin_settings_recalc")
        from bot import recalc_rankings_command
        await recalc_rankings_command(update, context)
        debug_print(f"🔥 admin_callback: ВОЗВРАТ None")
        return

    else:
        debug_print(f"🔥 admin_callback: неизвестный callback {data}")
        await send_or_edit(update, "⚠️ Раздел в разработке.")
        debug_print(f"🔥 admin_callback: ВОЗВРАТ None")
        return


@log_call
async def admin_exercises_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_data(update, context, "admin_exercises_menu")
    debug_print(f"🔥 admin_exercises_menu: вызвана")
    debug_print(f"🔥 admin_exercises_menu: user_data={context.user_data}")
    debug_print(f"📦 user_data на входе: {context.user_data if context else 'Нет context'}")

    keyboard = [
        [InlineKeyboardButton("📋 Список упражнений", callback_data="admin_ex_list")],
        [InlineKeyboardButton("➕ Добавить упражнение", callback_data="admin_ex_add")],
        [InlineKeyboardButton("✏️ Редактировать", callback_data="admin_ex_edit")],
        [InlineKeyboardButton("🗑️ Удалить", callback_data="admin_ex_delete")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_back")],
    ]

    debug_print(f"🔥 admin_exercises_menu: отправка списка упражнений")
    await update.callback_query.edit_message_text("🏋️ **Управление упражнениями**", parse_mode='Markdown',
                                                  reply_markup=InlineKeyboardMarkup(keyboard))

    debug_print(f"🔥 admin_exercises_menu: ВОЗВРАТ None")


@log_call
async def admin_complexes_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_data(update, context, "admin_complexes_menu")
    debug_print(f"🔥 admin_complexes_menu: вызвана")
    debug_print(f"🔥 admin_complexes_menu: user_data={context.user_data}")
    debug_print(f"📦 user_data на входе: {context.user_data if context else 'Нет context'}")

    keyboard = [
        [InlineKeyboardButton("📋 Список комплексов", callback_data="admin_cx_list")],
        [InlineKeyboardButton("➕ Добавить комплекс", callback_data="admin_cx_add")],
        [InlineKeyboardButton("✏️ Редактировать", callback_data="admin_cx_edit")],
        [InlineKeyboardButton("🗑️ Удалить", callback_data="admin_cx_delete")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_back")],
    ]

    debug_print(f"🔥 admin_complexes_menu: отправка списка комплексов")
    await update.callback_query.edit_message_text("🏋️‍♂️ **Управление комплексами**", parse_mode='Markdown',
                                                  reply_markup=InlineKeyboardMarkup(keyboard))

    debug_print(f"🔥 admin_complexes_menu: ВОЗВРАТ None")


@log_call
async def admin_challenges_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_data(update, context, "admin_challenges_menu")
    debug_print(f"🔥 admin_challenges_menu: вызвана")
    debug_print(f"🔥 admin_challenges_menu: user_data={context.user_data}")
    debug_print(f"📦 user_data на входе: {context.user_data if context else 'Нет context'}")

    keyboard = [
        [InlineKeyboardButton("📋 Список челленджей", callback_data="admin_ch_list")],
        [InlineKeyboardButton("➕ Добавить челлендж", callback_data="admin_ch_add")],
        [InlineKeyboardButton("✏️ Редактировать", callback_data="admin_ch_edit")],
        [InlineKeyboardButton("🗑️ Удалить", callback_data="admin_ch_delete")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_back")],
    ]

    debug_print(f"🔥 admin_challenges_menu: отправка списка челленджей")
    await update.callback_query.edit_message_text("🏆 **Управление челленджами**", parse_mode='Markdown',
                                                  reply_markup=InlineKeyboardMarkup(keyboard))

    debug_print(f"🔥 admin_challenges_menu: ВОЗВРАТ None")


@log_call
async def admin_stats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_data(update, context, "admin_stats_menu")
    debug_print(f"🔥 admin_stats_menu: вызвана")
    debug_print(f"📦 user_data на входе: {context.user_data if context else 'Нет context'}")

    keyboard = [
        [InlineKeyboardButton("📊 Статистика AI", callback_data="admin_stats_bot")],
        [InlineKeyboardButton("🏆 Топ пользователей", callback_data="admin_stats_top")],
        [InlineKeyboardButton("🏆 Топ челленджей", callback_data="admin_stats_challenges")],
        [InlineKeyboardButton("📋 Мои тренировки", callback_data="admin_stats_workouts")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_back")],
    ]
    await update.callback_query.edit_message_text("📊 **Статистика**", parse_mode='Markdown',
                                                  reply_markup=InlineKeyboardMarkup(keyboard))

    debug_print(f"🔥 admin_stats_menu: ВОЗВРАТ None")


@log_call
async def admin_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_data(update, context, "admin_settings_menu")
    debug_print(f"🔥 admin_settings_menu: вызвана")
    debug_print(f"📦 user_data на входе: {context.user_data if context else 'Нет context'}")

    keyboard = [
        [InlineKeyboardButton("📢 Канал публикаций", callback_data="admin_settings_channel")],
        [InlineKeyboardButton("🤖 Настройка AI", callback_data="admin_settings_ai")],
        [InlineKeyboardButton("🔄 Пересчёт рейтинга", callback_data="admin_settings_recalc")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_back")],
    ]
    await update.callback_query.edit_message_text("⚙️ **Настройки**", parse_mode='Markdown',
                                                  reply_markup=InlineKeyboardMarkup(keyboard))

    debug_print(f"🔥 admin_settings_menu: ВОЗВРАТ None")


@log_call
async def admin_exercise_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_data(update, context, "admin_exercise_list")
    debug_print(f"🔥 admin_exercise_list: вызвана")
    debug_print(f"📦 user_data на входе: {context.user_data if context else 'Нет context'}")

    exercises = get_all_exercises()
    debug_print(f"🔥 admin_exercise_list: all_exercises={exercises}")

    if not exercises:
        await update.callback_query.edit_message_text("📋 Список упражнений пуст.")
        debug_print(f"🔥 admin_exercise_list: ВОЗВРАТ None")
        return

    text = "📋 **Список упражнений:**\n\n"
    for ex in exercises:
        text += f"🔹 ID: {ex[0]} — {ex[1]} ({ex[5]})\n"

    debug_print(f"🔥 admin_exercise_list: отправка списка")
    await update.callback_query.edit_message_text(text, parse_mode='Markdown')

    debug_print(f"🔥 admin_exercise_list: ВОЗВРАТ None")


@log_call
async def admin_exercise_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_data(update, context, "admin_exercise_add_start")
    debug_print(f"🔥 admin_exercise_add_start: вызвана")
    debug_print(f"🔥 admin_exercise_add_start: user_data={context.user_data}")
    debug_print(f"📦 user_data на входе: {context.user_data if context else 'Нет context'}")

    await update.callback_query.edit_message_text("Введите название упражнения:")

    return_value = EXERCISE_NAME
    debug_print(f"🔥 admin_exercise_add_start: ВОЗВРАТ {return_value}")
    return return_value


@log_call
async def admin_exercise_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_data(update, context, "admin_exercise_add_name")
    debug_print(f"🔥 admin_exercise_add_name: name={update.message.text}")
    debug_print(f"🔥 admin_exercise_add_name: user_data={context.user_data}")
    debug_print(f"📦 user_data на входе: {context.user_data if context else 'Нет context'}")

    context.user_data['ex_name'] = update.message.text
    await update.message.reply_text("Введите описание (можно пропустить, отправьте '-'):")

    return_value = EXERCISE_DESC
    debug_print(f"🔥 admin_exercise_add_name: ВОЗВРАТ {return_value}")
    return return_value


@log_call
async def admin_exercise_add_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_data(update, context, "admin_exercise_add_desc")
    debug_print(f"🔥 admin_exercise_add_desc: description={update.message.text}")
    debug_print(f"📦 user_data на входе: {context.user_data if context else 'Нет context'}")

    desc = update.message.text
    if desc == '-':
        desc = ''
    context.user_data['ex_desc'] = desc

    keyboard = [
        [InlineKeyboardButton("🔢 Повторения (reps)", callback_data="ex_metric_reps")],
        [InlineKeyboardButton("⏱️ Время (time)", callback_data="ex_metric_time")],
    ]
    await update.message.reply_text("Выберите тип упражнения:", reply_markup=InlineKeyboardMarkup(keyboard))

    return_value = EXERCISE_METRIC
    debug_print(f"🔥 admin_exercise_add_desc: ВОЗВРАТ {return_value}")
    return return_value


@log_call
async def admin_exercise_add_metric(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_data(update, context, "admin_exercise_add_metric")
    query = update.callback_query
    await query.answer()
    data = query.data
    metric = data.split('_')[2]

    debug_print(f"🔥 admin_exercise_add_metric: data={data}")
    debug_print(f"🔥 admin_exercise_add_metric: metric={metric}")
    debug_print(f"📦 user_data на входе: {context.user_data if context else 'Нет context'}")

    context.user_data['ex_metric'] = metric
    await query.edit_message_text("Введите количество баллов (целое число):")

    return_value = EXERCISE_POINTS
    debug_print(f"🔥 admin_exercise_add_metric: ВОЗВРАТ {return_value}")
    return return_value


@log_call
async def admin_exercise_add_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_data(update, context, "admin_exercise_add_points")
    debug_print(f"🔥 admin_exercise_add_points: points={update.message.text}")
    debug_print(f"📦 user_data на входе: {context.user_data if context else 'Нет context'}")

    try:
        points = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Введите целое число баллов.")
        return_value = EXERCISE_POINTS
        debug_print(f"🔥 admin_exercise_add_points: ВОЗВРАТ {return_value}")
        return return_value

    context.user_data['ex_points'] = points
    await update.message.reply_text("Введите неделю (0 — всегда доступно):")

    return_value = EXERCISE_WEEK
    debug_print(f"🔥 admin_exercise_add_points: ВОЗВРАТ {return_value}")
    return return_value


@log_call
async def admin_exercise_add_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_data(update, context, "admin_exercise_add_week")
    debug_print(f"🔥 admin_exercise_add_week: week={update.message.text}")
    debug_print(f"📦 user_data на входе: {context.user_data if context else 'Нет context'}")

    try:
        week = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Введите целое число.")
        return_value = EXERCISE_WEEK
        debug_print(f"🔥 admin_exercise_add_week: ВОЗВРАТ {return_value}")
        return return_value

    context.user_data['ex_week'] = week

    keyboard = [
        [InlineKeyboardButton("👶 Новичок (beginner)", callback_data="ex_diff_beginner")],
        [InlineKeyboardButton("🏆 Профи (pro)", callback_data="ex_diff_pro")],
    ]
    await update.message.reply_text("Выберите уровень сложности:", reply_markup=InlineKeyboardMarkup(keyboard))

    return_value = EXERCISE_DIFF
    debug_print(f"🔥 admin_exercise_add_week: ВОЗВРАТ {return_value}")
    return return_value


@log_call
async def admin_exercise_add_diff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_data(update, context, "admin_exercise_add_diff")
    query = update.callback_query
    await query.answer()
    data = query.data
    difficulty = data.split('_')[2]

    debug_print(f"🔥 admin_exercise_add_diff: data={data}")
    debug_print(f"🔥 admin_exercise_add_diff: difficulty={difficulty}")
    debug_print(f"🔥 admin_exercise_add_diff: user_data={dict(context.user_data)}")
    debug_print(f"📦 user_data на входе: {context.user_data if context else 'Нет context'}")

    debug_print(f"🔥 admin_exercise_add_diff: сохранение упражнения")
    success = add_exercise(
        name=context.user_data['ex_name'],
        description=context.user_data['ex_desc'],
        metric=context.user_data['ex_metric'],
        points=context.user_data['ex_points'],
        week=context.user_data['ex_week'],
        difficulty=difficulty
    )

    debug_print(f"🔥 admin_exercise_add_diff: результат сохранения={success}")

    if success:
        await query.edit_message_text(f"✅ Упражнение «{context.user_data['ex_name']}» добавлено!")
    else:
        await query.edit_message_text("❌ Ошибка при добавлении.")

    context.user_data.clear()
    debug_print(f"🔥 admin_exercise_add_diff: user_data очищен")

    return_value = ConversationHandler.END
    debug_print(f"🔥 admin_exercise_add_diff: ВОЗВРАТ {return_value}")
    return return_value


@log_call
async def admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_data(update, context, "admin_cancel")
    debug_print(f"🔥 admin_cancel: вызвана")
    debug_print(f"📦 user_data на входе: {context.user_data if context else 'Нет context'}")

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ Операция отменена.")
    else:
        await update.message.reply_text("❌ Операция отменена.")

    context.user_data.clear()
    debug_print(f"🔥 admin_cancel: user_data очищен")

    return_value = ConversationHandler.END
    debug_print(f"🔥 admin_cancel: ВОЗВРАТ {return_value}")
    return return_value