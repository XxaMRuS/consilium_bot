import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import get_all_exercises, get_setting
from database_backup import add_exercise

logger = logging.getLogger(__name__)

# Состояния для добавления упражнения
EXERCISE_NAME, EXERCISE_DESC, EXERCISE_METRIC, EXERCISE_POINTS, EXERCISE_WEEK, EXERCISE_DIFF = range(10, 16)

async def send_or_edit(update: Update, text: str, **kwargs):
    if update.callback_query:
        await update.callback_query.edit_message_text(text, **kwargs)
    else:
        await update.message.reply_text(text, **kwargs)

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🏋️ Управление упражнениями", callback_data="admin_exercises")],
        [InlineKeyboardButton("🏋️‍♂️ Управление комплексами", callback_data="admin_complexes")],
        [InlineKeyboardButton("🏆 Управление челленджами", callback_data="admin_challenges")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.edit_message_text("⚙️ **Админ-панель**\n\nВыберите раздел:", parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text("⚙️ **Админ-панель**\n\nВыберите раздел:", parse_mode='Markdown', reply_markup=reply_markup)

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back_to_main":
        from bot import start
        await start(update, context)
        return

    elif data == "admin_exercises":
        await admin_exercises_menu(update, context)
        return

    elif data == "admin_complexes":
        await admin_complexes_menu(update, context)
        return

    elif data == "admin_challenges":
        await admin_challenges_menu(update, context)
        return

    elif data == "admin_stats":
        await admin_stats_menu(update, context)
        return

    elif data == "admin_settings":
        await admin_settings_menu(update, context)
        return

    elif data == "admin_back":
        await admin_menu(update, context)
        return

    elif data == "admin_ex_list":
        await admin_exercise_list(update, context)
        return

    elif data == "admin_ex_add":
        await admin_exercise_add_start(update, context)
        return

    elif data == "admin_ex_edit":
        await send_or_edit(update, "✏️ Редактирование упражнений:\n\nИспользуйте команду `/editexercise <id>`", parse_mode='Markdown')
        return

    elif data == "admin_ex_delete":
        await send_or_edit(update, "🗑️ Удаление упражнения:\n\nИспользуйте команду `/delexercise <id>`", parse_mode='Markdown')
        return

    elif data == "admin_cx_list":
        from bot import complexes_command
        await complexes_command(update, context)
        return

    elif data == "admin_cx_add":
        from bot import newcomplex_start
        await newcomplex_start(update, context)
        return

    elif data == "admin_cx_edit":
        await send_or_edit(update, "✏️ Редактирование комплекса:\n\nИспользуйте команду `/editcomplex <id>`", parse_mode='Markdown')
        return

    elif data == "admin_cx_delete":
        await send_or_edit(update, "🗑️ Удаление комплекса:\n\nИспользуйте команду `/deletecomplex <id>`", parse_mode='Markdown')
        return

    elif data == "admin_ch_list":
        from bot import challenges_command
        await challenges_command(update, context)
        return

    elif data == "admin_ch_add":
        from bot import addchallenge_start
        await addchallenge_start(update, context)
        return

    elif data == "admin_ch_edit":
        await send_or_edit(update, "✏️ Редактирование челленджа:\n\nИспользуйте команду `/editchallenge <id>`", parse_mode='Markdown')
        return

    elif data == "admin_ch_delete":
        await send_or_edit(update, "🗑️ Удаление челленджа:\n\nИспользуйте команду `/deletechallenge <id>`", parse_mode='Markdown')
        return

    elif data == "admin_stats_bot":
        from bot import config_command
        await config_command(update, context)
        return

    elif data == "admin_stats_top":
        from bot import top_command
        await top_command(update, context)
        return

    elif data == "admin_stats_challenges":
        from bot import challenges_command
        await challenges_command(update, context)
        return

    elif data == "admin_stats_workouts":
        from bot import mystats_command
        await mystats_command(update, context)
        return

    elif data == "admin_settings_channel":
        channel = get_setting("public_channel")
        await send_or_edit(update, f"📢 Текущий канал: {channel if channel else 'не установлен'}\n\nИспользуйте команду `/set_channel <id>`", parse_mode='Markdown')
        return

    elif data == "admin_settings_ai":
        from bot import config_command
        await config_command(update, context)
        return

    elif data == "admin_settings_recalc":
        from bot import recalc_rankings_command
        await recalc_rankings_command(update, context)
        return

    else:
        await send_or_edit(update, "⚠️ Раздел в разработке.")

async def admin_exercises_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📋 Список упражнений", callback_data="admin_ex_list")],
        [InlineKeyboardButton("➕ Добавить упражнение", callback_data="admin_ex_add")],
        [InlineKeyboardButton("✏️ Редактировать", callback_data="admin_ex_edit")],
        [InlineKeyboardButton("🗑️ Удалить", callback_data="admin_ex_delete")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_back")],
    ]
    await update.callback_query.edit_message_text("🏋️ **Управление упражнениями**", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_complexes_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📋 Список комплексов", callback_data="admin_cx_list")],
        [InlineKeyboardButton("➕ Добавить комплекс", callback_data="admin_cx_add")],
        [InlineKeyboardButton("✏️ Редактировать", callback_data="admin_cx_edit")],
        [InlineKeyboardButton("🗑️ Удалить", callback_data="admin_cx_delete")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_back")],
    ]
    await update.callback_query.edit_message_text("🏋️‍♂️ **Управление комплексами**", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_challenges_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📋 Список челленджей", callback_data="admin_ch_list")],
        [InlineKeyboardButton("➕ Добавить челлендж", callback_data="admin_ch_add")],
        [InlineKeyboardButton("✏️ Редактировать", callback_data="admin_ch_edit")],
        [InlineKeyboardButton("🗑️ Удалить", callback_data="admin_ch_delete")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_back")],
    ]
    await update.callback_query.edit_message_text("🏆 **Управление челленджами**", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_stats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 Статистика AI", callback_data="admin_stats_bot")],
        [InlineKeyboardButton("🏆 Топ пользователей", callback_data="admin_stats_top")],
        [InlineKeyboardButton("🏆 Топ челленджей", callback_data="admin_stats_challenges")],
        [InlineKeyboardButton("📋 Мои тренировки", callback_data="admin_stats_workouts")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_back")],
    ]
    await update.callback_query.edit_message_text("📊 **Статистика**", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📢 Канал публикаций", callback_data="admin_settings_channel")],
        [InlineKeyboardButton("🤖 Настройка AI", callback_data="admin_settings_ai")],
        [InlineKeyboardButton("🔄 Пересчёт рейтинга", callback_data="admin_settings_recalc")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_back")],
    ]
    await update.callback_query.edit_message_text("⚙️ **Настройки**", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_exercise_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    exercises = get_all_exercises()
    if not exercises:
        await update.callback_query.edit_message_text("📋 Список упражнений пуст.")
        return
    text = "📋 **Список упражнений:**\n\n"
    for ex in exercises:
        text += f"🔹 ID: {ex[0]} — {ex[1]} ({ex[5]})\n"
    await update.callback_query.edit_message_text(text, parse_mode='Markdown')

async def admin_exercise_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text("Введите название упражнения:")
    return EXERCISE_NAME

async def admin_exercise_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ex_name'] = update.message.text
    await update.message.reply_text("Введите описание (можно пропустить, отправьте '-'):")
    return EXERCISE_DESC

async def admin_exercise_add_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text
    if desc == '-':
        desc = ''
    context.user_data['ex_desc'] = desc
    keyboard = [
        [InlineKeyboardButton("🔢 Повторения (reps)", callback_data="ex_metric_reps")],
        [InlineKeyboardButton("⏱️ Время (time)", callback_data="ex_metric_time")],
    ]
    await update.message.reply_text("Выберите тип упражнения:", reply_markup=InlineKeyboardMarkup(keyboard))
    return EXERCISE_METRIC

async def admin_exercise_add_metric(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    metric = query.data.split('_')[2]
    context.user_data['ex_metric'] = metric
    await query.edit_message_text("Введите количество баллов (целое число):")
    return EXERCISE_POINTS

async def admin_exercise_add_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        points = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Введите целое число баллов.")
        return EXERCISE_POINTS
    context.user_data['ex_points'] = points
    await update.message.reply_text("Введите неделю (0 — всегда доступно):")
    return EXERCISE_WEEK

async def admin_exercise_add_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        week = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Введите целое число.")
        return EXERCISE_WEEK
    context.user_data['ex_week'] = week
    keyboard = [
        [InlineKeyboardButton("👶 Новичок (beginner)", callback_data="ex_diff_beginner")],
        [InlineKeyboardButton("🏆 Профи (pro)", callback_data="ex_diff_pro")],
    ]
    await update.message.reply_text("Выберите уровень сложности:", reply_markup=InlineKeyboardMarkup(keyboard))
    return EXERCISE_DIFF

async def admin_exercise_add_diff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    diff = query.data.split('_')[2]
    success = add_exercise(
        name=context.user_data['ex_name'],
        description=context.user_data['ex_desc'],
        metric=context.user_data['ex_metric'],
        points=context.user_data['ex_points'],
        week=context.user_data['ex_week'],
        difficulty=diff
    )
    if success:
        await query.edit_message_text(f"✅ Упражнение «{context.user_data['ex_name']}» добавлено!")
    else:
        await query.edit_message_text("❌ Ошибка при добавлении.")
    context.user_data.clear()
    return ConversationHandler.END

async def admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ Операция отменена.")
    else:
        await update.message.reply_text("❌ Операция отменена.")
    context.user_data.clear()
    return ConversationHandler.END