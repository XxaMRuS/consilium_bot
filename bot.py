import os
import logging
import asyncio
import re
import json
import threading
import sqlite3
import shlex
from datetime import datetime
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from collections import deque
from urllib.parse import urlparse, parse_qs
from admin_handlers import admin_menu, admin_callback
from config import EMOJI, SEPARATOR, WELCOME_TEXT, format_success, format_error, format_warning
from dotenv import load_dotenv
load_dotenv()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)
DEBUG = True
# Твои локальные модули
from activity_calendar import calendar_command, calendar_callback
from menu_handlers import main_menu_keyboard
from ai_work import start_consilium, stats as consilium_stats, ENABLED_PROVIDERS
from photo_processor import (
    convert_to_sketch, convert_to_anime, convert_to_sepia,
    convert_to_hard_rock, convert_to_pixel, convert_to_neon,
    convert_to_oil, convert_to_watercolor, convert_to_cartoon
)
from database_backup import (
    DB_NAME, init_db, add_user, get_exercises, add_workout, add_exercise,
    set_exercise_week, get_user_stats, get_leaderboard,
    get_all_exercises, delete_exercise,
    get_user_level, set_user_level,
    get_user_workouts, get_exercise_by_id,
    backup_database, recalculate_rankings,
    get_user_scoreboard_total, get_leaderboard_from_scoreboard,
    add_complex, add_complex_exercise, get_all_complexes, get_complex_by_id, get_complex_exercises,
    add_challenge, get_active_challenges, get_challenge_by_id, join_challenge,
    update_challenge_progress, check_challenge_completion, get_user_challenges,
    complete_challenge, get_challenges_by_status, get_setting, set_setting, get_challenge_name, leave_challenge, get_user_challenges_with_details,
    check_and_award_achievements, save_published_post, get_published_post_by_message_id
)
from workout_handlers import (
    workout_start, exercise_choice, result_input, video_input,
    workout_cancel, EXERCISE, RESULT, VIDEO, COMMENT,
    get_current_week, comment_input, comment_skip, comment_handler
)
from submit_handlers import (
    submit_complex_callback, submit_result_input, submit_video_input,
    submit_comment_input, submit_comment_skip
)

# ========== ТЕСТОВАЯ ФУНКЦИЯ ==========
async def test_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестовая функция для проверки вызова из колбэка"""
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("✅ Тест: вызвано из кнопки!")
    else:
        await update.message.reply_text("✅ Тест: вызвано из команды!")
    return

# === НАСТРОЙКА ЛОГИРОВАНИЯ ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Лог в файл для отладки
file_handler = logging.FileHandler('bot.log', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# === КОНСТАНТЫ И СОСТОЯНИЯ ===
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_USER_ID", 0))

COMPLEX_RESULT, COMPLEX_VIDEO, COMPLEX_COMMENT = range(10, 13)
COMPLEX_NAME, COMPLEX_DESC, COMPLEX_TYPE, COMPLEX_POINTS, COMPLEX_ADD_EXERCISE = range(20, 25)
COMPLEX_REPS = 25
CHALL_NAME, CHALL_DESC, CHALL_TYPE, CHALL_TARGET, CHALL_TARGET_VALUE, CHALL_START_DATE, CHALL_END_DATE, CHALL_BONUS = range(30, 38)
CONFIRM_DELETE = 40
EDIT_COMPLEX_ID, EDIT_COMPLEX_FIELD, EDIT_COMPLEX_VALUE = range(45, 48)
CONFIRM_DELETE_COMPLEX = 50
EDIT_EXERCISE_ID, EDIT_EXERCISE_VALUE = range(55, 57)
WAIT_DELETE_ID = 41
WAIT_DELETE_COMPLEX_ID = 42
WAIT_DELETE_CHALLENGE_ID = 43
EDIT_CHALLENGE_ID, EDIT_CHALLENGE_VALUE = range(60, 62)

# === УТИЛИТЫ ===
def clean_markdown(text):
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    text = re.sub(r'`(.*?)`', r'\1', text)
    return text

def is_admin(update: Update) -> bool:
    return update.effective_user.id == ADMIN_ID

def parse_date(date_str):
    try:
        day, month, year = date_str.split('.')
        return f"{year}-{month}-{day}"
    except:
        return None

# ========== ОБРАБОТЧИКИ ОСНОВНЫХ КОМАНД ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["🏋️ Спорт", "📸 Фото"],
        ["🤖 Задать вопрос", "❌ Отмена"],
        ["🏆 Рейтинг", "⚙️ Админ"],
        ["📅 Календарь"],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        WELCOME_TEXT,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("✏️ Карандаш", callback_data='sketch'),
         InlineKeyboardButton("🎌 Аниме", callback_data='anime')],
        [InlineKeyboardButton("🟫 Сепия", callback_data='sepia'),
         InlineKeyboardButton("🤘 Хард-рок", callback_data='hardrock')],
        [InlineKeyboardButton("🟩 Пиксель", callback_data='pixel'),
         InlineKeyboardButton("🌈 Неон", callback_data='neon')],
        [InlineKeyboardButton("🖼️ Масло", callback_data='oil'),
         InlineKeyboardButton("💧 Акварель", callback_data='watercolor')],
        [InlineKeyboardButton("🧸 Мультяшный", callback_data='cartoon')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🎨 Выбери стиль для фото:", reply_markup=reply_markup)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "📊 **Статистика работы AI:**\n"
    text += f"Всего попыток: {consilium_stats['attempts']}\n"
    text += f"Успешно: {consilium_stats['success']}\n"
    text += f"Ошибок: {consilium_stats['failures']}\n"
    for model, count in consilium_stats['models_used'].items():
        text += f"  {model}: {count}\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'user_history' in context.user_data:
        context.user_data['user_history'].clear()
    await update.message.reply_text("🔄 Твоя личная история диалога очищена.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🏋️ Спорт", callback_data='help_sport')],
        [InlineKeyboardButton("📸 Фото", callback_data='help_photo')],
        [InlineKeyboardButton("📊 Статистика", callback_data='help_stats')],
        [InlineKeyboardButton("🏆 Рейтинг", callback_data='help_top')],
    ]
    if is_admin(update):
        keyboard.append([InlineKeyboardButton("⚙️ Админ", callback_data='help_admin')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🤖 **Помощь**\nВыбери раздел, чтобы узнать подробнее:",
        parse_mode='Markdown', reply_markup=reply_markup
    )

async def publish_complex_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Публикует комплекс в канал с кнопкой 'Сдать результат'."""
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        return
    if not context.args:
        await update.message.reply_text("Использование: /publish_complex <id>")
        return
    try:
        complex_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return

    complex_data = get_complex_by_id(complex_id)
    if not complex_data:
        await update.message.reply_text("Комплекс не найден.")
        return

    channel_id = get_setting("public_channel")
    if not channel_id:
        await update.message.reply_text("Сначала установите канал командой /set_channel <id>")
        return

    try:
        channel_id_int = int(channel_id)
    except ValueError:
        await update.message.reply_text("ID канала должен быть числом.")
        return

    text = f"🏋️ *Новый комплекс: {complex_data[1]}*\n\n"
    text += f"{complex_data[2]}\n\n"
    text += f"Тип: {'Время' if complex_data[3] == 'for_time' else 'Повторения'}\n"
    text += f"Баллы: {complex_data[4]}\n\n"

    keyboard = [[InlineKeyboardButton("✅ Сдать результат", callback_data=f"submit_complex_{complex_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    bot = context.bot
    sent_message = await bot.send_message(
        chat_id=channel_id_int,
        text=text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    save_published_post('complex', complex_id, channel_id_int, sent_message.message_id)

    await update.message.reply_text(f"✅ Комплекс «{complex_data[1]}» опубликован в канале.")

async def set_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        return
    if not context.args:
        await update.message.reply_text("Использование: /set_channel <chat_id>")
        return
    try:
        chat_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return
    set_setting("public_channel", str(chat_id))
    await update.message.reply_text(f"✅ Канал для публикаций установлен: {chat_id}")

async def get_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        return
    channel = get_setting("public_channel")
    if channel:
        await update.message.reply_text(f"Текущий канал: {channel}")
    else:
        await update.message.reply_text("Канал не установлен.")

async def get_channel_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        chat_id = update.message.chat_id
        await update.message.reply_text(f"ID этого чата: {chat_id}")

# ========== ОБРАБОТКА ТЕКСТА И ФОТО ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_question = update.message.text
    await update.message.chat.send_action(action="typing")
    try:
        if 'user_history' not in context.user_data:
            context.user_data['user_history'] = deque(maxlen=5)
        answer = start_consilium(user_question, context.user_data['user_history'])
        clean_answer = clean_markdown(answer)
        if len(clean_answer) > 4000:
            for i in range(0, len(clean_answer), 4000):
                await update.message.reply_text(clean_answer[i:i+4000])
        else:
            await update.message.reply_text(clean_answer)
    except Exception as e:
        logger.exception("Ошибка в handle_message")
        await update.message.reply_text(format_error("Ошибка при ответе ИИ."))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['effect'] = query.data
    styles = {
        'sketch': 'карандаш', 'anime': 'аниме', 'sepia': 'сепия',
        'hardrock': 'хард-рок', 'pixel': 'пиксель', 'neon': 'неон',
        'oil': 'масло', 'watercolor': 'акварель', 'cartoon': 'мультяшный'
    }
    name = styles.get(query.data, query.data)
    await query.edit_message_text(f"✅ Выбран стиль: {name}. Теперь отправляй фото!")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'effect' not in context.user_data:
        await update.message.reply_text("Сначала выбери стиль через /menu")
        return
    effect = context.user_data['effect']
    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()
    try:
        await update.message.reply_text("⏳ Обрабатываю фото...")
        processors = {
            'sketch': convert_to_sketch,
            'anime': convert_to_anime,
            'sepia': convert_to_sepia,
            'hardrock': convert_to_hard_rock,
            'pixel': convert_to_pixel,
            'neon': convert_to_neon,
            'oil': convert_to_oil,
            'watercolor': convert_to_watercolor,
            'cartoon': convert_to_cartoon
        }
        if effect in processors:
            output = processors[effect](photo_bytes)
            await update.message.reply_photo(photo=output, caption=f"Готово! Стиль: {effect}")
        else:
            await update.message.reply_text("Неизвестный эффект.")
    except Exception as e:
        logger.exception("Ошибка в handle_photo")
        await update.message.reply_text("❌ Не удалось обработать фото.")

# ========== СПОРТИВНОЕ МЕНЮ ==========
async def sport_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📋 Каталог упражнений", callback_data='sport_catalog')],
        [InlineKeyboardButton("✍️ Записать тренировку", callback_data='sport_wod')],
        [InlineKeyboardButton("📊 Моя статистика", callback_data='sport_mystats')],
        [InlineKeyboardButton("🔄 Сменить уровень", callback_data='sport_setlevel')],
        [InlineKeyboardButton("◀️ Назад", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🏋️ Раздел «Спорт». Выбери действие:",
        reply_markup=reply_markup
    )

async def sport_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    try:
        if data == 'sport_catalog':
            await send_catalog_to_message(query.message)
        elif data == 'sport_wod':
            await query.message.reply_text("Отправь команду /wod, чтобы записать тренировку.")
        elif data == 'sport_mystats':
            await mystats_command(query.message, context)
        elif data == 'sport_setlevel':
            keyboard = [
                [InlineKeyboardButton("Новичок (beginner)", callback_data="setlevel_beginner")],
                [InlineKeyboardButton("Профи (pro)", callback_data="setlevel_pro")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text("Выбери уровень:", reply_markup=reply_markup)
        elif data == 'back_to_main':
            keyboard = [
                ["🏋️ Спорт", "📸 Фото"],
                ["🤖 Задать вопрос", "📊 Моя статистика"],
                ["🏆 Рейтинг", "⚙️ Админ"],
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await query.message.reply_text("Главное меню:", reply_markup=reply_markup)
            await query.message.delete()
    except Exception as e:
        logger.exception(f"Ошибка в sport_callback_handler: {e}")
        await query.message.reply_text(format_error("Произошла ошибка. Попробуй позже."))


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if DEBUG:
        print(f"DEBUG: menu_handler получил: {update.message.text}")

    # Если активен диалог сдачи результата – не мешаем
    if context.user_data.get('conversation_state') is not None:
        if DEBUG:
            print("DEBUG: menu_handler пропускает, активен диалог")
        return

    if not update.message:
        return

    text = update.message.text
    if DEBUG:
        print(f"DEBUG: menu_handler обрабатывает: {text}")

    if "Спорт" in text:
        await sport_menu(update, context)
    elif "Фото" in text:
        await show_menu(update, context)
    elif "Отмена" in text:
        context.user_data.clear()
        await update.message.reply_text("Все активные действия отменены. Можете начать заново.")
    elif "Задать вопрос" in text:
        await update.message.reply_text("Напиши свой вопрос — я отвечу.")
    elif "Рейтинг" in text:
        await top_command(update, context)
    elif "Календарь" in text:
        await calendar_command(update, context)
    elif "Админ" in text:
        if is_admin(update):
            await admin_menu(update, context)
        else:
            await update.message.reply_text("⛔ У вас нет прав на это.")
    else:
        await handle_message(update, context)

# ========== ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ОТПРАВКИ КАТАЛОГА ==========
async def send_catalog_to_message(message):
    current_week = get_current_week()
    exercises = get_all_exercises()
    if not exercises:
        await message.reply_text("Список упражнений пока пуст.")
        return

    permanent = []
    weekly = []
    for ex in exercises:
        if ex[4] == 0:
            permanent.append(ex)
        else:
            weekly.append(ex)

    text = "📋 **КАТАЛОГ УПРАЖНЕНИЙ**\n\n"
    keyboard = []

    if permanent:
        text += "♾️ **Доступны всегда**\n"
        for ex in permanent:
            name, points = ex[1], ex[3]
            icon = get_exercise_icon(name)
            text += f"• {icon} **{name}** – {points} баллов\n"
            keyboard.append([InlineKeyboardButton(f"{icon} {name}", callback_data=f"ex_{ex[0]}")])
        text += "\n"

    if weekly:
        text += "📅 **По неделям**\n"
        for ex in weekly:
            name, points, week = ex[1], ex[3], ex[4]
            icon = get_exercise_icon(name)
            if week == current_week:
                status = "✅ доступно сейчас"
            elif week < current_week:
                status = "⏳ прошлая неделя"
            else:
                status = f"🔜 будет на неделе {week}"
            text += f"• {icon} **{name}** – {points} баллов ({status})\n"
            keyboard.append([InlineKeyboardButton(f"{icon} {name}", callback_data=f"ex_{ex[0]}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)

# ========== КАТАЛОГ УПРАЖНЕНИЙ ==========
async def catalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_catalog_to_message(update.message)

# ========== СТАТИСТИКА И РЕЙТИНГ ==========
async def mystats_command(message, context: ContextTypes.DEFAULT_TYPE):
    user_id = message.chat.id
    total = get_user_scoreboard_total(user_id)
    workouts = get_user_workouts(user_id, limit=1000)
    workout_count = len(workouts)
    target = 100
    bar_len = int(20 * total / target) if target > 0 else 0
    bar = "▰" * bar_len + "▱" * (20 - bar_len)
    text = f"🏆 **Твоя статистика**\n\n"
    text += f"🏋️ Тренировок: {workout_count}\n"
    text += f"⭐ Баллов: {total}\n"
    text += f"📈 Прогресс до следующего уровня: {bar} {total}/{target}"
    await message.reply_text(text, parse_mode='Markdown')

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    leaderboard = get_leaderboard_from_scoreboard()
    if not leaderboard:
        await update.message.reply_text("Нет данных.")
        return

    max_points = leaderboard[0][3] if leaderboard else 1
    text = "🏆 **ТОП ИГРОКОВ**\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, (uid, fname, uname, total) in enumerate(leaderboard[:10], 1):
        name = fname or uname or f"User{uid}"
        if i <= 3:
            medal = medals[i-1]
        else:
            medal = f"{i}."
        bar_len = int(20 * total / max_points) if max_points > 0 else 0
        bar = "▰" * bar_len + "▱" * (20 - bar_len)
        text += f"{medal} **{name}** — {total} баллов\n   {bar} {total}\n\n"
    await update.message.reply_text(text, parse_mode='Markdown')

# ========== КОМАНДЫ ДЛЯ КОМПЛЕКСОВ ==========
async def add_complex_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        return
    try:
        text = update.message.text.split(maxsplit=1)[1]
        args = shlex.split(text)
        if len(args) < 4:
            await update.message.reply_text("Использование: /addcomplex <название> <описание> <тип> <баллы>\nТип: for_time или for_reps")
            return
        name, description, type_, points = args[0], args[1], args[2], int(args[3])
        if type_ not in ('for_time', 'for_reps'):
            await update.message.reply_text("Тип должен быть for_time или for_reps")
            return
        complex_id = add_complex(name, description, type_, points)
        await update.message.reply_text(f"✅ Комплекс «{name}» создан с ID {complex_id}.\nТеперь добавь упражнения командой /addcomplexexercise {complex_id} <id_упражнения> <повторения>")
    except Exception as e:
        await update.message.reply_text(format_error(f"Ошибка: {e}"))

async def add_complex_exercise_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        return
    try:
        args = context.args
        if len(args) != 3:
            await update.message.reply_text("Использование: /addcomplexexercise <complex_id> <exercise_id> <reps>")
            return
        complex_id = int(args[0])
        exercise_id = int(args[1])
        reps = int(args[2])
        complex_data = get_complex_by_id(complex_id)
        if not complex_data:
            await update.message.reply_text("Комплекс не найден.")
            return
        ex = get_exercise_by_id(exercise_id)
        if not ex:
            await update.message.reply_text("Упражнение не найдено.")
            return
        add_complex_exercise(complex_id, exercise_id, reps)
        await update.message.reply_text(f"✅ Упражнение «{ex[1]}» добавлено в комплекс {complex_data[1]} с {reps} повторениями.")
    except Exception as e:
        await update.message.reply_text(format_error(f"Ошибка: {e}"))


async def complexes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    page = 1
    if context.args and context.args[0].isdigit():
        page = int(context.args[0])
    all_complexes = get_all_complexes()
    if not all_complexes:
        if update.callback_query:
            await update.callback_query.edit_message_text("Комплексов пока нет.")
        else:
            await update.message.reply_text("Комплексов пока нет.")
        return

    complexes, keyboard = paginate(all_complexes, page, per_page=5, prefix='complex_page')
    text = "🏋️ **Доступные комплексы:**\n\n"
    for c in complexes:
        text += f"ID: {c[0]} — **{c[1]}**\n"
        text += f"   Тип: {'Время' if c[3] == 'for_time' else 'Повторения'}\n"
        text += f"   Баллы: {c[4]}\n\n"

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def complex_detail_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        complex_id = int(context.args[0])
    except:
        await update.message.reply_text("Использование: /complex <id>")
        return
    complex_data = get_complex_by_id(complex_id)
    if not complex_data:
        await update.message.reply_text("Комплекс не найден.")
        return
    exercises = get_complex_exercises(complex_id)
    if not exercises:
        await update.message.reply_text("В комплексе нет упражнений.")
        return
    text = f"**{complex_data[1]}**\n{complex_data[2]}\n\n"
    text += f"Тип: {'Время' if complex_data[3] == 'for_time' else 'Повторения'}\n"
    text += f"Баллы: {complex_data[4]}\n\n"
    text += "**Упражнения:**\n"
    for ex in exercises:
        text += f"• {ex[2]} — {ex[4]} повторений\n"
    keyboard = [[InlineKeyboardButton("✅ Выполнить комплекс", callback_data=f"do_complex_{complex_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)

# ========== ДИАЛОГ ВЫПОЛНЕНИЯ КОМПЛЕКСА (через команду /complex) ==========
async def do_complex_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    complex_id = int(query.data.split('_')[2])
    context.user_data['current_complex_id'] = complex_id
    complex_data = get_complex_by_id(complex_id)
    if not complex_data:
        await query.edit_message_text("Комплекс не найден.")
        return ConversationHandler.END
    context.user_data['complex_name'] = complex_data[1]
    context.user_data['complex_points'] = complex_data[4]
    await query.edit_message_text(f"Выполняем комплекс **{complex_data[1]}**.\nВведите результат:\n- Если тип 'время', укажи в формате ММ:СС (например, 03:45)\n- Если тип 'повторения', введи количество.")
    return COMPLEX_RESULT

async def complex_result_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result_text = update.message.text.strip()
    complex_id = context.user_data['current_complex_id']
    complex_data = get_complex_by_id(complex_id)
    complex_type = complex_data[3]
    if complex_type == 'for_time':
        try:
            parts = result_text.split(':')
            if len(parts) == 2:
                minutes = int(parts[0])
                seconds = int(parts[1])
                total_seconds = minutes * 60 + seconds
                context.user_data['complex_result_value'] = result_text
                context.user_data['complex_result_seconds'] = total_seconds
            else:
                raise ValueError
        except:
            await update.message.reply_text("Неверный формат. Используй ММ:СС, например 05:30")
            return COMPLEX_RESULT
    else:
        try:
            reps = int(result_text)
            context.user_data['complex_result_value'] = str(reps)
            context.user_data['complex_result_reps'] = reps
        except:
            await update.message.reply_text("Введи целое число повторений.")
            return COMPLEX_RESULT
    await update.message.reply_text("Отлично! Теперь отправь ссылку на видео (YouTube, Vimeo, или любой URL) подтверждения выполнения.\nИли нажми /skip, чтобы пропустить.")
    return COMPLEX_VIDEO

async def complex_video_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video_url = update.message.text.strip()
    context.user_data['complex_video'] = video_url
    await update.message.reply_text("Можешь добавить комментарий к тренировке (необязательно).\nИли нажми /skip, чтобы пропустить.")
    return COMPLEX_COMMENT

async def complex_comment_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    comment = update.message.text.strip()
    context.user_data['complex_comment'] = comment
    await save_complex_workout(update, context)
    return ConversationHandler.END

async def complex_comment_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['complex_comment'] = None
    await save_complex_workout(update, context)
    return ConversationHandler.END

async def save_complex_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    complex_id = context.user_data['current_complex_id']
    complex_data = get_complex_by_id(complex_id)
    complex_name = context.user_data['complex_name']
    points = context.user_data['complex_points']
    result = context.user_data['complex_result_value']
    video = context.user_data.get('complex_video', '')
    comment = context.user_data.get('complex_comment')
    user_level = get_user_level(user_id)

    _, new_achievements = add_workout(
        user_id=user_id,
        exercise_id=None,
        complex_id=complex_id,
        result_value=result,
        video_link=video,
        user_level=user_level,
        comment=comment,
        metric=None
    )
    for ach in new_achievements:
        ach_id, name, desc, cond_type, cond_value, icon = ach
        await update.message.reply_text(f"{icon} **{name}** — {desc}", parse_mode='Markdown')

# ========== КОНСТРУКТОР КОМПЛЕКСОВ ==========
async def newcomplex_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("newcomplex_start вызвана")
    if not is_admin(update):
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text("⛔ Нет прав.")
        else:
            await update.message.reply_text("⛔ Нет прав.")
        return ConversationHandler.END

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Введите название комплекса:")
    else:
        await update.message.reply_text("Введите название комплекса:")

    return COMPLEX_NAME

async def complex_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("complex_name_input вызвана")
    name = update.message.text
    context.user_data['complex_name'] = name
    await update.message.reply_text("Введите описание комплекса (можно пропустить, отправьте '-' ):")
    return COMPLEX_DESC

async def complex_desc_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("complex_desc_input вызвана")
    description = update.message.text
    if description == '-':
        description = ''
    context.user_data['complex_desc'] = description
    keyboard = [
        [InlineKeyboardButton("Время (for_time)", callback_data="type_for_time")],
        [InlineKeyboardButton("Повторения (for_reps)", callback_data="type_for_reps")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите тип комплекса:", reply_markup=reply_markup)
    return COMPLEX_TYPE

async def complex_points_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        points = int(update.message.text)
    except:
        await update.message.reply_text("Введите целое число баллов.")
        return COMPLEX_POINTS
    context.user_data['complex_points'] = points
    exercises = get_all_exercises()
    if not exercises:
        await update.message.reply_text("Нет упражнений. Сначала добавьте упражнения командой /addexercise.")
        return ConversationHandler.END
    keyboard = []
    for ex in exercises:
        ex_id, name, description, metric, points_ex, week, difficulty = ex
        keyboard.append([InlineKeyboardButton(name, callback_data=f"addex_{ex_id}")])
    keyboard.append([InlineKeyboardButton("✅ Завершить создание", callback_data="finish_complex")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите упражнения для добавления в комплекс. После выбора нужно будет указать количество повторений.", reply_markup=reply_markup)
    return COMPLEX_ADD_EXERCISE

async def complex_add_exercise_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logger.info(f"complex_add_exercise_callback вызвана с data = {query.data}")
    await query.answer()

    if query.data == "finish_complex":
        exercises_list = context.user_data.get('complex_exercises', [])
        if not exercises_list:
            await query.edit_message_text("Вы не добавили ни одного упражнения. Комплекс не создан.")
            return ConversationHandler.END

        name = context.user_data.get('complex_name')
        description = context.user_data.get('complex_desc', '')
        type_ = context.user_data.get('complex_type')
        points = context.user_data.get('complex_points')

        if not name or not type_ or not points:
            await query.edit_message_text("Ошибка: не все данные комплекса заполнены.")
            return ConversationHandler.END

        complex_id = add_complex(name, description, type_, points)
        if not complex_id:
            await query.edit_message_text("Ошибка при создании комплекса. Возможно, такое название уже существует.")
            return ConversationHandler.END

        for item in exercises_list:
            add_complex_exercise(complex_id, item['ex_id'], item['reps'])

        for key in ['complex_name', 'complex_desc', 'complex_type', 'complex_points', 'complex_exercises']:
            context.user_data.pop(key, None)

        await query.edit_message_text(f"✅ Комплекс «{name}» успешно создан с ID {complex_id} и {len(exercises_list)} упражнениями.")
        return ConversationHandler.END

    else:
        ex_id = int(query.data.split('_')[1])
        context.user_data['temp_exercise_id'] = ex_id
        await query.edit_message_text("Введите количество повторений для этого упражнения (целое число):")
        return COMPLEX_REPS

async def complex_type_temp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    type_ = query.data.split('_')[2]
    context.user_data['complex_type'] = type_
    await query.edit_message_text(f"Выбран тип: {type_}\nВведите количество баллов (целое число):")
    return COMPLEX_POINTS

async def complex_reps_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        reps = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Введите целое число повторений.")
        return COMPLEX_REPS

    ex_id = context.user_data.pop('temp_exercise_id')
    exercises_list = context.user_data.get('complex_exercises', [])
    exercises_list.append({'ex_id': ex_id, 'reps': reps})
    context.user_data['complex_exercises'] = exercises_list

    if exercises_list:
        ex_names = []
        for item in exercises_list:
            ex = get_exercise_by_id(item['ex_id'])
            name = ex[1] if ex else f"Упражнение {item['ex_id']}"
            ex_names.append(f"- {name} — {item['reps']} повторений")
        current_list = "\n".join(ex_names)
        await update.message.reply_text(f"📋 **Текущий список упражнений:**\n{current_list}")
    else:
        await update.message.reply_text("📋 Список упражнений пока пуст.")

    await update.message.reply_text(f"✅ Упражнение добавлено. Теперь выберите следующее упражнение или завершите создание.")

    exercises = get_all_exercises()
    if not exercises:
        await update.message.reply_text("Нет упражнений.")
        return ConversationHandler.END
    keyboard = []
    for ex in exercises:
        ex_id2, name, description, metric, points_ex, week, difficulty = ex
        keyboard.append([InlineKeyboardButton(name, callback_data=f"addex_{ex_id2}")])
    keyboard.append([InlineKeyboardButton("✅ Завершить создание", callback_data="finish_complex")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите следующее упражнение или завершите создание:", reply_markup=reply_markup)
    return COMPLEX_ADD_EXERCISE

async def delete_complex_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        return
    if not context.args:
        await update.message.reply_text("Использование: /deletecomplex <id>")
        return
    try:
        complex_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return

    complex_data = get_complex_by_id(complex_id)
    if not complex_data:
        await update.message.reply_text("Комплекс с таким ID не найден.")
        return

    context.user_data['delete_complex_id'] = complex_id
    context.user_data['delete_complex_name'] = complex_data[1]
    await update.message.reply_text(f"Вы уверены, что хотите удалить комплекс '{complex_data[1]}' (ID {complex_id})? Отправьте 'ДА' для подтверждения.")
    return CONFIRM_DELETE_COMPLEX

async def confirm_delete_complex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.upper() == "ДА":
        complex_id = context.user_data.get('delete_complex_id')
        if complex_id:
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            cur.execute("DELETE FROM complex_exercises WHERE complex_id = ?", (complex_id,))
            cur.execute("DELETE FROM complexes WHERE id = ?", (complex_id,))
            conn.commit()
            conn.close()
            await update.message.reply_text(f"✅ Комплекс ID {complex_id} удалён.")
        else:
            await update.message.reply_text("❌ Не удалось определить ID.")
    else:
        await update.message.reply_text("❌ Удаление отменено.")
    context.user_data.pop('delete_complex_id', None)
    context.user_data.pop('delete_complex_name', None)
    return ConversationHandler.END


async def delete_challenge_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает диалог удаления челленджа из кнопки."""
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Введите ID челленджа для удаления:")
    else:
        await update.message.reply_text("Введите ID челленджа для удаления:")
    return WAIT_DELETE_CHALLENGE_ID


async def delete_challenge_get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает ID челленджа и запрашивает подтверждение."""
    try:
        challenge_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("ID должен быть числом. Попробуйте ещё раз:")
        return WAIT_DELETE_CHALLENGE_ID

    challenge = get_challenge_by_id(challenge_id)
    if not challenge:
        await update.message.reply_text("Челлендж с таким ID не найден.")
        return ConversationHandler.END

    context.user_data['delete_challenge_id'] = challenge_id
    context.user_data['delete_challenge_name'] = challenge[1]
    await update.message.reply_text(
        f"Вы уверены, что хотите удалить челлендж '{challenge[1]}' (ID {challenge_id})? Отправьте 'ДА' для подтверждения."
    )
    return CONFIRM_DELETE


async def confirm_delete_challenge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение удаления челленджа."""
    text = update.message.text.strip()
    if text.upper() == "ДА":
        challenge_id = context.user_data.get('delete_challenge_id')
        if challenge_id:
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            cur.execute("DELETE FROM user_challenge_progress WHERE challenge_id = ?", (challenge_id,))
            cur.execute("DELETE FROM user_challenges WHERE challenge_id = ?", (challenge_id,))
            cur.execute("DELETE FROM challenges WHERE id = ?", (challenge_id,))
            conn.commit()
            conn.close()
            await update.message.reply_text(f"✅ Челлендж ID {challenge_id} удалён.")
        else:
            await update.message.reply_text("❌ Не удалось определить ID.")
    else:
        await update.message.reply_text("❌ Удаление отменено.")
    context.user_data.pop('delete_challenge_id', None)
    context.user_data.pop('delete_challenge_name', None)
    return ConversationHandler.END


async def edit_challenge_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает диалог редактирования челленджа."""
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Введите ID челленджа:")
    else:
        await update.message.reply_text("Введите ID челленджа:")
    return EDIT_CHALLENGE_ID


async def edit_challenge_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает ID челленджа и показывает поля для редактирования."""
    try:
        challenge_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("ID должен быть числом. Попробуйте ещё раз:")
        return EDIT_CHALLENGE_ID

    challenge = get_challenge_by_id(challenge_id)
    if not challenge:
        await update.message.reply_text("Челлендж с таким ID не найден.")
        return ConversationHandler.END

    context.user_data['edit_challenge_id'] = challenge_id
    context.user_data['edit_challenge_name'] = challenge[1]

    keyboard = [
        [InlineKeyboardButton("Название", callback_data="chfield_name")],
        [InlineKeyboardButton("Описание", callback_data="chfield_description")],
        [InlineKeyboardButton("Тип цели", callback_data="chfield_target_type")],
        [InlineKeyboardButton("Целевое значение", callback_data="chfield_target_value")],
        [InlineKeyboardButton("Дата начала", callback_data="chfield_start_date")],
        [InlineKeyboardButton("Дата окончания", callback_data="chfield_end_date")],
        [InlineKeyboardButton("Бонус", callback_data="chfield_bonus")],
        [InlineKeyboardButton("Отмена", callback_data="cancel_edit_ch")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Выберите поле для редактирования челленджа '{challenge[1]}' (ID {challenge_id}):",
        reply_markup=reply_markup
    )
    return EDIT_CHALLENGE_VALUE


async def edit_challenge_value_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор поля и ввод нового значения."""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        data = query.data

        if data == "cancel_edit_ch":
            await query.edit_message_text("Редактирование отменено.")
            return ConversationHandler.END

        field_map = {
            "chfield_name": "name",
            "chfield_description": "description",
            "chfield_target_type": "target_type",
            "chfield_target_value": "target_value",
            "chfield_start_date": "start_date",
            "chfield_end_date": "end_date",
            "chfield_bonus": "bonus_points",
        }

        field = field_map.get(data)
        if field:
            context.user_data['edit_challenge_field'] = field
            await query.edit_message_text(f"Введите новое значение для поля {field}:")
            return EDIT_CHALLENGE_VALUE
        else:
            await query.edit_message_text("Неизвестное поле.")
            return ConversationHandler.END
    else:
        # Обработка ввода значения
        text = update.message.text.strip()
        challenge_id = context.user_data.get('edit_challenge_id')
        field = context.user_data.get('edit_challenge_field')

        if not challenge_id or not field:
            await update.message.reply_text("Ошибка: не найден ID или поле.")
            return ConversationHandler.END

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()

        try:
            if field == "bonus_points":
                value = int(text)
            else:
                value = text

            cur.execute(f"UPDATE challenges SET {field} = ? WHERE id = ?", (value, challenge_id))
            conn.commit()
            await update.message.reply_text(f"✅ Поле {field} обновлено на '{value}'.")

        except Exception as e:
            await update.message.reply_text(format_error(f"Ошибка: {e}"))
            return EDIT_CHALLENGE_VALUE
        finally:
            conn.close()

        context.user_data.pop('edit_challenge_field', None)
        context.user_data.pop('edit_challenge_id', None)
        return ConversationHandler.END


async def edit_challenge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для редактирования челленджа."""
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        return
    await edit_challenge_start(update, context)


async def delete_complex_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает диалог удаления комплекса из кнопки."""
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Введите ID комплекса для удаления:")
    else:
        await update.message.reply_text("Введите ID комплекса для удаления:")
    return WAIT_DELETE_COMPLEX_ID


async def delete_complex_get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает ID комплекса и запрашивает подтверждение."""
    try:
        complex_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("ID должен быть числом. Попробуйте ещё раз:")
        return WAIT_DELETE_COMPLEX_ID

    complex_data = get_complex_by_id(complex_id)
    if not complex_data:
        await update.message.reply_text("Комплекс с таким ID не найден.")
        return ConversationHandler.END

    context.user_data['delete_complex_id'] = complex_id
    context.user_data['delete_complex_name'] = complex_data[1]
    await update.message.reply_text(
        f"Вы уверены, что хотите удалить комплекс '{complex_data[1]}' (ID {complex_id})? Отправьте 'ДА' для подтверждения."
    )
    return CONFIRM_DELETE_COMPLEX

# ========== КОНСТРУКТОР ЧЕЛЛЕНДЖЕЙ ==========
async def addchallenge_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("addchallenge_start вызвана")
    if not is_admin(update):
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text("⛔ Нет прав.")
        else:
            await update.message.reply_text("⛔ Нет прав.")
        return ConversationHandler.END

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Введите название челленджа:")
    else:
        await update.message.reply_text("Введите название челленджа:")

    return CHALL_NAME

async def challenge_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("challenge_name_input вызвана")
    name = update.message.text
    context.user_data['challenge_name'] = name
    await update.message.reply_text("Введите описание челленджа (можно пропустить, отправьте '-'):")
    return CHALL_DESC

async def challenge_desc_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("challenge_desc_input вызвана")
    description = update.message.text
    if description == '-':
        description = ''
    context.user_data['challenge_desc'] = description
    keyboard = [
        [InlineKeyboardButton("Упражнение", callback_data="chall_target_exercise")],
        [InlineKeyboardButton("Комплекс", callback_data="chall_target_complex")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите тип цели:", reply_markup=reply_markup)
    return CHALL_TYPE

async def challenge_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "chall_target_exercise":
        context.user_data['challenge_target_type'] = 'exercise'
        exercises = get_all_exercises()
        if not exercises:
            await query.edit_message_text("Нет упражнений. Сначала добавьте упражнения командой /addexercise.")
            return ConversationHandler.END
        keyboard = []
        for ex in exercises:
            ex_id, name, _, _, _, _ = ex
            keyboard.append([InlineKeyboardButton(name, callback_data=f"chall_ex_{ex_id}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите упражнение:", reply_markup=reply_markup)
        return CHALL_TARGET
    else:
        context.user_data['challenge_target_type'] = 'complex'
        complexes = get_all_complexes()
        if not complexes:
            await query.edit_message_text("Нет комплексов. Сначала создайте комплекс.")
            return ConversationHandler.END
        keyboard = []
        for c in complexes:
            c_id, name, _, _, _, _, _ = c
            keyboard.append([InlineKeyboardButton(name, callback_data=f"chall_cx_{c_id}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите комплекс:", reply_markup=reply_markup)
        return CHALL_TARGET

async def challenge_target_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("chall_ex_"):
        target_id = int(data.split('_')[2])
        context.user_data['challenge_target_id'] = target_id
        ex = get_exercise_by_id(target_id)
        if ex:
            context.user_data['challenge_metric'] = ex[3]
            await query.edit_message_text(f"Выбрано упражнение: {ex[1]}. Теперь введите целевое значение (для {ex[3]}):")
        else:
            await query.edit_message_text("Упражнение не найдено.")
            return ConversationHandler.END
        return CHALL_TARGET_VALUE
    else:
        target_id = int(data.split('_')[2])
        context.user_data['challenge_target_id'] = target_id
        complex_data = get_complex_by_id(target_id)
        if complex_data:
            context.user_data['challenge_metric'] = complex_data[3]
            await query.edit_message_text(f"Выбран комплекс: {complex_data[1]}. Введите целевое значение (для {complex_data[3]}):")
        else:
            await query.edit_message_text("Комплекс не найден.")
            return ConversationHandler.END
        return CHALL_TARGET_VALUE

async def challenge_target_value_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_value = update.message.text.strip()
    metric = context.user_data.get('challenge_metric')
    if metric == 'reps':
        try:
            int(target_value)
        except ValueError:
            await update.message.reply_text("Введите целое число повторений.")
            return CHALL_TARGET_VALUE
    else:
        if not re.match(r'^\d{1,2}:\d{2}$', target_value):
            await update.message.reply_text("Введите время в формате ММ:СС (например, 05:30).")
            return CHALL_TARGET_VALUE
    context.user_data['challenge_target_value'] = target_value
    await update.message.reply_text("Введите дату начала челленджа в формате ДД.ММ.ГГГГ (например, 01.04.2026):")
    return CHALL_START_DATE

async def challenge_start_date_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("challenge_start_date_input вызвана")
    start_date_str = update.message.text.strip()
    start_date = parse_date(start_date_str)
    if not start_date:
        await update.message.reply_text("Неверный формат. Введите дату в формате ДД.ММ.ГГГГ (например, 24.03.2026).")
        return CHALL_START_DATE
    context.user_data['challenge_start_date'] = start_date
    await update.message.reply_text("Введите дату окончания челленджа в формате ДД.ММ.ГГГГ (например, 30.04.2026):")
    return CHALL_END_DATE

async def challenge_end_date_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("challenge_end_date_input вызвана")
    end_date_str = update.message.text.strip()
    end_date = parse_date(end_date_str)
    if not end_date:
        await update.message.reply_text("Неверный формат. Введите дату в формате ДД.ММ.ГГГГ (например, 30.04.2026).")
        return CHALL_END_DATE
    start_date = context.user_data.get('challenge_start_date')
    if start_date and end_date <= start_date:
        await update.message.reply_text("Дата окончания должна быть позже даты начала. Попробуйте ещё раз.")
        return CHALL_END_DATE
    context.user_data['challenge_end_date'] = end_date
    await update.message.reply_text("Введите количество бонусных баллов за выполнение челленджа (целое число):")
    return CHALL_BONUS

async def challenge_bonus_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("challenge_bonus_input вызвана")
    try:
        bonus = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Введите целое число (бонусные баллы).")
        return CHALL_BONUS
    context.user_data['challenge_bonus'] = bonus

    success = add_challenge(
        name=context.user_data['challenge_name'],
        description=context.user_data.get('challenge_desc', ''),
        target_type=context.user_data['challenge_target_type'],
        target_id=context.user_data['challenge_target_id'],
        metric=context.user_data['challenge_metric'],
        target_value=context.user_data['challenge_target_value'],
        start_date=context.user_data['challenge_start_date'],
        end_date=context.user_data['challenge_end_date'],
        bonus_points=bonus
    )
    if success:
        await update.message.reply_text("✅ Челлендж успешно создан!")
    else:
        await update.message.reply_text(format_error("Ошибка при сохранении челленджа."))

    for key in ['challenge_name', 'challenge_desc', 'challenge_target_type', 'challenge_target_id',
                'challenge_metric', 'challenge_target_value', 'challenge_start_date', 'challenge_end_date', 'challenge_bonus']:
        context.user_data.pop(key, None)
    return ConversationHandler.END

# ========== ДИАЛОГ СДАЧИ РЕЗУЛЬТАТА (без ConversationHandler) ==========
async def catch_all_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if DEBUG:
        print(f"DEBUG: catch_all_text получил: {update.message.text}")
    if not update.message or not update.message.text:
        return
    # Если нет активного диалога — пропускаем
    if context.user_data.get('conversation_state') is None:
        if DEBUG:
            print("DEBUG: диалог не активен, пропускаем")
        return
    # Обработка отмены
    if update.message.text.endswith('Отмена'):
        await workout_cancel(update, context)
        return
    state = context.user_data.get('conversation_state')
    if state == 60:
        await submit_result_input(update, context)
    elif state == 61:
        await submit_video_input(update, context)
    elif state == 62:
        await submit_comment_input(update, context)

# ========== ОБЩИЕ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def paginate(items, page, per_page=5, prefix='page', extra_data=''):
    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = items[start:end]
    keyboard = []
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("◀️ Назад", callback_data=f"{prefix}_{page-1}_{extra_data}" if extra_data else f"{prefix}_{page-1}"))
    if end < total:
        nav.append(InlineKeyboardButton("Вперёд ▶️", callback_data=f"{prefix}_{page+1}_{extra_data}" if extra_data else f"{prefix}_{page+1}"))
    if nav:
        keyboard.append(nav)
    return page_items, keyboard

def get_exercise_icon(name):
    name_lower = name.lower()
    icons = {
        "присед": "🏋️‍♂️", "берпи": "💥", "бурпи": "💥", "отжим": "💪",
        "подтяг": "🤸", "бег": "🏃", "кросс": "🏃", "тяга": "🏋️",
        "становая": "🏋️", "складка": "🧘", "пресс": "🧘", "ходьба": "🚶", "стойка": "🚶"
    }
    for key, icon in icons.items():
        if key in name_lower: return icon
    return "📌"

# ========== ОБРАБОТЧИКИ КНОПОК ==========
async def setlevel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    level = query.data.split('_')[1]
    user_id = update.effective_user.id
    if set_user_level(user_id, level):
        await query.edit_message_text(f"✅ Уровень изменён на «{level}».")
    else:
        await query.edit_message_text(format_error("Ошибка при смене уровня."))

async def exercise_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ex_id = int(query.data.split('_')[1])
    ex = get_exercise_by_id(ex_id)
    if not ex:
        await query.edit_message_text("Упражнение не найдено.")
        return

    _, name, description, metric, points, week, difficulty = ex
    text = f"**{name}**\n"
    if description:
        text += f"{description}\n"
    text += f"🏅 Баллы: {points}\n"
    text += f"📏 Тип: {'повторения' if metric == 'reps' else 'время'}\n"
    text += f"🎯 Уровень: {'Новички' if difficulty == 'beginner' else 'Профи'}\n"
    if week != 0:
        text += f"🗓️ Активно: неделя {week}\n"

    keyboard = [[InlineKeyboardButton("✍️ Записать тренировку", callback_data=f"record_{ex_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def record_from_catalog_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ex_id = int(query.data.split('_')[1])
    context.user_data['pending_exercise'] = ex_id
    await query.edit_message_text("Теперь отправь команду /wod, чтобы записать это упражнение.")

async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == 'help_sport':
        text = "🏋️ **Спорт**\n"
        text += "/wod — записать тренировку\n"
        text += "/catalog — каталог упражнений\n"
        text += "/mystats — моя статистика\n"
        text += "/setlevel — сменить уровень (новичок/профи)"
    elif data == 'help_photo':
        text = "📸 **Фото**\n"
        text += "/menu — выбрать стиль и отправить фото.\n"
        text += "Доступны стили: карандаш, аниме, сепия, хард-рок, пиксель, неон, масло, акварель, мультяшный."
    elif data == 'help_stats':
        text = "📊 **Статистика**\n"
        text += "/mystats [day|week|month|year] — твоя статистика\n"
        text += "/top [day|week|month|year] [beginner|pro] — таблица лидеров"
    elif data == 'help_top':
        text = "🏆 **Рейтинг**\n"
        text += "/top — топ за всё время в твоей лиге\n"
        text += "Можно добавить период (day, week, month, year) и лигу (beginner, pro)."
    elif data == 'help_admin':
        text = "⚙️ **Админ**\n"
        text += "/config — настройка AI\n"
        text += "/addexercise — добавить упражнение\n"
        text += "/delexercise — удалить упражнение\n"
        text += "/listexercises — список упражнений\n"
        text += "/load_exercises — загрузить из JSON"
    else:
        text = "Информация не найдена."
    await query.edit_message_text(text, parse_mode='Markdown')

async def stats_period_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    period = query.data.split('_')[1] if query.data != 'stats_all' else None
    user_id = update.effective_user.id
    pts, wods = get_user_stats(user_id, period)
    period_text = f" за {period}" if period else " за всё время"
    await query.message.reply_text(f"📊 Твоя статистика{period_text}:\n🏋️ Тренировок: {wods or 0}\n⭐ Баллов: {pts or 0}")

async def top_league_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    league = query.data.split('_')[1]
    leaderboard = get_leaderboard(None, league)
    if not leaderboard:
        await query.message.reply_text("Нет данных.")
        return
    text = f"🏆 **Топ игроков ({'Новички' if league == 'beginner' else 'Профи'}):**\n"
    for i, (uid, fname, uname, total) in enumerate(leaderboard, 1):
        text += f"{i}. {fname or uname} — {total}\n"
    await query.message.reply_text(text, parse_mode='Markdown')

# ========== КОМАНДЫ ДЛЯ УПРАЖНЕНИЙ ==========
async def add_exercise_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        return
    full_text = update.message.text
    if ' ' not in full_text:
        await update.message.reply_text("Использование: /addexercise <название> <reps|time> <описание> <баллы> [неделя] [difficulty]")
        return
    args_part = full_text.split(maxsplit=1)[1]
    try:
        args = shlex.split(args_part)
        if len(args) < 4:
            await update.message.reply_text("❌ Нужно минимум 4 аргумента.")
            return
        name, metric, desc, points = args[0], args[1], args[2], int(args[3])
        week = int(args[4]) if len(args) > 4 and args[4].isdigit() else 0
        diff = args[5] if len(args) > 5 else 'beginner'
        if add_exercise(name, desc, metric, points, week, diff):
            await update.message.reply_text(f"✅ Упражнение '{name}' добавлено.")
        else:
            await update.message.reply_text(format_error("Ошибка добавления."))
    except Exception as e:
        await update.message.reply_text(format_error(f"Ошибка парсинга: {e}"))

async def delete_exercise_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        return
    if not context.args:
        await update.message.reply_text("Использование: /delexercise <id>")
        return
    try:
        exercise_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return

    ex = get_exercise_by_id(exercise_id)
    if not ex:
        await update.message.reply_text("Упражнение с таким ID не найдено.")
        return

    context.user_data['delete_exercise_id'] = exercise_id
    context.user_data['delete_exercise_name'] = ex[1]
    await update.message.reply_text(f"Вы уверены, что хотите удалить упражнение '{ex[1]}' (ID {exercise_id})? Отправьте 'ДА' для подтверждения.")
    return CONFIRM_DELETE

async def delete_exercise_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает диалог удаления упражнения из кнопки."""
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Введите ID упражнения для удаления:")
    else:
        await update.message.reply_text("Введите ID упражнения для удаления:")
    return WAIT_DELETE_ID


async def delete_exercise_get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает ID упражнения и запрашивает подтверждение."""
    try:
        exercise_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("ID должен быть числом. Попробуйте ещё раз:")
        return WAIT_DELETE_ID


    ex = get_exercise_by_id(exercise_id)
    if not ex:
        await update.message.reply_text("Упражнение с таким ID не найдено.")
        return ConversationHandler.END

    context.user_data['delete_exercise_id'] = exercise_id
    context.user_data['delete_exercise_name'] = ex[1]
    await update.message.reply_text(
        f"Вы уверены, что хотите удалить упражнение '{ex[1]}' (ID {exercise_id})? Отправьте 'ДА' для подтверждения.")
    return CONFIRM_DELETE

async def confirm_delete_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.upper() == "ДА":
        exercise_id = context.user_data.get('delete_exercise_id')
        if exercise_id:
            if delete_exercise(exercise_id):
                await update.message.reply_text(f"✅ Упражнение ID {exercise_id} удалено.")
            else:
                await update.message.reply_text(format_error("Ошибка при удалении."))
        else:
            await update.message.reply_text("❌ Не удалось определить ID.")
    else:
        await update.message.reply_text("❌ Удаление отменено.")
    context.user_data.pop('delete_exercise_id', None)
    context.user_data.pop('delete_exercise_name', None)
    return ConversationHandler.END

async def list_exercises_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    page = 1
    if context.args and context.args[0].isdigit():
        page = int(context.args[0])
    all_exercises = get_all_exercises()
    if not all_exercises:
        await update.message.reply_text("Упражнений пока нет.")
        return
    exercises, keyboard = paginate(all_exercises, page, per_page=5, prefix='ex_page')
    text = "📋 **Список упражнений:**\n\n"
    for ex in exercises:
        name = ex[1].replace('_', r'\_').replace('*', r'\*').replace('[', r'\[').replace(']', r'\]').replace('(', r'\(').replace(')', r'\)')
        text += f"🔹 ID: {ex[0]} — {name} ({ex[5]})\n"
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def exercise_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split('_')[2])
    all_exercises = get_all_exercises()
    exercises, keyboard = paginate(all_exercises, page, per_page=5, prefix='ex_page')
    text = "📋 **Список упражнений:**\n\n"
    for ex in exercises:
        name = ex[1].replace('_', r'\_').replace('*', r'\*').replace('[', r'\[').replace(']', r'\]').replace('(', r'\(').replace(')', r'\)')
        text += f"🔹 ID: {ex[0]} — {name} ({ex[5]})\n"
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def load_exercises_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    try:
        with open('exercises.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            for ex in data:
                add_exercise(ex['name'], ex.get('description',''), ex['metric'], ex['points'], ex.get('week',0), ex.get('difficulty','beginner'))
        await update.message.reply_text("✅ Загружено.")
    except Exception as e:
        await update.message.reply_text(format_error(f"Ошибка: {e}"))

async def recalc_rankings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        return
    await update.message.reply_text("⏳ Начинаю пересчёт рейтинга...")
    recalculate_rankings(period_days=7)
    await update.message.reply_text("✅ Рейтинг пересчитан. Баллы начислены.")

async def setlevel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if context.args and context.args[0] in ('beginner', 'pro'):
        if set_user_level(user_id, context.args[0]):
            await update.message.reply_text(f"✅ Уровень изменён на {context.args[0]}.")
        else:
            await update.message.reply_text(format_error("Ошибка при смене уровня."))
    else:
        keyboard = [
            [InlineKeyboardButton("Новичок (beginner)", callback_data="setlevel_beginner")],
            [InlineKeyboardButton("Профи (pro)", callback_data="setlevel_pro")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Выбери уровень:", reply_markup=reply_markup)

# ========== КОМАНДЫ ДЛЯ ЧЕЛЛЕНДЖЕЙ ==========
async def challenges_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = 'active'
    if context.args and len(context.args) > 0 and context.args[0] in ('active', 'past', 'future'):
        status = context.args[0]
    challenges = get_challenges_by_status(status)
    if not challenges:
        if update.callback_query:
            await update.callback_query.edit_message_text(f"Челленджей со статусом '{status}' нет.")
        else:
            await update.message.reply_text(f"Челленджей со статусом '{status}' нет.")
        return

    page = 1
    if context.args and len(context.args) > 1 and context.args[1].isdigit():
        page = int(context.args[1])
    items, keyboard = paginate(challenges, page, per_page=5, prefix='challenge_page', extra_data=status)
    text = f"🏆 **Челленджи ({status}):**\n\n"
    for ch in items:
        ch_id, name, desc, target_type, target_id, metric, target_value, start_date, end_date, bonus, target_name = ch
        name = name.replace('_', r'\_').replace('*', r'\*').replace('[', r'\[').replace(']', r'\]').replace('(', r'\(').replace(')', r'\)')
        target_name = target_name.replace('_', r'\_').replace('*', r'\*').replace('[', r'\[').replace(']', r'\]').replace('(', r'\(').replace(')', r'\)')
        text += f"**{name}** (ID {ch_id})\n"
        text += f"Цель: {'упражнение' if target_type == 'exercise' else 'комплекс'} «{target_name}» (ID {target_id})\n"
        text += f"Норма: {target_value} ({metric})\n"
        text += f"Период: {start_date} – {end_date}\n"
        text += f"Бонус: {bonus} баллов\n\n"

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def join_challenge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        challenge_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Использование: /join <id_челленджа>")
        return

    user_id = update.effective_user.id
    challenge = get_challenge_by_id(challenge_id)
    if not challenge:
        await update.message.reply_text("Челлендж с таким ID не найден или уже неактивен.")
        return

    challenge_name = challenge[1]
    success = join_challenge(user_id, challenge_id)
    if success:
        await update.message.reply_text(f"✅ Вы успешно присоединились к челленджу «{challenge_name}» (ID {challenge_id})!")
    else:
        await update.message.reply_text(f"❌ Вы уже участвуете в челлендже «{challenge_name}» (ID {challenge_id}).")

async def leave_challenge_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    challenge_id = int(query.data.split('_')[1])
    user_id = update.effective_user.id
    challenge_name = get_challenge_name(challenge_id) or str(challenge_id)
    leave_challenge(user_id, challenge_id)
    await query.edit_message_text(f"✅ Вы вышли из челленджа «{challenge_name}».")

async def my_challenges_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    challenges = get_user_challenges_with_details(user_id)
    if not challenges:
        await update.message.reply_text("Вы не участвуете ни в одном активном челлендже.")
        return

    text = "🏆 **Ваши челленджи:**\n\n"
    keyboard = []
    for ch in challenges:
        ch_id, name, target_type, target_id, metric, target_value, bonus, start, end, current, target_name = ch
        name = name.replace('_', r'\_').replace('*', r'\*').replace('[', r'\[').replace(']', r'\]')
        target_name = target_name.replace('_', r'\_').replace('*', r'\*').replace('[', r'\[').replace(']', r'\]')
        text += f"**{name}** (ID {ch_id})\n"
        text += f"Цель: {target_name} (ID {target_id})\n"
        text += f"Норма: {target_value} {metric}\n"
        text += f"Прогресс: {current} / {target_value}\n"
        text += f"Период: {start} – {end}\n"
        text += f"Бонус: {bonus} баллов\n\n"
        keyboard.append([InlineKeyboardButton(f"Выйти из {name}", callback_data=f"leave_{ch_id}")])

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def myprogress_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("myprogress_command вызвана")
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT c.id, c.name, c.target_value, c.metric,
               COALESCE(p.current_value, '0') as current_value
        FROM challenges c
        JOIN user_challenges uc ON c.id = uc.challenge_id
        LEFT JOIN user_challenge_progress p ON c.id = p.challenge_id AND p.user_id = uc.user_id
        WHERE uc.user_id = ? AND c.is_active = 1
          AND date('now') BETWEEN date(c.start_date) AND date(c.end_date)
        ORDER BY c.id
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()
    logger.info(f"Найдено челленджей: {len(rows)}")

    if not rows:
        await update.message.reply_text("Вы пока не участвуете ни в одном активном челлендже.")
        return

    text = "🏆 **Ваши активные челленджи:**\n\n"
    keyboard = []
    for row in rows:
        ch_id, name, target, metric, current = row
        name = name.replace('_', r'\_').replace('*', r'\*').replace('[', r'\[').replace(']', r'\]')
        if metric == 'reps':
            text += f"**{name}** (ID {ch_id})\n"
            text += f"Прогресс: {current} / {target} повторений\n\n"
        else:
            text += f"**{name}** (ID {ch_id})\n"
            text += f"Прогресс: {current} / {target} (время)\n\n"
        keyboard.append([InlineKeyboardButton(f"❌ Выйти из {name}", callback_data=f"leave_{ch_id}")])

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)

# ========== ДРУГИЕ КОМАНДЫ ==========
async def myhistory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    limit = 20
    if context.args and context.args[0].isdigit():
        limit = int(context.args[0])
        if limit > 50:
            limit = 50
    workouts = get_user_workouts(user_id, limit)
    if not workouts:
        await update.message.reply_text("У тебя пока нет записанных тренировок.")
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
    await update.message.reply_text(text, parse_mode='Markdown', disable_web_page_preview=True)

# ========== КОНФИГУРАЦИЯ КОНСИЛИУМА ==========
async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ У вас нет прав на эту команду.")
        return
    keyboard = []
    for provider, enabled in ENABLED_PROVIDERS.items():
        status = "✅ ВКЛ" if enabled else "❌ ВЫКЛ"
        keyboard.append([InlineKeyboardButton(f"{provider} {status}", callback_data=f"toggle_{provider}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "⚙️ **Настройки консилиума**\n"
        "Нажми на кнопку, чтобы включить/выключить участника:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def config_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("⛔ Недоступно.")
        return
    callback_data = query.data
    if callback_data.startswith("toggle_"):
        provider = callback_data.replace("toggle_", "")
        if provider in ENABLED_PROVIDERS:
            ENABLED_PROVIDERS[provider] = not ENABLED_PROVIDERS[provider]
            keyboard = []
            for p, enabled in ENABLED_PROVIDERS.items():
                status = "✅ ВКЛ" if enabled else "❌ ВЫКЛ"
                keyboard.append([InlineKeyboardButton(f"{p} {status}", callback_data=f"toggle_{p}")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "⚙️ **Настройки консилиума**\n"
                "Нажми на кнопку, чтобы включить/выключить участника:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

# ========== СЕРВЕР И БД ==========
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/cron'):
            query = parse_qs(urlparse(self.path).query)
            if query.get('key', [None])[0] == os.getenv("CRON_SECRET", "default_secret"):
                self.send_response(200)
                self.end_headers()
                threading.Thread(target=self._check_and_recalc).start()
                return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def _check_and_recalc(self):
        from database_backup import get_last_recalc, set_last_recalc
        now = datetime.now()
        last = get_last_recalc()
        if last is None or (now - last).days >= 7:
            recalculate_rankings(period_days=7)
            set_last_recalc(now)

init_db()
backup_database()
Thread(target=lambda: HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 10000))), HealthCheckHandler).serve_forever(), daemon=True).start()

async def complex_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split('_')[2])
    all_complexes = get_all_complexes()
    complexes, keyboard = paginate(all_complexes, page, per_page=5, prefix='complex_page')
    text = "🏋️ **Доступные комплексы:**\n\n"
    for c in complexes:
        text += f"ID: {c[0]} — **{c[1]}**\n"
        text += f"   Тип: {'Время' if c[3] == 'for_time' else 'Повторения'}\n"
        text += f"   Баллы: {c[4]}\n\n"
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def edit_complex_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("edit_complex_command вызвана")
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        return
    if not context.args:
        await update.message.reply_text("Использование: /editcomplex <id>")
        return
    try:
        complex_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return

    complex_data = get_complex_by_id(complex_id)
    if not complex_data:
        await update.message.reply_text("Комплекс с таким ID не найден.")
        return

    context.user_data['edit_complex_id'] = complex_id
    keyboard = [
        [InlineKeyboardButton("Название", callback_data="cfield_name")],
        [InlineKeyboardButton("Описание", callback_data="cfield_description")],
        [InlineKeyboardButton("Тип (for_time/for_reps)", callback_data="cfield_type")],
        [InlineKeyboardButton("Баллы", callback_data="cfield_points")],
        [InlineKeyboardButton("Добавить упражнение", callback_data="cfield_add_ex")],
        [InlineKeyboardButton("Удалить упражнение", callback_data="cfield_remove_ex")],
        [InlineKeyboardButton("Отмена", callback_data="cancel_edit")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Выберите поле для редактирования комплекса '{complex_data[1]}' (ID {complex_id}):",
        reply_markup=reply_markup
    )
    return EDIT_COMPLEX_ID


async def edit_complex_field_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор поля для редактирования."""
    logger.info("edit_complex_field_callback вызвана")
    query = update.callback_query
    logger.info(f"edit_complex_field_callback с data = {query.data}")
    await query.answer()

    if query.data == "cancel_edit":
        await query.edit_message_text("Редактирование отменено.")
        return ConversationHandler.END

    field_map = {
        "cfield_name": "name",
        "cfield_description": "description",
        "cfield_type": "type",
        "cfield_points": "points",
    }

    field = field_map.get(query.data)
    if field:
        context.user_data['edit_complex_field'] = field
        await query.edit_message_text(f"Введите новое значение для поля {field}:")
        return EDIT_COMPLEX_VALUE

    elif query.data == "cfield_add_ex":
        await query.edit_message_text("Введите ID упражнения и количество повторений через пробел, например: 5 10")
        context.user_data['edit_complex_action'] = 'add_ex'
        return EDIT_COMPLEX_VALUE

    elif query.data == "cfield_remove_ex":
        await query.edit_message_text("Введите ID упражнения, которое нужно удалить из комплекса:")
        context.user_data['edit_complex_action'] = 'remove_ex'
        return EDIT_COMPLEX_VALUE

    else:
        await query.edit_message_text("Неизвестное поле.")
        return ConversationHandler.END


async def edit_complex_value_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод нового значения."""
    text = update.message.text.strip()
    complex_id = context.user_data.get('edit_complex_id')
    action = context.user_data.get('edit_complex_action')
    field = context.user_data.get('edit_complex_field')

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    try:
        if action == 'add_ex':
            parts = text.split()
            if len(parts) != 2:
                await update.message.reply_text("Нужно указать ID упражнения и количество повторений, например: 5 10")
                return EDIT_COMPLEX_VALUE
            ex_id = int(parts[0])
            reps = int(parts[1])
            # Проверяем, есть ли уже такое упражнение
            cur.execute("SELECT 1 FROM complex_exercises WHERE complex_id = ? AND exercise_id = ?", (complex_id, ex_id))
            if cur.fetchone():
                await update.message.reply_text("Это упражнение уже есть в комплексе.")
            else:
                # Добавляем упражнение в комплекс
                cur.execute("""
                            INSERT INTO complex_exercises (complex_id, exercise_id, reps, order_index)
                            VALUES (?, ?, ?, (SELECT COALESCE(MAX(order_index), 0) + 1
                                              FROM complex_exercises
                                              WHERE complex_id = ?))
                            """, (complex_id, ex_id, reps, complex_id))
                conn.commit()
                await update.message.reply_text(f"✅ Упражнение {ex_id} добавлено с {reps} повторениями.")
            context.user_data.pop('edit_complex_action', None)
            return ConversationHandler.END

        elif action == 'remove_ex':
            ex_id = int(text)
            cur.execute("DELETE FROM complex_exercises WHERE complex_id = ? AND exercise_id = ?", (complex_id, ex_id))
            conn.commit()
            await update.message.reply_text(f"✅ Упражнение {ex_id} удалено из комплекса.")
            context.user_data.pop('edit_complex_action', None)
            return ConversationHandler.END

        elif field:
            if field == "points":
                try:
                    value = int(text)
                except ValueError:
                    await update.message.reply_text("Баллы должны быть числом.")
                    return EDIT_COMPLEX_VALUE
            else:
                value = text
            cur.execute(f"UPDATE complexes SET {field} = ? WHERE id = ?", (value, complex_id))
            conn.commit()
            await update.message.reply_text(f"✅ Поле {field} обновлено на '{value}'.")
            context.user_data.pop('edit_complex_field', None)
            return ConversationHandler.END

    except Exception as e:
        await update.message.reply_text(format_error(f"Ошибка: {e}"))
        return ConversationHandler.END
    finally:
        conn.close()

    context.user_data.pop('edit_complex_id', None)
    return ConversationHandler.END


async def edit_exercise_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает диалог редактирования упражнения."""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("Введите ID упражнения:")
    else:
        await update.message.reply_text("Введите ID упражнения:")
    return EDIT_EXERCISE_ID


async def edit_exercise_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("edit_exercise_id_input вызвана")
    try:
        exercise_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("ID должен быть числом. Попробуйте ещё раз:")
        return EDIT_EXERCISE_ID

    ex = get_exercise_by_id(exercise_id)
    if not ex:
        await update.message.reply_text("Упражнение с таким ID не найдено.")
        return ConversationHandler.END

    context.user_data['edit_exercise_id'] = exercise_id

    keyboard = [
        [InlineKeyboardButton("Название", callback_data="exfield_name")],
        [InlineKeyboardButton("Описание", callback_data="exfield_description")],
        [InlineKeyboardButton("Тип (reps/time)", callback_data="exfield_metric")],
        [InlineKeyboardButton("Баллы", callback_data="exfield_points")],
        [InlineKeyboardButton("Неделя", callback_data="exfield_week")],
        [InlineKeyboardButton("Уровень (beginner/pro)", callback_data="exfield_diff")],
        [InlineKeyboardButton("Отмена", callback_data="cancel_edit_ex")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Выберите поле для редактирования упражнения '{ex[1]}' (ID {exercise_id}):",
        reply_markup=reply_markup
    )
    logger.info("edit_exercise_id_input возвращает EDIT_EXERCISE_VALUE")
    return EDIT_EXERCISE_VALUE


async def edit_exercise_value_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("edit_exercise_value_input вызвана")
    """Обрабатывает выбор поля и ввод нового значения."""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        data = query.data
        logger.info(f"edit_exercise_value_input: колбэк data={data}")

        if data == "cancel_edit_ex":
            await query.edit_message_text("Редактирование отменено.")
            return ConversationHandler.END

        field_map = {
            "exfield_name": "name",
            "exfield_description": "description",
            "exfield_metric": "metric",
            "exfield_points": "points",
            "exfield_week": "week",
            "exfield_diff": "difficulty",
        }

        field = field_map.get(data)
        if field:
            context.user_data['edit_exercise_field'] = field
            await query.edit_message_text(f"Введите новое значение для поля {field}:")
            return EDIT_EXERCISE_VALUE
        else:
            await query.edit_message_text("Неизвестное поле.")
            return ConversationHandler.END
    else:
        # Обработка ввода значения
        text = update.message.text.strip()
        exercise_id = context.user_data.get('edit_exercise_id')
        field = context.user_data.get('edit_exercise_field')

        if not exercise_id or not field:
            await update.message.reply_text("Ошибка: не найден ID или поле.")
            return ConversationHandler.END

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()

        try:
            if field == "points":
                value = int(text)
            elif field == "week":
                value = int(text)
            elif field == "metric":
                if text not in ('reps', 'time'):
                    await update.message.reply_text("Тип должен быть 'reps' или 'time'.")
                    return EDIT_EXERCISE_VALUE
                value = text
            elif field == "difficulty":
                if text not in ('beginner', 'pro'):
                    await update.message.reply_text("Уровень должен быть 'beginner' или 'pro'.")
                    return EDIT_EXERCISE_VALUE
                value = text
            else:
                value = text

            cur.execute(f"UPDATE exercises SET {field} = ? WHERE id = ?", (value, exercise_id))
            conn.commit()
            await update.message.reply_text(f"✅ Поле {field} обновлено на '{value}'.")

        except Exception as e:
            await update.message.reply_text(format_error(f"Ошибка: {e}"))
            return EDIT_EXERCISE_VALUE
        finally:
            conn.close()

        context.user_data.pop('edit_exercise_field', None)
        context.user_data.pop('edit_exercise_id', None)
        return ConversationHandler.END

async def edit_exercise_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для редактирования упражнения."""
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        return
    await edit_exercise_start(update, context)

async def exercise_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split('_')[2])
    all_exercises = get_all_exercises()
    exercises, keyboard = paginate(all_exercises, page, per_page=5, prefix='ex_page')
    text = "📋 **Список упражнений:**\n\n"
    for ex in exercises:
        name = ex[1].replace('_', r'\_').replace('*', r'\*').replace('[', r'\[').replace(']', r'\]').replace('(', r'\(').replace(')', r'\)')
        text += f"🔹 ID: {ex[0]} — {name} ({ex[5]})\n"
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def challenge_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split('_')
    page = int(parts[2])
    status = parts[3] if len(parts) > 3 else 'active'
    challenges = get_challenges_by_status(status)
    items, keyboard = paginate(challenges, page, per_page=5, prefix='challenge_page', extra_data=status)
    text = f"🏆 **Челленджи ({status}):**\n\n"
    for ch in items:
        ch_id, name, desc, target_type, target_id, metric, target_value, start_date, end_date, bonus, target_name = ch
        name = name.replace('_', r'\_').replace('*', r'\*').replace('[', r'\[').replace(']', r'\]').replace('(', r'\(').replace(')', r'\)')
        target_name = target_name.replace('_', r'\_').replace('*', r'\*').replace('[', r'\[').replace(']', r'\]').replace('(', r'\(').replace(')', r'\)')
        text += f"**{name}** (ID {ch_id})\n"
        text += f"Цель: {'упражнение' if target_type == 'exercise' else 'комплекс'} «{target_name}» (ID {target_id})\n"
        text += f"Норма: {target_value} ({metric})\n"
        text += f"Период: {start_date} – {end_date}\n"
        text += f"Бонус: {bonus} баллов\n\n"
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def skip_comment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from workout_handlers import skip_comment_finalize
    await skip_comment_finalize(update, context)

async def cancel_submit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("❌ Ввод результата отменён.")

async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает текущее состояние диалога (только для админа)."""
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        return
    user_id = update.effective_user.id
    state = context.user_data.get('conversation_state')
    user_data_keys = list(context.user_data.keys())
    await update.message.reply_text(
        f"📊 **Состояние диалога**\n\n"
        f"`conversation_state`: {state}\n"
        f"`user_data` ключи: {user_data_keys}\n"
        f"👤 `user_id`: {user_id}\n\n"
        f"Если нужно больше данных — скажи.",
        parse_mode='Markdown'
    )

# ========== ОСНОВНАЯ ФУНКЦИЯ ЗАПУСКА ==========
def main():
    logger.info("MAIN: started")
    if not TOKEN:
        raise ValueError("Забыли TELEGRAM_BOT_TOKEN!")

    app = Application.builder().token(TOKEN).build()

    # ========== 1. КОМАНДЫ (все должны быть зарегистрированы до обработчиков сообщений) ==========
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", show_menu))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("config", config_command))
    app.add_handler(CommandHandler("addexercise", add_exercise_command))
    app.add_handler(CommandHandler("listexercises", list_exercises_command))
    app.add_handler(CommandHandler("load_exercises", load_exercises_command))
    app.add_handler(CommandHandler("mystats", lambda u, c: mystats_command(u.message, c)))
    app.add_handler(CommandHandler("top", top_command))
    app.add_handler(CommandHandler("setlevel", setlevel_command))
    app.add_handler(CommandHandler("catalog", catalog_command))
    app.add_handler(CommandHandler("myhistory", myhistory_command))
    app.add_handler(CommandHandler("recalc_rankings", recalc_rankings_command))
    app.add_handler(CommandHandler("addcomplex", add_complex_command))
    app.add_handler(CommandHandler("addcomplexexercise", add_complex_exercise_command))
    app.add_handler(CommandHandler("complexes", complexes_command))
    app.add_handler(CommandHandler("complex", complex_detail_command))
    app.add_handler(CommandHandler("challenges", challenges_command))
    app.add_handler(CommandHandler("join", join_challenge_command))
    app.add_handler(CommandHandler("deletecomplex", delete_complex_command))
    app.add_handler(CommandHandler("myprogress", myprogress_command))
    app.add_handler(CommandHandler("set_channel", set_channel_command))
    app.add_handler(CommandHandler("get_channel", get_channel_command))
    app.add_handler(CommandHandler("get_channel_id", get_channel_id))
    app.add_handler(CommandHandler("mychallenges", my_challenges_command))
    app.add_handler(CommandHandler("calendar", calendar_command))
    app.add_handler(CommandHandler("publish_complex", publish_complex_command))
    app.add_handler(CommandHandler("debug", debug_command))
    app.add_handler(CommandHandler("newcomplex", newcomplex_start))
    app.add_handler(CommandHandler("addchallenge", addchallenge_start))
    app.add_handler(CommandHandler("delexercise", delete_exercise_command))

    # ========== 2. ИМПОРТЫ ДЛЯ АДМИНКИ ==========
    from admin_handlers import (
        EXERCISE_NAME, EXERCISE_DESC, EXERCISE_METRIC, EXERCISE_POINTS, EXERCISE_WEEK, EXERCISE_DIFF,
        admin_exercise_add_name, admin_exercise_add_desc, admin_exercise_add_metric,
        admin_exercise_add_points, admin_exercise_add_week, admin_exercise_add_diff,
        admin_exercise_add_start, admin_cancel, admin_callback,
    )

    # ========== 3. CONVERSATION HANDLERS ==========

    # 3.0 Диалог редактирования комплекса (ДОЛЖЕН БЫТЬ ПЕРВЫМ)
    edit_complex_conv = ConversationHandler(
        entry_points=[CommandHandler('editcomplex', edit_complex_command)],
        states={
            EDIT_COMPLEX_ID: [CallbackQueryHandler(edit_complex_field_callback, pattern='^cfield_|cancel_edit')],
            EDIT_COMPLEX_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_complex_value_input)],
        },
        fallbacks=[CommandHandler('cancel', workout_cancel)],
    )
    app.add_handler(edit_complex_conv)

    # 3.1 Диалог редактирования упражнения
    edit_exercise_conv = ConversationHandler(
        entry_points=[
            CommandHandler('editexercise', edit_exercise_command),
            CallbackQueryHandler(edit_exercise_start, pattern='^admin_ex_edit$')
        ],
        states={
            EDIT_EXERCISE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_exercise_id_input)],
            EDIT_EXERCISE_VALUE: [
                CallbackQueryHandler(edit_exercise_value_input, pattern='^exfield_|cancel_edit_ex'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_exercise_value_input)
            ],
        },
        fallbacks=[CommandHandler('cancel', workout_cancel)],
    )
    app.add_handler(edit_exercise_conv)

    # 3.2 Диалог добавления упражнения
    admin_add_exercise_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_exercise_add_start, pattern='^admin_ex_add$')],
        states={
            EXERCISE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_exercise_add_name)],
            EXERCISE_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_exercise_add_desc)],
            EXERCISE_METRIC: [CallbackQueryHandler(admin_exercise_add_metric, pattern='^ex_metric_')],
            EXERCISE_POINTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_exercise_add_points)],
            EXERCISE_WEEK: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_exercise_add_week)],
            EXERCISE_DIFF: [CallbackQueryHandler(admin_exercise_add_diff, pattern='^ex_diff_')],
        },
        fallbacks=[CommandHandler('cancel', admin_cancel)],
    )
    app.add_handler(admin_add_exercise_conv)

    # 3.3 Диалог выполнения комплекса
    complex_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(do_complex_start, pattern='^do_complex_\\d+$')],
        states={
            COMPLEX_RESULT: [MessageHandler(filters.TEXT & ~filters.COMMAND, complex_result_input)],
            COMPLEX_VIDEO: [MessageHandler(filters.TEXT & ~filters.COMMAND, complex_video_input),
                            CommandHandler('skip', complex_comment_skip)],
            COMPLEX_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, complex_comment_input),
                              CommandHandler('skip', complex_comment_skip)],
        },
        fallbacks=[CommandHandler('cancel', workout_cancel)],
    )
    app.add_handler(complex_conv)

    # 3.4 Диалог тренировок
    workout_conv = ConversationHandler(
        entry_points=[CommandHandler('wod', workout_start)],
        states={
            EXERCISE: [CallbackQueryHandler(exercise_choice, pattern='^ex_|^cancel$')],
            RESULT: [MessageHandler(filters.TEXT & ~filters.COMMAND, result_input)],
            VIDEO: [MessageHandler(filters.TEXT & ~filters.COMMAND, video_input)],
            COMMENT: [MessageHandler(filters.TEXT, comment_handler)],
        },
        fallbacks=[CommandHandler('cancel', workout_cancel)],
    )
    app.add_handler(workout_conv)

    # 3.5 Диалог конструктора комплексов
    newcomplex_conv = ConversationHandler(
        entry_points=[
            CommandHandler('newcomplex', newcomplex_start),
            CallbackQueryHandler(newcomplex_start, pattern='^admin_cx_add$')
        ],
        states={
            COMPLEX_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, complex_name_input)],
            COMPLEX_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, complex_desc_input)],
            COMPLEX_TYPE: [CallbackQueryHandler(complex_type_temp, pattern='^type_')],
            COMPLEX_POINTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, complex_points_input)],
            COMPLEX_ADD_EXERCISE: [
                CallbackQueryHandler(complex_add_exercise_callback, pattern='^addex_|^finish_complex')
            ],
            COMPLEX_REPS: [MessageHandler(filters.TEXT & ~filters.COMMAND, complex_reps_input)],
        },
        fallbacks=[CommandHandler('cancel', workout_cancel)],
    )
    app.add_handler(newcomplex_conv)

    # 3.6 Диалог челленджа
    challenge_conv = ConversationHandler(
        entry_points=[
            CommandHandler('addchallenge', addchallenge_start),
            CallbackQueryHandler(addchallenge_start, pattern='^admin_ch_add$')
        ],
        states={
            CHALL_NAME: [MessageHandler(filters.TEXT, challenge_name_input)],
            CHALL_DESC: [MessageHandler(filters.TEXT, challenge_desc_input)],
            CHALL_TYPE: [CallbackQueryHandler(challenge_type_callback, pattern='^chall_target_')],
            CHALL_TARGET: [CallbackQueryHandler(challenge_target_callback, pattern='^chall_ex_|^chall_cx_')],
            CHALL_TARGET_VALUE: [MessageHandler(filters.TEXT, challenge_target_value_input)],
            CHALL_START_DATE: [MessageHandler(filters.TEXT, challenge_start_date_input)],
            CHALL_END_DATE: [MessageHandler(filters.TEXT, challenge_end_date_input)],
            CHALL_BONUS: [MessageHandler(filters.TEXT, challenge_bonus_input)],
        },
        fallbacks=[CommandHandler('cancel', workout_cancel)],
        per_user=True,
        per_chat=True,
    )
    app.add_handler(challenge_conv)

    # 3.7 Диалог удаления упражнения
    confirm_conv = ConversationHandler(
        entry_points=[
            CommandHandler('delexercise', delete_exercise_command),
            CallbackQueryHandler(delete_exercise_start, pattern='^admin_ex_delete$')
        ],
        states={
            WAIT_DELETE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_exercise_get_id)],
            CONFIRM_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_delete_exercise)],
        },
        fallbacks=[CommandHandler('cancel', workout_cancel)],
    )
    app.add_handler(confirm_conv)

    # 3.8 Диалог удаления комплекса
    delete_complex_conv = ConversationHandler(
        entry_points=[
            CommandHandler('deletecomplex', delete_complex_command),
            CallbackQueryHandler(delete_complex_start, pattern='^admin_cx_delete$')
        ],
        states={
            WAIT_DELETE_COMPLEX_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_complex_get_id)],
            CONFIRM_DELETE_COMPLEX: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_delete_complex)],
        },
        fallbacks=[CommandHandler('cancel', workout_cancel)],
    )
    app.add_handler(delete_complex_conv)

    # 3.9 Диалог удаления челленджа
    delete_challenge_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(delete_challenge_start, pattern='^admin_ch_delete$')
        ],
        states={
            WAIT_DELETE_CHALLENGE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_challenge_get_id)],
            CONFIRM_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_delete_challenge)],
        },
        fallbacks=[CommandHandler('cancel', workout_cancel)],
    )
    app.add_handler(delete_challenge_conv)

    # 3.10 Диалог редактирования челленджа
    edit_challenge_conv = ConversationHandler(
        entry_points=[
            CommandHandler('editchallenge', edit_challenge_command),
            CallbackQueryHandler(edit_challenge_start, pattern='^admin_ch_edit$')
        ],
        states={
            EDIT_CHALLENGE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_challenge_id_input)],
            EDIT_CHALLENGE_VALUE: [
                CallbackQueryHandler(edit_challenge_value_input, pattern='^chfield_|cancel_edit_ch'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_challenge_value_input)
            ],
        },
        fallbacks=[CommandHandler('cancel', workout_cancel)],
    )
    app.add_handler(edit_challenge_conv)

    # ========== 4. ADMINS CALLBACK (обрабатывает все остальные админ-кнопки) ==========
    app.add_handler(CallbackQueryHandler(admin_callback, pattern='^admin_'))

    # ========== 5. ОСТАЛЬНЫЕ CALLBACK HANDLERS ==========
    app.add_handler(CallbackQueryHandler(submit_complex_callback, pattern='^submit_complex_'))
    app.add_handler(CallbackQueryHandler(button_handler,
                                         pattern='^(sketch|anime|sepia|hardrock|pixel|neon|oil|watercolor|cartoon)$'))
    app.add_handler(CallbackQueryHandler(config_callback_handler, pattern="^toggle_"))
    app.add_handler(CallbackQueryHandler(setlevel_callback, pattern='^setlevel_'))
    app.add_handler(CallbackQueryHandler(sport_callback_handler, pattern='^sport_|^back_to_main$'))
    app.add_handler(CallbackQueryHandler(help_callback, pattern='^help_'))
    app.add_handler(CallbackQueryHandler(exercise_callback, pattern='^ex_'))
    app.add_handler(CallbackQueryHandler(record_from_catalog_callback, pattern='^record_'))
    app.add_handler(CallbackQueryHandler(stats_period_callback, pattern='^stats_'))
    app.add_handler(CallbackQueryHandler(top_league_callback, pattern='^top_league_'))
    app.add_handler(CallbackQueryHandler(complex_page_callback, pattern='^complex_page_'))
    app.add_handler(CallbackQueryHandler(exercise_page_callback, pattern='^ex_page_'))
    app.add_handler(CallbackQueryHandler(challenge_page_callback, pattern='^challenge_page_'))
    app.add_handler(CallbackQueryHandler(cancel_submit_callback, pattern='^cancel_submit$'))
    app.add_handler(CallbackQueryHandler(leave_challenge_callback, pattern='^leave_'))
    app.add_handler(CallbackQueryHandler(skip_comment_callback, pattern='^skip_comment$'))
    app.add_handler(CallbackQueryHandler(calendar_callback, pattern="^cal_"))

    # ========== 6. MESSAGE HANDLERS (должны быть последними) ==========
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler))

    # ========== 7. ОБРАБОТЧИК ОШИБОК ==========
    async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.error(msg="Exception while handling an update:", exc_info=context.error)
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=format_error(f"{str(context.error)[:500]}")
            )
        except:
            pass

    app.add_error_handler(error_handler)

    # ========== 8. ЗАПУСК ==========
    logger.info("MAIN: starting polling")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception("Критическая ошибка: %s", e)

