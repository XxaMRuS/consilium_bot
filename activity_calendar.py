import logging
from datetime import datetime
import calendar
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database_backup import get_user_activity_calendar

logger = logging.getLogger(__name__)

WEEKDAYS_RU = ['Пн ', 'Вт ', 'Ср ', 'Чт ', 'Пт ', 'Сб ', 'Вс ']


def _get_month_data(user_id, year, month):
    activities = get_user_activity_calendar(user_id, year, month)
    workouts = {day: {'has_workout': has_workout, 'has_record': has_record, 'volume': volume}
                for day, has_workout, has_record, volume in activities}
    return workouts


def _build_calendar_text(year, month, workouts):
    today = datetime.now()
    is_current_month = (today.year == year and today.month == month)
    today_day = today.day if is_current_month else None

    first_weekday, num_days = calendar.monthrange(year, month)

    month_header = f"📅 *{calendar.month_name[month]} {year}*"

    # ===== НАСТРОЙКИ ШИРИНЫ КОЛОНОК =====
    # 1. Задаём заголовки дней. Каждая строка должна иметь одинаковую длину.
    #    В данном примере длина 5 символов (буквы + 3 пробела).
    weekdays = ["Пн   ", "Вт   ", "Ср   ", "Чт   ", "Пт   ", "Сб   ", "Вс   "]
    header_line = "".join(weekdays)

    # 2. Пустая ячейка (5 пробелов, соответствует ширине колонки)
    empty_cell = "     "
    # ====================================

    lines = [header_line]
    week = [empty_cell] * first_weekday

    for day in range(1, num_days + 1):
        # Выбор символа
        if is_current_month and day == today_day:
            symbol = "@"
        elif day in workouts and workouts[day]['has_workout']:
            if workouts[day]['has_record']:
                symbol = "*"
            else:
                symbol = "#"
        else:
            symbol = "."

        # Формируем ячейку. Должна быть той же длины, что и empty_cell.
        if day < 10:
            cell = f"{symbol} {day}  "   # символ + пробел + цифра + 2 пробела → всего 5
        else:
            cell = f"{symbol}{day}  "     # символ + две цифры + 2 пробела → всего 5
        week.append(cell)

        if len(week) == 7 or day == num_days:
            lines.append("".join(week))
            week = []

    code_block = "```\n" + "\n".join(lines) + "\n```"

    # Статистика (без объёма)
    total_workouts = sum(1 for d in workouts.values() if d['has_workout'])
    total_records = sum(1 for d in workouts.values() if d['has_record'])
    stats = f"🏋️‍♂️ Тренировок: {total_workouts} | 🏆 Рекордов: {total_records}"

    legend = "\n\n_Легенда:_ `#` тренировка, `*` рекорд, `@` сегодня, `.` нет тренировки"
    return f"{month_header}\n{code_block}\n\n{stats}{legend}"

async def calendar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now = datetime.now()
    year = now.year
    month = now.month

    context.user_data['calendar_year'] = year
    context.user_data['calendar_month'] = month

    workouts = _get_month_data(user_id, year, month)
    text = _build_calendar_text(year, month, workouts)

    keyboard = [[
        InlineKeyboardButton("◀️ Пред", callback_data="cal_prev"),
        InlineKeyboardButton("Сейчас", callback_data="cal_now"),
        InlineKeyboardButton("След ▶️", callback_data="cal_next"),
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)


async def calendar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    data = query.data

    year = context.user_data.get('calendar_year', datetime.now().year)
    month = context.user_data.get('calendar_month', datetime.now().month)

    if data == "cal_prev":
        if month == 1:
            month = 12
            year -= 1
        else:
            month -= 1
    elif data == "cal_next":
        if month == 12:
            month = 1
            year += 1
        else:
            month += 1
    elif data == "cal_now":
        now = datetime.now()
        year, month = now.year, now.month
    else:
        return

    context.user_data['calendar_year'] = year
    context.user_data['calendar_month'] = month

    workouts = _get_month_data(user_id, year, month)
    text = _build_calendar_text(year, month, workouts)

    keyboard = [[
        InlineKeyboardButton("◀️ Пред", callback_data="cal_prev"),
        InlineKeyboardButton("Сейчас", callback_data="cal_now"),
        InlineKeyboardButton("След ▶️", callback_data="cal_next"),
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)