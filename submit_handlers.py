import logging
import re
import sqlite3
from telegram import Update
from telegram.ext import ContextTypes
from database import DB_NAME, get_complex_by_id

# Константы состояний (должны совпадать с теми, что в bot.py)
AWAIT_SUBMIT_RESULT = 60
AWAIT_SUBMIT_VIDEO = 61
AWAIT_SUBMIT_COMMENT = 62

logger = logging.getLogger(__name__)


async def submit_complex_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатия кнопки 'Сдать результат' в канале."""
    print("=== submit_complex_callback НАЧАЛО ===")
    query = update.callback_query
    await query.answer()

    complex_id = int(query.data.split('_')[2])

    # Сохраняем данные для публикации результата
    context.user_data['submit_entity_type'] = 'complex'
    context.user_data['submit_entity_id'] = complex_id
    context.user_data['submit_channel_post_id'] = query.message.message_id
    context.user_data['submit_channel_id'] = query.message.chat_id
    # Устанавливаем состояние диалога
    context.user_data['conversation_state'] = AWAIT_SUBMIT_RESULT

    # Отправляем сообщение в личный чат пользователя
    await update.effective_user.send_message(
        "Введите результат:\n"
        "- если это повторения, просто число (например, 10)\n"
        "- если время, в формате ММ:СС (например, 05:30)"
    )

    print(f"=== submit_complex_callback завершён, состояние = {context.user_data.get('conversation_state')} ===")


async def submit_result_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода результата."""
    print("=== submit_result_input: ВЫЗОВ ===")

    # Проверяем, что мы находимся в нужном состоянии
    if context.user_data.get('conversation_state') != AWAIT_SUBMIT_RESULT:
        print(f"Состояние не соответствует. Текущее состояние: {context.user_data.get('conversation_state')}")
        return

    user_input = update.message.text.strip()
    entity_type = context.user_data.get('submit_entity_type')
    entity_id = context.user_data.get('submit_entity_id')

    if entity_type != 'complex':
        await update.message.reply_text("Пока поддерживаются только комплексы.")
        context.user_data.pop('conversation_state', None)  # Очищаем состояние
        return

    complex_data = get_complex_by_id(entity_id)
    if not complex_data:
        await update.message.reply_text("Комплекс не найден. Попробуйте позже.")
        context.user_data.pop('conversation_state', None)
        return

    metric_type = complex_data[3]  # 'for_time' или 'for_reps'

    if metric_type == 'for_reps':
        if not user_input.isdigit():
            await update.message.reply_text("Введите целое число повторений.")
            return  # остаёмся в том же состоянии
        context.user_data['submit_result'] = user_input
    else:  # for_time
        if not re.match(r'^\d{1,2}:\d{2}$', user_input):
            await update.message.reply_text("Введите время в формате ММ:СС, например 05:30.")
            return
        context.user_data['submit_result'] = user_input

    # Переходим к следующему шагу
    context.user_data['conversation_state'] = AWAIT_SUBMIT_VIDEO
    await update.message.reply_text("Теперь отправьте ссылку на видео (YouTube, Google Drive и т.п.):")


async def submit_video_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода ссылки на видео."""
    print("=== submit_video_input: ВЫЗОВ ===")

    if context.user_data.get('conversation_state') != AWAIT_SUBMIT_VIDEO:
        print(f"Состояние не соответствует. Текущее состояние: {context.user_data.get('conversation_state')}")
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
    print("=== submit_comment_input: ВЫЗОВ ===")

    if context.user_data.get('conversation_state') != AWAIT_SUBMIT_COMMENT:
        print(f"Состояние не соответствует. Текущее состояние: {context.user_data.get('conversation_state')}")
        return

    comment = update.message.text
    if comment == '/skip':
        comment = None
    await finalize_submit(update, context, comment)


async def submit_comment_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропуск комментария (обработчик команды /skip)."""
    print("=== submit_comment_skip: ВЫЗОВ ===")

    if context.user_data.get('conversation_state') != AWAIT_SUBMIT_COMMENT:
        print(f"Состояние не соответствует. Текущее состояние: {context.user_data.get('conversation_state')}")
        return

    await finalize_submit(update, context, None)


async def finalize_submit(update: Update, context: ContextTypes.DEFAULT_TYPE, comment):
    """Публикация результата в канале."""
    user_id = update.effective_user.id
    entity_type = context.user_data.get('submit_entity_type')
    entity_id = context.user_data.get('submit_entity_id')
    result_value = context.user_data.get('submit_result')
    video_link = context.user_data.get('submit_video')
    channel_post_id = context.user_data.get('submit_channel_post_id')
    channel_id = context.user_data.get('submit_channel_id')

    # Получаем имя пользователя
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT first_name, username FROM users WHERE user_id = ?", (user_id,))
    user_row = cur.fetchone()
    conn.close()
    user_name = user_row[0] if user_row and user_row[0] else (user_row[1] if user_row else f"User{user_id}")

    # Формируем сообщение для публикации в канале
    publish_text = f"✅ **{user_name}** сдал результат: {result_value}\n"
    publish_text += f"📹 Видео: {video_link}\n"
    if comment:
        publish_text += f"💬 {comment}\n"

    bot = context.bot
    await bot.send_message(
        chat_id=channel_id,
        text=publish_text,
        parse_mode='Markdown',
        reply_to_message_id=channel_post_id
    )

    await update.message.reply_text("✅ Ваш результат сохранён и опубликован в канале!")

    # Очищаем все данные диалога
    context.user_data.clear()