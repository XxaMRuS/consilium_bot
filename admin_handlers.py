import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

# Состояния для добавления упражнения
(
    EXERCISE_NAME,
    EXERCISE_DESC,
    EXERCISE_METRIC,
    EXERCISE_POINTS,
    EXERCISE_WEEK,
    EXERCISE_DIFF,
) = range(10, 16)


async def send_or_edit(update: Update, text: str, **kwargs):
    """Универсальная отправка/редактирование сообщения."""
    if update.callback_query:
        await update.callback_query.edit_message_text(text, **kwargs)
    else:
        await update.message.reply_text(text, **kwargs)


async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает главное админ-меню."""
    keyboard = [
        [InlineKeyboardButton("🏋️ Управление упражнениями", callback_data="admin_exercises")],
        [InlineKeyboardButton("🏋️‍♂️ Управление комплексами", callback_data="admin_complexes")],
        [InlineKeyboardButton("🏆 Управление челленджами", callback_data="admin_challenges")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(
            "⚙️ **Админ-панель**\n\nВыберите раздел:",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    else:
        await update.callback_query.edit_message_text(
            "⚙️ **Админ-панель**\n\nВыберите раздел:",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import logging
    logger = logging.getLogger(__name__)

    query = update.callback_query
    logger.info(f"admin_callback: ВСЕГДА data={query.data}")  # добавить эту строку
    await query.answer()
    data = query.data
    # ...

    logger.info(f"admin_callback: data={data}")

    # ========== ГЛАВНОЕ МЕНЮ ==========
    if data == "back_to_main":
        from bot import start
        await start(update, context)
        return

    # ========== РАЗДЕЛ УПРАЖНЕНИЯ ==========
    elif data == "admin_exercises":
        await admin_exercises_menu(update, context)
        return

    elif data == "admin_ex_list":
        await admin_exercise_list(update, context)
        return

    elif data == "admin_ex_edit":
        await send_or_edit(update, "✏️ Редактирование упражнений:\n\n"
                                   "Используйте команду:\n"
                                   "`/setexerciseweek <id> <неделя>`\n"
                                   "`/setexercisepoints <id> <баллы>`",
                           parse_mode='Markdown')
        return

    elif data == "admin_ex_delete":
        await send_or_edit(update, "🗑️ Удаление упражнения:\n\n"
                                   "Используйте команду:\n"
                                   "`/delexercise <id>`",
                           parse_mode='Markdown')
        return

    # ========== РАЗДЕЛ КОМПЛЕКСЫ ==========
    elif data == "admin_complexes":
        await admin_complexes_menu(update, context)
        return

    elif data == "admin_cx_list":
        from bot import complexes_command
        await complexes_command(update, context)
        return

    elif data == "admin_cx_edit":
        await send_or_edit(update, "✏️ Редактирование комплекса:\n\n"
                                   "Используйте команду:\n"
                                   "`/editcomplex <id>`",
                           parse_mode='Markdown')
        return

    elif data == "admin_cx_delete":
        await send_or_edit(update, "🗑️ Удаление комплекса:\n\n"
                                   "Используйте команду:\n"
                                   "`/deletecomplex <id>`",
                           parse_mode='Markdown')
        return

    # ========== РАЗДЕЛ ЧЕЛЛЕНДЖИ ==========
    elif data == "admin_challenges":
        await admin_challenges_menu(update, context)
        return

    elif data == "admin_ch_list":
        from bot import challenges_command
        await challenges_command(update, context)
        return


    elif data == "admin_ch_edit":
        from bot import edit_challenge_start
        return await edit_challenge_start(update, context)


    elif data == "admin_ch_delete":
        from bot import delete_challenge_start
        return await delete_challenge_start(update, context)

    # ========== СТАТИСТИКА ==========
    elif data == "admin_stats":
        await admin_stats_menu(update, context)
        return



    elif data == "admin_stats_bot":
        from ai_work import stats as consilium_stats
        text = "📊 **Статистика работы AI:**\n"
        text += f"Всего попыток: {consilium_stats['attempts']}\n"
        text += f"Успешно: {consilium_stats['success']}\n"
        text += f"Ошибок: {consilium_stats['failures']}\n"
        for model, count in consilium_stats['models_used'].items():
            text += f"  {model}: {count}\n"
        await send_or_edit(update, text, parse_mode='Markdown')
        return


    elif data == "admin_stats_top":
        from bot import get_leaderboard_from_scoreboard

        leaderboard = get_leaderboard_from_scoreboard()
        if not leaderboard:
            await send_or_edit(update, "Нет данных.")
            return

        max_points = leaderboard[0][3] if leaderboard else 1
        text = "🏆 **ТОП ИГРОКОВ**\n\n"
        medals = ["🥇", "🥈", "🥉"]
        for i, (uid, fname, uname, total) in enumerate(leaderboard[:10], 1):
            name = fname or uname or f"User{uid}"
            if i <= 3:
                medal = medals[i - 1]
            else:
                medal = f"{i}."
            bar_len = int(20 * total / max_points) if max_points > 0 else 0
            bar = "▰" * bar_len + "▱" * (20 - bar_len)
            text += f"{medal} **{name}** — {total} баллов\n   {bar} {total}\n\n"
        await send_or_edit(update, text, parse_mode='Markdown')
        return


    elif data == "admin_stats_challenges":
        from bot import challenges_command
        return await challenges_command(update, context)



    elif data == "admin_stats_workouts":
        from bot import get_user_workouts
        from datetime import datetime

        user_id = update.effective_user.id
        limit = 20
        workouts = get_user_workouts(user_id, limit)
        if not workouts:
            await send_or_edit(update, "У тебя пока нет записанных тренировок.")
            return

        text = f"📋 **Твои последние {len(workouts)} тренировок:**\n\n"
        for w in workouts:
            wid, name, result, video, date, is_best, typ, comment = w
            date_str = datetime.fromisoformat(date).strftime("%d.%m.%Y %H:%M")
            best_mark = " 🏆" if is_best else ""
            line = f"• {date_str} — **{name}** ({typ}): {result} [ссылка]({video}){best_mark}"
            if comment:
                line += f"\n   💬 {comment}"
            text += line + "\n"
            if len(text) > 3500:
                text += "\n...и ещё"
                break
        await send_or_edit(update, text, parse_mode='Markdown', disable_web_page_preview=True)
        return

    # ========== НАСТРОЙКИ ==========
    elif data == "admin_settings":
        await admin_settings_menu(update, context)
        return

    elif data == "admin_settings_channel":
        await send_or_edit(update, "📢 Настройка канала:\n\n"
                                   "`/set_channel <id>` — установить канал\n"
                                   "`/get_channel` — посмотреть канал\n"
                                   "`/publish_complex <id>` — опубликовать комплекс",
                           parse_mode='Markdown')
        return

    elif data == "admin_settings_ai":
        from bot import config_command
        await config_command(update, context)
        return

    elif data == "admin_settings_recalc":
        from bot import recalc_rankings_command
        await recalc_rankings_command(update, context)
        return

    # ========== КНОПКА НАЗАД ==========
    elif data == "admin_back":
        await admin_menu(update, context)
        return

    # ========== ОБРАБОТКА РЕДАКТИРОВАНИЯ УПРАЖНЕНИЯ ==========
    elif data.startswith("exfield_") or data == "cancel_edit_ex":
        from bot import edit_exercise_value_input
        return await edit_exercise_value_input(update, context)

    else:
        await send_or_edit(update, "⚠️ Раздел в разработке.")

async def admin_exercises_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню управления упражнениями."""
    keyboard = [
        [InlineKeyboardButton("📋 Список упражнений", callback_data="admin_ex_list")],
        [InlineKeyboardButton("➕ Добавить упражнение", callback_data="admin_ex_add")],
        [InlineKeyboardButton("✏️ Редактировать упражнение", callback_data="admin_ex_edit")],
        [InlineKeyboardButton("🗑️ Удалить упражнение", callback_data="admin_ex_delete")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_back")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    query = update.callback_query
    await query.edit_message_text(
        "🏋️ **Управление упражнениями**\n\nВыберите действие:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def admin_complexes_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню управления комплексами."""
    keyboard = [
        [InlineKeyboardButton("📋 Список комплексов", callback_data="admin_cx_list")],
        [InlineKeyboardButton("➕ Добавить комплекс", callback_data="admin_cx_add")],
        [InlineKeyboardButton("✏️ Редактировать комплекс", callback_data="admin_cx_edit")],
        [InlineKeyboardButton("🗑️ Удалить комплекс", callback_data="admin_cx_delete")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_back")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    query = update.callback_query
    await query.edit_message_text(
        "🏋️‍♂️ **Управление комплексами**\n\nВыберите действие:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def admin_challenges_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню управления челленджами."""
    keyboard = [
        [InlineKeyboardButton("📋 Список челленджей", callback_data="admin_ch_list")],
        [InlineKeyboardButton("➕ Добавить челлендж", callback_data="admin_ch_add")],
        [InlineKeyboardButton("✏️ Редактировать челлендж", callback_data="admin_ch_edit")],
        [InlineKeyboardButton("🗑️ Удалить челлендж", callback_data="admin_ch_delete")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_back")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    query = update.callback_query
    await query.edit_message_text(
        "🏆 **Управление челленджами**\n\nВыберите действие:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def admin_stats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню статистики."""
    keyboard = [
        [InlineKeyboardButton("📊 Статистика работы бота", callback_data="admin_stats_bot")],
        [InlineKeyboardButton("📈 Топ пользователей", callback_data="admin_stats_top")],
        [InlineKeyboardButton("🏆 Топ по челленджам", callback_data="admin_stats_challenges")],
        [InlineKeyboardButton("📋 Отчёт по тренировкам", callback_data="admin_stats_workouts")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_back")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    query = update.callback_query
    await query.edit_message_text(
        "📊 **Статистика**\n\nВыберите отчёт:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def admin_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню настроек."""
    keyboard = [
        [InlineKeyboardButton("📢 Настроить канал публикаций", callback_data="admin_settings_channel")],
        [InlineKeyboardButton("🤖 Настройка AI", callback_data="admin_settings_ai")],
        [InlineKeyboardButton("🔄 Еженедельный пересчёт рейтинга", callback_data="admin_settings_recalc")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_back")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    query = update.callback_query
    await query.edit_message_text(
        "⚙️ **Настройки**\n\nВыберите настройку:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


# ========== УПРАВЛЕНИЕ УПРАЖНЕНИЯМИ ==========

async def admin_exercise_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список упражнений."""
    from database_backup import get_all_exercises
    from bot import paginate

    query = update.callback_query  # <-- это колбэк
    page = 1
    all_exercises = get_all_exercises()
    if not all_exercises:
        await query.edit_message_text("📋 Список упражнений пуст.")  # <-- правильно
        return

    exercises, keyboard = paginate(all_exercises, page, per_page=5, prefix='admin_ex_page')

    text = "📋 **Список упражнений:**\n\n"
    for ex in exercises:
        name = ex[1].replace('_', r'\_').replace('*', r'\*').replace('[', r'\[').replace(']', r'\]')
        text += f"🔹 ID: {ex[0]} — {name} ({ex[5]})\n"

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)  # <-- правильно


async def admin_exercise_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает диалог добавления упражнения."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info("🔥 admin_exercise_add_start ВЫЗВАНА")

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("Введите название упражнения:")
    else:
        await update.message.reply_text("Введите название упражнения:")

    logger.info(f"🔥 возвращаю EXERCISE_NAME = {EXERCISE_NAME}")
    return EXERCISE_NAME


async def admin_exercise_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохраняет название упражнения."""
    context.user_data['ex_name'] = update.message.text
    await update.message.reply_text("Введите описание упражнения (можно пропустить, отправьте '-'):")
    return EXERCISE_DESC


async def admin_exercise_add_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохраняет описание упражнения."""
    desc = update.message.text
    if desc == '-':
        desc = ''
    context.user_data['ex_desc'] = desc

    keyboard = [
        [InlineKeyboardButton("🔢 Повторения (reps)", callback_data="ex_metric_reps")],
        [InlineKeyboardButton("⏱️ Время (time)", callback_data="ex_metric_time")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите тип упражнения:", reply_markup=reply_markup)
    return EXERCISE_METRIC


async def admin_exercise_add_metric(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохраняет тип упражнения."""
    query = update.callback_query
    await query.answer()
    metric = query.data.split('_')[2]
    context.user_data['ex_metric'] = metric
    await query.edit_message_text("Введите количество баллов (целое число):")
    return EXERCISE_POINTS


async def admin_exercise_add_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохраняет баллы."""
    try:
        points = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Введите целое число баллов.")
        return EXERCISE_POINTS
    context.user_data['ex_points'] = points
    await update.message.reply_text("Введите неделю (0 — всегда доступно):")
    return EXERCISE_WEEK


async def admin_exercise_add_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохраняет неделю."""
    try:
        week = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Введите целое число (неделя).")
        return EXERCISE_WEEK
    context.user_data['ex_week'] = week

    keyboard = [
        [InlineKeyboardButton("👶 Новичок (beginner)", callback_data="ex_diff_beginner")],
        [InlineKeyboardButton("🏆 Профи (pro)", callback_data="ex_diff_pro")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите уровень сложности:", reply_markup=reply_markup)
    return EXERCISE_DIFF


async def admin_exercise_add_diff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохраняет уровень и создаёт упражнение."""
    query = update.callback_query
    await query.answer()
    diff = query.data.split('_')[2]

    from database_backup import add_exercise

    success = add_exercise(
        name=context.user_data['ex_name'],
        description=context.user_data['ex_desc'],
        metric=context.user_data['ex_metric'],
        points=context.user_data['ex_points'],
        week=context.user_data['ex_week'],
        difficulty=diff
    )

    if success:
        await query.edit_message_text(
            f"✅ Упражнение «{context.user_data['ex_name']}» добавлено!"
        )
    else:
        await query.edit_message_text("❌ Ошибка при добавлении упражнения.")

    context.user_data.clear()
    return ConversationHandler.END


async def admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена операции."""
    await update.message.reply_text("❌ Операция отменена.")
    context.user_data.clear()
    return ConversationHandler.END