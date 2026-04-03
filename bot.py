import os
import logging
import asyncio
from workout_handlers import (
    COMPLEX_EXERCISE,
    public_stats_menu,
    public_top_users,
    public_top_challenges,
    public_join_challenge,
    public_my_stats,
    back_to_public_stats
)
import re
import json
from functools import wraps
from datetime import datetime
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from collections import deque

from database import init_db
import sqlite3
import shlex

from admin_handlers import admin_menu, admin_callback, admin_exercise_add_start, admin_cancel, EXERCISE_NAME, \
    EXERCISE_DESC, EXERCISE_METRIC, EXERCISE_POINTS, EXERCISE_WEEK, EXERCISE_DIFF, admin_exercise_add_name, \
    admin_exercise_add_desc, admin_exercise_add_metric, admin_exercise_add_points, admin_exercise_add_week, \
    admin_exercise_add_diff
from config import EMOJI, SEPARATOR, WELCOME_TEXT, format_success, format_error, format_warning
from dotenv import load_dotenv

load_dotenv()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)
# ==================== ДЕБАГ-РЕЖИМ ====================
from debug_utils import debug_print, log_call, log_user_data, DEBUG_MODE

# Устанавливаем уровень логов
if DEBUG_MODE:
    logging.getLogger().setLevel(logging.DEBUG)
    debug_print("🐞 РЕЖИМ ОТЛАДКИ ВКЛЮЧЕН")

# ==================== НАСТРОЙКА ЛОГИРОВАНИЯ ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

file_handler = logging.FileHandler('bot.log', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# ==================== ИМПОРТЫ ЛОКАЛЬНЫХ МОДУЛЕЙ ====================
from activity_calendar import calendar_command, calendar_callback
from menu_handlers import main_menu_keyboard, sport_menu
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
    check_and_award_achievements, save_published_post, get_published_post_by_message_id, fix_scoreboard_duplicates
)
from workout_handlers import (
    workout_start, exercise_choice, result_input, video_input,
    workout_cancel, EXERCISE, RESULT, VIDEO, COMMENT,
    get_current_week, comment_input, comment_skip, comment_handler, skip_comment_finalize,
    complex_exercise_choice
)
from submit_handlers import (
    submit_complex_callback, submit_exercise_callback, submit_challenge_callback,
    submit_result_input, submit_video_input, submit_comment_input, submit_comment_skip,
    cancel_submit_callback
)
from channel_notifier import send_to_channel

# ==================== КОНСТАНТЫ ====================
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


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
@log_call
def clean_markdown(text):
    debug_print(f"🔥 clean_markdown: ВХОД, text={text[:50] if text else None}")
    result = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    result = re.sub(r'\*(.*?)\*', r'\1', result)
    result = re.sub(r'__(.*?)__', r'\1', result)
    result = re.sub(r'`(.*?)`', r'\1', result)
    debug_print(f"📤 clean_markdown: ВОЗВРАТ {result[:50] if result else None}")
    return result


@log_call
def is_admin(update: Update) -> bool:
    debug_print(f"🔥 is_admin: ВХОД, user_id={update.effective_user.id if update.effective_user else None}")
    result = update.effective_user.id == ADMIN_ID
    debug_print(f"📤 is_admin: ВОЗВРАТ {result}")
    return result


@log_call
def parse_date(date_str):
    debug_print(f"🔥 parse_date: ВХОД, date_str={date_str}")
    try:
        day, month, year = date_str.split('.')
        result = f"{year}-{month}-{day}"
        debug_print(f"📤 parse_date: ВОЗВРАТ {result}")
        return result
    except (ValueError, AttributeError) as e:
        debug_print(f"❌ parse_date: Ошибка {e}")
        return None


@log_call
def paginate(items, page, per_page=5, prefix='page', extra_data=''):
    debug_print(f"🔥 paginate: ВХОД, items_count={len(items) if items else 0}, page={page}")
    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = items[start:end]
    keyboard = []
    if page > 1:
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=f"{prefix}_{page - 1}")])
    if end < total:
        keyboard.append([InlineKeyboardButton("Вперёд ▶️", callback_data=f"{prefix}_{page + 1}")])
    debug_print(f"📤 paginate: ВОЗВРАТ {len(page_items)} items, keyboard={len(keyboard)} buttons")
    return page_items, keyboard


@log_call
def get_exercise_icon(name):
    return "📌"


async def debug_global_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Только ЛОГИРУЕТ, не обрабатывает повторно"""
    if DEBUG_MODE:
        print(f"\n{'=' * 60}")
        print(f"🌍 ГЛОБАЛЬНЫЙ ЛОГ:")
        if update.callback_query:
            print(f"   📨 callback_data: {update.callback_query.data}")
            print(f"   👤 user_id: {update.callback_query.from_user.id}")
        if update.message:
            print(f"   💬 текст: {update.message.text}")
        print(f"{'=' * 60}\n")

    # ❌ НЕ ВЫЗЫВАЕМ ОБРАБОТЧИКИ ЗДЕСЬ!
    # Просто логируем и возвращаем None
    return None

    # Передаём управление дальше в основной обработчик
    # Не возвращаем None, а вызываем соответствующий обработчик
    if update.callback_query:
        # Если это callback, передаём в sport_callback_handler
        from bot import sport_callback_handler
        await sport_callback_handler(update, context)
    elif update.message and update.message.text:
        # Если это текст, передаём в catch_all_text
        from bot import catch_all_text
        await catch_all_text(update, context)

    if DEBUG_MODE:
        print(f"📤 debug_global_handler: ВЫХОД")
        print(f"{'=' * 60}\n")


# ==================== КОМАНДЫ ДЕБАГА ====================
@log_call
async def toggle_debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключает режим отладки (только админ)"""
    global DEBUG_MODE
    debug_print(f"🔥 toggle_debug_command: ВХОД")
    debug_print(f"📦 user_data: {context.user_data}")

    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав для переключения режима отладки.")
        debug_print(f"📤 toggle_debug_command: ВОЗВРАТ (нет прав)")
        return

    DEBUG_MODE = not DEBUG_MODE
    status = "✅ ВКЛЮЧЁН" if DEBUG_MODE else "❌ ВЫКЛЮЧЕН"

    set_setting("debug_mode", str(DEBUG_MODE))

    await update.message.reply_text(
        f"🐞 **Режим отладки {status}**\n\n"
        f"Теперь {'все действия будут логироваться' if DEBUG_MODE else 'логирование отключено'}.\n\n"
        f"💡 Логи пишутся в файл `bot.log`",
        parse_mode='Markdown'
    )

    logger.info(f"🔧 Режим отладки переключён на {DEBUG_MODE} админом {update.effective_user.id}")
    debug_print(f"📤 toggle_debug_command: ВОЗВРАТ (новый статус {DEBUG_MODE})")


@log_call
async def toggle_debug_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопка для переключения дебага"""
    debug_print(f"🔥 toggle_debug_button: ВХОД")
    debug_print(f"📦 user_data: {context.user_data}")

    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        debug_print(f"📤 toggle_debug_button: ВОЗВРАТ (нет прав)")
        return

    keyboard = [
        [InlineKeyboardButton(
            f"{'🔴 ВЫКЛЮЧИТЬ' if DEBUG_MODE else '🟢 ВКЛЮЧИТЬ'} отладку",
            callback_data="toggle_debug_callback"
        )],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_debug")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    current_status = "включён ✅" if DEBUG_MODE else "выключен ❌"
    await update.message.reply_text(
        f"🐞 **Режим отладки**\n\nТекущее состояние: {current_status}\n\n"
        f"Нажми на кнопку, чтобы переключить:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    debug_print(f"📤 toggle_debug_button: ВОЗВРАТ")


@log_call
async def toggle_debug_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback для переключения дебага через кнопку"""
    global DEBUG_MODE
    debug_print(f"🔥 toggle_debug_callback_handler: ВХОД")

    query = update.callback_query
    await query.answer()
    debug_print(f"📥 Callback data: {query.data}")

    if not is_admin(update):
        await query.edit_message_text("⛔ Нет прав.")
        debug_print(f"📤 toggle_debug_callback_handler: ВОЗВРАТ (нет прав)")
        return

    if query.data == "toggle_debug_callback":
        DEBUG_MODE = not DEBUG_MODE
        set_setting("debug_mode", str(DEBUG_MODE))
        status = "✅ ВКЛЮЧЁН" if DEBUG_MODE else "❌ ВЫКЛЮЧЕН"
        await query.edit_message_text(f"🐞 Режим отладки {status}", parse_mode='Markdown')
        logger.info(f"🔧 Дебаг переключён через callback на {DEBUG_MODE}")
    elif query.data == "cancel_debug":
        await query.edit_message_text("❌ Отменено.")

    debug_print(f"📤 toggle_debug_callback_handler: ВОЗВРАТ")


# ==================== ОСНОВНЫЕ КОМАНДЫ ====================
@log_call
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 start: ВХОД")
    debug_print(f"📦 user_data ДО ОЧИСТКИ: {context.user_data}")

    if DEBUG_MODE:
        text = update.message.text if update.message else 'no message'
        debug_print(f"📨 start: text={text}")

    keyboard = [
        ["🏋️ Спорт", "📸 Фото"],
        ["🤖 Задать вопрос", "❌ Отмена"],
        ["🏆 Рейтинг", "⚙️ Админ"],
        ["📅 Календарь", "🐞 Отладка"],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    em = update.effective_message
    if em:
        await em.reply_text("✅ Диалог очищен. Вы вернулись в главное меню.", reply_markup=reply_markup,
                            parse_mode='Markdown')
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=WELCOME_TEXT,
            reply_markup=reply_markup,
            parse_mode='Markdown',
        )
    debug_print(f"📤 start: ВОЗВРАТ")


@log_call
async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 show_menu: ВХОД")
    debug_print(f"📦 user_data: {context.user_data}")

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
    debug_print(f"📤 show_menu: ВОЗВРАТ")


@log_call
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 stats_command: ВХОД")

    text = "📊 **Статистика работы AI:**\n"
    text += f"Всего попыток: {consilium_stats['attempts']}\n"
    text += f"Успешно: {consilium_stats['success']}\n"
    text += f"Ошибок: {consilium_stats['failures']}\n"
    for model, count in consilium_stats['models_used'].items():
        text += f"  {model}: {count}\n"
    await update.message.reply_text(text, parse_mode='Markdown')
    debug_print(f"📤 stats_command: ВОЗВРАТ")


@log_call
async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 reset_command: ВХОД")
    debug_print(f"📦 user_data ДО: {context.user_data}")

    if 'user_history' in context.user_data:
        context.user_data['user_history'].clear()
    await update.message.reply_text("🔄 История диалога очищена.")

    debug_print(f"📦 user_data ПОСЛЕ: {context.user_data}")
    debug_print(f"📤 reset_command: ВОЗВРАТ")


@log_call
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 help_command: ВХОД")

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
    debug_print(f"📤 help_command: ВОЗВРАТ")


@log_call
async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Настройка AI"""
    debug_print(f"🔥 config_command: ВХОД")

    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        debug_print(f"📤 config_command: ВОЗВРАТ (нет прав)")
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
    debug_print(f"📤 config_command: ВОЗВРАТ")


@log_call
async def config_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 config_callback_handler: ВХОД")

    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("⛔ Недоступно.")
        debug_print(f"📤 config_callback_handler: ВОЗВРАТ (не админ)")
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
    debug_print(f"📤 config_callback_handler: ВОЗВРАТ")


# ==================== ПУБЛИКАЦИЯ В КАНАЛ ====================
@log_call
async def publish_complex_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Публикует комплекс в канал с кнопкой 'Сдать результат'."""
    debug_print(f"🔥 publish_complex_command: ВХОД")

    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        debug_print(f"📤 publish_complex_command: ВОЗВРАТ (нет прав)")
        return
    if not context.args:
        await update.message.reply_text("Использование: /publish_complex <id>")
        debug_print(f"📤 publish_complex_command: ВОЗВРАТ (нет аргументов)")
        return
    try:
        complex_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        debug_print(f"📤 publish_complex_command: ВОЗВРАТ (ошибка ID)")
        return

    complex_data = get_complex_by_id(complex_id)
    if not complex_data:
        await update.message.reply_text("Комплекс не найден.")
        debug_print(f"📤 publish_complex_command: ВОЗВРАТ (комплекс не найден)")
        return

    channel_id = get_setting("public_channel")
    if not channel_id:
        await update.message.reply_text("Сначала установите канал командой /set_channel <id>")
        debug_print(f"📤 publish_complex_command: ВОЗВРАТ (нет канала)")
        return

    try:
        channel_id_int = int(channel_id)
    except ValueError:
        await update.message.reply_text("ID канала должен быть числом.")
        debug_print(f"📤 publish_complex_command: ВОЗВРАТ (ошибка ID канала)")
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
        debug_print(f"📤 publish_complex_command: ВОЗВРАТ (ошибка отправки)")
        return
    save_published_post('complex', complex_id, channel_id_int, sent_message.message_id)

    await update.message.reply_text(f"✅ Комплекс «{complex_data[1]}» опубликован в канале.")
    debug_print(f"📤 publish_complex_command: ВОЗВРАТ")


@log_call
async def publish_exercise_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Публикует упражнение в канал с кнопкой 'Сдать результат'."""
    debug_print(f"🔥 publish_exercise_command: ВХОД")

    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        debug_print(f"📤 publish_exercise_command: ВОЗВРАТ (нет прав)")
        return
    if not context.args:
        await update.message.reply_text("Использование: /publish_exercise <id>")
        debug_print(f"📤 publish_exercise_command: ВОЗВРАТ (нет аргументов)")
        return
    try:
        exercise_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        debug_print(f"📤 publish_exercise_command: ВОЗВРАТ (ошибка ID)")
        return

    exercise = get_exercise_by_id(exercise_id)
    if not exercise:
        await update.message.reply_text("Упражнение не найдено.")
        debug_print(f"📤 publish_exercise_command: ВОЗВРАТ (упражнение не найдено)")
        return

    channel_id = get_setting("public_channel")
    if not channel_id:
        await update.message.reply_text("Сначала установите канал командой /set_channel <id>")
        debug_print(f"📤 publish_exercise_command: ВОЗВРАТ (нет канала)")
        return

    try:
        channel_id_int = int(channel_id)
    except ValueError:
        await update.message.reply_text("ID канала должен быть числом.")
        debug_print(f"📤 publish_exercise_command: ВОЗВРАТ (ошибка ID канала)")
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
        debug_print(f"📤 publish_exercise_command: ВОЗВРАТ (ошибка отправки)")
        return
    save_published_post('exercise', exercise_id, channel_id_int, sent_message.message_id)

    await update.message.reply_text(f"✅ Упражнение «{name}» опубликовано в канале.")
    debug_print(f"📤 publish_exercise_command: ВОЗВРАТ")


@log_call
async def publish_challenge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Публикует челлендж в канал с кнопкой 'Сдать результат'."""
    debug_print(f"🔥 publish_challenge_command: ВХОД")

    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        debug_print(f"📤 publish_challenge_command: ВОЗВРАТ (нет прав)")
        return
    if not context.args:
        await update.message.reply_text("Использование: /publish_challenge <id>")
        debug_print(f"📤 publish_challenge_command: ВОЗВРАТ (нет аргументов)")
        return
    try:
        challenge_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        debug_print(f"📤 publish_challenge_command: ВОЗВРАТ (ошибка ID)")
        return

    challenge = get_challenge_by_id(challenge_id)
    if not challenge:
        await update.message.reply_text("Челлендж не найден.")
        debug_print(f"📤 publish_challenge_command: ВОЗВРАТ (челлендж не найден)")
        return

    channel_id = get_setting("public_channel")
    if not channel_id:
        await update.message.reply_text("Сначала установите канал командой /set_channel <id>")
        debug_print(f"📤 publish_challenge_command: ВОЗВРАТ (нет канала)")
        return

    try:
        channel_id_int = int(channel_id)
    except ValueError:
        await update.message.reply_text("ID канала должен быть числом.")
        debug_print(f"📤 publish_challenge_command: ВОЗВРАТ (ошибка ID канала)")
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
        debug_print(f"📤 publish_challenge_command: ВОЗВРАТ (ошибка отправки)")
        return
    save_published_post('challenge', challenge_id, channel_id_int, sent_message.message_id)

    await update.message.reply_text(f"✅ Челлендж «{name}» опубликован в канале.")
    debug_print(f"📤 publish_challenge_command: ВОЗВРАТ")


@log_call
async def set_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 set_channel_command: ВХОД")

    if not is_admin(update):
        debug_print(f"📤 set_channel_command: ВОЗВРАТ (нет прав)")
        return
    if not context.args:
        await update.message.reply_text("Использование: /set_channel <chat_id>")
        debug_print(f"📤 set_channel_command: ВОЗВРАТ (нет аргументов)")
        return
    try:
        chat_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        debug_print(f"📤 set_channel_command: ВОЗВРАТ (ошибка ID)")
        return
    set_setting("public_channel", str(chat_id))
    await update.message.reply_text(f"✅ Канал установлен: {chat_id}")
    debug_print(f"📤 set_channel_command: ВОЗВРАТ")


@log_call
async def get_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 get_channel_command: ВХОД")

    if not is_admin(update):
        debug_print(f"📤 get_channel_command: ВОЗВРАТ (нет прав)")
        return
    channel = get_setting("public_channel")
    await update.message.reply_text(f"Текущий канал: {channel}" if channel else "Канал не установлен")
    debug_print(f"📤 get_channel_command: ВОЗВРАТ")


@log_call
async def get_channel_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 get_channel_id: ВХОД")

    if update.message:
        chat_id = update.message.chat_id
        await update.message.reply_text(f"ID этого чата: {chat_id}")
    debug_print(f"📤 get_channel_id: ВОЗВРАТ")


@log_call
async def comment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для добавления комментария к посту в канале"""
    debug_print(f"🔥 comment_command: ВХОД")

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ Использование: /comment <id_сообщения> <текст>\n\n"
            "Например: /comment 123 Отличная тренировка!"
        )
        debug_print(f"📤 comment_command: ВОЗВРАТ (недостаточно аргументов)")
        return

    try:
        message_id = int(context.args[0])
        comment_text = " ".join(context.args[1:])
    except ValueError:
        await update.message.reply_text("❌ ID сообщения должен быть числом.")
        debug_print(f"📤 comment_command: ВОЗВРАТ (ошибка ID)")
        return

    channel_id = get_setting("public_channel")
    if not channel_id:
        await update.message.reply_text("❌ Канал не настроен.")
        debug_print(f"📤 comment_command: ВОЗВРАТ (нет канала)")
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

    debug_print(f"📤 comment_command: ВОЗВРАТ")


@log_call
async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает текущее состояние диалога (только для админа)."""
    debug_print(f"🔥 debug_command: ВХОД")

    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        debug_print(f"📤 debug_command: ВОЗВРАТ (нет прав)")
        return
    state = context.user_data.get('conversation_state')
    await update.message.reply_text(f"📊 Состояние диалога: {state}", parse_mode='Markdown')
    debug_print(f"📤 debug_command: ВОЗВРАТ, state={state}")


# ==================== ОБРАБОТКА ТЕКСТА И ФОТО ====================
@log_call
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 handle_message: ВХОД")
    debug_print(f"📦 user_data: {context.user_data}")

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

    debug_print(f"📤 handle_message: ВОЗВРАТ")


@log_call
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 button_handler: ВХОД")

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
    debug_print(f"📤 button_handler: ВОЗВРАТ")


@log_call
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 handle_photo: ВХОД")
    debug_print(f"📦 user_data: {context.user_data}")

    if 'effect' not in context.user_data:
        await update.message.reply_text("Сначала выбери стиль через /menu")
        debug_print(f"📤 handle_photo: ВОЗВРАТ (нет эффекта)")
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

    debug_print(f"📤 handle_photo: ВОЗВРАТ")


# ==================== СПОРТИВНЫЕ КОМАНДЫ ====================
@log_call
async def sport_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # ✅ ОБРАБОТКА ОТМЕНЫ ПРЯМО ЗДЕСЬ
    if data == "cancel":
        debug_print(f"🔥 sport_callback_handler: ОТМЕНА!")
        await query.edit_message_text("❌ Запись тренировки отменена.")
        context.user_data.clear()
        # Возвращаем в главное меню
        await start(update, context)
        return

    # ... остальной код

    debug_print(f"🔥 sport_callback_handler: ВХОД")
    debug_print(f"📨 ПОЛУЧЕН CALLBACK: {data}")
    debug_print(f"📦 user_data: {context.user_data}")
    debug_print(f"🏷️ состояние: {context.user_data.get('conversation_state')}")

    if DEBUG_MODE:
        debug_print(f"🔥 sport_callback_handler: data={data}")

    # Ветки обработки
    if data == 'sport_catalog':
        debug_print(f"🔥 sport_callback_handler: ветка sport_catalog")
        await catalog_command(update, context)
        # elif data == 'sport_wod':
        #     debug_print(f"🔥 sport_callback_handler: ветка sport_wod")
        #     await workout_start(update, context)
    elif data == 'sport_mystats':
        debug_print(f"🔥 sport_callback_handler: ветка sport_mystats")
        await mystats_command(update, context)
    elif data == 'sport_setlevel':
        debug_print(f"🔥 sport_callback_handler: ветка sport_setlevel")
        await setlevel_command(update, context)
    elif data == 'back_to_main':
        debug_print(f"🔥 sport_callback_handler: ветка back_to_main")
        await start(update, context)
    elif data == 'sport_complexes':
        debug_print(f"🔥 sport_callback_handler: ветка sport_complexes")
        await complexes_command(update, context)
    elif data == 'sport_challenges':
        debug_print(f"🔥 sport_callback_handler: ветка sport_challenges")
        await challenges_command(update, context)
    elif data.startswith('join_challenge_'):
        debug_print(f"🔥 sport_callback_handler: ветка join_challenge_")
        logger.debug(f"🔹 Попытка присоединиться к челленджу: {data}")
        challenge_id = int(data.split('_')[2])
        await update.callback_query.edit_message_text(f"Вы присоединились к челленджу #{challenge_id}")
    elif data == "cancel_catalog":
        debug_print(f"🔥 sport_callback_handler: ветка cancel_catalog")
        await do_exercise_callback(update, context)
        return
    elif data == "cancel_challenges":
        debug_print(f"🔥 sport_callback_handler: ветка cancel_challenges")
        await start(update, context)
        return
    elif data == "cancel_complex":
        debug_print(f"🔥 sport_callback_handler: ветка cancel_complex")
        from utils import handle_cancel
        return await handle_cancel(update, context)
    elif data.startswith('complex_ex_'):
        debug_print(f"🔥 sport_callback_handler: ветка complex_ex_")
        # Выполнение упражнения из комплекса
        parts = data.split('_')
        exercise_id = int(parts[2])
        complex_id = int(parts[3])
        reps = int(parts[4])
        context.user_data['pending_exercise'] = exercise_id
        context.user_data['submit_entity_type'] = 'exercise'
        context.user_data['submit_entity_id'] = exercise_id
        context.user_data['complex_reps'] = reps
        context.user_data['current_complex_id'] = complex_id
        state = await workout_start(update, context)
        if state:
            context.user_data['conversation_state'] = state
    else:
        debug_print(f"🔥 sport_callback_handler: неизвестная ветка: {data}")

    debug_print(f"📤 sport_callback_handler: ВОЗВРАТ")


@log_call
async def send_catalog_to_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 send_catalog_to_message: ВХОД")

    exercises = get_all_exercises()
    if not exercises:
        if update.callback_query:
            await update.callback_query.edit_message_text("Список упражнений пуст.")
        else:
            await update.message.reply_text("Список упражнений пуст.")
        debug_print(f"📤 send_catalog_to_message: ВОЗВРАТ (нет упражнений)")
        return

    keyboard = []
    for ex in exercises:
        ex_id = ex[0]
        ex_name = ex[1]
        ex_points = ex[3]
        keyboard.append(
            [InlineKeyboardButton(f"💪 {ex_name} ({ex_points} баллов)", callback_data=f'do_exercise_{ex_id}')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "📋 **КАТАЛОГ УПРАЖНЕНИЙ**\n\nВыбери упражнение для выполнения:"

    if DEBUG_MODE:
        debug_print(f"🔥 send_catalog_to_message: клавиатура создана, кнопок={len(keyboard)}")
        for btn_row in keyboard:
            for btn in btn_row:
                debug_print(f"   кнопка: {btn.text} -> {btn.callback_data}")

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)

    debug_print(f"📤 send_catalog_to_message: ВОЗВРАТ")


@log_call
async def mystats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 mystats_command: ВХОД")
    debug_print(f"📦 user_data: {context.user_data}")

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

    debug_print(f"📤 mystats_command: ВОЗВРАТ")


@log_call
async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 top_command: ВХОД")

    leaderboard = get_leaderboard_from_scoreboard()
    if not leaderboard:
        await update.message.reply_text("Нет данных.")
        debug_print(f"📤 top_command: ВОЗВРАТ (нет данных)")
        return
    text = "🏆 **ТОП ИГРОКОВ**\n\n" + "\n".join(
        [f"{i + 1}. {row[1] or row[2]} — {row[3]} баллов" for i, row in enumerate(leaderboard[:10])])
    await update.message.reply_text(text, parse_mode='Markdown')
    debug_print(f"📤 top_command: ВОЗВРАТ")


@log_call
async def setlevel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 setlevel_command: ВХОД")
    debug_print(f"📦 user_data: {context.user_data}")

    # Если есть аргументы командной строки (/setlevel beginner)
    if context.args and context.args[0] in ('beginner', 'pro'):
        set_user_level(update.effective_user.id, context.args[0])
        msg = f"✅ Уровень изменён на {context.args[0]}."
        if update.callback_query:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
    else:
        # Если нет аргументов — показываем кнопки выбора уровня
        debug_print(f"🔥 setlevel_command: показать кнопки выбора уровня")

        # Получаем текущий уровень пользователя
        current_level = get_user_level(update.effective_user.id)
        debug_print(f"🔥 setlevel_command: текущий уровень = {current_level}")

        # Создаём кнопки
        keyboard = [
            [InlineKeyboardButton("🟢 Новичок (beginner) ✅" if current_level == 'beginner' else "🟢 Новичок (beginner)",
                                  callback_data='setlevel_beginner')],
            [InlineKeyboardButton("🔴 Профи (pro) ✅" if current_level == 'pro' else "🔴 Профи (pro)",
                                  callback_data='setlevel_pro')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        msg = f"🎯 **Выбор уровня**\n\nТвой текущий уровень: **{current_level}**\n\nВыбери уровень:"

        if update.callback_query:
            await update.callback_query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
        else:
            await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)

    debug_print(f"📤 setlevel_command: ВОЗВРАТ")


@log_call
async def delete_exercise_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 delete_exercise_command: ВХОД")

    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        debug_print(f"📤 delete_exercise_command: ВОЗВРАТ (нет прав)")
        return
    if not context.args:
        await update.message.reply_text("Использование: /delexercise <id>")
        debug_print(f"📤 delete_exercise_command: ВОЗВРАТ (нет аргументов)")
        return
    try:
        exercise_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        debug_print(f"📤 delete_exercise_command: ВОЗВРАТ (ошибка ID)")
        return

    ex = get_exercise_by_id(exercise_id)
    if not ex:
        await update.message.reply_text("Упражнение не найдено.")
        debug_print(f"📤 delete_exercise_command: ВОЗВРАТ (упражнение не найдено)")
        return

    context.user_data['delete_exercise_id'] = exercise_id
    context.user_data['delete_exercise_name'] = ex[1]
    await update.message.reply_text(
        f"Вы уверены, что хотите удалить упражнение '{ex[1]}' (ID {exercise_id})? Отправьте 'ДА' для подтверждения.")
    debug_print(f"📤 delete_exercise_command: ВОЗВРАТ CONFIRM_DELETE")
    return CONFIRM_DELETE


@log_call
async def delete_exercise_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 delete_exercise_start: ВХОД")

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Введите ID упражнения для удаления:")
    else:
        await update.message.reply_text("Введите ID упражнения для удаления:")
    debug_print(f"📤 delete_exercise_start: ВОЗВРАТ WAIT_DELETE_ID")
    return WAIT_DELETE_ID


@log_call
async def delete_exercise_get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 delete_exercise_get_id: ВХОД")
    debug_print(f"📨 ТЕКСТ: {update.message.text}")

    try:
        exercise_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("ID должен быть числом. Попробуйте ещё раз:")
        debug_print(f"📤 delete_exercise_get_id: ВОЗВРАТ WAIT_DELETE_ID (ошибка ID)")
        return WAIT_DELETE_ID
    ex = get_exercise_by_id(exercise_id)
    if not ex:
        await update.message.reply_text("Упражнение не найдено.")
        debug_print(f"📤 delete_exercise_get_id: ВОЗВРАТ END")
        return ConversationHandler.END
    context.user_data['delete_exercise_id'] = exercise_id
    context.user_data['delete_exercise_name'] = ex[1]
    await update.message.reply_text(
        f"Вы уверены, что хотите удалить упражнение '{ex[1]}' (ID {exercise_id})? Отправьте 'ДА' для подтверждения.")
    debug_print(f"📤 delete_exercise_get_id: ВОЗВРАТ CONFIRM_DELETE")
    return CONFIRM_DELETE


@log_call
async def confirm_delete_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 confirm_delete_exercise: ВХОД")
    debug_print(f"📨 ТЕКСТ: {update.message.text}")

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
    debug_print(f"📤 confirm_delete_exercise: ВОЗВРАТ END")
    return ConversationHandler.END


@log_call
async def list_exercises_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 list_exercises_command: ВХОД")

    if not is_admin(update):
        debug_print(f"📤 list_exercises_command: ВОЗВРАТ (нет прав)")
        return
    page = 1
    if context.args and context.args[0].isdigit():
        page = int(context.args[0])
    all_exercises = get_all_exercises()
    if not all_exercises:
        await update.message.reply_text("Упражнений пока нет.")
        debug_print(f"📤 list_exercises_command: ВОЗВРАТ (нет упражнений)")
        return
    exercises, keyboard = paginate(all_exercises, page, per_page=5, prefix='ex_page')
    text = "📋 **Список упражнений:**\n\n"
    for ex in exercises:
        name = ex[1].replace('_', r'\_').replace('*', r'\*').replace('[', r'\[').replace(']', r'\]')
        text += f"🔹 ID: {ex[0]} — {name} ({ex[5]})\n"
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    debug_print(f"📤 list_exercises_command: ВОЗВРАТ")


@log_call
async def exercise_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 exercise_page_callback: ВХОД")

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
    debug_print(f"📤 exercise_page_callback: ВОЗВРАТ")


@log_call
async def load_exercises_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 load_exercises_command: ВХОД")

    if not is_admin(update):
        debug_print(f"📤 load_exercises_command: ВОЗВРАТ (нет прав)")
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
    debug_print(f"📤 load_exercises_command: ВОЗВРАТ")


@log_call
async def recalc_rankings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 recalc_rankings_command: ВХОД")

    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        debug_print(f"📤 recalc_rankings_command: ВОЗВРАТ (нет прав)")
        return
    await update.message.reply_text("⏳ Начинаю пересчёт рейтинга...")
    recalculate_rankings(period_days=7)
    await update.message.reply_text("✅ Рейтинг пересчитан.")
    debug_print(f"📤 recalc_rankings_command: ВОЗВРАТ")


@log_call
async def myhistory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 myhistory_command: ВХОД")

    user_id = update.effective_user.id
    limit = 20
    if context.args and context.args[0].isdigit():
        limit = int(context.args[0])
        if limit > 50:
            limit = 50
    workouts = get_user_workouts(user_id, limit)
    if not workouts:
        await update.message.reply_text("Нет тренировок.")
        debug_print(f"📤 myhistory_command: ВОЗВРАТ (нет тренировок)")
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
    debug_print(f"📤 myhistory_command: ВОЗВРАТ")


# ==================== КОМАНДЫ ДЛЯ КОМПЛЕКСОВ ====================
@log_call
async def add_complex_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 add_complex_command: ВХОД")

    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        debug_print(f"📤 add_complex_command: ВОЗВРАТ (нет прав)")
        return
    try:
        text = update.message.text.split(maxsplit=1)[1]
        args = shlex.split(text)
        if len(args) < 4:
            await update.message.reply_text(
                "Использование: /addcomplex <название> <описание> <тип> <баллы>\nТип: for_time или for_reps")
            debug_print(f"📤 add_complex_command: ВОЗВРАТ (мало аргументов)")
            return
        name, description, type_, points = args[0], args[1], args[2], int(args[3])
        if type_ not in ('for_time', 'for_reps'):
            await update.message.reply_text("Тип должен быть for_time или for_reps")
            debug_print(f"📤 add_complex_command: ВОЗВРАТ (неверный тип)")
            return
        complex_id = add_complex(name, description, type_, points)
        await update.message.reply_text(f"✅ Комплекс «{name}» создан с ID {complex_id}.")
    except Exception as e:
        await update.message.reply_text(format_error(f"Ошибка: {e}"))
    debug_print(f"📤 add_complex_command: ВОЗВРАТ")


@log_call
async def add_complex_exercise_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 add_complex_exercise_command: ВХОД")

    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        debug_print(f"📤 add_complex_exercise_command: ВОЗВРАТ (нет прав)")
        return
    try:
        args = context.args
        if len(args) != 3:
            await update.message.reply_text("Использование: /addcomplexexercise <complex_id> <exercise_id> <reps>")
            debug_print(f"📤 add_complex_exercise_command: ВОЗВРАТ (не 3 аргумента)")
            return
        complex_id = int(args[0])
        exercise_id = int(args[1])
        reps = int(args[2])
        complex_data = get_complex_by_id(complex_id)
        if not complex_data:
            await update.message.reply_text("Комплекс не найден.")
            debug_print(f"📤 add_complex_exercise_command: ВОЗВРАТ (комплекс не найден)")
            return
        ex = get_exercise_by_id(exercise_id)
        if not ex:
            await update.message.reply_text("Упражнение не найдено.")
            debug_print(f"📤 add_complex_exercise_command: ВОЗВРАТ (упражнение не найдено)")
            return
        add_complex_exercise(complex_id, exercise_id, reps)
        await update.message.reply_text(f"✅ Упражнение «{ex[1]}» добавлено в комплекс {complex_data[1]}.")
    except Exception as e:
        await update.message.reply_text(format_error(f"Ошибка: {e}"))
    debug_print(f"📤 add_complex_exercise_command: ВОЗВРАТ")


@log_call
async def complexes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 complexes_command: ВХОД")

    if DEBUG_MODE:
        debug_print("🔥 complexes_command: вызвана")

    all_complexes = get_all_complexes()
    if not all_complexes:
        if update.callback_query:
            await update.callback_query.edit_message_text("Комплексов пока нет.")
        else:
            await update.message.reply_text("Комплексов пока нет.")
        debug_print(f"📤 complexes_command: ВОЗВРАТ (нет комплексов)")
        return

    keyboard = []
    for c in all_complexes:
        complex_id = c[0]
        complex_name = c[1]
        keyboard.append([InlineKeyboardButton(f"📦 {complex_name}", callback_data=f'do_complex_{complex_id}')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "📦 **Доступные комплексы:**\n\nВыбери комплекс для выполнения:"

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)

    debug_print(f"📤 complexes_command: ВОЗВРАТ")


@log_call
async def complex_detail_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 complex_detail_command: ВХОД")

    try:
        complex_id = int(context.args[0])
    except (ValueError, IndexError, TypeError):
        await update.message.reply_text("Использование: /complex <id>")
        debug_print(f"📤 complex_detail_command: ВОЗВРАТ (ошибка ID)")
        return
    complex_data = get_complex_by_id(complex_id)
    if not complex_data:
        await update.message.reply_text("Комплекс не найден.")
        debug_print(f"📤 complex_detail_command: ВОЗВРАТ (комплекс не найден)")
        return
    exercises = get_complex_exercises(complex_id)
    text = f"**{complex_data[1]}**\n{complex_data[2]}\n\nТип: {'Время' if complex_data[3] == 'for_time' else 'Повторения'}\nБаллы: {complex_data[4]}\n\n**Упражнения:**\n"
    for ex in exercises:
        text += f"• {ex[2]} — {ex[4]} повторений\n"
    await update.message.reply_text(text, parse_mode='Markdown')
    debug_print(f"📤 complex_detail_command: ВОЗВРАТ")


@log_call
async def delete_complex_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 delete_complex_command: ВХОД")

    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        debug_print(f"📤 delete_complex_command: ВОЗВРАТ (нет прав)")
        return
    if not context.args:
        await update.message.reply_text("Использование: /deletecomplex <id>")
        debug_print(f"📤 delete_complex_command: ВОЗВРАТ (нет аргументов)")
        return
    try:
        complex_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        debug_print(f"📤 delete_complex_command: ВОЗВРАТ (ошибка ID)")
        return
    complex_data = get_complex_by_id(complex_id)
    if not complex_data:
        await update.message.reply_text("Комплекс не найден.")
        debug_print(f"📤 delete_complex_command: ВОЗВРАТ (комплекс не найден)")
        return
    context.user_data['delete_complex_id'] = complex_id
    await update.message.reply_text(
        f"Вы уверены, что хотите удалить комплекс '{complex_data[1]}'? Отправьте 'ДА' для подтверждения.")
    debug_print(f"📤 delete_complex_command: ВОЗВРАТ CONFIRM_DELETE_COMPLEX")
    return CONFIRM_DELETE_COMPLEX


@log_call
async def confirm_delete_complex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 confirm_delete_complex: ВХОД")
    debug_print(f"📨 ТЕКСТ: {update.message.text}")

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
    debug_print(f"📤 confirm_delete_complex: ВОЗВРАТ END")
    return ConversationHandler.END


# ==================== КОМАНДЫ ДЛЯ ЧЕЛЛЕНДЖЕЙ ====================
@log_call
async def addchallenge_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 addchallenge_start: ВХОД")

    if not is_admin(update):
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text("⛔ Нет прав.")
        else:
            await update.message.reply_text("⛔ Нет прав.")
        debug_print(f"📤 addchallenge_start: ВОЗВРАТ END (нет прав)")
        return ConversationHandler.END
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Введите название челленджа:")
    else:
        await update.message.reply_text("Введите название челленджа:")
    debug_print(f"📤 addchallenge_start: ВОЗВРАТ CHALL_NAME")
    return CHALL_NAME


@log_call
async def challenge_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 challenge_name_input: ВХОД")
    debug_print(f"📨 ТЕКСТ: {update.message.text}")

    context.user_data['challenge_name'] = update.message.text
    await update.message.reply_text("Введите описание челленджа (можно пропустить, отправьте '-'):")
    debug_print(f"📤 challenge_name_input: ВОЗВРАТ CHALL_DESC")
    return CHALL_DESC


@log_call
async def challenge_desc_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 challenge_desc_input: ВХОД")
    debug_print(f"📨 ТЕКСТ: {update.message.text}")

    desc = update.message.text
    if desc == '-':
        desc = ''
    context.user_data['challenge_desc'] = desc
    keyboard = [
        [InlineKeyboardButton("Упражнение", callback_data="chall_target_exercise")],
        [InlineKeyboardButton("Комплекс", callback_data="chall_target_complex")],
    ]
    await update.message.reply_text("Выберите тип цели:", reply_markup=InlineKeyboardMarkup(keyboard))
    debug_print(f"📤 challenge_desc_input: ВОЗВРАТ CHALL_TYPE")
    return CHALL_TYPE


@log_call
async def challenge_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 challenge_type_callback: ВХОД")

    query = update.callback_query
    await query.answer()
    if query.data == "chall_target_exercise":
        context.user_data['challenge_target_type'] = 'exercise'
        exercises = get_all_exercises()
        if not exercises:
            await query.edit_message_text("Нет упражнений.")
            debug_print(f"📤 challenge_type_callback: ВОЗВРАТ END")
            return ConversationHandler.END
        keyboard = []
        for ex in exercises:
            keyboard.append([InlineKeyboardButton(ex[1], callback_data=f"chall_ex_{ex[0]}")])
        await query.edit_message_text("Выберите упражнение:", reply_markup=InlineKeyboardMarkup(keyboard))
        debug_print(f"📤 challenge_type_callback: ВОЗВРАТ CHALL_TARGET")
        return CHALL_TARGET
    else:
        context.user_data['challenge_target_type'] = 'complex'
        complexes = get_all_complexes()
        if not complexes:
            await query.edit_message_text("Нет комплексов.")
            debug_print(f"📤 challenge_type_callback: ВОЗВРАТ END")
            return ConversationHandler.END
        keyboard = []
        for c in complexes:
            keyboard.append([InlineKeyboardButton(c[1], callback_data=f"chall_cx_{c[0]}")])
        await query.edit_message_text("Выберите комплекс:", reply_markup=InlineKeyboardMarkup(keyboard))
        debug_print(f"📤 challenge_type_callback: ВОЗВРАТ CHALL_TARGET")
        return CHALL_TARGET


@log_call
async def challenge_target_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 challenge_target_callback: ВХОД")

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
            debug_print(f"📤 challenge_target_callback: ВОЗВРАТ END")
            return ConversationHandler.END
        debug_print(f"📤 challenge_target_callback: ВОЗВРАТ CHALL_TARGET_VALUE")
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
            debug_print(f"📤 challenge_target_callback: ВОЗВРАТ END")
            return ConversationHandler.END
        debug_print(f"📤 challenge_target_callback: ВОЗВРАТ CHALL_TARGET_VALUE")
        return CHALL_TARGET_VALUE


@log_call
async def challenge_target_value_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 challenge_target_value_input: ВХОД")
    debug_print(f"📨 ТЕКСТ: {update.message.text}")

    target_value = update.message.text.strip()
    metric = context.user_data.get('challenge_metric')
    if metric == 'reps':
        if not target_value.isdigit():
            await update.message.reply_text("Введите целое число повторений.")
            debug_print(f"📤 challenge_target_value_input: ВОЗВРАТ CHALL_TARGET_VALUE (не число)")
            return CHALL_TARGET_VALUE
    else:
        if not re.match(r'^\d{1,2}:\d{2}$', target_value):
            await update.message.reply_text("Введите время в формате ММ:СС (например, 05:30).")
            debug_print(f"📤 challenge_target_value_input: ВОЗВРАТ CHALL_TARGET_VALUE (неверный формат)")
            return CHALL_TARGET_VALUE
    context.user_data['challenge_target_value'] = target_value
    await update.message.reply_text("Введите дату начала челленджа в формате ДД.ММ.ГГГГ:")
    debug_print(f"📤 challenge_target_value_input: ВОЗВРАТ CHALL_START_DATE")
    return CHALL_START_DATE


@log_call
async def challenge_start_date_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 challenge_start_date_input: ВХОД")
    debug_print(f"📨 ТЕКСТ: {update.message.text}")

    start_date_str = update.message.text.strip()
    start_date = parse_date(start_date_str)
    if not start_date:
        await update.message.reply_text("Неверный формат. Введите дату в формате ДД.ММ.ГГГГ.")
        debug_print(f"📤 challenge_start_date_input: ВОЗВРАТ CHALL_START_DATE (неверный формат)")
        return CHALL_START_DATE
    context.user_data['challenge_start_date'] = start_date
    await update.message.reply_text("Введите дату окончания челленджа в формате ДД.ММ.ГГГГ:")
    debug_print(f"📤 challenge_start_date_input: ВОЗВРАТ CHALL_END_DATE")
    return CHALL_END_DATE


@log_call
async def challenge_end_date_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 challenge_end_date_input: ВХОД")
    debug_print(f"📨 ТЕКСТ: {update.message.text}")

    end_date_str = update.message.text.strip()
    end_date = parse_date(end_date_str)
    if not end_date:
        await update.message.reply_text("Неверный формат. Введите дату в формате ДД.ММ.ГГГГ.")
        debug_print(f"📤 challenge_end_date_input: ВОЗВРАТ CHALL_END_DATE (неверный формат)")
        return CHALL_END_DATE
    start_date = context.user_data.get('challenge_start_date')
    if start_date and end_date <= start_date:
        await update.message.reply_text("Дата окончания должна быть позже даты начала.")
        debug_print(f"📤 challenge_end_date_input: ВОЗВРАТ CHALL_END_DATE (дата окончания <= даты начала)")
        return CHALL_END_DATE
    context.user_data['challenge_end_date'] = end_date
    await update.message.reply_text("Введите количество бонусных баллов (целое число):")
    debug_print(f"📤 challenge_end_date_input: ВОЗВРАТ CHALL_BONUS")
    return CHALL_BONUS


@log_call
async def challenge_bonus_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 challenge_bonus_input: ВХОД")
    debug_print(f"📨 ТЕКСТ: {update.message.text}")

    try:
        bonus = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Введите целое число.")
        debug_print(f"📤 challenge_bonus_input: ВОЗВРАТ CHALL_BONUS (не число)")
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
    debug_print(f"📤 challenge_bonus_input: ВОЗВРАТ END")
    return ConversationHandler.END


@log_call
async def challenges_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 challenges_command: ВХОД")

    if DEBUG_MODE:
        debug_print("🔥 challenges_command: вызвана")

    logger.debug("🔹 Вызов challenges_command")
    challenges = get_challenges_by_status('active')
    logger.debug(f"🔹 Найдено челленджей: {len(challenges)}")
    if not challenges:
        if update.callback_query:
            await update.callback_query.edit_message_text("Активных челленджей нет.")
        else:
            await update.message.reply_text("Активных челленджей нет.")
        debug_print(f"📤 challenges_command: ВОЗВРАТ (нет челленджей)")
        return

    keyboard = []
    for ch in challenges:
        ch_id = ch[0]
        ch_name = ch[1]
        ch_bonus = ch[9]
        keyboard.append(
            [InlineKeyboardButton(f"🏆 {ch_name} (бонус: {ch_bonus})", callback_data=f'join_challenge_{ch_id}')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "🏆 **Активные челленджи:**\n\nВыбери челлендж для участия:"

    if update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)

    debug_print(f"📤 challenges_command: ВОЗВРАТ")


@log_call
async def join_challenge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 join_challenge_command: ВХОД")

    try:
        challenge_id = int(context.args[0])
    except (ValueError, IndexError, TypeError):
        await update.message.reply_text("Использование: /join <id>")
        debug_print(f"📤 join_challenge_command: ВОЗВРАТ (ошибка ID)")
        return
    success = join_challenge(update.effective_user.id, challenge_id)
    if success:
        await update.message.reply_text("✅ Вы присоединились к челленджу!")
    else:
        await update.message.reply_text("❌ Не удалось присоединиться.")
    debug_print(f"📤 join_challenge_command: ВОЗВРАТ")


@log_call
async def my_challenges_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 my_challenges_command: ВХОД")

    challenges = get_user_challenges_with_details(update.effective_user.id)
    if not challenges:
        await update.message.reply_text("Вы не участвуете в челленджах.")
        debug_print(f"📤 my_challenges_command: ВОЗВРАТ (нет челленджей)")
        return
    text = "🏆 **Ваши челленджи:**\n\n"
    for ch in challenges:
        text += f"**{ch[1]}** — прогресс: {ch[9]}/{ch[6]}\n"
    await update.message.reply_text(text, parse_mode='Markdown')
    debug_print(f"📤 my_challenges_command: ВОЗВРАТ")


@log_call
async def myprogress_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 myprogress_command: ВХОД")
    await my_challenges_command(update, context)
    debug_print(f"📤 myprogress_command: ВОЗВРАТ")


# ==================== ДИАЛОГ ВЫПОЛНЕНИЯ КОМПЛЕКСА ====================
@log_call
async def do_complex_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 do_complex_start: ВХОД")

    query = update.callback_query
    await query.answer()
    complex_id = int(query.data.split('_')[2])
    complex_data = get_complex_by_id(complex_id)
    if not complex_data:
        await query.edit_message_text("Комплекс не найден.")
        debug_print(f"📤 do_complex_start: ВОЗВРАТ END")
        return ConversationHandler.END
    context.user_data['current_complex_id'] = complex_id
    context.user_data['complex_name'] = complex_data[1]
    context.user_data['complex_points'] = complex_data[4]
    await query.edit_message_text(
        f"Выполняем комплекс **{complex_data[1]}**.\nВведите результат:",
        parse_mode='Markdown',
    )
    debug_print(f"📤 do_complex_start: ВОЗВРАТ COMPLEX_RESULT")
    return COMPLEX_RESULT


@log_call
async def complex_result_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 complex_result_input: ВХОД")
    debug_print(f"📨 ТЕКСТ: {update.message.text}")

    result_text = update.message.text.strip()
    complex_id = context.user_data['current_complex_id']
    complex_data = get_complex_by_id(complex_id)
    if not complex_data:
        await update.message.reply_text("Комплекс не найден.")
        debug_print(f"📤 complex_result_input: ВОЗВРАТ END")
        return ConversationHandler.END
    complex_type = complex_data[3]
    if complex_type == 'for_time':
        if not re.match(r'^\d{1,2}:\d{2}$', result_text):
            await update.message.reply_text("Неверный формат. Используй ММ:СС")
            debug_print(f"📤 complex_result_input: ВОЗВРАТ COMPLEX_RESULT (неверный формат)")
            return COMPLEX_RESULT
        context.user_data['complex_result_value'] = result_text
    else:
        if not result_text.isdigit():
            await update.message.reply_text("Введи число повторений.")
            debug_print(f"📤 complex_result_input: ВОЗВРАТ COMPLEX_RESULT (не число)")
            return COMPLEX_RESULT
        context.user_data['complex_result_value'] = result_text
    await update.message.reply_text("Отправь ссылку на видео:")
    debug_print(f"📤 complex_result_input: ВОЗВРАТ COMPLEX_VIDEO")
    return COMPLEX_VIDEO


@log_call
async def complex_video_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 complex_video_input: ВХОД")
    debug_print(f"📨 ТЕКСТ: {update.message.text}")

    video_url = update.message.text.strip()
    context.user_data['complex_video'] = video_url
    await update.message.reply_text("Добавь комментарий (или /skip):")
    debug_print(f"📤 complex_video_input: ВОЗВРАТ COMPLEX_COMMENT")
    return COMPLEX_COMMENT


@log_call
async def complex_comment_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 complex_comment_input: ВХОД")
    debug_print(f"📨 ТЕКСТ: {update.message.text}")

    comment = update.message.text.strip()
    context.user_data['complex_comment'] = comment
    await save_complex_workout(update, context)
    debug_print(f"📤 complex_comment_input: ВОЗВРАТ END")
    return ConversationHandler.END


@log_call
async def complex_comment_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 complex_comment_skip: ВХОД")

    context.user_data['complex_comment'] = None
    await save_complex_workout(update, context)
    debug_print(f"📤 complex_comment_skip: ВОЗВРАТ END")
    return ConversationHandler.END


@log_call
async def save_complex_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 save_complex_workout: ВХОД")
    debug_print(f"📦 user_data: {context.user_data}")

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
    debug_print(f"📤 save_complex_workout: ВОЗВРАТ")


# ==================== КОНСТРУКТОР КОМПЛЕКСОВ ====================
@log_call
async def newcomplex_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 newcomplex_start: ВХОД")

    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        debug_print(f"📤 newcomplex_start: ВОЗВРАТ END (нет прав)")
        return ConversationHandler.END
    await update.message.reply_text("Введите название комплекса:")
    debug_print(f"📤 newcomplex_start: ВОЗВРАТ COMPLEX_NAME")
    return COMPLEX_NAME


@log_call
async def complex_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 complex_name_input: ВХОД")
    debug_print(f"📨 ТЕКСТ: {update.message.text}")

    context.user_data['complex_name'] = update.message.text
    await update.message.reply_text("Введите описание (можно пропустить, отправьте '-'):")
    debug_print(f"📤 complex_name_input: ВОЗВРАТ COMPLEX_DESC")
    return COMPLEX_DESC


@log_call
async def complex_desc_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 complex_desc_input: ВХОД")
    debug_print(f"📨 ТЕКСТ: {update.message.text}")

    desc = update.message.text
    if desc == '-':
        desc = ''
    context.user_data['complex_desc'] = desc
    keyboard = [
        [InlineKeyboardButton("Время (for_time)", callback_data="type_for_time")],
        [InlineKeyboardButton("Повторения (for_reps)", callback_data="type_for_reps")],
    ]
    await update.message.reply_text("Выберите тип комплекса:", reply_markup=InlineKeyboardMarkup(keyboard))
    debug_print(f"📤 complex_desc_input: ВОЗВРАТ COMPLEX_TYPE")
    return COMPLEX_TYPE


@log_call
async def complex_type_temp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 complex_type_temp: ВХОД")

    query = update.callback_query
    await query.answer()
    type_ = query.data.split('_')[2]
    context.user_data['complex_type'] = type_
    await query.edit_message_text("Введите количество баллов:")
    debug_print(f"📤 complex_type_temp: ВОЗВРАТ COMPLEX_POINTS")
    return COMPLEX_POINTS


@log_call
async def complex_points_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 complex_points_input: ВХОД")
    debug_print(f"📨 ТЕКСТ: {update.message.text}")

    try:
        points = int(update.message.text)
    except:
        await update.message.reply_text("Введите число.")
        debug_print(f"📤 complex_points_input: ВОЗВРАТ COMPLEX_POINTS (не число)")
        return COMPLEX_POINTS
    context.user_data['complex_points'] = points
    exercises = get_all_exercises()
    if not exercises:
        await update.message.reply_text("Нет упражнений.")
        debug_print(f"📤 complex_points_input: ВОЗВРАТ END")
        return ConversationHandler.END
    keyboard = []
    for ex in exercises:
        keyboard.append([InlineKeyboardButton(ex[1], callback_data=f"addex_{ex[0]}")])
    keyboard.append([InlineKeyboardButton("✅ Завершить", callback_data="finish_complex")])
    await update.message.reply_text("Выберите упражнения для добавления:", reply_markup=InlineKeyboardMarkup(keyboard))
    debug_print(f"📤 complex_points_input: ВОЗВРАТ COMPLEX_ADD_EXERCISE")
    return COMPLEX_ADD_EXERCISE


@log_call
async def complex_add_exercise_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 complex_add_exercise_callback: ВХОД")

    query = update.callback_query
    await query.answer()
    if query.data == "finish_complex":
        exercises_list = context.user_data.get('complex_exercises', [])
        if not exercises_list:
            await query.edit_message_text("Нет упражнений. Комплекс не создан.")
            debug_print(f"📤 complex_add_exercise_callback: ВОЗВРАТ END (нет упражнений)")
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
        debug_print(f"📤 complex_add_exercise_callback: ВОЗВРАТ END")
        return ConversationHandler.END
    else:
        ex_id = int(query.data.split('_')[1])
        context.user_data['temp_exercise_id'] = ex_id
        await query.edit_message_text("Введите количество повторений для этого упражнения:")
        debug_print(f"📤 complex_add_exercise_callback: ВОЗВРАТ COMPLEX_REPS")
        return COMPLEX_REPS


@log_call
async def complex_reps_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 complex_reps_input: ВХОД")
    debug_print(f"📨 ТЕКСТ: {update.message.text}")

    try:
        reps = int(update.message.text)
    except:
        await update.message.reply_text("Введите число.")
        debug_print(f"📤 complex_reps_input: ВОЗВРАТ COMPLEX_REPS (не число)")
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
    debug_print(f"📤 complex_reps_input: ВОЗВРАТ COMPLEX_ADD_EXERCISE")
    return COMPLEX_ADD_EXERCISE


# ==================== ДРУГИЕ КОМАНДЫ ====================
@log_call
async def setlevel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 setlevel_callback: ВХОД")

    query = update.callback_query
    await query.answer()
    level = query.data.split('_')[1]
    set_user_level(update.effective_user.id, level)
    await query.edit_message_text(f"✅ Уровень изменён на {level}.")
    debug_print(f"📤 setlevel_callback: ВОЗВРАТ")


@log_call
async def exercise_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 exercise_callback: ВХОД")

    query = update.callback_query
    await query.answer()
    ex_id = int(query.data.split('_')[1])
    ex = get_exercise_by_id(ex_id)
    if not ex:
        await query.edit_message_text("Упражнение не найдено.")
        debug_print(f"📤 exercise_callback: ВОЗВРАТ")
        return
    text = f"**{ex[1]}**\n{ex[2]}\n🏅 Баллы: {ex[4]}\n📏 Тип: {'повторения' if ex[3] == 'reps' else 'время'}"
    keyboard = [[InlineKeyboardButton("✍️ Записать", callback_data=f"record_{ex_id}")]]
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    debug_print(f"📤 exercise_callback: ВОЗВРАТ")


@log_call
async def record_from_catalog_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 record_from_catalog_callback: ВХОД")

    query = update.callback_query
    await query.answer()
    ex_id = int(query.data.split('_')[1])
    context.user_data['pending_exercise'] = ex_id
    await query.edit_message_text("Теперь отправь /wod")
    debug_print(f"📤 record_from_catalog_callback: ВОЗВРАТ")


@log_call
async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 help_callback: ВХОД")

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
    debug_print(f"📤 help_callback: ВОЗВРАТ")


@log_call
async def stats_period_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 stats_period_callback: ВХОД")

    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Статистика за период (демо)")
    debug_print(f"📤 stats_period_callback: ВОЗВРАТ")


@log_call
async def top_league_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 top_league_callback: ВХОД")

    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Топ лиги (демо)")
    debug_print(f"📤 top_league_callback: ВОЗВРАТ")


@log_call
async def complex_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 complex_page_callback: ВХОД")

    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Список комплексов (демо)")
    debug_print(f"📤 complex_page_callback: ВОЗВРАТ")


@log_call
async def edit_complex_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 edit_complex_command: ВХОД")

    await update.message.reply_text("Редактирование комплексов (в разработке)")
    debug_print(f"📤 edit_complex_command: ВОЗВРАТ")


@log_call
async def edit_complex_field_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 edit_complex_field_callback: ВХОД")

    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Редактирование (в разработке)")
    debug_print(f"📤 edit_complex_field_callback: ВОЗВРАТ")


@log_call
async def edit_complex_value_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 edit_complex_value_input: ВХОД")

    await update.message.reply_text("Редактирование (в разработке)")
    debug_print(f"📤 edit_complex_value_input: ВОЗВРАТ")


@log_call
async def edit_exercise_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 edit_exercise_start: ВХОД")

    await update.message.reply_text("Введите ID упражнения для редактирования:")
    debug_print(f"📤 edit_exercise_start: ВОЗВРАТ EDIT_EXERCISE_ID")
    return EDIT_EXERCISE_ID


@log_call
async def edit_exercise_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 edit_exercise_id_input: ВХОД")
    debug_print(f"📨 ТЕКСТ: {update.message.text}")

    try:
        exercise_id = int(update.message.text)
    except:
        await update.message.reply_text("ID должен быть числом.")
        debug_print(f"📤 edit_exercise_id_input: ВОЗВРАТ EDIT_EXERCISE_ID (не число)")
        return EDIT_EXERCISE_ID
    ex = get_exercise_by_id(exercise_id)
    if not ex:
        await update.message.reply_text("Упражнение не найдено.")
        debug_print(f"📤 edit_exercise_id_input: ВОЗВРАТ END")
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
    debug_print(f"📤 edit_exercise_id_input: ВОЗВРАТ EDIT_EXERCISE_VALUE")
    return EDIT_EXERCISE_VALUE


@log_call
async def edit_exercise_value_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 edit_exercise_value_input: ВХОД")

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        if query.data == "cancel_edit_ex":
            await query.edit_message_text("Отменено.")
            debug_print(f"📤 edit_exercise_value_input: ВОЗВРАТ END")
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
            debug_print(f"📤 edit_exercise_value_input: ВОЗВРАТ EDIT_EXERCISE_VALUE")
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
        debug_print(f"📤 edit_exercise_value_input: ВОЗВРАТ END")
        return ConversationHandler.END
    debug_print(f"📤 edit_exercise_value_input: ВОЗВРАТ EDIT_EXERCISE_VALUE")
    return EDIT_EXERCISE_VALUE


@log_call
async def edit_exercise_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 edit_exercise_command: ВХОД")
    await edit_exercise_start(update, context)
    debug_print(f"📤 edit_exercise_command: ВОЗВРАТ")


@log_call
async def challenge_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 challenge_page_callback: ВХОД")

    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Список челленджей (демо)")
    debug_print(f"📤 challenge_page_callback: ВОЗВРАТ")


@log_call
async def skip_comment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 skip_comment_callback: ВХОД")

    result = await skip_comment_finalize(update, context)
    debug_print(f"📤 skip_comment_callback: ВОЗВРАТ {result}")
    return result


@log_call
async def delete_challenge_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 delete_challenge_start: ВХОД")

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Введите ID челленджа для удаления:")
    else:
        await update.message.reply_text("Введите ID челленджа для удаления:")
    debug_print(f"📤 delete_challenge_start: ВОЗВРАТ WAIT_DELETE_CHALLENGE_ID")
    return WAIT_DELETE_CHALLENGE_ID


@log_call
async def delete_challenge_get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 delete_challenge_get_id: ВХОД")
    debug_print(f"📨 ТЕКСТ: {update.message.text}")

    try:
        challenge_id = int(update.message.text)
    except (ValueError, TypeError):
        await update.message.reply_text("ID должен быть числом.")
        debug_print(f"📤 delete_challenge_get_id: ВОЗВРАТ WAIT_DELETE_CHALLENGE_ID (не число)")
        return WAIT_DELETE_CHALLENGE_ID
    context.user_data['delete_challenge_id'] = challenge_id
    await update.message.reply_text(f"Удалить челлендж {challenge_id}? Отправьте 'ДА'")
    debug_print(f"📤 delete_challenge_get_id: ВОЗВРАТ CONFIRM_DELETE")
    return CONFIRM_DELETE


@log_call
async def confirm_delete_challenge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 confirm_delete_challenge: ВХОД")
    debug_print(f"📨 ТЕКСТ: {update.message.text}")

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
    debug_print(f"📤 confirm_delete_challenge: ВОЗВРАТ END")
    return ConversationHandler.END


@log_call
async def edit_challenge_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 edit_challenge_start: ВХОД")

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Введите ID челленджа для редактирования:")
    else:
        await update.message.reply_text("Введите ID челленджа для редактирования:")
    debug_print(f"📤 edit_challenge_start: ВОЗВРАТ EDIT_CHALLENGE_ID")
    return EDIT_CHALLENGE_ID


@log_call
async def edit_challenge_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 edit_challenge_id_input: ВХОД")
    debug_print(f"📨 ТЕКСТ: {update.message.text}")

    try:
        challenge_id = int(update.message.text)
    except:
        await update.message.reply_text("ID должен быть числом.")
        debug_print(f"📤 edit_challenge_id_input: ВОЗВРАТ EDIT_CHALLENGE_ID (не число)")
        return EDIT_CHALLENGE_ID
    challenge = get_challenge_by_id(challenge_id)
    if not challenge:
        await update.message.reply_text("Челлендж не найден.")
        debug_print(f"📤 edit_challenge_id_input: ВОЗВРАТ END")
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
    debug_print(f"📤 edit_challenge_id_input: ВОЗВРАТ EDIT_CHALLENGE_VALUE")
    return EDIT_CHALLENGE_VALUE


@log_call
async def edit_challenge_value_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 edit_challenge_value_input: ВХОД")

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        if query.data == "cancel_edit_ch":
            await query.edit_message_text("Отменено.")
            debug_print(f"📤 edit_challenge_value_input: ВОЗВРАТ END")
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
            debug_print(f"📤 edit_challenge_value_input: ВОЗВРАТ EDIT_CHALLENGE_VALUE")
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
        debug_print(f"📤 edit_challenge_value_input: ВОЗВРАТ END")
        return ConversationHandler.END
    debug_print(f"📤 edit_challenge_value_input: ВОЗВРАТ EDIT_CHALLENGE_VALUE")
    return EDIT_CHALLENGE_VALUE


@log_call
async def edit_challenge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 edit_challenge_command: ВХОД")
    await edit_challenge_start(update, context)
    debug_print(f"📤 edit_challenge_command: ВОЗВРАТ")


@log_call
async def delete_complex_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 delete_complex_start: ВХОД")

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Введите ID комплекса для удаления:")
    else:
        await update.message.reply_text("Введите ID комплекса для удаления:")
    debug_print(f"📤 delete_complex_start: ВОЗВРАТ WAIT_DELETE_COMPLEX_ID")
    return WAIT_DELETE_COMPLEX_ID


@log_call
async def delete_complex_get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 delete_complex_get_id: ВХОД")
    debug_print(f"📨 ТЕКСТ: {update.message.text}")

    try:
        complex_id = int(update.message.text)
    except (ValueError, TypeError):
        await update.message.reply_text("ID должен быть числом.")
        debug_print(f"📤 delete_complex_get_id: ВОЗВРАТ WAIT_DELETE_COMPLEX_ID (не число)")
        return WAIT_DELETE_COMPLEX_ID
    context.user_data['delete_complex_id'] = complex_id
    await update.message.reply_text(f"Удалить комплекс {complex_id}? Отправьте 'ДА'")
    debug_print(f"📤 delete_complex_get_id: ВОЗВРАТ CONFIRM_DELETE_COMPLEX")
    return CONFIRM_DELETE_COMPLEX


@log_call
async def leave_challenge_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 leave_challenge_callback: ВХОД")

    query = update.callback_query
    await query.answer()
    challenge_id = int(query.data.split('_')[1])
    leave_challenge(update.effective_user.id, challenge_id)
    await query.edit_message_text("✅ Вы вышли из челленджа.")
    debug_print(f"📤 leave_challenge_callback: ВОЗВРАТ")


@log_call
async def cancel_reply_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 cancel_reply_callback: ВХОД")

    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("❌ Отменено.")
    debug_print(f"📤 cancel_reply_callback: ВОЗВРАТ")


@log_call
async def process_reply_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 process_reply_comment: ВХОД")
    # pass
    debug_print(f"📤 process_reply_comment: ВОЗВРАТ")


# ==================== ОБРАБОТЧИК ДИАЛОГА ====================
@log_call
async def catch_all_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 catch_all_text: ВХОД")

    if not update.message or not update.message.text:
        debug_print(f"📤 catch_all_text: ВОЗВРАТ (нет текста)")
        return

    text = update.message.text.strip()

    debug_print(f"📨 ПОЛУЧЕН ТЕКСТ: '{text}'")
    debug_print(f"📦 user_data: {context.user_data}")
    debug_print(f"🏷️ состояние: {context.user_data.get('conversation_state')}")

    if DEBUG_MODE:
        debug_print(
            f"🔥 catch_all_text: ВХОДЯЩЕЕ СООБЩЕНИЕ: '{update.message.text}' (repr: {repr(update.message.text)})")

    # Обработка "Отмена"
    if text == "❌ Отмена":
        from utils import handle_cancel
        result = await handle_cancel(update, context)
        debug_print(f"📤 catch_all_text: ВОЗВРАТ (Отмена)")
        return result

    # Получаем состояние диалога
    state = context.user_data.get('conversation_state')
    if DEBUG_MODE:
        debug_print(f"🔥 catch_all_text: text={text}, state={state}")

    # Если есть активный диалог — обрабатываем его
    if state == 61:  # RESULT
        await submit_result_input(update, context)
        debug_print(f"📤 catch_all_text: ВОЗВРАТ (submit_result_input)")
        return
    elif state == 62:  # VIDEO
        await submit_video_input(update, context)
        debug_print(f"📤 catch_all_text: ВОЗВРАТ (submit_video_input)")
        return
    elif state == 63:  # COMMENT
        await submit_comment_input(update, context)
        debug_print(f"📤 catch_all_text: ВОЗВРАТ (submit_comment_input)")
        return

    if text == "❌ Отмена":
        context.user_data.clear()
        await start(update, context)
        debug_print(f"📤 catch_all_text: ВОЗВРАТ (Отмена через старт)")
        return

    if text == "🐞 Отладка":
        await toggle_debug_button(update, context)
        debug_print(f"📤 catch_all_text: ВОЗВРАТ (Отладка)")
        return

    # Игнорируем служебные сообщения
    if "Тренировка успешно записана" in text or "Спасибо" in text:
        debug_print(f"📤 catch_all_text: ВОЗВРАТ (игнорируем служебное)")
        return

    # Всё остальное — в menu_handler
    await menu_handler(update, context)
    debug_print(f"📤 catch_all_text: ВОЗВРАТ (menu_handler)")


@log_call
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 menu_handler: ВХОД")

    if not update.message or not update.message.text:
        debug_print(f"📤 menu_handler: ВОЗВРАТ (нет текста)")
        return

    text = update.message.text.strip()
    debug_print(f"📨 MENU_HANDLER ТЕКСТ: '{text}'")
    debug_print(f"📦 user_data: {context.user_data}")

    if DEBUG_MODE:
        debug_print(f"🔥 menu_handler: text={text}")

    # Отмена
    if text == "❌ Отмена":
        context.user_data.clear()
        await start(update, context)
        debug_print(f"📤 menu_handler: ВОЗВРАТ (Отмена)")
        return

    # Отладка
    if text == "🐞 Отладка":
        await toggle_debug_button(update, context)
        debug_print(f"📤 menu_handler: ВОЗВРАТ (Отладка)")
        return

    # Рейтинг
    if text == "🏆 Рейтинг":
        await top_command(update, context)
        debug_print(f"📤 menu_handler: ВОЗВРАТ (Рейтинг)")
        return

    # Админ
    if text == "⚙️ Админ":
        if is_admin(update):
            await admin_menu(update, context)
        else:
            await update.message.reply_text("⛔ Нет прав.")
        debug_print(f"📤 menu_handler: ВОЗВРАТ (Админ)")
        return

    # Календарь
    if text == "📅 Календарь":
        await calendar_command(update, context)
        debug_print(f"📤 menu_handler: ВОЗВРАТ (Календарь)")
        return

    # Задать вопрос
    if text == "🤖 Задать вопрос":
        await update.message.reply_text("Напиши свой вопрос, и я постараюсь помочь!")
        debug_print(f"📤 menu_handler: ВОЗВРАТ (Задать вопрос)")
        return

    # Фото
    if text == "📸 Фото":
        await show_menu(update, context)
        debug_print(f"📤 menu_handler: ВОЗВРАТ (Фото)")
        return

    # Спорт
    if text == "🏋️ Спорт" or text == "Спорт":
        context.user_data.clear()
        await sport_menu(update, context)
        debug_print(f"📤 menu_handler: ВОЗВРАТ (Спорт)")
        return ConversationHandler.END

    # Остальные кнопки главного меню
    if "Каталог упражнений" in text:
        await catalog_command(update, context)
    elif "Записать тренировку" in text:
        await workout_start(update, context)
    elif "Моя статистика" in text:
        await mystats_command(update, context)
    elif "Сменить уровень" in text:
        await setlevel_command(update, context)
    elif "Назад" in text:
        await start(update, context)
    else:
        await update.message.reply_text("Я не понимаю эту команду. Воспользуйся меню!")
        debug_print(f"📤 menu_handler: ВОЗВРАТ (неизвестная команда)")
        return ConversationHandler.END

    debug_print(f"📤 menu_handler: ВОЗВРАТ")


# ==================== ОБЩИЕ ФУНКЦИИ ====================
@log_call
async def testchannel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 testchannel_command: ВХОД")
    await send_to_channel(context.bot, "✅ Тест")
    debug_print(f"📤 testchannel_command: ВОЗВРАТ")


@log_call
async def testresult_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 testresult_command: ВХОД")
    if update.message:
        await update.message.reply_text("Тест")
    debug_print(f"📤 testresult_command: ВОЗВРАТ")


@log_call
async def join_challenge_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 join_challenge_callback: ВХОД")

    query = update.callback_query
    await query.answer()
    data = query.data
    logger.debug(f"🔹 join_challenge_callback: {data}")
    challenge_id = int(data.split('_')[2])
    await query.edit_message_text(f"Вы присоединились к челленджу #{challenge_id}")
    debug_print(f"📤 join_challenge_callback: ВОЗВРАТ")


@log_call
async def do_exercise_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    debug_print(f"🔥 do_exercise_callback: ВХОД")
    debug_print(f"📨 ПОЛУЧЕН CALLBACK: {data}")
    debug_print(f"📦 user_data: {context.user_data}")
    debug_print(f"🏷️ состояние: {context.user_data.get('conversation_state')}")

    if DEBUG_MODE:
        debug_print(f"🔥 do_exercise_callback: data={data}")

    if data == "cancel_catalog":
        await query.edit_message_text("❌ Отменено.")
        keyboard = [
            ["🏋️ Спорт", "📸 Фото"],
            ["🤖 Задать вопрос", "❌ Отмена"],
            ["🏆 Рейтинг", "⚙️ Админ"],
            ["📅 Календарь", "🐞 Отладка"],
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await query.message.reply_text(WELCOME_TEXT, reply_markup=reply_markup, parse_mode='Markdown')
        debug_print(f"📤 do_exercise_callback: ВОЗВРАТ (cancel_catalog)")
        return

    exercise_id = int(data.split('_')[2])
    context.user_data['pending_exercise'] = exercise_id
    context.user_data['submit_entity_type'] = 'exercise'
    context.user_data['submit_entity_id'] = exercise_id
    state = await workout_start(update, context)
    if DEBUG_MODE:
        debug_print(f"🔥 do_exercise_callback: workout_start вернул {state}")
    if state:
        context.user_data['conversation_state'] = state

    debug_print(f"📤 do_exercise_callback: ВОЗВРАТ")


@log_call
async def catalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 catalog_command: ВХОД")
    await send_catalog_to_message(update, context)
    debug_print(f"📤 catalog_command: ВОЗВРАТ")


@log_call
async def do_complex_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    debug_print(f"🔥 do_complex_callback: ВХОД")
    debug_print(f"📨 ПОЛУЧЕН CALLBACK: {data}")
    debug_print(f"📦 user_data: {context.user_data}")
    debug_print(f"🏷️ состояние: {context.user_data.get('conversation_state')}")

    if DEBUG_MODE:
        debug_print(f"🔥 do_complex_callback: data={data}")
    complex_id = int(data.split('_')[2])
    context.user_data['pending_complex'] = complex_id
    context.user_data['submit_entity_type'] = 'complex'
    context.user_data['submit_entity_id'] = complex_id
    state = await workout_start(update, context)
    if state:
        context.user_data['conversation_state'] = state
    debug_print(f"📤 do_complex_callback: ВОЗВРАТ")


# ==================== СЕРВЕР ====================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

# ==================== КОМАНДЫ ДЛЯ УПРАЖНЕНИЙ ====================
@log_call
async def add_exercise_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 add_exercise_command: ВХОД")

    if not is_admin(update):
        await update.message.reply_text("⛔ Нет прав.")
        debug_print(f"📤 add_exercise_command: ВОЗВРАТ (нет прав)")
        return
    full_text = update.message.text
    if ' ' not in full_text:
        await update.message.reply_text(
            "Использование: /addexercise <название> <reps|time> <описание> <баллы> [неделя] [difficulty]")
        debug_print(f"📤 add_exercise_command: ВОЗВРАТ (недостаточно аргументов)")
        return
    args_part = full_text.split(maxsplit=1)[1]
    try:
        args = shlex.split(args_part)
        if len(args) < 4:
            await update.message.reply_text("❌ Нужно минимум 4 аргумента.")
            debug_print(f"📤 add_exercise_command: ВОЗВРАТ (мало аргументов)")
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

    debug_print(f"📤 add_exercise_command: ВОЗВРАТ")


@log_call
async def list_exercises_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 list_exercises_command: ВХОД")

    if not is_admin(update):
        debug_print(f"📤 list_exercises_command: ВОЗВРАТ (нет прав)")
        return
    page = 1
    if context.args and context.args[0].isdigit():
        page = int(context.args[0])
    all_exercises = get_all_exercises()
    if not all_exercises:
        await update.message.reply_text("Упражнений пока нет.")
        debug_print(f"📤 list_exercises_command: ВОЗВРАТ (нет упражнений)")
        return
    exercises, keyboard = paginate(all_exercises, page, per_page=5, prefix='ex_page')
    text = "📋 **Список упражнений:**\n\n"
    for ex in exercises:
        name = ex[1].replace('_', r'\_').replace('*', r'\*').replace('[', r'\[').replace(']', r'\]')
        text += f"🔹 ID: {ex[0]} — {name} ({ex[5]})\n"
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    debug_print(f"📤 list_exercises_command: ВОЗВРАТ")


@log_call
async def load_exercises_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 load_exercises_command: ВХОД")

    if not is_admin(update):
        debug_print(f"📤 load_exercises_command: ВОЗВРАТ (нет прав)")
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
    debug_print(f"📤 load_exercises_command: ВОЗВРАТ")


@log_call
async def myhistory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_print(f"🔥 myhistory_command: ВХОД")

    user_id = update.effective_user.id
    limit = 20
    if context.args and context.args[0].isdigit():
        limit = int(context.args[0])
        if limit > 50:
            limit = 50
    workouts = get_user_workouts(user_id, limit)
    if not workouts:
        await update.message.reply_text("Нет тренировок.")
        debug_print(f"📤 myhistory_command: ВОЗВРАТ (нет тренировок)")
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
    debug_print(f"📤 myhistory_command: ВОЗВРАТ")

# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================
@log_call
def main():
    global DEBUG_MODE
    logger.info("🚀 MAIN: запуск бота")
    debug_print(f"🔥 main: ВХОД")

    if not TOKEN:
        raise ValueError("Нет TELEGRAM_BOT_TOKEN!")

    # Загружаем сохранённое состояние дебага из БД
    saved_debug = get_setting("debug_mode")
    if saved_debug is not None:
        DEBUG_MODE = saved_debug.lower() == 'true'
        logger.info(f"📂 Загружен DEBUG_MODE из БД: {DEBUG_MODE}")

    app = Application.builder().token(TOKEN).build()

    # Глобальный перехватчик для дебага (самый первый!)
    # КОММЕНТИРУЕМ ЭТИ СТРОКИ:
    # app.add_handler(MessageHandler(filters.ALL, debug_global_handler), group=-1)
    # app.add_handler(CallbackQueryHandler(debug_global_handler, pattern='.*'), group=-1)
    #
    # async def log_all_updates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #     debug_print(f"🌍 ГЛОБАЛЬНО: {update}")
    #     return
    #
    # app.add_handler(MessageHandler(filters.ALL, log_all_updates), group=-1)

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", show_menu))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("config", config_command))
    app.add_handler(CommandHandler("toggle_debug", toggle_debug_command))
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
    # /skip используется в submit-потоке (комментарий к видео) при отсутствии ConversationHandler
    app.add_handler(CommandHandler("skip", submit_comment_skip))
    app.add_handler(CommandHandler("testresult", testresult_command))

    # Callback handlers для упражнений и комплексов
    app.add_handler(CallbackQueryHandler(do_exercise_callback, pattern='^do_exercise_'))
    app.add_handler(CallbackQueryHandler(do_exercise_callback, pattern='^complex_ex_'))  # Добавлен для комплексов
    app.add_handler(CallbackQueryHandler(do_complex_callback, pattern='^do_complex_'))
    app.add_handler(
        CallbackQueryHandler(toggle_debug_callback_handler, pattern='^(toggle_debug_callback|cancel_debug)$'))

    # ConversationHandlers
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler('editcomplex', edit_complex_command)],
        states={EDIT_COMPLEX_ID: [CallbackQueryHandler(edit_complex_field_callback, pattern='^cfield_|cancel_edit')],
                EDIT_COMPLEX_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_complex_value_input)]},
        fallbacks=[CommandHandler('cancel', workout_cancel)],
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler('editexercise', edit_exercise_command),
                      CallbackQueryHandler(edit_exercise_start, pattern='^admin_ex_edit$')],
        states={EDIT_EXERCISE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_exercise_id_input)],
                EDIT_EXERCISE_VALUE: [
                    CallbackQueryHandler(edit_exercise_value_input, pattern='^exfield_|cancel_edit_ex'),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, edit_exercise_value_input)]},
        fallbacks=[CommandHandler('cancel', workout_cancel)],
    ))

    app.add_handler(ConversationHandler(
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

    app.add_handler(ConversationHandler(
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
        states={
            EXERCISE: [CallbackQueryHandler(exercise_choice, pattern='^ex_|^cancel$')],
            RESULT: [MessageHandler(filters.TEXT & ~filters.COMMAND, result_input)],
            VIDEO: [MessageHandler(filters.TEXT & ~filters.COMMAND, video_input)],
            COMMENT: [
                CallbackQueryHandler(skip_comment_callback, pattern='^skip_comment$'),
                MessageHandler(filters.TEXT, comment_handler),
            ],
            COMPLEX_EXERCISE: [
                CallbackQueryHandler(complex_exercise_choice, pattern='^complex_ex_'),
            ]},
        fallbacks=[
            CommandHandler('cancel', workout_cancel),
            #MessageHandler(filters.Regex('^❌ Отмена$'), workout_cancel),
            MessageHandler(filters.Regex('^(🏋️ Спорт|Спорт)$'), menu_handler),
        ],
    ))

    app.add_handler(ConversationHandler(
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

    app.add_handler(ConversationHandler(
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

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler('delexercise', delete_exercise_command),
                      CallbackQueryHandler(delete_exercise_start, pattern='^admin_ex_delete$')],
        states={WAIT_DELETE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_exercise_get_id)],
                CONFIRM_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_delete_exercise)]},
        fallbacks=[CommandHandler('cancel', workout_cancel)],
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler('deletecomplex', delete_complex_command),
                      CallbackQueryHandler(delete_complex_start, pattern='^admin_cx_delete$')],
        states={WAIT_DELETE_COMPLEX_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_complex_get_id)],
                CONFIRM_DELETE_COMPLEX: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_delete_complex)]},
        fallbacks=[CommandHandler('cancel', workout_cancel)],
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(delete_challenge_start, pattern='^admin_ch_delete$')],
        states={WAIT_DELETE_CHALLENGE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_challenge_get_id)],
                CONFIRM_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_delete_challenge)]},
        fallbacks=[CommandHandler('cancel', workout_cancel)],
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler('editchallenge', edit_challenge_command),
                      CallbackQueryHandler(edit_challenge_start, pattern='^admin_ch_edit$')],
        states={EDIT_CHALLENGE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_challenge_id_input)],
                EDIT_CHALLENGE_VALUE: [
                    CallbackQueryHandler(edit_challenge_value_input, pattern='^chfield_|cancel_edit_ch'),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, edit_challenge_value_input)]},
        fallbacks=[CommandHandler('cancel', workout_cancel)],
    ))

    # В bot.py, где-то после всех импортов, но перед регистрацией обработчиков

    async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик для кнопки Отмена"""
        query = update.callback_query
        await query.answer()

        print(f"🔥🔥🔥 CANCEL_CALLBACK: ОТМЕНА СРАБОТАЛА!")

        # Создаем спортивное меню
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton

        keyboard = [
            [InlineKeyboardButton("📋 Все упражнения", callback_data='sport_catalog')],
            [InlineKeyboardButton("📦 Комплексы", callback_data='sport_complexes')],
            [InlineKeyboardButton("🏆 Челленджи", callback_data='sport_challenges')],
            [InlineKeyboardButton("🔥 Тренировка недели", callback_data='sport_wod')],
            [InlineKeyboardButton("📊 Статистика", callback_data='sport_mystats')],
            [InlineKeyboardButton("🔄 Уровень", callback_data='sport_setlevel')],
            [InlineKeyboardButton("◀️ Назад", callback_data='back_to_main')]
        ]

        await query.edit_message_text(
            "🏋️ Спорт:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        context.user_data.clear()

    # Callback handlers
    # ✅ ОБРАБОТЧИК ОТМЕНЫ (ДОЛЖЕН БЫТЬ ПЕРВЫМ!)
    app.add_handler(CallbackQueryHandler(cancel_callback, pattern='^cancel$'))

    # Админские обработчики
    app.add_handler(CallbackQueryHandler(admin_callback, pattern='^admin_'))
    app.add_handler(CallbackQueryHandler(submit_complex_callback, pattern='^submit_complex_'))
    app.add_handler(CallbackQueryHandler(submit_exercise_callback, pattern='^submit_exercise_'))
    app.add_handler(CallbackQueryHandler(submit_challenge_callback, pattern='^submit_challenge_'))

    # Обработчики пропуска и фото
    app.add_handler(CallbackQueryHandler(skip_comment_callback, pattern='^skip_comment$'))
    app.add_handler(CallbackQueryHandler(button_handler,
                                         pattern='^(sketch|anime|sepia|hardrock|pixel|neon|oil|watercolor|cartoon)$'))

    # Настройки и уровень
    app.add_handler(CallbackQueryHandler(config_callback_handler, pattern="^toggle_"))
    app.add_handler(CallbackQueryHandler(setlevel_callback, pattern='^setlevel_'))

    # Тренировка недели (специфичный обработчик)
    app.add_handler(CallbackQueryHandler(workout_start, pattern='^sport_wod$'))

    # Публичная статистика (Топы и рекорды)
    app.add_handler(CallbackQueryHandler(public_stats_menu, pattern='^public_stats$'))
    app.add_handler(CallbackQueryHandler(public_top_users, pattern='^public_stats_top$'))
    app.add_handler(CallbackQueryHandler(public_top_challenges, pattern='^public_stats_challenges$'))
    app.add_handler(CallbackQueryHandler(public_join_challenge, pattern='^public_join_challenge_'))
    app.add_handler(CallbackQueryHandler(public_my_stats, pattern='^public_stats_my$'))
    app.add_handler(CallbackQueryHandler(back_to_public_stats, pattern='^back_to_public_stats$'))
    app.add_handler(CallbackQueryHandler(sport_menu, pattern='^back_to_sport$'))

    # Основные обработчики спортивного меню
    app.add_handler(CallbackQueryHandler(sport_callback_handler, pattern='^sport_|^back_to_main$'))
    app.add_handler(CallbackQueryHandler(help_callback, pattern='^help_'))

    # Упражнения и статистика
    app.add_handler(CallbackQueryHandler(exercise_callback, pattern='^ex_'))
    app.add_handler(CallbackQueryHandler(record_from_catalog_callback, pattern='^record_'))
    app.add_handler(CallbackQueryHandler(stats_period_callback, pattern='^stats_'))
    app.add_handler(CallbackQueryHandler(top_league_callback, pattern='^top_league_'))

    # Пагинация
    app.add_handler(CallbackQueryHandler(complex_page_callback, pattern='^complex_page_'))
    app.add_handler(CallbackQueryHandler(exercise_page_callback, pattern='^ex_page_'))
    app.add_handler(CallbackQueryHandler(challenge_page_callback, pattern='^challenge_page_'))

    # Отмена и выход
    app.add_handler(CallbackQueryHandler(cancel_submit_callback, pattern='^cancel_submit$'))
    app.add_handler(CallbackQueryHandler(leave_challenge_callback, pattern='^leave_'))

    # Календарь и челленджи
    app.add_handler(CallbackQueryHandler(calendar_callback, pattern="^cal_"))
    app.add_handler(CallbackQueryHandler(join_challenge_callback, pattern='^join_challenge_'))

    # Message handlers
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, catch_all_text))

    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
        logger.error("Exception while handling an update", exc_info=context.error)

    app.add_error_handler(error_handler)

    init_db()
    # fix_scoreboard_duplicates()  # <--- ДОБАВЬ ЭТУ СТРОКУ
    backup_database()

    # Запуск healthcheck сервера
    Thread(
        target=lambda: HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 10000))), HealthCheckHandler).serve_forever(),
        daemon=True).start()

    app.run_polling()
    debug_print(f"📤 main: ВОЗВРАТ")

    # Простой HTTP-сервер для UptimeRobot
    from aiohttp import web

    async def health_check(request):
        return web.Response(text="OK", status=200)

    async def start_health_server():
        app = web.Application()
        app.router.add_get('/health', health_check)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', 8080)
        await site.start()
        print("✅ Health check server started on port 8080")

    # Запускаем health-сервер отдельно
    import asyncio
    asyncio.create_task(start_health_server())

# ========== HEALTH CHECK ДЛЯ RENDER ==========
from aiohttp import web

async def health_handler(request):
    return web.Response(text="OK")

app_web = web.Application()
app_web.router.add_get('/health', health_handler)

def run_health_server():
    import asyncio
    import os
    port = int(os.environ.get('PORT', 8080))
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    web.run_app(app_web, host='0.0.0.0', port=port)

import threading
threading.Thread(target=run_health_server, daemon=True).start()
# ============================================


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception("Критическая ошибка: %s", e)