from telegram import Update, ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import WELCOME_TEXT

# Добавляем отладочные утилиты
from debug_utils import debug_print, log_call, log_user_data, DEBUG_MODE


@log_call
async def handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Логируем пользовательские данные
    log_user_data(update, context, "handle_cancel")
    debug_print(f"🔥 utils: handle_cancel: ВЫЗВАНА")
    debug_print(f"📥 Аргументы: update={update}, context={context}")
    debug_print(f"🔥 utils: handle_cancel: update={update}")
    debug_print(
        f"🔥 utils: handle_cancel: context.user_data ДО ОЧИСТКИ = {context.user_data if context else 'Нет context'}")

    # Очищаем данные текущего диалога
    debug_print(f"🔥 utils: handle_cancel: очистка user_data")
    context.user_data.clear()

    # Убираем Reply-кнопку "❌ Отмена" из-под поля ввода
    debug_print(f"🔥 utils: handle_cancel: отправка сообщения 'Действие отменено'")
    debug_print(f"🔥 utils: handle_cancel: удаление Reply-клавиатуры")
    await update.message.reply_text("Действие отменено.", reply_markup=ReplyKeyboardRemove())

    # Восстанавливаем главное меню (Reply-панель внизу)
    debug_print(f"🔥 utils: handle_cancel: создание главного меню (ReplyKeyboardMarkup)")
    keyboard = [
        ["🏋️ Спорт", "📸 Фото"],
        ["🤖 Задать вопрос", "❌ Отмена"],
        ["🏆 Рейтинг", "⚙️ Админ"],
        ["📅 Календарь"],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    debug_print(f"🔥 utils: handle_cancel: отправка главного меню с WELCOME_TEXT")
    await update.message.reply_text(WELCOME_TEXT, reply_markup=reply_markup, parse_mode='Markdown')

    # Показываем спортивное меню (Inline-кнопки)
    debug_print(f"🔥 utils: handle_cancel: вызов sport_menu")
    from bot import sport_menu
    await sport_menu(update, context)

    # Завершаем ConversationHandler
    debug_print(f"🔥 utils: handle_cancel: возврат ConversationHandler.END")
    return_value = ConversationHandler.END
    debug_print(f"🔥 utils: handle_cancel: ВОЗВРАТ {return_value}")
    return return_value


# Пример дополнительных функций с отладкой (если они есть в вашем файле)

@log_call
def format_date(date_obj):
    debug_print(f"🔥 utils: format_date: ВЫЗВАНА")
    debug_print(f"📥 Аргументы: date_obj={date_obj}")

    try:
        result = date_obj.strftime("%d.%m.%Y")
        debug_print(f"🔥 utils: format_date: результат={result}")
        debug_print(f"🔥 utils: format_date: ВОЗВРАТ {result}")
        return result
    except Exception as e:
        debug_print(f"🔥 utils: ОШИБКА: {e}")
        import traceback
        debug_print(f"🔥 utils: traceback: {traceback.format_exc()}")
        return None


@log_call
def validate_input(user_input, expected_type=str):
    debug_print(f"🔥 utils: validate_input: ВЫЗВАНА")
    debug_print(f"📥 Аргументы: user_input={user_input}, expected_type={expected_type}")

    try:
        if expected_type == int:
            result = int(user_input)
        elif expected_type == float:
            result = float(user_input)
        else:
            result = str(user_input)

        debug_print(f"🔥 utils: validate_input: результат={result}")
        debug_print(f"🔥 utils: validate_input: ВОЗВРАТ {result}")
        return result
    except ValueError as e:
        debug_print(f"🔥 utils: ОШИБКА: {e}")
        import traceback
        debug_print(f"🔥 utils: traceback: {traceback.format_exc()}")
        return None
    except Exception as e:
        debug_print(f"🔥 utils: ОШИБКА: {e}")
        import traceback
        debug_print(f"🔥 utils: traceback: {traceback.format_exc()}")
        return None


@log_call
async def some_other_function(update: Update, context: ContextTypes.DEFAULT_TYPE, param=None):
    log_user_data(update, context, "some_other_function")
    debug_print(f"🔥 utils: some_other_function: ВЫЗВАНА")
    debug_print(f"📥 Аргументы: update={update}, context={context}, param={param}")

    try:
        # Какая-то логика функции
        debug_print(f"🔥 utils: some_other_function: выполнение основной логики")
        result = f"Обработано с параметром {param}"

        debug_print(f"🔥 utils: some_other_function: результат={result}")
        debug_print(f"🔥 utils: some_other_function: ВОЗВРАТ {result}")
        return result
    except Exception as e:
        debug_print(f"🔥 utils: ОШИБКА: {e}")
        import traceback
        debug_print(f"🔥 utils: traceback: {traceback.format_exc()}")
        return None


# Если есть обработчики ошибок
@log_call
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_data(update, context, "error_handler")
    debug_print(f"🔥 utils: error_handler: ВЫЗВАНА")
    debug_print(f"📥 Аргументы: update={update}, context={context}")

    try:
        debug_print(f"🔥 utils: error_handler: обработка ошибки")
        error = context.error
        debug_print(f"🔥 utils: error_handler: ошибка = {error}")

        # Логика обработки ошибки
        if update and update.message:
            await update.message.reply_text("Произошла ошибка. Пожалуйста, попробуйте позже.")

        debug_print(f"🔥 utils: error_handler: ВОЗВРАТ None")
        return None
    except Exception as e:
        debug_print(f"🔥 utils: ОШИБКА в error_handler: {e}")
        import traceback
        debug_print(f"🔥 utils: traceback: {traceback.format_exc()}")
        return None