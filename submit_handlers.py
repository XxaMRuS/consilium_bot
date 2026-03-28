import logging
import re
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import DB_NAME, get_complex_by_id

# Константы состояний
AWAIT_SUBMIT_RESULT = 60
AWAIT_SUBMIT_VIDEO = 61
AWAIT_SUBMIT_COMMENT = 62

logger = logging.getLogger(__name__)


async def submit_complex_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатия кнопки 'Сдать результат' в канале."""
    query = update.callback_query
    await query.answer()

    complex_id = int(query.data.split('_')[2])

    context.user_data['submit_entity_type'] = 'complex'
    context.user_data['submit_entity_id'] = complex_id
    context.user_data['submit_channel_post_id'] = query.message.message_id
    context.user_data['submit_channel_id'] = query.message.chat_id
    context.user_data['conversation_state'] = AWAIT_SUBMIT_RESULT

    await update.effective_user.send_message(
        "Введите результат:\n"
        "- если это повторения, просто число (например, 10)\n"
        "- если время, в формате ММ:СС (например, 05:30)"
    )



async def submit_result_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода результата."""

    if context.user_data.get('conversation_state') != AWAIT_SUBMIT_RESULT:

    user_input = update.message.text.strip()
    entity_type = context.user_data.get('submit_entity_type')
    entity_id = context.user_data.get('submit_entity_id')

    if entity_type != 'complex':
        await update.message.reply_text("Пока поддерживаются только комплексы.")
        context.user_data.pop('conversation_state', None)
        return

    complex_data = get_complex_by_id(entity_id)
    if not complex_data:
        await update.message.reply_text("Комплекс не найден. Попробуйте позже.")
        context.user_data.pop('conversation_state', None)
        return

    metric_type = complex_data[3]

    if metric_type == 'for_reps':
        if not user_input.isdigit():
            await update.message.reply_text("Введите целое число повторений.")
            return
        context.user_data['submit_result'] = user_input
    else:
        if not re.match(r'^\d{1,2}:\d{2}$', user_input):
            await update.message.reply_text("Введите время в формате ММ:СС, например 05:30.")
            return
        context.user_data['submit_result'] = user_input

    context.user_data['conversation_state'] = AWAIT_SUBMIT_VIDEO
    await update.message.reply_text("Теперь отправьте ссылку на видео (YouTube, Google Drive и т.п.):")


async def submit_video_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода ссылки на видео."""

    if context.user_data.get('conversation_state') != AWAIT_SUBMIT_VIDEO:
        return

    video_link = update.message.text.strip()
    if not video_link.startswith(('http://', 'https://')):
        await update.message.reply_text("Ссылка должна начинаться с http:// или https://. Попробуйте снова.")
        return

    context.user_data['submit_video'] = video_link
    context.user_data['conversation_state'] = AWAIT_SUBMIT_COMMENT
    await update.message.reply_text("Можете добавить комментарий (или нажмите /skip):")


async def submit_comment_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода комментария."""

    if context.user_data.get('conversation_state') != AWAIT_SUBMIT_COMMENT:
        return

    comment = update.message.text
    if comment == '/skip':
        comment = None
    await finalize_submit(update, context, comment)


async def submit_comment_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропуск комментария."""

    if context.user_data.get('conversation_state') != AWAIT_SUBMIT_COMMENT:
        return

    await finalize_submit(update, context, None)


async def finalize_submit(update: Update, context: ContextTypes.DEFAULT_TYPE, comment):
    """Публикация результата в канале."""
    import re
    def escape_markdown(text):
        """Экранирует специальные символы Markdown."""
        chars = r'_*[]()~`>#+-=|{}.!'
        return ''.join(f'\\{c}' if c in chars else c for c in text)

    user_id = update.effective_user.id
    entity_type = context.user_data.get('submit_entity_type')
    entity_id = context.user_data.get('submit_entity_id')
    result_value = context.user_data.get('submit_result')
    video_link = context.user_data.get('submit_video')
    channel_post_id = context.user_data.get('submit_channel_post_id')
    channel_id = context.user_data.get('submit_channel_id')

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT first_name, username FROM users WHERE user_id = ?", (user_id,))
    user_row = cur.fetchone()
    conn.close()
    user_name = user_row[0] if user_row and user_row[0] else (user_row[1] if user_row else f"User{user_id}")

    # Экранируем текст
    user_name_clean = escape_markdown(user_name)
    result_value_clean = escape_markdown(str(result_value))
    comment_clean = escape_markdown(comment) if comment else ''

    publish_text = f"✅ **{user_name_clean}** сдал результат: {result_value_clean}\n"
    publish_text += f"📹 Видео: {video_link}\n"
    if comment:
        publish_text += f"💬 {comment_clean}\n"

    bot = context.bot

    # Отправляем сообщение в канал (без Markdown)
    sent = await bot.send_message(
        chat_id=channel_id,
        text=publish_text,
        reply_to_message_id=channel_post_id
    )

    # Добавляем кнопку "Комментировать"
    comment_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Комментировать", callback_data=f"comment_{sent.message_id}")]
    ])

    await bot.edit_message_reply_markup(
        chat_id=channel_id,
        message_id=sent.message_id,
        reply_markup=comment_keyboard
    )

    await update.message.reply_text("✅ Ваш результат сохранён и опубликован в канале!")
    context.user_data.clear()