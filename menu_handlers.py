import asyncio
import logging
import traceback
from datetime import datetime
from functools import wraps
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

# ==================== ДЕБАГ-РЕЖИМ ====================
from debug_utils import debug_print, log_call, log_user_data, DEBUG_MODE

# ==================== НАСТРОЙКА ЛОГИРОВАНИЯ ====================
logger = logging.getLogger(__name__)


# ==================== ОСНОВНЫЕ ФУНКЦИИ ====================
@log_call
async def sport_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_data(update, context, "sport_menu")
    debug_print(f"🔥 menu_handlers: sport_menu: ВЫЗВАНА")
    debug_print(f"📥 Аргументы: update={update}, context={context}")
    debug_print(f"🔥 menu_handlers: sport_menu: user_data={context.user_data if context else 'Нет context'}")

    try:
        debug_print(f"🔥 menu_handlers: sport_menu: создание Inline-клавиатуры")

        keyboard = [
            [InlineKeyboardButton("📋 Все упражнения", callback_data='sport_catalog')],
            [InlineKeyboardButton("📦 Комплексы", callback_data='sport_complexes')],
            [InlineKeyboardButton("🏆 Челленджи", callback_data='sport_challenges')],
            [InlineKeyboardButton("🔥 Тренировка недели", callback_data='sport_wod')],
            [InlineKeyboardButton("📊 Статистика", callback_data='sport_mystats')],
            [InlineKeyboardButton("🏆 Топы и рекорды", callback_data='public_stats')],  # ← НОВАЯ КНОПКА
            [InlineKeyboardButton("🔄 Уровень", callback_data='sport_setlevel')],
            [InlineKeyboardButton("◀️ Назад", callback_data='back_to_main')]
        ]

        debug_print(f"🔥 menu_handlers: sport_menu: отправка сообщения с клавиатурой")

        # ИСПРАВЛЕНО: используем anchor (message или callback_query.message)
        anchor = update.message if update.message else update.callback_query.message
        await anchor.reply_text("🏋️ Спорт:", reply_markup=InlineKeyboardMarkup(keyboard))

        debug_print(f"🔥 menu_handlers: sport_menu: ВОЗВРАТ")
        return

    except Exception as e:
        debug_print(f"🔥 menu_handlers: ОШИБКА в sport_menu: {e}")
        debug_print(f"🔥 menu_handlers: traceback: {traceback.format_exc()}")
        raise


@log_call
def main_menu_keyboard():
    log_user_data(None, None, "main_menu_keyboard")
    debug_print(f"🔥 menu_handlers: main_menu_keyboard: ВЫЗВАНА")
    debug_print(f"📥 Аргументы: нет аргументов")
    debug_print(f"🔥 menu_handlers: main_menu_keyboard: создание клавиатуры")

    try:
        keyboard = [
            [InlineKeyboardButton("🏋️ Записать тренировку", callback_data="workout")],
            [InlineKeyboardButton("📊 Моя статистика", callback_data="mystats")],
            [InlineKeyboardButton("🏆 Таблица лидеров", callback_data="top")],
            [InlineKeyboardButton("📅 Календарь активности", callback_data="calendar")],
            [InlineKeyboardButton("❓ Помощь", callback_data="help")],
        ]

        debug_print(
            f"🔥 menu_handlers: main_menu_keyboard: кнопки: Спорт, Фото, Задать вопрос, Отмена, Рейтинг, Админ, Календарь")

        result = InlineKeyboardMarkup(keyboard)

        debug_print(f"🔥 menu_handlers: main_menu_keyboard: ВОЗВРАТ {result}")
        debug_print(f"🔥 menu_handlers: main_menu_keyboard: ВОЗВРАТ клавиатуры")

        return result

    except Exception as e:
        debug_print(f"🔥 menu_handlers: ОШИБКА в main_menu_keyboard: {e}")
        debug_print(f"🔥 menu_handlers: traceback: {traceback.format_exc()}")
        raise

# ==================== ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ (если есть) ====================
# Раскомментируй и добавь отладку для других функций по аналогии

# @log_call
# async def admin_menu_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     log_user_data(update, context, "admin_menu_keyboard")
#     debug_print(f"🔥 menu_handlers: admin_menu_keyboard: ВЫЗВАНА")
#     debug_print(f"📥 Аргументы: update={update}, context={context}")
#     try:
#         debug_print(f"🔥 menu_handlers: admin_menu_keyboard: создание клавиатуры")
#         keyboard = [
#             [InlineKeyboardButton("📊 Статистика бота", callback_data="admin_stats")],
#             [InlineKeyboardButton("👥 Пользователи", callback_data="admin_users")],
#             [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
#         ]
#         debug_print(f"🔥 menu_handlers: admin_menu_keyboard: кнопки: Статистика бота, Пользователи, Назад")
#         result = InlineKeyboardMarkup(keyboard)
#         debug_print(f"🔥 menu_handlers: admin_menu_keyboard: ВОЗВРАТ {result}")
#         return result
#     except Exception as e:
#         debug_print(f"🔥 menu_handlers: ОШИБКА в admin_menu_keyboard: {e}")
#         debug_print(f"🔥 menu_handlers: traceback: {traceback.format_exc()}")
#         raise

# @log_call
# async def back_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     log_user_data(update, context, "back_menu")
#     debug_print(f"🔥 menu_handlers: back_menu: ВЫЗВАНА")
#     debug_print(f"📥 Аргументы: update={update}, context={context}")
#     try:
#         debug_print(f"🔥 menu_handlers: back_menu: возврат в главное меню")
#         await update.message.reply_text("Главное меню:", reply_markup=main_menu_keyboard())
#         debug_print(f"🔥 menu_handlers: back_menu: ВОЗВРАТ")
#         return
#     except Exception as e:
#         debug_print(f"🔥 menu_handlers: ОШИБКА в back_menu: {e}")
#         debug_print(f"🔥 menu_handlers: traceback: {traceback.format_exc()}")
#         raise