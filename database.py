import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import logging
import traceback

# ==================== ДЕБАГ-РЕЖИМ ====================
from debug_utils import debug_print, log_call, log_user_data, DEBUG_MODE

logger = logging.getLogger(__name__)

# Определяем, в какой среде работаем
DATABASE_URL = os.getenv("DATABASE_URL")
IS_POSTGRES = DATABASE_URL and DATABASE_URL.startswith("postgresql")

# Для SQLite используем локальный файл
DB_NAME = "workouts.db"


@log_call
def get_connection():
    """Возвращает соединение с БД (PostgreSQL или SQLite)"""
    debug_print(f"🔥 БД: get_connection: ВЫЗВАНА")
    debug_print(f"🔥 БД: IS_POSTGRES={IS_POSTGRES}")
    debug_print(f"🔥 БД: DATABASE_URL={DATABASE_URL[:50] if DATABASE_URL else 'None'}...")

    if DEBUG_MODE:
        debug_print("🔹 БД: get_connection вызвана")

    if IS_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL)
    else:
        conn = sqlite3.connect(DB_NAME)

    debug_print(f"🔥 БД: get_connection: ВОЗВРАЩАЕТ соединение")
    return conn


@log_call
def init_db():
    """Инициализирует базу данных (создаёт таблицы, если их нет)"""
    debug_print(f"🔥 БД: init_db: ВЫЗВАНА")
    debug_print(f"🔥 БД: init_db: IS_POSTGRES={IS_POSTGRES}")

    if DEBUG_MODE:
        debug_print("🔹 БД: init_db вызвана")

    debug_print(f"🔥 БД: init_db: создание таблиц...")
    conn = get_connection()
    cur = conn.cursor()

    if IS_POSTGRES:
        # PostgreSQL синтаксис
        cur.execute("""
                    CREATE TABLE IF NOT EXISTS settings
                    (
                        key
                        TEXT
                        PRIMARY
                        KEY,
                        value
                        TEXT
                    )
                    """)

        cur.execute("""
                    CREATE TABLE IF NOT EXISTS users
                    (
                        id
                        INTEGER
                        PRIMARY
                        KEY,
                        first_name
                        TEXT,
                        last_name
                        TEXT,
                        username
                        TEXT,
                        level
                        TEXT
                        DEFAULT
                        'beginner',
                        total_points
                        INTEGER
                        DEFAULT
                        0,
                        created_at
                        TIMESTAMP
                        DEFAULT
                        CURRENT_TIMESTAMP
                    )
                    """)

        cur.execute("""
                    CREATE TABLE IF NOT EXISTS exercises
                    (
                        id
                        SERIAL
                        PRIMARY
                        KEY,
                        name
                        TEXT
                        UNIQUE,
                        description
                        TEXT,
                        metric
                        TEXT,
                        points
                        INTEGER,
                        week
                        INTEGER,
                        difficulty
                        TEXT
                    )
                    """)

        # Добавляем колонку difficulty, если её нет
        try:
            cur.execute("SELECT difficulty FROM exercises LIMIT 1")
        except Exception:
            cur.execute("ALTER TABLE exercises ADD COLUMN difficulty TEXT DEFAULT 'beginner'")
            logger.info("Добавлена колонка difficulty в exercises")

        cur.execute("""
                    CREATE TABLE IF NOT EXISTS workouts
                    (
                        id
                        SERIAL
                        PRIMARY
                        KEY,
                        user_id
                        INTEGER,
                        exercise_id
                        INTEGER,
                        complex_id
                        INTEGER,
                        result_value
                        TEXT,
                        video_link
                        TEXT,
                        comment
                        TEXT,
                        date
                        TIMESTAMP
                        DEFAULT
                        CURRENT_TIMESTAMP,
                        is_best
                        BOOLEAN
                        DEFAULT
                        FALSE,
                        type
                        TEXT,
                        metric
                        TEXT
                    )
                    """)

        # Добавляем колонку date в workouts, если её нет
        try:
            cur.execute("SELECT date FROM workouts LIMIT 1")
        except Exception:
            cur.execute("ALTER TABLE workouts ADD COLUMN date TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            logger.info("Добавлена колонка date в workouts")

        cur.execute("""
                    CREATE TABLE IF NOT EXISTS complexes
                    (
                        id
                        SERIAL
                        PRIMARY
                        KEY,
                        name
                        TEXT
                        UNIQUE,
                        description
                        TEXT,
                        type
                        TEXT,
                        points
                        INTEGER
                    )
                    """)

        cur.execute("""
                    CREATE TABLE IF NOT EXISTS complex_exercises
                    (
                        id
                        SERIAL
                        PRIMARY
                        KEY,
                        complex_id
                        INTEGER,
                        exercise_id
                        INTEGER,
                        reps
                        INTEGER,
                        order_index
                        INTEGER
                    )
                    """)

        cur.execute("""
                    CREATE TABLE IF NOT EXISTS challenges
                    (
                        id
                        SERIAL
                        PRIMARY
                        KEY,
                        name
                        TEXT,
                        description
                        TEXT,
                        target_type
                        TEXT,
                        target_id
                        INTEGER,
                        metric
                        TEXT,
                        target_value
                        TEXT,
                        start_date
                        DATE,
                        end_date
                        DATE,
                        bonus_points
                        INTEGER,
                        is_active
                        BOOLEAN
                        DEFAULT
                        TRUE
                    )
                    """)

        cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_challenges
                    (
                        id
                        SERIAL
                        PRIMARY
                        KEY,
                        user_id
                        INTEGER,
                        challenge_id
                        INTEGER,
                        joined_at
                        TIMESTAMP
                        DEFAULT
                        CURRENT_TIMESTAMP,
                        completed
                        BOOLEAN
                        DEFAULT
                        FALSE,
                        completed_at
                        TIMESTAMP
                    )
                    """)

        cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_challenge_progress
                    (
                        id
                        SERIAL
                        PRIMARY
                        KEY,
                        user_id
                        INTEGER,
                        challenge_id
                        INTEGER,
                        current_value
                        TEXT,
                        updated_at
                        TIMESTAMP
                        DEFAULT
                        CURRENT_TIMESTAMP
                    )
                    """)

        cur.execute("""
                    CREATE TABLE IF NOT EXISTS achievements
                    (
                        id
                        SERIAL
                        PRIMARY
                        KEY,
                        name
                        TEXT,
                        description
                        TEXT,
                        condition_type
                        TEXT,
                        condition_value
                        TEXT,
                        icon
                        TEXT
                    )
                    """)

        cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_achievements
                    (
                        id
                        SERIAL
                        PRIMARY
                        KEY,
                        user_id
                        INTEGER,
                        achievement_id
                        INTEGER,
                        earned_at
                        TIMESTAMP
                        DEFAULT
                        CURRENT_TIMESTAMP
                    )
                    """)

        cur.execute("""
                    CREATE TABLE IF NOT EXISTS published_posts
                    (
                        id
                        SERIAL
                        PRIMARY
                        KEY,
                        type
                        TEXT,
                        item_id
                        INTEGER,
                        channel_id
                        INTEGER,
                        message_id
                        INTEGER,
                        published_at
                        TIMESTAMP
                        DEFAULT
                        CURRENT_TIMESTAMP
                    )
                    """)

        cur.execute("""
                    CREATE TABLE IF NOT EXISTS scoreboard
                    (
                        id
                        SERIAL
                        PRIMARY
                        KEY,
                        user_id
                        INTEGER,
                        period
                        TEXT,
                        points
                        INTEGER
                    )
                    """)

    else:
        # SQLite синтаксис (для локальной разработки)
        cur.executescript(
                          """
                          CREATE TABLE IF NOT EXISTS settings
                          (
                              key
                              TEXT
                              PRIMARY
                              KEY,
                              value
                              TEXT
                          );
                          CREATE TABLE IF NOT EXISTS users
                          (
                              id
                              INTEGER
                              PRIMARY
                              KEY,
                              first_name
                              TEXT,
                              last_name
                              TEXT,
                              username
                              TEXT,
                              level
                              TEXT
                              DEFAULT
                              'beginner',
                              total_points
                              INTEGER
                              DEFAULT
                              0,
                              created_at
                              TIMESTAMP
                              DEFAULT
                              CURRENT_TIMESTAMP
                          );
                          CREATE TABLE IF NOT EXISTS exercises
                          (
                              id
                              INTEGER
                              PRIMARY
                              KEY
                              AUTOINCREMENT,
                              name
                              TEXT
                              UNIQUE,
                              description
                              TEXT,
                              metric
                              TEXT,
                              points
                              INTEGER,
                              week
                              INTEGER,
                              difficulty
                              TEXT
                          );
                          CREATE TABLE IF NOT EXISTS workouts
                          (
                              id
                              INTEGER
                              PRIMARY
                              KEY
                              AUTOINCREMENT,
                              user_id
                              INTEGER,
                              exercise_id
                              INTEGER,
                              complex_id
                              INTEGER,
                              result_value
                              TEXT,
                              video_link
                              TEXT,
                              comment
                              TEXT,
                              date
                              TIMESTAMP
                              DEFAULT
                              CURRENT_TIMESTAMP,
                              is_best
                              BOOLEAN
                              DEFAULT
                              FALSE,
                              type
                              TEXT,
                              metric
                              TEXT
                          );
                          CREATE TABLE IF NOT EXISTS complexes
                          (
                              id
                              INTEGER
                              PRIMARY
                              KEY
                              AUTOINCREMENT,
                              name
                              TEXT
                              UNIQUE,
                              description
                              TEXT,
                              type
                              TEXT,
                              points
                              INTEGER
                          );
                          CREATE TABLE IF NOT EXISTS complex_exercises
                          (
                              id
                              INTEGER
                              PRIMARY
                              KEY
                              AUTOINCREMENT,
                              complex_id
                              INTEGER,
                              exercise_id
                              INTEGER,
                              reps
                              INTEGER,
                              order_index
                              INTEGER
                          );
                          CREATE TABLE IF NOT EXISTS challenges
                          (
                              id
                              INTEGER
                              PRIMARY
                              KEY
                              AUTOINCREMENT,
                              name
                              TEXT,
                              description
                              TEXT,
                              target_type
                              TEXT,
                              target_id
                              INTEGER,
                              metric
                              TEXT,
                              target_value
                              TEXT,
                              start_date
                              DATE,
                              end_date
                              DATE,
                              bonus_points
                              INTEGER,
                              is_active
                              BOOLEAN
                              DEFAULT
                              TRUE
                          );
                          CREATE TABLE IF NOT EXISTS user_challenges
                          (
                              id
                              INTEGER
                              PRIMARY
                              KEY
                              AUTOINCREMENT,
                              user_id
                              INTEGER,
                              challenge_id
                              INTEGER,
                              joined_at
                              TIMESTAMP
                              DEFAULT
                              CURRENT_TIMESTAMP,
                              completed
                              BOOLEAN
                              DEFAULT
                              FALSE,
                              completed_at
                              TIMESTAMP
                          );
                          CREATE TABLE IF NOT EXISTS user_challenge_progress
                          (
                              id
                              INTEGER
                              PRIMARY
                              KEY
                              AUTOINCREMENT,
                              user_id
                              INTEGER,
                              challenge_id
                              INTEGER,
                              current_value
                              TEXT,
                              updated_at
                              TIMESTAMP
                              DEFAULT
                              CURRENT_TIMESTAMP
                          );
                          CREATE TABLE IF NOT EXISTS achievements
                          (
                              id
                              INTEGER
                              PRIMARY
                              KEY
                              AUTOINCREMENT,
                              name
                              TEXT,
                              description
                              TEXT,
                              condition_type
                              TEXT,
                              condition_value
                              TEXT,
                              icon
                              TEXT
                          );
                          CREATE TABLE IF NOT EXISTS user_achievements
                          (
                              id
                              INTEGER
                              PRIMARY
                              KEY
                              AUTOINCREMENT,
                              user_id
                              INTEGER,
                              achievement_id
                              INTEGER,
                              earned_at
                              TIMESTAMP
                              DEFAULT
                              CURRENT_TIMESTAMP
                          );
                          CREATE TABLE IF NOT EXISTS published_posts
                          (
                              id
                              INTEGER
                              PRIMARY
                              KEY
                              AUTOINCREMENT,
                              type
                              TEXT,
                              item_id
                              INTEGER,
                              channel_id
                              INTEGER,
                              message_id
                              INTEGER,
                              published_at
                              TIMESTAMP
                              DEFAULT
                              CURRENT_TIMESTAMP
                          );
                          CREATE TABLE IF NOT EXISTS scoreboard
                          (
                              id
                              INTEGER
                              PRIMARY
                              KEY
                              AUTOINCREMENT,
                              user_id
                              INTEGER,
                              period
                              TEXT,
                              points
                              INTEGER);
                          """)

    conn.commit()
    conn.close()

    debug_print(f"🔥 БД: init_db: таблицы созданы")
    debug_print(f"🔥 БД: init_db: init_achievements вызвана")
    # Добавляем базовые достижения
    init_achievements()

    debug_print(f"🔥 БД: init_db: ВОЗВРАТ")
    return None


@log_call
def init_achievements():
    """Добавляет базовые достижения, если их нет"""
    debug_print(f"🔥 БД: init_achievements: ВЫЗВАНА")

    if DEBUG_MODE:
        debug_print("🔹 БД: init_achievements вызвана")

    achievements = [
        ("Первый шаг", "Записать первую тренировку", "workout_count", "1", "🎯"),
        ("Серийный спортсмен", "Записать 10 тренировок", "workout_count", "10", "🏅"),
        ("Трудоголик", "Записать 50 тренировок", "workout_count", "50", "🏆"),
        ("Рекордсмен", "Побить личный рекорд", "best_result", "1", "📈"),
    ]

    conn = get_connection()
    cur = conn.cursor()

    for name, desc, cond_type, cond_value, icon in achievements:
        if IS_POSTGRES:
            cur.execute(
                "INSERT INTO achievements (name, description, condition_type, condition_value, icon) "
                "SELECT %s, %s, %s, %s, %s WHERE NOT EXISTS (SELECT 1 FROM achievements WHERE name = %s)",
                (name, desc, cond_type, cond_value, icon, name)
            )
        else:
            cur.execute(
                "INSERT OR IGNORE INTO achievements (name, description, condition_type, condition_value, icon) "
                "VALUES (?, ?, ?, ?, ?)",
                (name, desc, cond_type, cond_value, icon)
            )

    conn.commit()
    conn.close()

    debug_print(f"🔥 БД: init_achievements: ВОЗВРАТ None")
    return None


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ДАННЫМИ ==========

@log_call
def get_setting(key):
    """Получает настройку из таблицы settings"""
    debug_print(f"🔥 БД: get_setting: ВЫЗВАНА")
    debug_print(f"🔥 БД: get_setting: key={key}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: get_setting вызвана с key={key}")

    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT value FROM settings WHERE key = %s" if IS_POSTGRES else "SELECT value FROM settings WHERE key = ?"
    params = (key,)

    debug_print(f"🔥 БД: SQL: {query}")
    debug_print(f"🔥 БД: params={params}")

    if IS_POSTGRES:
        cur.execute(query, params)
    else:
        cur.execute(query, params)

    row = cur.fetchone()
    conn.close()

    result = row[0] if row else None
    debug_print(f"🔥 БД: get_setting: ВОЗВРАТ {result}")
    return result


@log_call
def set_setting(key, value):
    """Сохраняет настройку в таблицу settings"""
    debug_print(f"🔥 БД: set_setting: ВЫЗВАНА")
    debug_print(f"🔥 БД: set_setting: key={key}, value={value}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: set_setting вызвана с key={key}, value={value}")

    conn = get_connection()
    cur = conn.cursor()

    if IS_POSTGRES:
        query = "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
        params = (key, value)
    else:
        query = "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)"
        params = (key, value)

    debug_print(f"🔥 БД: SQL: {query}")
    debug_print(f"🔥 БД: params={params}")

    cur.execute(query, params)
    conn.commit()
    conn.close()

    debug_print(f"🔥 БД: set_setting: ВОЗВРАТ None")
    return None


@log_call
def add_user(user_id, first_name, last_name, username, level='beginner'):
    """Добавляет или обновляет пользователя"""
    debug_print(f"🔥 БД: add_user: ВЫЗВАНА")
    debug_print(f"🔥 БД: add_user: user_id={user_id}")
    debug_print(f"🔥 БД: add_user: first_name={first_name}")
    debug_print(f"🔥 БД: add_user: last_name={last_name}")
    debug_print(f"🔥 БД: add_user: username={username}")
    debug_print(f"🔥 БД: add_user: level={level}")

    if DEBUG_MODE:
        debug_print(
            f"🔹 БД: add_user вызвана с user_id={user_id}, first_name={first_name}, username={username}, level={level}")

    conn = get_connection()
    cur = conn.cursor()

    if IS_POSTGRES:
        query = "INSERT INTO users (id, first_name, last_name, username, level) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO UPDATE SET first_name = EXCLUDED.first_name, last_name = EXCLUDED.last_name, username = EXCLUDED.username"
        params = (user_id, first_name, last_name, username, level)
    else:
        query = "INSERT OR REPLACE INTO users (id, first_name, last_name, username, level) VALUES (?, ?, ?, ?, ?)"
        params = (user_id, first_name, last_name, username, level)

    debug_print(f"🔥 БД: SQL: {query}")
    debug_print(f"🔥 БД: params={params}")

    cur.execute(query, params)
    conn.commit()
    conn.close()

    debug_print(f"🔥 БД: add_user: пользователь добавлен/обновлён")
    debug_print(f"🔥 БД: add_user: ВОЗВРАТ None")
    return None


@log_call
def get_user_level(user_id):
    """Возвращает уровень пользователя"""
    debug_print(f"🔥 БД: get_user_level: ВЫЗВАНА")
    debug_print(f"🔥 БД: get_user_level: user_id={user_id}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: get_user_level вызвана с user_id={user_id}")

    conn = get_connection()
    cur = conn.cursor()

    query = "SELECT level FROM users WHERE id = %s" if IS_POSTGRES else "SELECT level FROM users WHERE id = ?"
    params = (user_id,)

    debug_print(f"🔥 БД: SQL: {query}")
    debug_print(f"🔥 БД: params={params}")

    if IS_POSTGRES:
        cur.execute(query, params)
    else:
        cur.execute(query, params)

    row = cur.fetchone()
    conn.close()

    level = row[0] if row else 'beginner'
    debug_print(f"🔥 БД: get_user_level: результат={level}")
    debug_print(f"🔥 БД: get_user_level: ВОЗВРАТ {level}")
    return level


@log_call
def set_user_level(user_id, level):
    """Устанавливает уровень пользователя"""
    debug_print(f"🔥 БД: set_user_level: ВЫЗВАНА")
    debug_print(f"🔥 БД: set_user_level: user_id={user_id}")
    debug_print(f"🔥 БД: set_user_level: level={level}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: set_user_level вызвана с user_id={user_id}, level={level}")

    conn = get_connection()
    cur = conn.cursor()

    if IS_POSTGRES:
        query = "UPDATE users SET level = %s WHERE id = %s"
        params = (level, user_id)
    else:
        query = "UPDATE users SET level = ? WHERE id = ?"
        params = (level, user_id)

    debug_print(f"🔥 БД: SQL: {query}")
    debug_print(f"🔥 БД: params={params}")

    cur.execute(query, params)
    conn.commit()
    conn.close()

    debug_print(f"🔥 БД: set_user_level: ВОЗВРАТ True")
    return True


@log_call
def get_exercises(active_only=True, week=None, difficulty=None):
    """Возвращает список упражнений"""
    debug_print(f"🔥 БД: get_exercises: ВЫЗВАНА")
    debug_print(f"🔥 БД: get_exercises: active_only={active_only}")
    debug_print(f"🔥 БД: get_exercises: week={week}")
    debug_print(f"🔥 БД: get_exercises: difficulty={difficulty}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: get_exercises вызвана с active_only={active_only}, week={week}, difficulty={difficulty}")

    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT id, name, metric, points, week, difficulty FROM exercises"
    conditions = []
    params = []

    if active_only:
        conditions.append("week <= ?" if not IS_POSTGRES else "week <= %s")
        params.append(week or 100)

    if difficulty:
        conditions.append("difficulty = ?" if not IS_POSTGRES else "difficulty = %s")
        params.append(difficulty)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY week, name"

    debug_print(f"🔥 БД: SQL: {query}")
    debug_print(f"🔥 БД: params={params}")

    if IS_POSTGRES:
        cur.execute(query, tuple(params))
    else:
        cur.execute(query, params)

    rows = cur.fetchall()
    conn.close()

    debug_print(f"🔥 БД: get_exercises: количество упражнений={len(rows)}")
    debug_print(f"🔥 БД: get_exercises: ВОЗВРАТ {len(rows)} записей")
    return rows


@log_call
def get_all_exercises():
    debug_print(f"🔥 БД: get_all_exercises: ВЫЗВАНА")

    if DEBUG_MODE:
        debug_print("🔹 БД: get_all_exercises вызвана")

    conn = get_connection()
    cur = conn.cursor()

    query = "SELECT id, name, description, metric, points, week, difficulty FROM exercises ORDER BY id"
    debug_print(f"🔥 БД: SQL: {query}")

    if IS_POSTGRES:
        cur.execute(query)
    else:
        cur.execute(query)

    rows = cur.fetchall()

    debug_print(f"DEBUG: rows count = {len(rows)}")
    if rows:
        debug_print(f"DEBUG: first row = {rows[0]}")
        debug_print(f"DEBUG: first row length = {len(rows[0])}")

    conn.close()

    result = []
    for row in rows:
        if len(row) == 6:
            result.append((row[0], row[1], "", row[2], row[3], row[4], row[5]))
        elif len(row) == 7:
            result.append(row)
        else:
            raise ValueError(f"Неверное количество полей в упражнении: {len(row)}")

    debug_print(f"🔥 БД: get_all_exercises: количество={len(result)}")
    debug_print(f"🔥 БД: get_all_exercises: ВОЗВРАТ {len(result)} записей")
    return result


@log_call
def get_exercise_by_id(exercise_id):
    """Возвращает упражнение по ID"""
    debug_print(f"🔥 БД: get_exercise_by_id: ВЫЗВАНА")
    debug_print(f"🔥 БД: get_exercise_by_id: exercise_id={exercise_id}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: get_exercise_by_id вызвана с exercise_id={exercise_id}")

    conn = get_connection()
    cur = conn.cursor()

    query = "SELECT id, name, description, metric, points, week, difficulty FROM exercises WHERE id = %s" if IS_POSTGRES else "SELECT id, name, description, metric, points, week, difficulty FROM exercises WHERE id = ?"
    params = (exercise_id,)

    debug_print(f"🔥 БД: SQL: {query}")
    debug_print(f"🔥 БД: params={params}")

    if IS_POSTGRES:
        cur.execute(query, params)
    else:
        cur.execute(query, params)

    row = cur.fetchone()
    conn.close()

    debug_print(f"🔥 БД: get_exercise_by_id: найдено={row is not None}")
    debug_print(f"🔥 БД: get_exercise_by_id: ВОЗВРАТ {row}")
    return row


@log_call
def add_exercise(name, description, metric, points, week=0, difficulty='beginner'):
    """Добавляет упражнение"""
    debug_print(f"🔥 БД: add_exercise: ВЫЗВАНА")
    debug_print(f"🔥 БД: add_exercise: name={name}")
    debug_print(f"🔥 БД: add_exercise: description={description[:50] if description else 'None'}...")
    debug_print(f"🔥 БД: add_exercise: metric={metric}")
    debug_print(f"🔥 БД: add_exercise: points={points}")
    debug_print(f"🔥 БД: add_exercise: week={week}")
    debug_print(f"🔥 БД: add_exercise: difficulty={difficulty}")

    if DEBUG_MODE:
        debug_print(
            f"🔹 БД: add_exercise вызвана с name={name}, metric={metric}, points={points}, week={week}, difficulty={difficulty}")

    conn = get_connection()
    cur = conn.cursor()
    try:
        if IS_POSTGRES:
            query = "INSERT INTO exercises (name, description, metric, points, week, difficulty) VALUES (%s, %s, %s, %s, %s, %s)"
            params = (name, description, metric, points, week, difficulty)
        else:
            query = "INSERT INTO exercises (name, description, metric, points, week, difficulty) VALUES (?, ?, ?, ?, ?, ?)"
            params = (name, description, metric, points, week, difficulty)

        debug_print(f"🔥 БД: SQL: {query}")
        debug_print(f"🔥 БД: params={params}")

        cur.execute(query, params)
        conn.commit()
        return True
    except Exception as e:
        debug_print(f"🔥 БД: ОШИБКА: {e}")
        debug_print(f"🔥 БД: traceback: {traceback.format_exc()}")
        logger.error(f"Ошибка добавления упражнения: {e}")
        return False
    finally:
        conn.close()


@log_call
def delete_exercise(exercise_id):
    """Удаляет упражнение"""
    debug_print(f"🔥 БД: delete_exercise: ВЫЗВАНА")
    debug_print(f"🔥 БД: delete_exercise: exercise_id={exercise_id}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: delete_exercise вызвана с exercise_id={exercise_id}")

    conn = get_connection()
    cur = conn.cursor()
    try:
        if IS_POSTGRES:
            query = "DELETE FROM exercises WHERE id = %s"
            params = (exercise_id,)
        else:
            query = "DELETE FROM exercises WHERE id = ?"
            params = (exercise_id,)

        debug_print(f"🔥 БД: SQL: {query}")
        debug_print(f"🔥 БД: params={params}")

        cur.execute(query, params)
        conn.commit()
        return True
    except Exception as e:
        debug_print(f"🔥 БД: ОШИБКА: {e}")
        debug_print(f"🔥 БД: traceback: {traceback.format_exc()}")
        logger.error(f"Ошибка удаления упражнения: {e}")
        return False
    finally:
        conn.close()


# ========== ФУНКЦИИ ДЛЯ ТРЕНИРОВОК ==========

@log_call
def add_workout(user_id, exercise_id=None, complex_id=None, result_value=None, video_link=None,
                user_level=None, comment=None, metric=None, notify_record_callback=None):
    """Добавляет тренировку и начисляет баллы"""
    debug_print(f"🔥 БД: add_workout: ВЫЗВАНА")
    debug_print(f"🔥 БД: add_workout: user_id={user_id}")
    debug_print(f"🔥 БД: add_workout: exercise_id={exercise_id}")
    debug_print(f"🔥 БД: add_workout: complex_id={complex_id}")
    debug_print(f"🔥 БД: add_workout: result_value={result_value}")
    debug_print(f"🔥 БД: add_workout: video_link={video_link[:50] if video_link else 'None'}...")
    debug_print(f"🔥 БД: add_workout: comment={comment[:50] if comment else 'None'}...")
    debug_print(f"🔥 БД: add_workout: metric={metric}")

    if DEBUG_MODE:
        debug_print(
            f"🔹 БД: add_workout вызвана с user_id={user_id}, exercise_id={exercise_id}, complex_id={complex_id}, result_value={result_value}")

    conn = get_connection()
    cur = conn.cursor()

    # Определяем тип и баллы
    if exercise_id:
        ex = get_exercise_by_id(exercise_id)
        if not ex:
            conn.close()
            debug_print(f"🔥 БД: add_workout: ВОЗВРАТ (None, []) - упражнение не найдено")
            return None, []
        points = ex[4] if len(ex) > 4 else 0
        workout_type = "exercise"
        workout_metric = metric
    else:
        # Это комплекс
        complex_data = get_complex_by_id(complex_id)
        points = complex_data[4] if complex_data else 0
        workout_type = "complex"
        workout_metric = None

    # Вставляем тренировку
    if IS_POSTGRES:
        query = "INSERT INTO workouts (user_id, exercise_id, complex_id, result_value, video_link, comment, type, metric, date) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
        params = (user_id, exercise_id, complex_id, result_value, video_link, comment, workout_type, workout_metric,
                  datetime.now())
    else:
        query = "INSERT INTO workouts (user_id, exercise_id, complex_id, result_value, video_link, comment, type, metric, date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        params = (user_id, exercise_id, complex_id, result_value, video_link, comment, workout_type, workout_metric,
                  datetime.now())

    debug_print(f"🔥 БД: SQL: {query[:200]}")
    debug_print(f"🔥 БД: params={params}")

    cur.execute(query, params)

    if IS_POSTGRES:
        cur.execute("SELECT LASTVAL()")
        workout_id = cur.fetchone()[0]
    else:
        workout_id = cur.lastrowid

    conn.commit()
    conn.close()

    # Начисляем баллы (через scoreboard)
    add_points_to_scoreboard(user_id, points)

    # Проверяем достижения
    new_achievements = check_and_award_achievements(user_id)

    # Уведомление (если нужно)
    if notify_record_callback:
        notify_record_callback(user_id, exercise_id or complex_id, result_value, workout_metric)

    debug_print(f"🔥 БД: add_workout: workout_id={workout_id}")
    debug_print(f"🔥 БД: add_workout: новые достижения={new_achievements}")
    debug_print(f"🔥 БД: add_workout: ВОЗВРАТ ({points}, {new_achievements})")
    return points, new_achievements


@log_call
def get_user_workouts(user_id, limit=20):
    """Возвращает последние тренировки пользователя"""
    debug_print(f"🔥 БД: get_user_workouts: ВЫЗВАНА")
    debug_print(f"🔥 БД: get_user_workouts: user_id={user_id}")
    debug_print(f"🔥 БД: get_user_workouts: limit={limit}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: get_user_workouts вызвана с user_id={user_id}, limit={limit}")

    conn = get_connection()
    cur = conn.cursor()

    if IS_POSTGRES:
        query = """
                SELECT w.id,
                       COALESCE(e.name, c.name) as name,
                       w.result_value, \
                       w.video_link, \
                       w.date, \
                       w.is_best, \
                       w.type, \
                       w.comment
                FROM workouts w
                         LEFT JOIN exercises e ON w.exercise_id = e.id
                         LEFT JOIN complexes c ON w.complex_id = c.id
                WHERE w.user_id = %s
                ORDER BY w.date DESC
                    LIMIT %s \
                """
        params = (user_id, limit)
    else:
        query = """
                SELECT w.id,
                       COALESCE(e.name, c.name) as name,
                       w.result_value, \
                       w.video_link, \
                       w.date, \
                       w.is_best, \
                       w.type, \
                       w.comment
                FROM workouts w
                         LEFT JOIN exercises e ON w.exercise_id = e.id
                         LEFT JOIN complexes c ON w.complex_id = c.id
                WHERE w.user_id = ?
                ORDER BY w.date DESC LIMIT ? \
                """
        params = (user_id, limit)

    debug_print(f"🔥 БД: SQL: {query[:200]}")
    debug_print(f"🔥 БД: params={params}")

    cur.execute(query, params)

    rows = cur.fetchall()
    conn.close()

    debug_print(f"🔥 БД: get_user_workouts: количество={len(rows)}")
    debug_print(f"🔥 БД: get_user_workouts: ВОЗВРАТ {len(rows)} записей")
    return rows


# ========== ФУНКЦИИ ДЛЯ КОМПЛЕКСОВ ==========

@log_call
def add_complex(name, description, type_, points):
    """Добавляет комплекс"""
    debug_print(f"🔥 БД: add_complex: ВЫЗВАНА")
    debug_print(f"🔥 БД: add_complex: name={name}")
    debug_print(f"🔥 БД: add_complex: type={type_}")
    debug_print(f"🔥 БД: add_complex: points={points}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: add_complex вызвана с name={name}, type={type_}, points={points}")

    conn = get_connection()
    cur = conn.cursor()
    try:
        if IS_POSTGRES:
            query = "INSERT INTO complexes (name, description, type, points) VALUES (%s, %s, %s, %s) RETURNING id"
            params = (name, description, type_, points)
            debug_print(f"🔥 БД: SQL: {query}")
            debug_print(f"🔥 БД: params={params}")
            cur.execute(query, params)
            complex_id = cur.fetchone()[0]
        else:
            query = "INSERT INTO complexes (name, description, type, points) VALUES (?, ?, ?, ?)"
            params = (name, description, type_, points)
            debug_print(f"🔥 БД: SQL: {query}")
            debug_print(f"🔥 БД: params={params}")
            cur.execute(query, params)
            complex_id = cur.lastrowid
        conn.commit()
        return complex_id
    except Exception as e:
        debug_print(f"🔥 БД: ОШИБКА: {e}")
        debug_print(f"🔥 БД: traceback: {traceback.format_exc()}")
        logger.error(f"Ошибка добавления комплекса: {e}")
        return None
    finally:
        conn.close()


@log_call
def get_all_complexes():
    """Возвращает все комплексы"""
    debug_print(f"🔥 БД: get_all_complexes: ВЫЗВАНА")

    if DEBUG_MODE:
        debug_print("🔹 БД: get_all_complexes вызвана")

    conn = get_connection()
    cur = conn.cursor()

    query = "SELECT id, name, description, type, points FROM complexes ORDER BY id"
    debug_print(f"🔥 БД: SQL: {query}")

    if IS_POSTGRES:
        cur.execute(query)
    else:
        cur.execute(query)

    rows = cur.fetchall()
    conn.close()

    debug_print(f"🔥 БД: get_all_complexes: ВОЗВРАТ {len(rows)} записей")
    return rows


@log_call
def get_complex_by_id(complex_id):
    """Возвращает комплекс по ID"""
    debug_print(f"🔥 БД: get_complex_by_id: ВЫЗВАНА")
    debug_print(f"🔥 БД: get_complex_by_id: complex_id={complex_id}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: get_complex_by_id вызвана с complex_id={complex_id}")

    conn = get_connection()
    cur = conn.cursor()

    query = "SELECT id, name, description, type, points FROM complexes WHERE id = %s" if IS_POSTGRES else "SELECT id, name, description, type, points FROM complexes WHERE id = ?"
    params = (complex_id,)

    debug_print(f"🔥 БД: SQL: {query}")
    debug_print(f"🔥 БД: params={params}")

    if IS_POSTGRES:
        cur.execute(query, params)
    else:
        cur.execute(query, params)

    row = cur.fetchone()
    conn.close()

    debug_print(f"🔥 БД: get_complex_by_id: ВОЗВРАТ {row}")
    return row


@log_call
def add_complex_exercise(complex_id, exercise_id, reps):
    """Добавляет упражнение в комплекс"""
    debug_print(f"🔥 БД: add_complex_exercise: ВЫЗВАНА")
    debug_print(f"🔥 БД: add_complex_exercise: complex_id={complex_id}")
    debug_print(f"🔥 БД: add_complex_exercise: exercise_id={exercise_id}")
    debug_print(f"🔥 БД: add_complex_exercise: reps={reps}")

    if DEBUG_MODE:
        debug_print(
            f"🔹 БД: add_complex_exercise вызвана с complex_id={complex_id}, exercise_id={exercise_id}, reps={reps}")

    conn = get_connection()
    cur = conn.cursor()
    try:
        if IS_POSTGRES:
            query = "INSERT INTO complex_exercises (complex_id, exercise_id, reps) VALUES (%s, %s, %s)"
            params = (complex_id, exercise_id, reps)
        else:
            query = "INSERT INTO complex_exercises (complex_id, exercise_id, reps) VALUES (?, ?, ?)"
            params = (complex_id, exercise_id, reps)

        debug_print(f"🔥 БД: SQL: {query}")
        debug_print(f"🔥 БД: params={params}")

        cur.execute(query, params)
        conn.commit()
        return True
    except Exception as e:
        debug_print(f"🔥 БД: ОШИБКА: {e}")
        debug_print(f"🔥 БД: traceback: {traceback.format_exc()}")
        logger.error(f"Ошибка добавления упражнения в комплекс: {e}")
        return False
    finally:
        conn.close()


@log_call
def get_complex_exercises(complex_id):
    """Возвращает упражнения комплекса"""
    debug_print(f"🔥 БД: get_complex_exercises: ВЫЗВАНА")
    debug_print(f"🔥 БД: get_complex_exercises: complex_id={complex_id}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: get_complex_exercises вызвана с complex_id={complex_id}")

    conn = get_connection()
    cur = conn.cursor()

    if IS_POSTGRES:
        query = """
                SELECT ce.id, ce.complex_id, e.id, e.name, ce.reps
                FROM complex_exercises ce
                         JOIN exercises e ON ce.exercise_id = e.id
                WHERE ce.complex_id = %s
                ORDER BY ce.order_index \
                """
        params = (complex_id,)
    else:
        query = """
                SELECT ce.id, ce.complex_id, e.id, e.name, ce.reps
                FROM complex_exercises ce
                         JOIN exercises e ON ce.exercise_id = e.id
                WHERE ce.complex_id = ?
                ORDER BY ce.order_index \
                """
        params = (complex_id,)

    debug_print(f"🔥 БД: SQL: {query[:200]}")
    debug_print(f"🔥 БД: params={params}")

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    debug_print(f"🔥 БД: get_complex_exercises: ВОЗВРАТ {len(rows)} записей")
    return rows


# ========== ФУНКЦИИ ДЛЯ РЕЙТИНГА ==========

@log_call
def add_points_to_scoreboard(user_id, points, period='total'):
    """Добавляет баллы пользователю в scoreboard"""
    debug_print(f"🔥 БД: add_points_to_scoreboard: ВЫЗВАНА")
    debug_print(f"🔥 БД: add_points_to_scoreboard: user_id={user_id}")
    debug_print(f"🔥 БД: add_points_to_scoreboard: points={points}")
    debug_print(f"🔥 БД: add_points_to_scoreboard: period={period}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: add_points_to_scoreboard вызвана с user_id={user_id}, points={points}, period={period}")

    conn = get_connection()
    cur = conn.cursor()

    if IS_POSTGRES:
        query = """
                INSERT INTO scoreboard (user_id, period, points)
                VALUES (%s, %s, %s) ON CONFLICT (user_id, period) 
            DO \
                UPDATE SET points = scoreboard.points + EXCLUDED.points \
                """
        params = (user_id, period, points)
    else:
        # SQLite: сначала проверяем, есть ли запись
        cur.execute("SELECT points FROM scoreboard WHERE user_id = ? AND period = ?", (user_id, period))
        row = cur.fetchone()

        if row:
            # Обновляем существующую запись
            new_points = row[0] + points
            query = "UPDATE scoreboard SET points = ? WHERE user_id = ? AND period = ?"
            params = (new_points, user_id, period)
        else:
            # Создаём новую запись
            query = "INSERT INTO scoreboard (user_id, period, points) VALUES (?, ?, ?)"
            params = (user_id, period, points)

    debug_print(f"🔥 БД: SQL: {query}")
    debug_print(f"🔥 БД: params={params}")

    cur.execute(query, params)
    conn.commit()
    conn.close()

    debug_print(f"🔥 БД: add_points_to_scoreboard: ВОЗВРАТ None")
    return None


@log_call
def get_user_scoreboard_total(user_id):
    """Возвращает общее количество баллов пользователя"""
    debug_print(f"🔥 БД: get_user_scoreboard_total: ВЫЗВАНА")
    debug_print(f"🔥 БД: get_user_scoreboard_total: user_id={user_id}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: get_user_scoreboard_total вызвана с user_id={user_id}")

    conn = get_connection()
    cur = conn.cursor()

    query = "SELECT points FROM scoreboard WHERE user_id = %s AND period = 'total'" if IS_POSTGRES else "SELECT points FROM scoreboard WHERE user_id = ? AND period = 'total'"
    params = (user_id,)

    debug_print(f"🔥 БД: SQL: {query}")
    debug_print(f"🔥 БД: params={params}")

    cur.execute(query, params)
    row = cur.fetchone()
    conn.close()

    total = row[0] if row else 0
    debug_print(f"🔥 БД: get_user_scoreboard_total: total={total}")
    debug_print(f"🔥 БД: get_user_scoreboard_total: ВОЗВРАТ {total}")
    return total


@log_call
def get_leaderboard_from_scoreboard(period='total'):
    """Возвращает таблицу лидеров"""
    debug_print(f"🔥 БД: get_leaderboard_from_scoreboard: ВЫЗВАНА")
    debug_print(f"🔥 БД: get_leaderboard_from_scoreboard: period={period}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: get_leaderboard_from_scoreboard вызвана с period={period}")

    conn = get_connection()
    cur = conn.cursor()

    if IS_POSTGRES:
        query = """
                SELECT u.id, u.first_name, u.username, s.points
                FROM scoreboard s
                         JOIN users u ON s.user_id = u.id
                WHERE s.period = %s
                ORDER BY s.points DESC \
                """
        params = (period,)
    else:
        query = """
                SELECT u.id, u.first_name, u.username, s.points
                FROM scoreboard s
                         JOIN users u ON s.user_id = u.id
                WHERE s.period = ?
                ORDER BY s.points DESC \
                """
        params = (period,)

    debug_print(f"🔥 БД: SQL: {query[:200]}")
    debug_print(f"🔥 БД: params={params}")

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    debug_print(f"🔥 БД: get_leaderboard_from_scoreboard: количество={len(rows)}")
    debug_print(f"🔥 БД: get_leaderboard_from_scoreboard: ВОЗВРАТ {len(rows)} записей")
    return rows


# ========== ФУНКЦИИ ДЛЯ ЧЕЛЛЕНДЖЕЙ ==========

@log_call
def add_challenge(name, description, target_type, target_id, metric, target_value,
                  start_date, end_date, bonus_points):
    """Добавляет челлендж"""
    debug_print(f"🔥 БД: add_challenge: ВЫЗВАНА")
    debug_print(f"🔥 БД: add_challenge: name={name}")
    debug_print(f"🔥 БД: add_challenge: target_type={target_type}")
    debug_print(f"🔥 БД: add_challenge: bonus_points={bonus_points}")

    if DEBUG_MODE:
        debug_print(
            f"🔹 БД: add_challenge вызвана с name={name}, target_type={target_type}, bonus_points={bonus_points}")

    conn = get_connection()
    cur = conn.cursor()
    try:
        if IS_POSTGRES:
            query = """
                    INSERT INTO challenges (name, description, target_type, target_id, metric, target_value,
                                            start_date, end_date, bonus_points)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) \
                    """
            params = (name, description, target_type, target_id, metric, target_value, start_date, end_date,
                      bonus_points)
        else:
            query = """
                    INSERT INTO challenges (name, description, target_type, target_id, metric, target_value,
                                            start_date, end_date, bonus_points)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) \
                    """
            params = (name, description, target_type, target_id, metric, target_value, start_date, end_date,
                      bonus_points)

        debug_print(f"🔥 БД: SQL: {query[:200]}")
        debug_print(f"🔥 БД: params={params}")

        cur.execute(query, params)
        conn.commit()
        return True
    except Exception as e:
        debug_print(f"🔥 БД: ОШИБКА: {e}")
        debug_print(f"🔥 БД: traceback: {traceback.format_exc()}")
        logger.error(f"Ошибка добавления челленджа: {e}")
        return False
    finally:
        conn.close()


@log_call
def get_challenge_by_id(challenge_id):
    """Возвращает челлендж по ID"""
    debug_print(f"🔥 БД: get_challenge_by_id: ВЫЗВАНА")
    debug_print(f"🔥 БД: get_challenge_by_id: challenge_id={challenge_id}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: get_challenge_by_id вызвана с challenge_id={challenge_id}")

    conn = get_connection()
    cur = conn.cursor()

    query = "SELECT * FROM challenges WHERE id = %s" if IS_POSTGRES else "SELECT * FROM challenges WHERE id = ?"
    params = (challenge_id,)

    debug_print(f"🔥 БД: SQL: {query}")
    debug_print(f"🔥 БД: params={params}")

    if IS_POSTGRES:
        cur.execute(query, params)
    else:
        cur.execute(query, params)

    row = cur.fetchone()
    conn.close()

    debug_print(f"🔥 БД: get_challenge_by_id: ВОЗВРАТ {row}")
    return row


@log_call
def get_challenges_by_status(status='active'):
    """Возвращает челленджи по статусу"""
    debug_print(f"🔥 БД: get_challenges_by_status: ВЫЗВАНА")
    debug_print(f"🔥 БД: get_challenges_by_status: status={status}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: get_challenges_by_status вызвана с status={status}")

    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().date()

    if status == 'active':
        condition = "start_date <= ? AND end_date >= ?" if not IS_POSTGRES else "start_date <= %s AND end_date >= %s"
        params = (now, now)
    elif status == 'past':
        condition = "end_date < ?" if not IS_POSTGRES else "end_date < %s"
        params = (now,)
    else:  # future
        condition = "start_date > ?" if not IS_POSTGRES else "start_date > %s"
        params = (now,)

    query = f"SELECT * FROM challenges WHERE {condition} ORDER BY start_date"
    debug_print(f"🔥 БД: SQL: {query}")
    debug_print(f"🔥 БД: params={params}")

    if IS_POSTGRES:
        cur.execute(query, params)
    else:
        cur.execute(query, params)

    rows = cur.fetchall()
    conn.close()

    debug_print(f"🔥 БД: get_challenges_by_status: ВОЗВРАТ {len(rows)} записей")
    return rows


@log_call
def get_challenge_name(challenge_id):
    """Возвращает название челленджа"""
    debug_print(f"🔥 БД: get_challenge_name: ВЫЗВАНА")
    debug_print(f"🔥 БД: get_challenge_name: challenge_id={challenge_id}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: get_challenge_name вызвана с challenge_id={challenge_id}")

    conn = get_connection()
    cur = conn.cursor()

    query = "SELECT name FROM challenges WHERE id = %s" if IS_POSTGRES else "SELECT name FROM challenges WHERE id = ?"
    params = (challenge_id,)

    debug_print(f"🔥 БД: SQL: {query}")
    debug_print(f"🔥 БД: params={params}")

    if IS_POSTGRES:
        cur.execute(query, params)
    else:
        cur.execute(query, params)

    row = cur.fetchone()
    conn.close()

    result = row[0] if row else None
    debug_print(f"🔥 БД: get_challenge_name: ВОЗВРАТ {result}")
    return result


@log_call
def join_challenge(user_id, challenge_id):
    """Добавляет пользователя в челлендж"""
    debug_print(f"🔥 БД: join_challenge: ВЫЗВАНА")
    debug_print(f"🔥 БД: join_challenge: user_id={user_id}")
    debug_print(f"🔥 БД: join_challenge: challenge_id={challenge_id}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: join_challenge вызвана с user_id={user_id}, challenge_id={challenge_id}")

    conn = get_connection()
    cur = conn.cursor()
    try:
        if IS_POSTGRES:
            query = "INSERT INTO user_challenges (user_id, challenge_id) VALUES (%s, %s) ON CONFLICT (user_id, challenge_id) DO NOTHING"
            params = (user_id, challenge_id)
        else:
            query = "INSERT OR IGNORE INTO user_challenges (user_id, challenge_id) VALUES (?, ?)"
            params = (user_id, challenge_id)

        debug_print(f"🔥 БД: SQL: {query}")
        debug_print(f"🔥 БД: params={params}")

        cur.execute(query, params)
        conn.commit()
        return True
    except Exception as e:
        debug_print(f"🔥 БД: ОШИБКА: {e}")
        debug_print(f"🔥 БД: traceback: {traceback.format_exc()}")
        logger.error(f"Ошибка присоединения к челленджу: {e}")
        return False
    finally:
        conn.close()


@log_call
def leave_challenge(user_id, challenge_id):
    """Удаляет пользователя из челленджа"""
    debug_print(f"🔥 БД: leave_challenge: ВЫЗВАНА")
    debug_print(f"🔥 БД: leave_challenge: user_id={user_id}")
    debug_print(f"🔥 БД: leave_challenge: challenge_id={challenge_id}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: leave_challenge вызвана с user_id={user_id}, challenge_id={challenge_id}")

    conn = get_connection()
    cur = conn.cursor()

    if IS_POSTGRES:
        query1 = "DELETE FROM user_challenges WHERE user_id = %s AND challenge_id = %s"
        query2 = "DELETE FROM user_challenge_progress WHERE user_id = %s AND challenge_id = %s"
        params = (user_id, challenge_id)
    else:
        query1 = "DELETE FROM user_challenges WHERE user_id = ? AND challenge_id = ?"
        query2 = "DELETE FROM user_challenge_progress WHERE user_id = ? AND challenge_id = ?"
        params = (user_id, challenge_id)

    debug_print(f"🔥 БД: SQL: {query1}")
    debug_print(f"🔥 БД: SQL: {query2}")
    debug_print(f"🔥 БД: params={params}")

    cur.execute(query1, params)
    cur.execute(query2, params)
    conn.commit()
    conn.close()

    debug_print(f"🔥 БД: leave_challenge: ВОЗВРАТ None")
    return None


@log_call
def get_user_challenges(user_id):
    """Возвращает челленджи пользователя"""
    debug_print(f"🔥 БД: get_user_challenges: ВЫЗВАНА")
    debug_print(f"🔥 БД: get_user_challenges: user_id={user_id}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: get_user_challenges вызвана с user_id={user_id}")

    conn = get_connection()
    cur = conn.cursor()

    if IS_POSTGRES:
        query = """
                SELECT c.id, c.target_type, c.target_id, c.target_value, c.metric, c.bonus_points
                FROM user_challenges uc
                         JOIN challenges c ON uc.challenge_id = c.id
                WHERE uc.user_id = %s \
                  AND uc.completed = FALSE \
                """
        params = (user_id,)
    else:
        query = """
                SELECT c.id, c.target_type, c.target_id, c.target_value, c.metric, c.bonus_points
                FROM user_challenges uc
                         JOIN challenges c ON uc.challenge_id = c.id
                WHERE uc.user_id = ? \
                  AND uc.completed = FALSE \
                """
        params = (user_id,)

    debug_print(f"🔥 БД: SQL: {query[:200]}")
    debug_print(f"🔥 БД: params={params}")

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    debug_print(f"🔥 БД: get_user_challenges: ВОЗВРАТ {len(rows)} записей")
    return rows


@log_call
def get_user_challenges_with_details(user_id):
    """Возвращает челленджи пользователя с деталями"""
    debug_print(f"🔥 БД: get_user_challenges_with_details: ВЫЗВАНА")
    debug_print(f"🔥 БД: get_user_challenges_with_details: user_id={user_id}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: get_user_challenges_with_details вызвана с user_id={user_id}")

    conn = get_connection()
    cur = conn.cursor()

    if IS_POSTGRES:
        query = """
                SELECT c.id, \
                       c.name, \
                       c.target_type, \
                       c.target_id, \
                       c.metric, \
                       c.target_value, \
                       c.bonus_points,
                       c.start_date, \
                       c.end_date,
                       COALESCE(p.current_value, '0') as current_value,
                       COALESCE(e.name, cx.name)      as target_name
                FROM user_challenges uc
                         JOIN challenges c ON uc.challenge_id = c.id
                         LEFT JOIN user_challenge_progress p ON c.id = p.challenge_id AND p.user_id = uc.user_id
                         LEFT JOIN exercises e ON c.target_type = 'exercise' AND c.target_id = e.id
                         LEFT JOIN complexes cx ON c.target_type = 'complex' AND c.target_id = cx.id
                WHERE uc.user_id = %s \
                """
        params = (user_id,)
    else:
        query = """
                SELECT c.id, \
                       c.name, \
                       c.target_type, \
                       c.target_id, \
                       c.metric, \
                       c.target_value, \
                       c.bonus_points,
                       c.start_date, \
                       c.end_date,
                       COALESCE(p.current_value, '0') as current_value,
                       COALESCE(e.name, cx.name)      as target_name
                FROM user_challenges uc
                         JOIN challenges c ON uc.challenge_id = c.id
                         LEFT JOIN user_challenge_progress p ON c.id = p.challenge_id AND p.user_id = uc.user_id
                         LEFT JOIN exercises e ON c.target_type = 'exercise' AND c.target_id = e.id
                         LEFT JOIN complexes cx ON c.target_type = 'complex' AND c.target_id = cx.id
                WHERE uc.user_id = ? \
                """
        params = (user_id,)

    debug_print(f"🔥 БД: SQL: {query[:200]}")
    debug_print(f"🔥 БД: params={params}")

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    debug_print(f"🔥 БД: get_user_challenges_with_details: ВОЗВРАТ {len(rows)} записей")
    return rows


@log_call
def update_challenge_progress(user_id, challenge_id, result_value):
    """Обновляет прогресс пользователя в челлендже"""
    debug_print(f"🔥 БД: update_challenge_progress: ВЫЗВАНА")
    debug_print(f"🔥 БД: update_challenge_progress: user_id={user_id}")
    debug_print(f"🔥 БД: update_challenge_progress: challenge_id={challenge_id}")
    debug_print(f"🔥 БД: update_challenge_progress: result_value={result_value}")

    if DEBUG_MODE:
        debug_print(
            f"🔹 БД: update_challenge_progress вызвана с user_id={user_id}, challenge_id={challenge_id}, result_value={result_value}")

    conn = get_connection()
    cur = conn.cursor()

    if IS_POSTGRES:
        query = """
                INSERT INTO user_challenge_progress (user_id, challenge_id, current_value)
                VALUES (%s, %s, %s) ON CONFLICT (user_id, challenge_id) DO \
                UPDATE SET
                    current_value = EXCLUDED.current_value, \
                    updated_at = CURRENT_TIMESTAMP \
                """
        params = (user_id, challenge_id, result_value)
    else:
        query = """
            INSERT OR REPLACE INTO user_challenge_progress (user_id, challenge_id, current_value, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """
        params = (user_id, challenge_id, result_value)

    debug_print(f"🔥 БД: SQL: {query[:200]}")
    debug_print(f"🔥 БД: params={params}")

    cur.execute(query, params)
    conn.commit()
    conn.close()

    debug_print(f"🔥 БД: update_challenge_progress: ВОЗВРАТ None")
    return None


@log_call
def check_challenge_completion(user_id, challenge_id, target_value, metric):
    """Проверяет, завершён ли челлендж"""
    debug_print(f"🔥 БД: check_challenge_completion: ВЫЗВАНА")
    debug_print(f"🔥 БД: check_challenge_completion: user_id={user_id}")
    debug_print(f"🔥 БД: check_challenge_completion: challenge_id={challenge_id}")
    debug_print(f"🔥 БД: check_challenge_completion: target_value={target_value}")
    debug_print(f"🔥 БД: check_challenge_completion: metric={metric}")

    if DEBUG_MODE:
        debug_print(
            f"🔹 БД: check_challenge_completion вызвана с user_id={user_id}, challenge_id={challenge_id}, target_value={target_value}, metric={metric}")

    conn = get_connection()
    cur = conn.cursor()

    query = "SELECT current_value FROM user_challenge_progress WHERE user_id = %s AND challenge_id = %s" if IS_POSTGRES else "SELECT current_value FROM user_challenge_progress WHERE user_id = ? AND challenge_id = ?"
    params = (user_id, challenge_id)

    debug_print(f"🔥 БД: SQL: {query}")
    debug_print(f"🔥 БД: params={params}")

    if IS_POSTGRES:
        cur.execute(query, params)
    else:
        cur.execute(query, params)

    row = cur.fetchone()
    conn.close()

    if not row:
        debug_print(f"🔥 БД: check_challenge_completion: ВОЗВРАТ False - нет прогресса")
        return False

    current = row[0]
    if metric == 'reps':
        result = int(current) >= int(target_value)
        debug_print(f"🔥 БД: check_challenge_completion: ВОЗВРАТ {result}")
        return result
    else:
        # Для времени нужно сравнивать секунды
        try:
            current_seconds = sum(int(x) * 60 ** i for i, x in enumerate(reversed(current.split(':'))))
            target_seconds = sum(int(x) * 60 ** i for i, x in enumerate(reversed(target_value.split(':'))))
            result = current_seconds <= target_seconds
            debug_print(f"🔥 БД: check_challenge_completion: ВОЗВРАТ {result}")
            return result
        except:
            debug_print(f"🔥 БД: check_challenge_completion: ВОЗВРАТ False - ошибка парсинга")
            return False


@log_call
def complete_challenge(user_id, challenge_id):
    """Завершает челлендж и начисляет бонус"""
    debug_print(f"🔥 БД: complete_challenge: ВЫЗВАНА")
    debug_print(f"🔥 БД: complete_challenge: user_id={user_id}")
    debug_print(f"🔥 БД: complete_challenge: challenge_id={challenge_id}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: complete_challenge вызвана с user_id={user_id}, challenge_id={challenge_id}")

    conn = get_connection()
    cur = conn.cursor()
    try:
        # Получаем бонус
        if IS_POSTGRES:
            query = "SELECT bonus_points FROM challenges WHERE id = %s"
            params = (challenge_id,)
        else:
            query = "SELECT bonus_points FROM challenges WHERE id = ?"
            params = (challenge_id,)

        debug_print(f"🔥 БД: SQL: {query}")
        debug_print(f"🔥 БД: params={params}")

        cur.execute(query, params)
        row = cur.fetchone()
        bonus = row[0] if row else 0

        # Отмечаем челлендж как завершённый
        if IS_POSTGRES:
            query = "UPDATE user_challenges SET completed = TRUE, completed_at = CURRENT_TIMESTAMP WHERE user_id = %s AND challenge_id = %s"
            params = (user_id, challenge_id)
        else:
            query = "UPDATE user_challenges SET completed = TRUE, completed_at = CURRENT_TIMESTAMP WHERE user_id = ? AND challenge_id = ?"
            params = (user_id, challenge_id)

        debug_print(f"🔥 БД: SQL: {query}")
        debug_print(f"🔥 БД: params={params}")

        cur.execute(query, params)

        # Начисляем бонус
        add_points_to_scoreboard(user_id, bonus)

        conn.commit()
        return True
    except Exception as e:
        debug_print(f"🔥 БД: ОШИБКА: {e}")
        debug_print(f"🔥 БД: traceback: {traceback.format_exc()}")
        logger.error(f"Ошибка завершения челленджа: {e}")
        return False
    finally:
        conn.close()


# ========== ФУНКЦИИ ДЛЯ ДОСТИЖЕНИЙ ==========

@log_call
def check_and_award_achievements(user_id):
    """Проверяет и выдаёт достижения"""
    debug_print(f"🔥 БД: check_and_award_achievements: ВЫЗВАНА")
    debug_print(f"🔥 БД: check_and_award_achievements: user_id={user_id}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: check_and_award_achievements вызвана с user_id={user_id}")

    conn = get_connection()
    cur = conn.cursor()

    # Получаем все достижения
    query = "SELECT id, name, description, condition_type, condition_value, icon FROM achievements"
    debug_print(f"🔥 БД: SQL: {query}")

    if IS_POSTGRES:
        cur.execute(query)
    else:
        cur.execute(query)
    achievements = cur.fetchall()

    # Получаем уже полученные достижения
    query = "SELECT achievement_id FROM user_achievements WHERE user_id = %s" if IS_POSTGRES else "SELECT achievement_id FROM user_achievements WHERE user_id = ?"
    params = (user_id,)

    debug_print(f"🔥 БД: SQL: {query}")
    debug_print(f"🔥 БД: params={params}")

    if IS_POSTGRES:
        cur.execute(query, params)
    else:
        cur.execute(query, params)
    earned = {row[0] for row in cur.fetchall()}

    # Получаем количество тренировок
    query = "SELECT COUNT(*) FROM workouts WHERE user_id = %s" if IS_POSTGRES else "SELECT COUNT(*) FROM workouts WHERE user_id = ?"
    params = (user_id,)

    debug_print(f"🔥 БД: SQL: {query}")
    debug_print(f"🔥 БД: params={params}")

    if IS_POSTGRES:
        cur.execute(query, params)
    else:
        cur.execute(query, params)
    workout_count = cur.fetchone()[0]

    # Получаем лучший результат
    query = "SELECT COUNT(*) FROM workouts WHERE user_id = %s AND is_best = TRUE" if IS_POSTGRES else "SELECT COUNT(*) FROM workouts WHERE user_id = ? AND is_best = TRUE"
    params = (user_id,)

    debug_print(f"🔥 БД: SQL: {query}")
    debug_print(f"🔥 БД: params={params}")

    if IS_POSTGRES:
        cur.execute(query, params)
    else:
        cur.execute(query, params)
    best_count = cur.fetchone()[0]

    new_achievements = []

    for ach in achievements:
        ach_id, name, desc, cond_type, cond_value, icon = ach

        if ach_id in earned:
            continue

        earned_flag = False
        if cond_type == 'workout_count' and workout_count >= int(cond_value):
            earned_flag = True
        elif cond_type == 'best_result' and best_count >= int(cond_value):
            earned_flag = True

        if earned_flag:
            if IS_POSTGRES:
                query = "INSERT INTO user_achievements (user_id, achievement_id) VALUES (%s, %s)"
                params = (user_id, ach_id)
            else:
                query = "INSERT INTO user_achievements (user_id, achievement_id) VALUES (?, ?)"
                params = (user_id, ach_id)

            debug_print(f"🔥 БД: SQL: {query}")
            debug_print(f"🔥 БД: params={params}")

            cur.execute(query, params)
            new_achievements.append(ach)

    conn.commit()
    conn.close()

    debug_print(f"🔥 БД: check_and_award_achievements: новые достижения={new_achievements}")
    debug_print(f"🔥 БД: check_and_award_achievements: ВОЗВРАТ {new_achievements}")
    return new_achievements


# ========== ФУНКЦИИ ДЛЯ ПУБЛИКАЦИЙ ==========

@log_call
def save_published_post(post_type, item_id, channel_id, message_id):
    """Сохраняет опубликованный пост"""
    debug_print(f"🔥 БД: save_published_post: ВЫЗВАНА")
    debug_print(f"🔥 БД: save_published_post: post_type={post_type}")
    debug_print(f"🔥 БД: save_published_post: item_id={item_id}")
    debug_print(f"🔥 БД: save_published_post: channel_id={channel_id}")
    debug_print(f"🔥 БД: save_published_post: message_id={message_id}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: save_published_post вызвана с post_type={post_type}, item_id={item_id}")

    conn = get_connection()
    cur = conn.cursor()

    if IS_POSTGRES:
        query = "INSERT INTO published_posts (type, item_id, channel_id, message_id) VALUES (%s, %s, %s, %s)"
        params = (post_type, item_id, channel_id, message_id)
    else:
        query = "INSERT INTO published_posts (type, item_id, channel_id, message_id) VALUES (?, ?, ?, ?)"
        params = (post_type, item_id, channel_id, message_id)

    debug_print(f"🔥 БД: SQL: {query}")
    debug_print(f"🔥 БД: params={params}")

    cur.execute(query, params)
    conn.commit()
    conn.close()

    debug_print(f"🔥 БД: save_published_post: ВОЗВРАТ None")
    return None


@log_call
def get_published_post_by_message_id(message_id):
    """Получает опубликованный пост по ID сообщения"""
    debug_print(f"🔥 БД: get_published_post_by_message_id: ВЫЗВАНА")
    debug_print(f"🔥 БД: get_published_post_by_message_id: message_id={message_id}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: get_published_post_by_message_id вызвана с message_id={message_id}")

    conn = get_connection()
    cur = conn.cursor()

    query = "SELECT * FROM published_posts WHERE message_id = %s" if IS_POSTGRES else "SELECT * FROM published_posts WHERE message_id = ?"
    params = (message_id,)

    debug_print(f"🔥 БД: SQL: {query}")
    debug_print(f"🔥 БД: params={params}")

    if IS_POSTGRES:
        cur.execute(query, params)
    else:
        cur.execute(query, params)

    row = cur.fetchone()
    conn.close()

    debug_print(f"🔥 БД: get_published_post_by_message_id: ВОЗВРАТ {row}")
    return row


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

@log_call
def backup_database():
    """Создаёт резервную копию базы данных (только для SQLite)"""
    debug_print(f"🔥 БД: backup_database: ВЫЗВАНА")

    if DEBUG_MODE:
        debug_print("🔹 БД: backup_database вызвана")

    if not IS_POSTGRES:
        import shutil
        backup_path = "workouts_backup.db"
        shutil.copy2(DB_NAME, backup_path)
        logger.info("✅ Резервная копия базы создана: workouts_backup.db")

        size = os.path.getsize(backup_path) if os.path.exists(backup_path) else 0
        debug_print(f"🔥 БД: backup_database: backup_path={backup_path}")
        debug_print(f"🔥 БД: backup_database: размер={size} байт")
        debug_print(f"🔥 БД: backup_database: ВОЗВРАТ True")
        return True

    debug_print(f"🔥 БД: backup_database: ВОЗВРАТ False (не SQLite)")
    return False


@log_call
def recalculate_rankings(period_days=7):
    """Пересчитывает рейтинг (только для SQLite)"""
    debug_print(f"🔥 БД: recalculate_rankings: ВЫЗВАНА")
    debug_print(f"🔥 БД: recalculate_rankings: period_days={period_days}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: recalculate_rankings вызвана с period_days={period_days}")

    # Для PostgreSQL этот функционал будет реализован отдельно
    if not IS_POSTGRES:
        logger.info("Рекомендуется настроить пересчёт рейтинга через cron")
        debug_print(f"🔥 БД: recalculate_rankings: ВОЗВРАТ None")
    return None


@log_call
def get_user_activity_calendar(user_id, year, month):
    """Возвращает календарь активности пользователя"""
    debug_print(f"🔥 БД: get_user_activity_calendar: ВЫЗВАНА")
    debug_print(f"🔥 БД: get_user_activity_calendar: user_id={user_id}")
    debug_print(f"🔥 БД: get_user_activity_calendar: year={year}")
    debug_print(f"🔥 БД: get_user_activity_calendar: month={month}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: get_user_activity_calendar вызвана с user_id={user_id}, year={year}, month={month}")

    conn = get_connection()
    cur = conn.cursor()

    start_date = f"{year}-{month:02d}-01"
    # Определяем последний день месяца
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"

    if IS_POSTGRES:
        query = """
                SELECT date, COUNT (*) as workouts
                FROM workouts
                WHERE user_id = %s
                  AND date >= %s
                  AND date
                    < %s
                GROUP BY date
                ORDER BY date \
                """
        params = (user_id, start_date, end_date)
    else:
        query = """
                SELECT date, COUNT (*) as workouts
                FROM workouts
                WHERE user_id = ?
                  AND date >= ?
                  AND date
                    < ?
                GROUP BY date
                ORDER BY date \
                """
        params = (user_id, start_date, end_date)

    debug_print(f"🔥 БД: SQL: {query}")
    debug_print(f"🔥 БД: params={params}")

    cur.execute(query, params)

    rows = cur.fetchall()
    conn.close()

    # Формируем словарь {день: количество тренировок}
    result = {}
    for row in rows:
        if IS_POSTGRES:
            day = row[0].day
        else:
            day = int(row[0].split('-')[2])
        result[day] = row[1]

    debug_print(f"🔥 БД: get_user_activity_calendar: ВОЗВРАТ {result}")
    return result


@log_call
def set_exercise_week(exercise_id, week):
    """Устанавливает неделю для упражнения"""
    debug_print(f"🔥 БД: set_exercise_week: ВЫЗВАНА")
    debug_print(f"🔥 БД: set_exercise_week: exercise_id={exercise_id}")
    debug_print(f"🔥 БД: set_exercise_week: week={week}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: set_exercise_week вызвана с exercise_id={exercise_id}, week={week}")

    conn = get_connection()
    cur = conn.cursor()
    try:
        if IS_POSTGRES:
            query = "UPDATE exercises SET week = %s WHERE id = %s"
            params = (week, exercise_id)
        else:
            query = "UPDATE exercises SET week = ? WHERE id = ?"
            params = (week, exercise_id)

        debug_print(f"🔥 БД: SQL: {query}")
        debug_print(f"🔥 БД: params={params}")

        cur.execute(query, params)
        conn.commit()
        return True
    except Exception as e:
        debug_print(f"🔥 БД: ОШИБКА: {e}")
        debug_print(f"🔥 БД: traceback: {traceback.format_exc()}")
        logger.error(f"Ошибка установки недели упражнения: {e}")
        return False
    finally:
        conn.close()


@log_call
def set_exercise_points(exercise_id, points):
    """Устанавливает баллы для упражнения"""
    debug_print(f"🔥 БД: set_exercise_points: ВЫЗВАНА")
    debug_print(f"🔥 БД: set_exercise_points: exercise_id={exercise_id}")
    debug_print(f"🔥 БД: set_exercise_points: points={points}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: set_exercise_points вызвана с exercise_id={exercise_id}, points={points}")

    conn = get_connection()
    cur = conn.cursor()
    try:
        if IS_POSTGRES:
            query = "UPDATE exercises SET points = %s WHERE id = %s"
            params = (points, exercise_id)
        else:
            query = "UPDATE exercises SET points = ? WHERE id = ?"
            params = (points, exercise_id)

        debug_print(f"🔥 БД: SQL: {query}")
        debug_print(f"🔥 БД: params={params}")

        cur.execute(query, params)
        conn.commit()
        return True
    except Exception as e:
        debug_print(f"🔥 БД: ОШИБКА: {e}")
        debug_print(f"🔥 БД: traceback: {traceback.format_exc()}")
        logger.error(f"Ошибка установки баллов упражнения: {e}")
        return False
    finally:
        conn.close()


@log_call
def get_user_stats(user_id, period=None):
    """Возвращает статистику пользователя (баллы и количество тренировок)"""
    debug_print(f"🔥 БД: get_user_stats: ВЫЗВАНА")
    debug_print(f"🔥 БД: get_user_stats: user_id={user_id}")
    debug_print(f"🔥 БД: get_user_stats: period={period}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: get_user_stats вызвана с user_id={user_id}, period={period}")

    conn = get_connection()
    cur = conn.cursor()

    # Получаем общее количество баллов
    total_points = get_user_scoreboard_total(user_id)

    # Получаем количество тренировок
    if period:
        if IS_POSTGRES:
            query = "SELECT COUNT(*) FROM workouts WHERE user_id = %s AND date >= NOW() - INTERVAL '1 %s'"
            params = (user_id, period)
        else:
            query = "SELECT COUNT(*) FROM workouts WHERE user_id = ? AND date >= datetime('now', '-1 ' || ?)"
            params = (user_id, period)
    else:
        if IS_POSTGRES:
            query = "SELECT COUNT(*) FROM workouts WHERE user_id = %s"
            params = (user_id,)
        else:
            query = "SELECT COUNT(*) FROM workouts WHERE user_id = ?"
            params = (user_id,)

    debug_print(f"🔥 БД: SQL: {query}")
    debug_print(f"🔥 БД: params={params}")

    cur.execute(query, params)
    workout_count = cur.fetchone()[0]
    conn.close()

    debug_print(f"🔥 БД: get_user_stats: ВОЗВРАТ ({total_points}, {workout_count})")
    return total_points, workout_count


@log_call
def get_leaderboard(period=None, league=None):
    """Возвращает таблицу лидеров (совместимость со старым кодом)"""
    debug_print(f"🔥 БД: get_leaderboard: ВЫЗВАНА")
    debug_print(f"🔥 БД: get_leaderboard: period={period}")
    debug_print(f"🔥 БД: get_leaderboard: league={league}")

    if DEBUG_MODE:
        debug_print(f"🔹 БД: get_leaderboard вызвана с period={period}, league={league}")

    result = get_leaderboard_from_scoreboard(period or 'total')
    debug_print(f"🔥 БД: get_leaderboard: ВОЗВРАТ {len(result)} записей")
    return result


@log_call
def get_active_challenges():
    """Возвращает активные челленджи (совместимость со старым кодом)"""
    debug_print(f"🔥 БД: get_active_challenges: ВЫЗВАНА")

    if DEBUG_MODE:
        debug_print("🔹 БД: get_active_challenges вызвана")

    result = get_challenges_by_status('active')
    debug_print(f"🔥 БД: get_active_challenges: ВОЗВРАТ {len(result)} записей")
    return result


@log_call
def fix_scoreboard_duplicates():
    """Очищает дубликаты в scoreboard и пересчитывает баллы"""
    debug_print("🔥 БД: fix_scoreboard_duplicates: ВЫЗВАНА")

    conn = get_connection()
    cur = conn.cursor()

    # Очищаем таблицу scoreboard
    cur.execute("DELETE FROM scoreboard")
    debug_print("🔥 БД: scoreboard очищена")

    # Пересчитываем баллы из тренировок
    if IS_POSTGRES:
        query = """
                INSERT INTO scoreboard (user_id, period, points)
                SELECT w.user_id, \
                       'total', \
                       COALESCE(SUM( \
                                        CASE \
                                            WHEN w.exercise_id IS NOT NULL \
                                                THEN (SELECT points FROM exercises WHERE id = w.exercise_id) \
                                            WHEN w.complex_id IS NOT NULL \
                                                THEN (SELECT points FROM complexes WHERE id = w.complex_id) \
                                            ELSE 0 \
                                            END \
                                ), 0) as points
                FROM workouts w
                WHERE w.result_value IS NOT NULL
                GROUP BY w.user_id \
                """
    else:
        # SQLite
        query = """
                INSERT INTO scoreboard (user_id, period, points)
                SELECT w.user_id, \
                       'total', \
                       COALESCE(SUM( \
                                        CASE \
                                            WHEN w.exercise_id IS NOT NULL \
                                                THEN (SELECT points FROM exercises WHERE id = w.exercise_id) \
                                            WHEN w.complex_id IS NOT NULL \
                                                THEN (SELECT points FROM complexes WHERE id = w.complex_id) \
                                            ELSE 0 \
                                            END \
                                ), 0) as points
                FROM workouts w
                WHERE w.result_value IS NOT NULL
                GROUP BY w.user_id \
                """

    debug_print(f"🔥 БД: SQL: {query[:200]}")
    cur.execute(query)
    conn.commit()

    # Проверяем результат
    cur.execute("SELECT COUNT(*) FROM scoreboard")
    count = cur.fetchone()[0]
    debug_print(f"🔥 БД: в scoreboard добавлено {count} записей")

    conn.close()
    debug_print("🔥 БД: fix_scoreboard_duplicates: ВОЗВРАТ None")
    return None

