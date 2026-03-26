from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🏋️ Записать тренировку", callback_data="workout")],
        [InlineKeyboardButton("📊 Моя статистика", callback_data="mystats")],
        [InlineKeyboardButton("🏆 Таблица лидеров", callback_data="top")],
        [InlineKeyboardButton("📅 Календарь активности", callback_data="calendar")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")],
    ]
    return InlineKeyboardMarkup(keyboard)