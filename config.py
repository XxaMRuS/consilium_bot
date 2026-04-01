# config.py - настройки оформления бота

# Эмодзи для разных разделов
EMOJI = {
    "sport": "🏋️",
    "photo": "📸",
    "ai": "🤖",
    "rating": "🏆",
    "admin": "⚙️",
    "stats": "📊",
    "welcome": "🔥",
    "error": "❌",
    "success": "✅",
    "warning": "⚠️",
    "list": "📋",
    "add": "➕",
    "edit": "✏️",
    "delete": "🗑️",
    "back": "◀️",
    "cancel": "❌",
    "calendar": "📅",
    "question": "🤖",
}

# Разделитель
SEPARATOR = "━━━━━━━━━━━━━━━━━━━━━"

# Тексты сообщений
WELCOME_TEXT = (
    f"{EMOJI['welcome']} **Привет! Я твой фитнес-помощник и AI-консилиум.**\n\n"
    "Выбери, что хочешь сделать:"
)

HELP_SECTION = {
    "sport": f"{EMOJI['sport']} **Спорт**\n"
             "/wod — записать тренировку\n"
             "/catalog — каталог упражнений\n"
             "/mystats — моя статистика\n"
             "/setlevel — сменить уровень (новичок/профи)",
    "photo": f"{EMOJI['photo']} **Фото**\n"
             "/menu — выбрать стиль и отправить фото\n"
             "Доступны стили: карандаш, аниме, сепия, хард-рок, пиксель, неон, масло, акварель, мультяшный",
    "stats": f"{EMOJI['stats']} **Статистика**\n"
             "/mystats [day|week|month|year] — твоя статистика\n"
             "/top [day|week|month|year] [beginner|pro] — таблица лидеров",
    "rating": f"{EMOJI['rating']} **Рейтинг**\n"
              "/top — топ за всё время в твоей лиге\n"
              "Можно добавить период (day, week, month, year) и лигу (beginner, pro)",
    "admin": f"{EMOJI['admin']} **Админ**\n"
             "/config — настройка AI\n"
             "/addexercise — добавить упражнение\n"
             "/delexercise — удалить упражнение\n"
             "/listexercises — список упражнений\n"
             "/load_exercises — загрузить из JSON",
}

# Форматирование сообщений
def format_success(text: str) -> str:
    return f"{EMOJI['success']} {text}"

def format_error(text: str) -> str:
    return f"{EMOJI['error']} **Ошибка:** {text}"

def format_warning(text: str) -> str:
    return f"{EMOJI['warning']} **Внимание:** {text}"

# ID канала для уведомлений
NOTIFICATION_CHANNEL_ID = -1003634185270