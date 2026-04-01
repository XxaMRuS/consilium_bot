import os
import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def ask_code_assistant(prompt: str, code: str = "", logs: str = "") -> str:
    """Отправляет запрос к OpenRouter для анализа кода."""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    system_prompt = """Ты — эксперт по Python и Telegram ботам. 
Анализируй код, находи ошибки, предлагай исправления. 
Отвечай кратко и по делу. Используй русский язык."""

    user_prompt = f"{prompt}\n\n"
    if code:
        user_prompt += f"Код:\n```python\n{code}\n```\n\n"
    if logs:
        user_prompt += f"Логи:\n```\n{logs}\n```\n\n"
    user_prompt += "Что нужно исправить?"

    data = {
        "model": "openai/gpt-4o-mini",  # можно заменить на "openai/gpt-4", "anthropic/claude-3-haiku"
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 2000,
    }

    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Ошибка при запросе: {e}"


# Пример использования
from code_assistant import ask_code_assistant

code = """
def get_all_exercises():
    conn = get_connection()
    cur = conn.cursor()
    if IS_POSTGRES:
        cur.execute("SELECT id, name, description, metric, points, week, difficulty FROM exercises ORDER BY id")
    else:
        cur.execute("SELECT id, name, description, metric, points, week, difficulty FROM exercises ORDER BY id")
    rows = cur.fetchall()
    conn.close()

    result = []
    for row in rows:
        if len(row) == 6:
            result.append((row[0], row[1], "", row[2], row[3], row[4], row[5]))
        else:
            result.append(row)
    return result
"""

answer = ask_code_assistant(
    "Проверь эту функцию. Всегда ли она возвращает 7 полей?",
    code=code
)
print(answer)