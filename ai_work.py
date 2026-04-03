import os
import requests
import logging
import traceback
import google.generativeai as genai
from collections import deque
from dotenv import load_dotenv

# Добавляем импорт debug_utils (предполагается, что файл debug_utils.py существует)
try:
    from debug_utils import debug_print, log_call, DEBUG_MODE
except ImportError:
    # fallback, если файла нет
    DEBUG_MODE = True


    def debug_print(*args, **kwargs):
        if DEBUG_MODE:
            print(*args, **kwargs)


    def log_call(func):
        return func

load_dotenv()

YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# === ФЛАГИ ВКЛЮЧЕНИЯ ПРОВАЙДЕРОВ ===
ENABLED_PROVIDERS = {
    "openrouter": True,
    "groq": True,
    "yandex": True,
    "deepseek_old": False,
    "gemini_old": False,
}

if not all([YANDEX_API_KEY, YANDEX_FOLDER_ID, DEEPSEEK_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY, GROQ_API_KEY]):
    debug_print("🔥 ai_work: ОШИБКА: не все ключи найдены в .env")
    raise ValueError("❌ Не все ключи найдены в .env! Проверь файл.")

# === НАСТРОЙКА ЛОГИРОВАНИЯ ===
logging.basicConfig(
    filename='consilium.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger('').addHandler(console)

REQUEST_TIMEOUT = (10, 30)

# === АКТУАЛЬНЫЕ БЕСПЛАТНЫЕ МОДЕЛИ OPENROUTER ===
FREE_MODELS = [
    "stepfun/step-3.5-flash:free",
    "arcee-ai/trinity-large-preview:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "z-ai/glm-4.5-air:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "arcee-ai/trinity-mini:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
    "nvidia/nemotron-nano-9b-v2:free",
    "qwen/qwen3-coder:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "openai/gpt-oss-120b:free",
    "liquid/lfm-2.5-1.2b-thinking:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "google/gemma-3-27b-it:free",
    "qwen/qwen3-4b:free",
    "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "google/gemma-3-4b-it:free",
    "minimax/minimax-m2.5:free",
    "google/gemma-3-12b-it:free",
    "google/gemma-3n-e4b-it:free",
    "google/gemma-3n-e2b-it:free",
    "nvidia/llama-nemotron-embed-vl-1b-v2:free",
    "openrouter/free"
]

# === СТАТИСТИКА ===
stats = {
    "attempts": 0,
    "success": 0,
    "failures": 0,
    "models_used": {}
}


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
@log_call
def log_error(context, error):
    debug_print(f"🔥 ai_work: log_error: ВЫЗВАНА")
    debug_print(f"📥 Аргументы: context={context}, error={error}")
    logging.error(f"{context}: {error}")
    debug_print(f"🔥 ai_work: log_error: ВОЗВРАТ None")


@log_call
def log_info(message):
    debug_print(f"🔥 ai_work: log_info: ВЫЗВАНА")
    debug_print(f"📥 Аргументы: message={message}")
    logging.info(message)
    debug_print(f"🔥 ai_work: log_info: ВОЗВРАТ None")


@log_call
def update_stats(success, model_name=None):
    debug_print(f"🔥 ai_work: update_stats: ВЫЗВАНА")
    debug_print(f"📥 Аргументы: success={success}, model_name={model_name}")
    stats["attempts"] += 1
    if success:
        stats["success"] += 1
        if model_name:
            stats["models_used"][model_name] = stats["models_used"].get(model_name, 0) + 1
    else:
        stats["failures"] += 1
    debug_print(f"🔥 ai_work: update_stats: stats теперь {stats}")
    debug_print(f"🔥 ai_work: update_stats: ВОЗВРАТ None")


# ========== ФУНКЦИИ ПРОВАЙДЕРОВ ==========
@log_call
def ask_openrouter(text, system_prompt=None, role_name="unknown"):
    debug_print(f"🔥 ai_work: ask_openrouter: ВЫЗВАНА")
    debug_print(
        f"📥 Аргументы: text={text[:100] if text else 'None'}..., system_prompt={system_prompt[:100] if system_prompt else 'None'}..., role_name={role_name}")
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "AI Consilium"
    }
    last_error = None
    for model in FREE_MODELS:
        try:
            debug_print(f"🔥 ai_work: ask_openrouter: попытка model={model}")
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": text})
            data = {"model": model, "messages": messages}
            response = requests.post(url, json=data, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            result = response.json()
            content = result['choices'][0]['message']['content']
            debug_print(f"🔥 ai_work: ask_openrouter: ответ получен: {content[:100]}...")
            log_info(f"OpenRouter {role_name} использовал {model}")
            update_stats(True, model)
            debug_print(f"🔥 ai_work: ask_openrouter: ВОЗВРАТ {content[:100]}...")
            return content
        except Exception as e:
            last_error = e
            debug_print(f"🔥 ai_work: ask_openrouter: ОШИБКА: {e}")
            debug_print(f"🔥 ai_work: traceback: {traceback.format_exc()}")
            log_error(f"OpenRouter {role_name} {model} ошибка", e)
            update_stats(False, model)
            continue
    debug_print(f"🔥 ai_work: ask_openrouter: все модели недоступны, последняя ошибка {last_error}")
    raise Exception(f"Все OpenRouter модели недоступны: {last_error}")


@log_call
def ask_groq(text, system_prompt=None, role_name="unknown"):
    debug_print(f"🔥 ai_work: ask_groq: ВЫЗВАНА")
    debug_print(
        f"📥 Аргументы: text={text[:100] if text else 'None'}..., system_prompt={system_prompt[:100] if system_prompt else 'None'}..., role_name={role_name}")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    models = [
        "llama-3.3-70b-versatile",
        "mixtral-8x7b-32768",
        "gemma2-9b-it"
    ]
    last_error = None
    for model in models:
        try:
            debug_print(f"🔥 ai_work: ask_groq: попытка model={model}")
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": text})
            data = {
                "model": model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 4000
            }
            response = requests.post(url, json=data, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            content = response.json()['choices'][0]['message']['content']
            debug_print(f"🔥 ai_work: ask_groq: ответ получен: {content[:100]}...")
            log_info(f"Groq {role_name} использовал {model}")
            update_stats(True, f"Groq/{model}")
            debug_print(f"🔥 ai_work: ask_groq: ВОЗВРАТ {content[:100]}...")
            return content
        except Exception as e:
            last_error = e
            debug_print(f"🔥 ai_work: ask_groq: ОШИБКА: {e}")
            debug_print(f"🔥 ai_work: traceback: {traceback.format_exc()}")
            log_error(f"Groq {role_name} {model} ошибка", e)
            update_stats(False, f"Groq/{model}")
            continue
    debug_print(f"🔥 ai_work: ask_groq: все модели недоступны, последняя ошибка {last_error}")
    raise Exception(f"Все Groq модели недоступны: {last_error}")


@log_call
def ask_yandex(text):
    debug_print(f"🔥 ai_work: ask_yandex: ВЫЗВАНА")
    debug_print(f"📥 Аргументы: text={text[:100] if text else 'None'}...")
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {"Authorization": f"Api-Key {YANDEX_API_KEY}"}
    data = {
        "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite",
        "completionOptions": {"stream": False, "temperature": 0.6, "maxTokens": 2000},
        "messages": [{"role": "user", "text": text}]
    }
    try:
        response = requests.post(url, json=data, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        res_json = response.json()
        content = res_json['result']['alternatives'][0]['message']['text']
        debug_print(f"🔥 ai_work: ask_yandex: ответ получен: {content[:100]}...")
        log_info("Yandex успешно ответил")
        update_stats(True, "YandexGPT")
        debug_print(f"🔥 ai_work: ask_yandex: ВОЗВРАТ {content[:100]}...")
        return content
    except Exception as e:
        debug_print(f"🔥 ai_work: ask_yandex: ОШИБКА: {e}")
        debug_print(f"🔥 ai_work: traceback: {traceback.format_exc()}")
        log_error("Yandex error", e)
        update_stats(False, "YandexGPT")
        raise


@log_call
def ask_deepseek(text):
    debug_print(f"🔥 ai_work: ask_deepseek: ВЫЗВАНА")
    debug_print(f"📥 Аргументы: text={text[:100] if text else 'None'}...")
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}
    data = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": text}]
    }
    try:
        response = requests.post(url, json=data, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content']
        debug_print(f"🔥 ai_work: ask_deepseek: ответ получен: {content[:100]}...")
        log_info("DeepSeek успешно ответил")
        update_stats(True, "DeepSeek (old)")
        debug_print(f"🔥 ai_work: ask_deepseek: ВОЗВРАТ {content[:100]}...")
        return content
    except Exception as e:
        debug_print(f"🔥 ai_work: ask_deepseek: ОШИБКА: {e}")
        debug_print(f"🔥 ai_work: traceback: {traceback.format_exc()}")
        log_error("DeepSeek error", e)
        update_stats(False, "DeepSeek (old)")
        raise


@log_call
def ask_gemini(text):
    debug_print(f"🔥 ai_work: ask_gemini: ВЫЗВАНА")
    debug_print(f"📥 Аргументы: text={text[:100] if text else 'None'}...")
    client = genai.Client(api_key=GEMINI_API_KEY)
    try:
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=text
        )
        content = response.text
        debug_print(f"🔥 ai_work: ask_gemini: ответ получен: {content[:100]}...")
        log_info("Gemini успешно ответил")
        update_stats(True, "Gemini (old)")
        debug_print(f"🔥 ai_work: ask_gemini: ВОЗВРАТ {content[:100]}...")
        return content
    except Exception as e:
        debug_print(f"🔥 ai_work: ask_gemini: ОШИБКА: {e}")
        debug_print(f"🔥 ai_work: traceback: {traceback.format_exc()}")
        log_error("Gemini error", e)
        update_stats(False, "Gemini (old)")
        raise


@log_call
def ask_any_ai(text, system_prompt=None, role_name="unknown"):
    debug_print(f"🔥 ai_work: ask_any_ai: ВЫЗВАНА")
    debug_print(
        f"📥 Аргументы: text={text[:100] if text else 'None'}..., system_prompt={system_prompt[:100] if system_prompt else 'None'}..., role_name={role_name}")

    if ENABLED_PROVIDERS["openrouter"]:
        try:
            debug_print("🔥 ai_work: ask_any_ai: пробуем OpenRouter")
            result = ask_openrouter(text, system_prompt, role_name)
            debug_print(f"🔥 ai_work: ask_any_ai: ВОЗВРАТ от openrouter: {result[:100]}...")
            return result
        except Exception as e:
            debug_print(f"🔥 ai_work: ask_any_ai: OpenRouter failed: {e}")
            log_error(f"OpenRouter {role_name} failed", e)

    if ENABLED_PROVIDERS["groq"]:
        try:
            debug_print("🔥 ai_work: ask_any_ai: пробуем Groq")
            result = ask_groq(text, system_prompt, role_name)
            debug_print(f"🔥 ai_work: ask_any_ai: ВОЗВРАТ от groq: {result[:100]}...")
            return result
        except Exception as e:
            debug_print(f"🔥 ai_work: ask_any_ai: Groq failed: {e}")
            log_error(f"Groq {role_name} failed", e)

    if ENABLED_PROVIDERS["yandex"]:
        try:
            debug_print("🔥 ai_work: ask_any_ai: пробуем Yandex")
            full_text = text
            if system_prompt:
                full_text = f"{system_prompt}\n\n{text}"
            result = ask_yandex(full_text)
            debug_print(f"🔥 ai_work: ask_any_ai: ВОЗВРАТ от yandex: {result[:100]}...")
            return result
        except Exception as e:
            debug_print(f"🔥 ai_work: ask_any_ai: Yandex failed: {e}")
            log_error(f"Yandex {role_name} failed", e)

    if ENABLED_PROVIDERS["deepseek_old"]:
        try:
            debug_print("🔥 ai_work: ask_any_ai: пробуем DeepSeek (old)")
            full_text = text
            if system_prompt:
                full_text = f"{system_prompt}\n\n{text}"
            result = ask_deepseek(full_text)
            debug_print(f"🔥 ai_work: ask_any_ai: ВОЗВРАТ от deepseek: {result[:100]}...")
            return result
        except Exception as e:
            debug_print(f"🔥 ai_work: ask_any_ai: DeepSeek failed: {e}")
            log_error(f"DeepSeek(old) {role_name} failed", e)

    if ENABLED_PROVIDERS["gemini_old"]:
        try:
            debug_print("🔥 ai_work: ask_any_ai: пробуем Gemini (old)")
            full_text = text
            if system_prompt:
                full_text = f"{system_prompt}\n\n{text}"
            result = ask_gemini(full_text)
            debug_print(f"🔥 ai_work: ask_any_ai: ВОЗВРАТ от gemini: {result[:100]}...")
            return result
        except Exception as e:
            debug_print(f"🔥 ai_work: ask_any_ai: Gemini failed: {e}")
            log_error(f"Gemini(old) {role_name} failed", e)

    debug_print("🔥 ai_work: ask_any_ai: все модели не ответили")
    raise Exception("Все включённые AI недоступны")


# ========== ОСНОВНЫЕ ФУНКЦИИ КОНСИЛИУМА ==========
@log_call
def get_primary_answer(question, user_history):
    debug_print(f"🔥 ai_work: get_primary_answer: ВЫЗВАНА")
    debug_print(f"📥 Аргументы: question={question[:100] if question else 'None'}..., user_history={user_history}")
    context = ""
    if user_history:
        context = "Предыдущий диалог:\n"
        for i, (q, a) in enumerate(user_history, 1):
            context += f"Вопрос {i}: {q}\nОтвет {i}: {a}\n"
        context += "\n"
    full_question = context + question if context else question
    try:
        ans = ask_any_ai(full_question, role_name="primary")
        debug_print(f"🔥 ai_work: get_primary_answer: ВОЗВРАТ ({ans[:100] if ans else 'None'}..., auto)")
        return ans, "auto"
    except Exception as e:
        debug_print(f"🔥 ai_work: get_primary_answer: ОШИБКА: {e}")
        debug_print(f"🔥 ai_work: traceback: {traceback.format_exc()}")
        log_error("Все AI недоступны для primary", e)
        debug_print(f"🔥 ai_work: get_primary_answer: ВОЗВРАТ (None, None)")
        return None, None


@log_call
def get_analysis(question, primary_answer, primary_source):
    debug_print(f"🔥 ai_work: get_analysis: ВЫЗВАНА")
    debug_print(
        f"📥 Аргументы: question={question[:100] if question else 'None'}..., primary_answer={primary_answer[:100] if primary_answer else 'None'}..., primary_source={primary_source}")
    prompt = f"Вопрос пользователя: {question}\nОтвет ({primary_source}): {primary_answer}\nПроверь этот ответ и предложи улучшения, укажи на возможные ошибки или добавь важные детали."
    try:
        ans = ask_any_ai(prompt, role_name="analyst")
        debug_print(f"🔥 ai_work: get_analysis: ВОЗВРАТ {ans[:100] if ans else 'None'}...")
        return ans
    except Exception as e:
        debug_print(f"🔥 ai_work: get_analysis: ОШИБКА: {e}")
        debug_print(f"🔥 ai_work: traceback: {traceback.format_exc()}")
        log_error("Analysis failed (все AI недоступны)", e)
        debug_print(f"🔥 ai_work: get_analysis: ВОЗВРАТ None")
        return None


@log_call
def get_synthesis(question, primary_answer, primary_source, analysis=None):
    debug_print(f"🔥 ai_work: get_synthesis: ВЫЗВАНА")
    debug_print(
        f"📥 Аргументы: question={question[:100] if question else 'None'}..., primary_answer={primary_answer[:100] if primary_answer else 'None'}..., primary_source={primary_source}, analysis={analysis[:100] if analysis else 'None'}...")
    if analysis:
        prompt = f"Вопрос: {question}\nМнение 1 (от {primary_source}): {primary_answer}\nМнение 2 (анализ): {analysis}\nОбъедини оба мнения в один идеальный ответ. Будь полезным и точным."
    else:
        prompt = f"Вопрос: {question}\nОтвет (от {primary_source}): {primary_answer}\nУлучши этот ответ, сделай его более полным и понятным."
    try:
        ans = ask_any_ai(prompt, role_name="synthesizer")
        debug_print(f"🔥 ai_work: get_synthesis: ВОЗВРАТ {ans[:100] if ans else 'None'}...")
        return ans
    except Exception as e:
        debug_print(f"🔥 ai_work: get_synthesis: ОШИБКА: {e}")
        debug_print(f"🔥 ai_work: traceback: {traceback.format_exc()}")
        log_error("Synthesis failed (все AI недоступны)", e)
        debug_print(f"🔥 ai_work: get_synthesis: ВОЗВРАТ primary_answer (fallback)")
        return primary_answer


@log_call
def print_stats():
    debug_print(f"🔥 ai_work: print_stats: ВЫЗВАНА")
    debug_print(
        f"📥 Аргументы: attempts={stats['attempts']}, success={stats['success']}, failures={stats['failures']}, models_used={stats['models_used']}")
    print("\n--- СТАТИСТИКА РАБОТЫ КОНСИЛИУМА ---")
    print(f"Всего попыток запросов: {stats['attempts']}")
    print(f"Успешно: {stats['success']}")
    print(f"Ошибок: {stats['failures']}")
    print("Использованные модели:")
    for model, count in stats['models_used'].items():
        print(f"  {model}: {count} раз(а)")
    print("------------------------------------\n")
    debug_print(f"🔥 ai_work: print_stats: ВОЗВРАТ None")


@log_call
def start_consilium(question, user_history):
    debug_print(f"🔥 ai_work: start_consilium: ВЫЗВАНА")
    debug_print(f"📥 Аргументы: question={question[:100] if question else 'None'}..., user_history={user_history}")

    log_info(f"Новый запрос: {question}")
    debug_print(f"🔥 ai_work: start_consilium: question={question[:100] if question else 'None'}...")
    debug_print(f"🔥 ai_work: start_consilium: history={user_history}")

    primary_answer, primary_source = get_primary_answer(question, user_history)
    if not primary_answer:
        debug_print(f"🔥 ai_work: start_consilium: primary_answer пуст, выходим с ошибкой")
        print_stats()
        debug_print(f"🔥 ai_work: start_consilium: ВОЗВРАТ ❌ Не удалось получить ответ ни от одного AI.")
        return "❌ Не удалось получить ответ ни от одного AI."

    analysis = get_analysis(question, primary_answer, primary_source)
    final_answer = get_synthesis(question, primary_answer, primary_source, analysis)

    # Добавляем в историю пользователя
    user_history.append((question, final_answer))
    debug_print(f"🔥 ai_work: start_consilium: история обновлена, теперь {len(user_history)} записей")

    print_stats()
    debug_print(f"🔥 ai_work: start_consilium: ВОЗВРАТ {final_answer[:100] if final_answer else 'None'}...")
    return final_answer