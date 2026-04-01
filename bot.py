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
from admin_handlers import admin_menu, admin_callback, admin_exercise_add_start, admin_cancel, EXERCISE_NAME, EXERCISE_DESC, EXERCISE_METRIC, EXERCISE_POINTS, EXERCISE_WEEK, EXERCISE_DIFF, admin_exercise_add_name, admin_exercise_add_desc, admin_exercise_add_metric, admin_exercise_add_points, admin_exercise_add_week, admin_exercise_add_diff
from config import EMOJI, SEPARATOR, WELCOME_TEXT, format_success, format_error, format_warning
from dotenv import load_dotenv

load_dotenv()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.error import TelegramError
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
from database import (
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
    complete_challenge, get_challenges_by_status, get_setting, set_setting, get_challenge_name, leave_challenge,
    get_user_challenges_with_details,
    check_and_award_achievements, save_published_post, get_published_post_by_message_id
)
from workout_handlers import (
    workout_start, exercise_choice, result_input, video_input,
    workout_cancel, EXERCISE, RESULT, VIDEO, COMMENT,
    get_current_week, comment_input, comment_skip, comment_handler
)
from submit_handlers import (
    submit_complex_callback, submit_exercise_callback, submit_challenge_callback,
    submit_result_input, submit_video_input, submit_comment_input, submit_comment_skip,
    cancel_submit_callback
)
from channel_notifier import send_to_channel

# === НАСТРОЙКА ЛОГИРОВАНИЯ ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

file_handler = logging.FileHandler('bot.log', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# === КОНСТАНТЫ ===
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_USER_ID", 0))

COMPLEX_RESULT, COMPLEX_VIDEO, COMPLEX_COMMENT = range(10, 13)
COMPLEX_NAME, COMPLEX_DESC, COMPLEX_TYPE, COMPLEX_POINTS, COMPLEX_ADD_EXERCISE = range(20, 25)
COMPLEX_REPS = 25
CHALL_NAME, CHALL_DESC, CHALL_TYPE, CHALL_TARGET, CHALL_TARGET_VALUE, CHALL_START_DATE, CHALL_END_DATE, CHALL_BONUS = range(
    30, 38)
CONFIRM_DELETE = 40
EDIT_COMPLEX_ID, EDIT_COMPLEX_FIELD, EDIT_COMPLEX_VALUE = range(45, 48)
CONFIRM_DELETE_COMPLEX = 50
EDIT_EXERCISE_ID, EDIT_EXERCISE_VALUE = range(55, 57)
WAIT_DELETE_ID = 41
WAIT_DELETE_COMPLEX_ID = 42
WAIT_DELETE_CHALLENGE_ID = 43
EDIT_CHALLENGE_ID, EDIT_CHALLENGE_VALUE = range(60, 62)


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
    except (ValueError, AttributeError):
        return None


# ========== КОМАНДЫ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["🏋️ Спорт", "📸 Фото"],
        ["🤖 Задать вопрос", "❌ Отмена"],
        ["🏆 Рейтинг", "⚙️ Админ"],
        ["📅 Календарь"],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    em = update.effective_message
    if em:
        await em.reply_text(WELCOME_TEXT, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=WELCOME_TEXT,
            reply_markup=reply_markup,
            parse_mode='Markdown',
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
    await update.message.reply_text("🔄 История диалога очищена.")


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
        "🤖 **Помощь**\nВыбери раздел:",
        parse_mode='Markdown', reply_markup=reply_markup
    )


async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Настройка AI"""
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        return
    keyboard = []
    for provider, enabled in ENABLED_PROVIDERS.items():
        status = "✅ ВКЛ" if enabled else "❌ ВЫКЛ"
        keyboard.append([InlineKeyboardButton(f"{provider} {status}", callback_data=f"toggle_{provider}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "⚙️ **Настройки консилиума**\nНажми на кнопку, чтобы включить/выключить участника:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def config_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("⛔ Недоступно.")
        return
    provider = query.data.replace("toggle_", "")
    if provider in ENABLED_PROVIDERS:
        ENABLED_PROVIDERS[provider] = not ENABLED_PROVIDERS[provider]
        keyboard = []
        for p, enabled in ENABLED_PROVIDERS.items():
            status = "✅ ВКЛ" if enabled else "❌ ВЫКЛ"
            keyboard.append([InlineKeyboardButton(f"{p} {status}", callback_data=f"toggle_{p}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "⚙️ **Настройки консилиума**\nНажми на кнопку, чтобы включить/выключить участника:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
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
    try:
        sent_message = await bot.send_message(
            chat_id=channel_id_int,
            text=text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    except TelegramError as e:
        logger.exception("Ошибка публикации комплекса в канал")
        await update.message.reply_text(f"❌ Не удалось отправить в канал: {e}")
        return
    save_published_post('complex', complex_id, channel_id_int, sent_message.message_id)

    await update.message.reply_text(f"✅ Комплекс «{complex_data[1]}» опубликован в канале.")


async def publish_exercise_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Публикует упражнение в канал с кнопкой 'Сдать результат'."""
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        return
    if not context.args:
        await update.message.reply_text("Использование: /publish_exercise <id>")
        return
    try:
        exercise_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return

    exercise = get_exercise_by_id(exercise_id)
    if not exercise:
        await update.message.reply_text("Упражнение не найдено.")
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

    name = exercise[1]
    description = exercise[2] if exercise[2] else "Нет описания"
    metric = exercise[3]
    points = exercise[4]
    metric_text = "повторения" if metric == "reps" else "время"

    text = f"💪 *Новое упражнение: {name}*\n\n{description}\n\n📏 Тип: {metric_text}\n⭐ Баллы: {points}\n\n"

    keyboard = [[InlineKeyboardButton("✅ Сдать результат", callback_data=f"submit_exercise_{exercise_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    bot = context.bot
    try:
        sent_message = await bot.send_message(
            chat_id=channel_id_int,
            text=text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    except TelegramError as e:
        logger.exception("Ошибка публикации упражнения в канал")
        await update.message.reply_text(f"❌ Не удалось отправить в канал: {e}")
        return
    save_published_post('exercise', exercise_id, channel_id_int, sent_message.message_id)

    await update.message.reply_text(f"✅ Упражнение «{name}» опубликовано в канале.")


async def publish_challenge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Публикует челлендж в канал с кнопкой 'Сдать результат'."""
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        return
    if not context.args:
        await update.message.reply_text("Использование: /publish_challenge <id>")
        return
    try:
        challenge_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return

    challenge = get_challenge_by_id(challenge_id)
    if not challenge:
        await update.message.reply_text("Челлендж не найден.")
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

    name = challenge[1]
    description = challenge[2] if challenge[2] else "Нет описания"
    metric = challenge[5]
    target_value = challenge[6]
    bonus = challenge[9]
    metric_text = "повторений" if metric == "reps" else "время"

    text = f"🏆 *Новый челлендж: {name}*\n\n{description}\n\n🎯 Цель: {target_value} {metric_text}\n🎁 Бонус: {bonus} баллов\n\n✅ *Как участвовать:*\n1. Выполните задание\n2. Отправьте результат боту\n3. Соревнуйтесь с другими!\n\n💬 *Обсуждайте в комментариях* 👇"

    keyboard = [[InlineKeyboardButton("✅ Сдать результат", callback_data=f"submit_challenge_{challenge_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    bot = context.bot
    try:
        sent_message = await bot.send_message(
            chat_id=channel_id_int,
            text=text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    except TelegramError as e:
        logger.exception("Ошибка публикации челленджа в канал")
        await update.message.reply_text(f"❌ Не удалось отправить в канал: {e}")
        return
    save_published_post('challenge', challenge_id, channel_id_int, sent_message.message_id)

    await update.message.reply_text(f"✅ Челлендж «{name}» опубликован в канале.")


async def set_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
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
    await update.message.reply_text(f"✅ Канал установлен: {chat_id}")


async def get_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    channel = get_setting("public_channel")
    await update.message.reply_text(f"Текущий канал: {channel}" if channel else "Канал не установлен")


async def get_channel_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        chat_id = update.message.chat_id
        await update.message.reply_text(f"ID этого чата: {chat_id}")


async def comment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для добавления комментария к посту в канале"""
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ Использование: /comment <id_сообщения> <текст>\n\n"
            "Например: /comment 123 Отличная тренировка!"
        )
        return

    try:
        message_id = int(context.args[0])
        comment_text = " ".join(context.args[1:])
    except ValueError:
        await update.message.reply_text("❌ ID сообщения должен быть числом.")
        return

    channel_id = get_setting("public_channel")
    if not channel_id:
        await update.message.reply_text("❌ Канал не настроен.")
        return

    user = update.effective_user
    user_name = user.first_name or user.username or f"User{user.id}"

    try:
        await context.bot.send_message(
            chat_id=int(channel_id),
            text=f"💬 *{user_name}*:\n{comment_text}",
            parse_mode='Markdown',
            reply_to_message_id=message_id
        )
        await update.message.reply_text("✅ Комментарий опубликован в канале!")
        logger.info(f"Комментарий от {user_name} к сообщению {message_id} опубликован")
    except Exception as e:
        logger.error(f"Ошибка комментария: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает текущее состояние диалога (только для админа)."""
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        return
    state = context.user_data.get('conversation_state')
    await update.message.reply_text(f"📊 Состояние диалога: {state}", parse_mode='Markdown')


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
                await update.message.reply_text(clean_answer[i:i + 4000])
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
            'sketch': convert_to_sketch, 'anime': convert_to_anime, 'sepia': convert_to_sepia,
            'hardrock': convert_to_hard_rock, 'pixel': convert_to_pixel, 'neon': convert_to_neon,
            'oil': convert_to_oil, 'watercolor': convert_to_watercolor, 'cartoon': convert_to_cartoon
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
        [InlineKeyboardButton("📋 Каталог", callback_data='sport_catalog')],
        [InlineKeyboardButton("✍️ Тренировка", callback_data='sport_wod')],
        [InlineKeyboardButton("📊 Статистика", callback_data='sport_mystats')],
        [InlineKeyboardButton("🔄 Уровень", callback_data='sport_setlevel')],
        [InlineKeyboardButton("◀️ Назад", callback_data='back_to_main')]
    ]
    await update.message.reply_text("🏋️ Спорт:", reply_markup=InlineKeyboardMarkup(keyboard))


async def sport_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'sport_catalog':
        # Получаем сообщение из query
        await catalog_command(update, context)
    elif data == 'sport_wod':
        await query.edit_message_text("Отправь /wod для записи тренировки")
    elif data == 'sport_mystats':
        await mystats_command(update, context)
    elif data == 'sport_setlevel':
        await setlevel_command(update, context)
    elif data == 'back_to_main':
        await start(update, context)


async def send_catalog_to_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_week = get_current_week()
    exercises = get_all_exercises()
    if not exercises:
        if update.callback_query:
            await update.callback_query.edit_message_text("Список упражнений пуст.")
        else:
            await update.message.reply_text("Список упражнений пуст.")
        return

    text = "📋 **КАТАЛОГ УПРАЖНЕНИЙ**\n\n"
    for ex in exercises:
        text += f"• {ex[1]} – {ex[3]} баллов\n"

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, parse_mode='Markdown')


async def catalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_catalog_to_message(update, context)


async def mystats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    total = get_user_scoreboard_total(user_id)
    workouts = get_user_workouts(user_id, limit=1000)
    text = (
        f"🏆 **Твоя статистика**\n\n🏋️ Тренировок: {len(workouts)}\n⭐ Баллов: {total}"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, parse_mode='Markdown')


async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    leaderboard = get_leaderboard_from_scoreboard()
    if not leaderboard:
        await update.message.reply_text("Нет данных.")
        return
    text = "🏆 **ТОП ИГРОКОВ**\n\n" + "\n".join(
        [f"{i + 1}. {row[1] or row[2]} — {row[3]} баллов" for i, row in enumerate(leaderboard[:10])])
    await update.message.reply_text(text, parse_mode='Markdown')


async def setlevel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and context.args[0] in ('beginner', 'pro'):
        set_user_level(update.effective_user.id, context.args[0])
        msg = f"✅ Уровень изменён на {context.args[0]}."
    else:
        msg = "/setlevel beginner|pro"
    if update.callback_query:
        await update.callback_query.edit_message_text(msg)
    else:
        await update.message.reply_text(msg)


# ========== КОМАНДЫ ДЛЯ УПРАЖНЕНИЙ ==========
async def add_exercise_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        return
    full_text = update.message.text
    if ' ' not in full_text:
        await update.message.reply_text(
            "Использование: /addexercise <название> <reps|time> <описание> <баллы> [неделя] [difficulty]")
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
        await update.message.reply_text("Упражнение не найдено.")
        return

    context.user_data['delete_exercise_id'] = exercise_id
    context.user_data['delete_exercise_name'] = ex[1]
    await update.message.reply_text(
        f"Вы уверены, что хотите удалить упражнение '{ex[1]}' (ID {exercise_id})? Отправьте 'ДА' для подтверждения.")
    return CONFIRM_DELETE


async def delete_exercise_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Введите ID упражнения для удаления:")
    else:
        await update.message.reply_text("Введите ID упражнения для удаления:")
    return WAIT_DELETE_ID


async def delete_exercise_get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        exercise_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("ID должен быть числом. Попробуйте ещё раз:")
        return WAIT_DELETE_ID
    ex = get_exercise_by_id(exercise_id)
    if not ex:
        await update.message.reply_text("Упражнение не найдено.")
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
        name = ex[1].replace('_', r'\_').replace('*', r'\*').replace('[', r'\[').replace(']', r'\]')
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
        name = ex[1].replace('_', r'\_').replace('*', r'\*').replace('[', r'\[').replace(']', r'\]')
        text += f"🔹 ID: {ex[0]} — {name} ({ex[5]})\n"
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)


async def load_exercises_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    try:
        with open('exercises.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            for ex in data:
                add_exercise(ex['name'], ex.get('description', ''), ex['metric'], ex['points'], ex.get('week', 0),
                             ex.get('difficulty', 'beginner'))
        await update.message.reply_text("✅ Загружено.")
    except Exception as e:
        await update.message.reply_text(format_error(f"Ошибка: {e}"))


async def recalc_rankings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        return
    await update.message.reply_text("⏳ Начинаю пересчёт рейтинга...")
    recalculate_rankings(period_days=7)
    await update.message.reply_text("✅ Рейтинг пересчитан.")


async def myhistory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    limit = 20
    if context.args and context.args[0].isdigit():
        limit = int(context.args[0])
        if limit > 50:
            limit = 50
    workouts = get_user_workouts(user_id, limit)
    if not workouts:
        await update.message.reply_text("Нет тренировок.")
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


# ========== КОМАНДЫ ДЛЯ КОМПЛЕКСОВ ==========
async def add_complex_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        return
    try:
        text = update.message.text.split(maxsplit=1)[1]
        args = shlex.split(text)
        if len(args) < 4:
            await update.message.reply_text(
                "Использование: /addcomplex <название> <описание> <тип> <баллы>\nТип: for_time или for_reps")
            return
        name, description, type_, points = args[0], args[1], args[2], int(args[3])
        if type_ not in ('for_time', 'for_reps'):
            await update.message.reply_text("Тип должен быть for_time или for_reps")
            return
        complex_id = add_complex(name, description, type_, points)
        await update.message.reply_text(f"✅ Комплекс «{name}» создан с ID {complex_id}.")
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
        await update.message.reply_text(f"✅ Упражнение «{ex[1]}» добавлено в комплекс {complex_data[1]}.")
    except Exception as e:
        await update.message.reply_text(format_error(f"Ошибка: {e}"))


async def complexes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    all_complexes = get_all_complexes()
    if not all_complexes:
        await update.message.reply_text("Комплексов пока нет.")
        return
    text = "🏋️ **Доступные комплексы:**\n\n"
    for c in all_complexes:
        text += f"ID: {c[0]} — **{c[1]}**\n"
    await update.message.reply_text(text, parse_mode='Markdown')


async def complex_detail_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        complex_id = int(context.args[0])
    except (ValueError, IndexError, TypeError):
        await update.message.reply_text("Использование: /complex <id>")
        return
    complex_data = get_complex_by_id(complex_id)
    if not complex_data:
        await update.message.reply_text("Комплекс не найден.")
        return
    exercises = get_complex_exercises(complex_id)
    text = f"**{complex_data[1]}**\n{complex_data[2]}\n\nТип: {'Время' if complex_data[3] == 'for_time' else 'Повторения'}\nБаллы: {complex_data[4]}\n\n**Упражнения:**\n"
    for ex in exercises:
        text += f"• {ex[2]} — {ex[4]} повторений\n"
    await update.message.reply_text(text, parse_mode='Markdown')


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
        await update.message.reply_text("Комплекс не найден.")
        return
    context.user_data['delete_complex_id'] = complex_id
    await update.message.reply_text(
        f"Вы уверены, что хотите удалить комплекс '{complex_data[1]}'? Отправьте 'ДА' для подтверждения.")
    return CONFIRM_DELETE_COMPLEX


async def confirm_delete_complex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if text.upper() == "ДА":
        complex_id = context.user_data.get('delete_complex_id')
        if complex_id:
            conn = None
            try:
                conn = sqlite3.connect(DB_NAME)
                cur = conn.cursor()
                cur.execute("DELETE FROM complex_exercises WHERE complex_id = ?", (complex_id,))
                cur.execute("DELETE FROM complexes WHERE id = ?", (complex_id,))
                conn.commit()
            finally:
                if conn:
                    conn.close()
            await update.message.reply_text(f"✅ Комплекс ID {complex_id} удалён.")
        else:
            await update.message.reply_text("❌ Не удалось определить ID.")
    else:
        await update.message.reply_text("❌ Удаление отменено.")
    context.user_data.clear()
    return ConversationHandler.END


# ========== КОМАНДЫ ДЛЯ ЧЕЛЛЕНДЖЕЙ ==========
async def addchallenge_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    context.user_data['challenge_name'] = update.message.text
    await update.message.reply_text("Введите описание челленджа (можно пропустить, отправьте '-'):")
    return CHALL_DESC


async def challenge_desc_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text
    if desc == '-':
        desc = ''
    context.user_data['challenge_desc'] = desc
    keyboard = [
        [InlineKeyboardButton("Упражнение", callback_data="chall_target_exercise")],
        [InlineKeyboardButton("Комплекс", callback_data="chall_target_complex")],
    ]
    await update.message.reply_text("Выберите тип цели:", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHALL_TYPE


async def challenge_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "chall_target_exercise":
        context.user_data['challenge_target_type'] = 'exercise'
        exercises = get_all_exercises()
        if not exercises:
            await query.edit_message_text("Нет упражнений.")
            return ConversationHandler.END
        keyboard = []
        for ex in exercises:
            keyboard.append([InlineKeyboardButton(ex[1], callback_data=f"chall_ex_{ex[0]}")])
        await query.edit_message_text("Выберите упражнение:", reply_markup=InlineKeyboardMarkup(keyboard))
        return CHALL_TARGET
    else:
        context.user_data['challenge_target_type'] = 'complex'
        complexes = get_all_complexes()
        if not complexes:
            await query.edit_message_text("Нет комплексов.")
            return ConversationHandler.END
        keyboard = []
        for c in complexes:
            keyboard.append([InlineKeyboardButton(c[1], callback_data=f"chall_cx_{c[0]}")])
        await query.edit_message_text("Выберите комплекс:", reply_markup=InlineKeyboardMarkup(keyboard))
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
            await query.edit_message_text(f"Выбрано упражнение: {ex[1]}. Введите целевое значение (для {ex[3]}):")
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
            await query.edit_message_text(
                f"Выбран комплекс: {complex_data[1]}. Введите целевое значение (для {complex_data[3]}):")
        else:
            await query.edit_message_text("Комплекс не найден.")
            return ConversationHandler.END
        return CHALL_TARGET_VALUE


async def challenge_target_value_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_value = update.message.text.strip()
    metric = context.user_data.get('challenge_metric')
    if metric == 'reps':
        if not target_value.isdigit():
            await update.message.reply_text("Введите целое число повторений.")
            return CHALL_TARGET_VALUE
    else:
        if not re.match(r'^\d{1,2}:\d{2}$', target_value):
            await update.message.reply_text("Введите время в формате ММ:СС (например, 05:30).")
            return CHALL_TARGET_VALUE
    context.user_data['challenge_target_value'] = target_value
    await update.message.reply_text("Введите дату начала челленджа в формате ДД.ММ.ГГГГ:")
    return CHALL_START_DATE


async def challenge_start_date_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_date_str = update.message.text.strip()
    start_date = parse_date(start_date_str)
    if not start_date:
        await update.message.reply_text("Неверный формат. Введите дату в формате ДД.ММ.ГГГГ.")
        return CHALL_START_DATE
    context.user_data['challenge_start_date'] = start_date
    await update.message.reply_text("Введите дату окончания челленджа в формате ДД.ММ.ГГГГ:")
    return CHALL_END_DATE


async def challenge_end_date_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    end_date_str = update.message.text.strip()
    end_date = parse_date(end_date_str)
    if not end_date:
        await update.message.reply_text("Неверный формат. Введите дату в формате ДД.ММ.ГГГГ.")
        return CHALL_END_DATE
    start_date = context.user_data.get('challenge_start_date')
    if start_date and end_date <= start_date:
        await update.message.reply_text("Дата окончания должна быть позже даты начала.")
        return CHALL_END_DATE
    context.user_data['challenge_end_date'] = end_date
    await update.message.reply_text("Введите количество бонусных баллов (целое число):")
    return CHALL_BONUS


async def challenge_bonus_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        bonus = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Введите целое число.")
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
        await update.message.reply_text("✅ Челлендж создан!")
    else:
        await update.message.reply_text("❌ Ошибка.")
    context.user_data.clear()
    return ConversationHandler.END


async def challenges_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    challenges = get_challenges_by_status('active')
    if not challenges:
        if update.callback_query:
            await update.callback_query.edit_message_text("Активных челленджей нет.")
        else:
            await update.message.reply_text("Активных челленджей нет.")
        return

    text = "🏆 **Активные челленджи:**\n\n"
    for ch in challenges:
        text += f"**{ch[1]}** — цель: {ch[6]} {ch[5]}, бонус: {ch[9]} баллов\n"

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, parse_mode='Markdown')


async def join_challenge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        challenge_id = int(context.args[0])
    except (ValueError, IndexError, TypeError):
        await update.message.reply_text("Использование: /join <id>")
        return
    success = join_challenge(update.effective_user.id, challenge_id)
    if success:
        await update.message.reply_text("✅ Вы присоединились к челленджу!")
    else:
        await update.message.reply_text("❌ Не удалось присоединиться.")


async def my_challenges_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    challenges = get_user_challenges_with_details(update.effective_user.id)
    if not challenges:
        await update.message.reply_text("Вы не участвуете в челленджах.")
        return
    text = "🏆 **Ваши челленджи:**\n\n"
    for ch in challenges:
        text += f"**{ch[1]}** — прогресс: {ch[9]}/{ch[6]}\n"
    await update.message.reply_text(text, parse_mode='Markdown')


async def myprogress_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await my_challenges_command(update, context)


# ========== ДИАЛОГ ВЫПОЛНЕНИЯ КОМПЛЕКСА ==========
async def do_complex_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    complex_id = int(query.data.split('_')[2])
    complex_data = get_complex_by_id(complex_id)
    if not complex_data:
        await query.edit_message_text("Комплекс не найден.")
        return ConversationHandler.END
    context.user_data['current_complex_id'] = complex_id
    context.user_data['complex_name'] = complex_data[1]
    context.user_data['complex_points'] = complex_data[4]
    await query.edit_message_text(
        f"Выполняем комплекс **{complex_data[1]}**.\nВведите результат:",
        parse_mode='Markdown',
    )
    return COMPLEX_RESULT


async def complex_result_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result_text = update.message.text.strip()
    complex_id = context.user_data['current_complex_id']
    complex_data = get_complex_by_id(complex_id)
    if not complex_data:
        await update.message.reply_text("Комплекс не найден.")
        return ConversationHandler.END
    complex_type = complex_data[3]
    if complex_type == 'for_time':
        if not re.match(r'^\d{1,2}:\d{2}$', result_text):
            await update.message.reply_text("Неверный формат. Используй ММ:СС")
            return COMPLEX_RESULT
        context.user_data['complex_result_value'] = result_text
    else:
        if not result_text.isdigit():
            await update.message.reply_text("Введи число повторений.")
            return COMPLEX_RESULT
        context.user_data['complex_result_value'] = result_text
    await update.message.reply_text("Отправь ссылку на видео:")
    return COMPLEX_VIDEO


async def complex_video_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video_url = update.message.text.strip()
    context.user_data['complex_video'] = video_url
    await update.message.reply_text("Добавь комментарий (или /skip):")
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
    result = context.user_data['complex_result_value']
    video = context.user_data.get('complex_video', '')
    comment = context.user_data.get('complex_comment')
    user_level = get_user_level(user_id)
    _, new_achievements = add_workout(
        user_id=user_id,
        complex_id=complex_id,
        result_value=result,
        video_link=video,
        user_level=user_level,
        comment=comment,
        metric=None
    )
    for ach in new_achievements:
        await update.message.reply_text(f"{ach[5]} **{ach[1]}** — {ach[2]}", parse_mode='Markdown')
    await update.message.reply_text("✅ Тренировка записана!")


# ========== КОНСТРУКТОР КОМПЛЕКСОВ ==========
async def newcomplex_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        return ConversationHandler.END
    await update.message.reply_text("Введите название комплекса:")
    return COMPLEX_NAME


async def complex_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['complex_name'] = update.message.text
    await update.message.reply_text("Введите описание (можно пропустить, отправьте '-'):")
    return COMPLEX_DESC


async def complex_desc_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text
    if desc == '-':
        desc = ''
    context.user_data['complex_desc'] = desc
    keyboard = [
        [InlineKeyboardButton("Время (for_time)", callback_data="type_for_time")],
        [InlineKeyboardButton("Повторения (for_reps)", callback_data="type_for_reps")],
    ]
    await update.message.reply_text("Выберите тип комплекса:", reply_markup=InlineKeyboardMarkup(keyboard))
    return COMPLEX_TYPE


async def complex_type_temp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    type_ = query.data.split('_')[2]
    context.user_data['complex_type'] = type_
    await query.edit_message_text("Введите количество баллов:")
    return COMPLEX_POINTS


async def complex_points_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        points = int(update.message.text)
    except:
        await update.message.reply_text("Введите число.")
        return COMPLEX_POINTS
    context.user_data['complex_points'] = points
    exercises = get_all_exercises()
    if not exercises:
        await update.message.reply_text("Нет упражнений.")
        return ConversationHandler.END
    keyboard = []
    for ex in exercises:
        keyboard.append([InlineKeyboardButton(ex[1], callback_data=f"addex_{ex[0]}")])
    keyboard.append([InlineKeyboardButton("✅ Завершить", callback_data="finish_complex")])
    await update.message.reply_text("Выберите упражнения для добавления:", reply_markup=InlineKeyboardMarkup(keyboard))
    return COMPLEX_ADD_EXERCISE


async def complex_add_exercise_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "finish_complex":
        exercises_list = context.user_data.get('complex_exercises', [])
        if not exercises_list:
            await query.edit_message_text("Нет упражнений. Комплекс не создан.")
            return ConversationHandler.END
        name = context.user_data.get('complex_name')
        description = context.user_data.get('complex_desc', '')
        type_ = context.user_data.get('complex_type')
        points = context.user_data.get('complex_points')
        complex_id = add_complex(name, description, type_, points)
        for item in exercises_list:
            add_complex_exercise(complex_id, item['ex_id'], item['reps'])
        context.user_data.clear()
        await query.edit_message_text(f"✅ Комплекс «{name}» создан!")
        return ConversationHandler.END
    else:
        ex_id = int(query.data.split('_')[1])
        context.user_data['temp_exercise_id'] = ex_id
        await query.edit_message_text("Введите количество повторений для этого упражнения:")
        return COMPLEX_REPS


async def complex_reps_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        reps = int(update.message.text)
    except:
        await update.message.reply_text("Введите число.")
        return COMPLEX_REPS
    ex_id = context.user_data.pop('temp_exercise_id')
    exercises_list = context.user_data.get('complex_exercises', [])
    exercises_list.append({'ex_id': ex_id, 'reps': reps})
    context.user_data['complex_exercises'] = exercises_list
    exercises = get_all_exercises()
    keyboard = []
    for ex in exercises:
        keyboard.append([InlineKeyboardButton(ex[1], callback_data=f"addex_{ex[0]}")])
    keyboard.append([InlineKeyboardButton("✅ Завершить", callback_data="finish_complex")])
    await update.message.reply_text("Добавлено! Выберите следующее упражнение или завершите:",
                                    reply_markup=InlineKeyboardMarkup(keyboard))
    return COMPLEX_ADD_EXERCISE


# ========== ДРУГИЕ КОМАНДЫ ==========
async def setlevel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    level = query.data.split('_')[1]
    set_user_level(update.effective_user.id, level)
    await query.edit_message_text(f"✅ Уровень изменён на {level}.")


async def exercise_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ex_id = int(query.data.split('_')[1])
    ex = get_exercise_by_id(ex_id)
    if not ex:
        await query.edit_message_text("Упражнение не найдено.")
        return
    text = f"**{ex[1]}**\n{ex[2]}\n🏅 Баллы: {ex[4]}\n📏 Тип: {'повторения' if ex[3] == 'reps' else 'время'}"
    keyboard = [[InlineKeyboardButton("✍️ Записать", callback_data=f"record_{ex_id}")]]
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))


async def record_from_catalog_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ex_id = int(query.data.split('_')[1])
    context.user_data['pending_exercise'] = ex_id
    await query.edit_message_text("Теперь отправь /wod")


async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == 'help_sport':
        text = "🏋️ /wod, /catalog, /mystats, /setlevel"
    elif data == 'help_photo':
        text = "📸 /menu, отправь фото"
    elif data == 'help_stats':
        text = "📊 /mystats, /top"
    elif data == 'help_top':
        text = "🏆 /top"
    elif data == 'help_admin':
        text = "⚙️ /addexercise, /delexercise, /listexercises, /addcomplex, /addchallenge"
    else:
        text = "Помощь не найдена"
    await query.edit_message_text(text, parse_mode='Markdown')


async def stats_period_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Статистика за период (демо)")


async def top_league_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Топ лиги (демо)")


async def complex_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Список комплексов (демо)")


async def edit_complex_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Редактирование комплексов (в разработке)")


async def edit_complex_field_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Редактирование (в разработке)")


async def edit_complex_value_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Редактирование (в разработке)")


async def edit_exercise_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите ID упражнения для редактирования:")
    return EDIT_EXERCISE_ID


async def edit_exercise_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        exercise_id = int(update.message.text)
    except:
        await update.message.reply_text("ID должен быть числом.")
        return EDIT_EXERCISE_ID
    ex = get_exercise_by_id(exercise_id)
    if not ex:
        await update.message.reply_text("Упражнение не найдено.")
        return ConversationHandler.END
    context.user_data['edit_exercise_id'] = exercise_id
    keyboard = [
        [InlineKeyboardButton("Название", callback_data="exfield_name")],
        [InlineKeyboardButton("Описание", callback_data="exfield_description")],
        [InlineKeyboardButton("Тип", callback_data="exfield_metric")],
        [InlineKeyboardButton("Баллы", callback_data="exfield_points")],
        [InlineKeyboardButton("Отмена", callback_data="cancel_edit_ex")],
    ]
    await update.message.reply_text(f"Редактируем {ex[1]}:", reply_markup=InlineKeyboardMarkup(keyboard))
    return EDIT_EXERCISE_VALUE


async def edit_exercise_value_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        if query.data == "cancel_edit_ex":
            await query.edit_message_text("Отменено.")
            return ConversationHandler.END
        field_map = {
            "exfield_name": "name",
            "exfield_description": "description",
            "exfield_metric": "metric",
            "exfield_points": "points",
        }
        field = field_map.get(query.data)
        if field:
            context.user_data['edit_field'] = field
            await query.edit_message_text(f"Введите новое значение для {field}:")
            return EDIT_EXERCISE_VALUE
    else:
        text = update.message.text.strip()
        exercise_id = context.user_data.get('edit_exercise_id')
        field = context.user_data.get('edit_field')
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        if field == "points":
            value = int(text)
        else:
            value = text
        cur.execute(f"UPDATE exercises SET {field} = ? WHERE id = ?", (value, exercise_id))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ {field} обновлён на '{value}'")
        context.user_data.clear()
        return ConversationHandler.END
    return EDIT_EXERCISE_VALUE


async def edit_exercise_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await edit_exercise_start(update, context)


async def challenge_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Список челленджей (демо)")


async def skip_comment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from workout_handlers import skip_comment_finalize
    await skip_comment_finalize(update, context)


async def delete_challenge_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Введите ID челленджа для удаления:")
    else:
        await update.message.reply_text("Введите ID челленджа для удаления:")
    return WAIT_DELETE_CHALLENGE_ID

async def delete_challenge_get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        challenge_id = int(update.message.text)
    except (ValueError, TypeError):
        await update.message.reply_text("ID должен быть числом.")
        return WAIT_DELETE_CHALLENGE_ID
    context.user_data['delete_challenge_id'] = challenge_id
    await update.message.reply_text(f"Удалить челлендж {challenge_id}? Отправьте 'ДА'")
    return CONFIRM_DELETE


async def confirm_delete_challenge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.upper() == "ДА":
        challenge_id = context.user_data.get('delete_challenge_id')
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("DELETE FROM user_challenge_progress WHERE challenge_id = ?", (challenge_id,))
        cur.execute("DELETE FROM user_challenges WHERE challenge_id = ?", (challenge_id,))
        cur.execute("DELETE FROM challenges WHERE id = ?", (challenge_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ Челлендж {challenge_id} удалён.")
    else:
        await update.message.reply_text("❌ Отменено.")
    context.user_data.clear()
    return ConversationHandler.END


async def edit_challenge_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Введите ID челленджа для редактирования:")
    else:
        await update.message.reply_text("Введите ID челленджа для редактирования:")
    return EDIT_CHALLENGE_ID


async def edit_challenge_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        challenge_id = int(update.message.text)
    except:
        await update.message.reply_text("ID должен быть числом.")
        return EDIT_CHALLENGE_ID
    challenge = get_challenge_by_id(challenge_id)
    if not challenge:
        await update.message.reply_text("Челлендж не найден.")
        return ConversationHandler.END
    context.user_data['edit_challenge_id'] = challenge_id
    keyboard = [
        [InlineKeyboardButton("Название", callback_data="chfield_name")],
        [InlineKeyboardButton("Описание", callback_data="chfield_description")],
        [InlineKeyboardButton("Цель", callback_data="chfield_target_value")],
        [InlineKeyboardButton("Бонус", callback_data="chfield_bonus")],
        [InlineKeyboardButton("Отмена", callback_data="cancel_edit_ch")],
    ]
    await update.message.reply_text(f"Редактируем {challenge[1]}:", reply_markup=InlineKeyboardMarkup(keyboard))
    return EDIT_CHALLENGE_VALUE


async def edit_challenge_value_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        if query.data == "cancel_edit_ch":
            await query.edit_message_text("Отменено.")
            return ConversationHandler.END
        field_map = {
            "chfield_name": "name",
            "chfield_description": "description",
            "chfield_target_value": "target_value",
            "chfield_bonus": "bonus_points",
        }
        field = field_map.get(query.data)
        if field:
            context.user_data['edit_field'] = field
            await query.edit_message_text(f"Введите новое значение для {field}:")
            return EDIT_CHALLENGE_VALUE
    else:
        text = update.message.text.strip()
        challenge_id = context.user_data.get('edit_challenge_id')
        field = context.user_data.get('edit_field')
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        if field == "bonus_points":
            value = int(text)
        else:
            value = text
        cur.execute(f"UPDATE challenges SET {field} = ? WHERE id = ?", (value, challenge_id))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ {field} обновлён на '{value}'")
        context.user_data.clear()
        return ConversationHandler.END
    return EDIT_CHALLENGE_VALUE


async def edit_challenge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await edit_challenge_start(update, context)


async def delete_complex_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Введите ID комплекса для удаления:")
    else:
        await update.message.reply_text("Введите ID комплекса для удаления:")
    return WAIT_DELETE_COMPLEX_ID


async def delete_complex_get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        complex_id = int(update.message.text)
    except (ValueError, TypeError):
        await update.message.reply_text("ID должен быть числом.")
        return WAIT_DELETE_COMPLEX_ID
    context.user_data['delete_complex_id'] = complex_id
    await update.message.reply_text(f"Удалить комплекс {complex_id}? Отправьте 'ДА'")
    return CONFIRM_DELETE_COMPLEX


async def leave_challenge_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    challenge_id = int(query.data.split('_')[1])
    leave_challenge(update.effective_user.id, challenge_id)
    await query.edit_message_text("✅ Вы вышли из челленджа.")


async def cancel_reply_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("❌ Отменено.")


async def process_reply_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass


# ========== ОБРАБОТЧИК ДИАЛОГА ==========
async def catch_all_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('conversation_state')
    if state == 60:
        await submit_result_input(update, context)
    elif state == 61:
        await submit_video_input(update, context)
    elif state == 62:
        await submit_comment_input(update, context)
    else:
        await menu_handler(update, context)


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    text = update.message.text
    if "Спорт" in text:
        await sport_menu(update, context)
    elif "Фото" in text:
        await show_menu(update, context)
    elif "Рейтинг" in text:
        await top_command(update, context)
    elif "Календарь" in text:
        await calendar_command(update, context)
    elif "Админ" in text:
        if is_admin(update):
            await admin_menu(update, context)
        else:
            await update.message.reply_text("⛔ Нет прав.")
    elif "Отмена" in text:
        context.user_data.clear()
        await update.message.reply_text("Отменено.")
    else:
        await handle_message(update, context)


# ========== ОБЩИЕ ФУНКЦИИ ==========
def paginate(items, page, per_page=5, prefix='page', extra_data=''):
    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = items[start:end]
    keyboard = []
    if page > 1:
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=f"{prefix}_{page - 1}")])
    if end < total:
        keyboard.append([InlineKeyboardButton("Вперёд ▶️", callback_data=f"{prefix}_{page + 1}")])
    return page_items, keyboard


def get_exercise_icon(name):
    return "📌"


async def testchannel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_to_channel(context.bot, "✅ Тест")


async def testresult_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("Тест")


# ========== СЕРВЕР ==========
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")


init_db()
backup_database()
Thread(target=lambda: HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 10000))), HealthCheckHandler).serve_forever(),
       daemon=True).start()


# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
def main():
    logger.info("MAIN: started")
    if not TOKEN:
        raise ValueError("Нет TELEGRAM_BOT_TOKEN!")

    app = Application.builder().token(TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", show_menu))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("config", config_command))
    app.add_handler(CommandHandler("addexercise", add_exercise_command))
    app.add_handler(CommandHandler("listexercises", list_exercises_command))
    app.add_handler(CommandHandler("load_exercises", load_exercises_command))
    app.add_handler(CommandHandler("mystats", mystats_command))
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
    app.add_handler(CommandHandler("myprogress", myprogress_command))
    app.add_handler(CommandHandler("set_channel", set_channel_command))
    app.add_handler(CommandHandler("get_channel", get_channel_command))
    app.add_handler(CommandHandler("get_channel_id", get_channel_id))
    app.add_handler(CommandHandler("mychallenges", my_challenges_command))
    app.add_handler(CommandHandler("calendar", calendar_command))
    app.add_handler(CommandHandler("publish_complex", publish_complex_command))
    app.add_handler(CommandHandler("publish_exercise", publish_exercise_command))
    app.add_handler(CommandHandler("publish_challenge", publish_challenge_command))
    app.add_handler(CommandHandler("debug", debug_command))
    app.add_handler(CommandHandler("testchannel", testchannel_command))
    app.add_handler(CommandHandler("comment", comment_command))
    app.add_handler(CommandHandler("testresult", testresult_command))

    # ConversationHandlers
    app.add_handler(edit_complex_conv := ConversationHandler(
        entry_points=[CommandHandler('editcomplex', edit_complex_command)],
        states={EDIT_COMPLEX_ID: [CallbackQueryHandler(edit_complex_field_callback, pattern='^cfield_|cancel_edit')],
                EDIT_COMPLEX_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_complex_value_input)]},
        fallbacks=[CommandHandler('cancel', workout_cancel)],
    ))

    app.add_handler(edit_exercise_conv := ConversationHandler(
        entry_points=[CommandHandler('editexercise', edit_exercise_command),
                      CallbackQueryHandler(edit_exercise_start, pattern='^admin_ex_edit$')],
        states={EDIT_EXERCISE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_exercise_id_input)],
                EDIT_EXERCISE_VALUE: [
                    CallbackQueryHandler(edit_exercise_value_input, pattern='^exfield_|cancel_edit_ex'),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, edit_exercise_value_input)]},
        fallbacks=[CommandHandler('cancel', workout_cancel)],
    ))

    app.add_handler(admin_add_exercise_conv := ConversationHandler(
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
    ))

    app.add_handler(complex_conv := ConversationHandler(
        entry_points=[CallbackQueryHandler(do_complex_start, pattern='^do_complex_\\d+$')],
        states={COMPLEX_RESULT: [MessageHandler(filters.TEXT & ~filters.COMMAND, complex_result_input)],
                COMPLEX_VIDEO: [MessageHandler(filters.TEXT & ~filters.COMMAND, complex_video_input),
                                CommandHandler('skip', complex_comment_skip)],
                COMPLEX_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, complex_comment_input),
                                  CommandHandler('skip', complex_comment_skip)]},
        fallbacks=[CommandHandler('cancel', workout_cancel)],
    ))

    app.add_handler(workout_conv := ConversationHandler(
        entry_points=[CommandHandler('wod', workout_start)],
        states={EXERCISE: [CallbackQueryHandler(exercise_choice, pattern='^ex_|^cancel$')],
                RESULT: [MessageHandler(filters.TEXT & ~filters.COMMAND, result_input)],
                VIDEO: [MessageHandler(filters.TEXT & ~filters.COMMAND, video_input)],
                COMMENT: [MessageHandler(filters.TEXT, comment_handler)]},
        fallbacks=[CommandHandler('cancel', workout_cancel)],
    ))

    app.add_handler(newcomplex_conv := ConversationHandler(
        entry_points=[CommandHandler('newcomplex', newcomplex_start),
                      CallbackQueryHandler(newcomplex_start, pattern='^admin_cx_add$')],
        states={COMPLEX_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, complex_name_input)],
                COMPLEX_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, complex_desc_input)],
                COMPLEX_TYPE: [CallbackQueryHandler(complex_type_temp, pattern='^type_')],
                COMPLEX_POINTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, complex_points_input)],
                COMPLEX_ADD_EXERCISE: [
                    CallbackQueryHandler(complex_add_exercise_callback, pattern='^addex_|^finish_complex')],
                COMPLEX_REPS: [MessageHandler(filters.TEXT & ~filters.COMMAND, complex_reps_input)]},
        fallbacks=[CommandHandler('cancel', workout_cancel)],
    ))

    app.add_handler(challenge_conv := ConversationHandler(
        entry_points=[CommandHandler('addchallenge', addchallenge_start),
                      CallbackQueryHandler(addchallenge_start, pattern='^admin_ch_add$')],
        states={CHALL_NAME: [MessageHandler(filters.TEXT, challenge_name_input)],
                CHALL_DESC: [MessageHandler(filters.TEXT, challenge_desc_input)],
                CHALL_TYPE: [CallbackQueryHandler(challenge_type_callback, pattern='^chall_target_')],
                CHALL_TARGET: [CallbackQueryHandler(challenge_target_callback, pattern='^chall_ex_|^chall_cx_')],
                CHALL_TARGET_VALUE: [MessageHandler(filters.TEXT, challenge_target_value_input)],
                CHALL_START_DATE: [MessageHandler(filters.TEXT, challenge_start_date_input)],
                CHALL_END_DATE: [MessageHandler(filters.TEXT, challenge_end_date_input)],
                CHALL_BONUS: [MessageHandler(filters.TEXT, challenge_bonus_input)]},
        fallbacks=[CommandHandler('cancel', workout_cancel)],
        per_user=True, per_chat=True,
    ))

    app.add_handler(confirm_conv := ConversationHandler(
        entry_points=[CommandHandler('delexercise', delete_exercise_command),
                      CallbackQueryHandler(delete_exercise_start, pattern='^admin_ex_delete$')],
        states={WAIT_DELETE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_exercise_get_id)],
                CONFIRM_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_delete_exercise)]},
        fallbacks=[CommandHandler('cancel', workout_cancel)],
    ))

    app.add_handler(delete_complex_conv := ConversationHandler(
        entry_points=[CommandHandler('deletecomplex', delete_complex_command),
                      CallbackQueryHandler(delete_complex_start, pattern='^admin_cx_delete$')],
        states={WAIT_DELETE_COMPLEX_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_complex_get_id)],
                CONFIRM_DELETE_COMPLEX: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_delete_complex)]},
        fallbacks=[CommandHandler('cancel', workout_cancel)],
    ))

    app.add_handler(delete_challenge_conv := ConversationHandler(
        entry_points=[CallbackQueryHandler(delete_challenge_start, pattern='^admin_ch_delete$')],
        states={WAIT_DELETE_CHALLENGE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_challenge_get_id)],
                CONFIRM_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_delete_challenge)]},
        fallbacks=[CommandHandler('cancel', workout_cancel)],
    ))

    app.add_handler(edit_challenge_conv := ConversationHandler(
        entry_points=[CommandHandler('editchallenge', edit_challenge_command),
                      CallbackQueryHandler(edit_challenge_start, pattern='^admin_ch_edit$')],
        states={EDIT_CHALLENGE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_challenge_id_input)],
                EDIT_CHALLENGE_VALUE: [
                    CallbackQueryHandler(edit_challenge_value_input, pattern='^chfield_|cancel_edit_ch'),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, edit_challenge_value_input)]},
        fallbacks=[CommandHandler('cancel', workout_cancel)],
    ))

    # Callback handlers
    app.add_handler(CallbackQueryHandler(admin_callback, pattern='^admin_'))
    app.add_handler(CallbackQueryHandler(submit_complex_callback, pattern='^submit_complex_'))
    app.add_handler(CallbackQueryHandler(submit_exercise_callback, pattern='^submit_exercise_'))
    app.add_handler(CallbackQueryHandler(submit_challenge_callback, pattern='^submit_challenge_'))
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

    # Message handlers
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, catch_all_text))

    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
        logger.error("Exception while handling an update", exc_info=context.error)

    app.add_error_handler(error_handler)

    init_db()
    backup_database()
    app.run_polling()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception("Критическая ошибка: %s", e)