import logging
import inspect
import traceback
from functools import wraps
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

# ==================== НАСТРОЙКА ====================
DEBUG_MODE = True
LOG_FILE = "debug.log"

# Логгер
debug_logger = logging.getLogger("debug")
debug_logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
debug_logger.addHandler(file_handler)


# ==================== ОСНОВНЫЕ ФУНКЦИИ ====================
def debug_print(*args, **kwargs):
    """Печать в консоль и файл при DEBUG_MODE"""
    if DEBUG_MODE:
        msg = " ".join(str(a) for a in args)
        print(msg)
        debug_logger.debug(msg)


def log_call(func):
    """Декоратор для логирования вызовов ЛЮБОЙ функции"""

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        if not DEBUG_MODE:
            return await func(*args, **kwargs)

        func_name = func.__name__
        debug_print(f"\n{'=' * 60}")
        debug_print(f"🔵 ВЫЗОВ ФУНКЦИИ: {func_name}")
        debug_print(f"🕐 Время: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")

        # Логируем аргументы
        for i, arg in enumerate(args):
            if hasattr(arg, 'callback_query') and arg.callback_query:
                debug_print(f"   📨 callback_data: {arg.callback_query.data}")
                debug_print(f"   👤 user_id: {arg.callback_query.from_user.id}")
            if hasattr(arg, 'message') and arg.message:
                if arg.message.text:
                    debug_print(f"   💬 текст: {arg.message.text[:200]}")
                if arg.message.chat:
                    debug_print(f"   💬 chat_id: {arg.message.chat.id}")

        # Логируем context.user_data
        for arg in args:
            if hasattr(arg, 'user_data'):
                debug_print(f"   📦 user_data: {arg.user_data}")
                debug_print(f"   🏷️ conversation_state: {arg.user_data.get('conversation_state')}")
            if hasattr(arg, 'context') and hasattr(arg.context, 'user_data'):
                debug_print(f"   📦 user_data: {arg.context.user_data}")
                debug_print(f"   🏷️ conversation_state: {arg.context.user_data.get('conversation_state')}")

        try:
            result = await func(*args, **kwargs)
            debug_print(f"🔴 ВОЗВРАТ: {func_name} -> {result}")
            debug_print(f"{'=' * 60}\n")
            return result
        except Exception as e:
            debug_print(f"💥 ОШИБКА в {func_name}: {e}")
            debug_print(traceback.format_exc())
            debug_print(f"{'=' * 60}\n")
            raise

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        if not DEBUG_MODE:
            return func(*args, **kwargs)

        func_name = func.__name__
        debug_print(f"\n{'=' * 60}")
        debug_print(f"🔵 ВЫЗОВ ФУНКЦИИ: {func_name}")
        debug_print(f"🕐 Время: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")

        try:
            result = func(*args, **kwargs)
            debug_print(f"🔴 ВОЗВРАТ: {func_name} -> {result}")
            debug_print(f"{'=' * 60}\n")
            return result
        except Exception as e:
            debug_print(f"💥 ОШИБКА в {func_name}: {e}")
            debug_print(traceback.format_exc())
            debug_print(f"{'=' * 60}\n")
            raise

    return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper


def log_user_data(update: Update, context: ContextTypes.DEFAULT_TYPE, tag: str = ""):
    """Логирование состояния user_data"""
    if not DEBUG_MODE:
        return
    prefix = f"[{tag}] " if tag else ""
    if context and hasattr(context, 'user_data'):
        debug_print(f"📊 {prefix}user_data: {context.user_data}")
        debug_print(f"   conversation_state: {context.user_data.get('conversation_state')}")
    if update and update.callback_query:
        debug_print(f"   callback_data: {update.callback_query.data}")
    if update and update.message and update.message.text:
        debug_print(f"   message_text: {update.message.text[:100]}")


def log_state_change(context: ContextTypes.DEFAULT_TYPE, old_state, new_state):
    """Логирование смены состояния диалога"""
    if DEBUG_MODE:
        debug_print(f"🔄 СМЕНА СОСТОЯНИЯ: {old_state} -> {new_state}")
        debug_print(f"   user_data: {context.user_data}")


def log_callback(data: str, user_id: int, user_data: dict):
    """Логирование callback-запроса"""
    if DEBUG_MODE:
        debug_print(f"📨 CALLBACK: data={data}, user_id={user_id}")
        debug_print(f"   user_data: {user_data}")


def log_message(text: str, user_id: int, state: any):
    """Логирование текстового сообщения"""
    if DEBUG_MODE:
        debug_print(f"💬 СООБЩЕНИЕ: '{text[:100]}', user_id={user_id}, state={state}")