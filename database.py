import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Определяем, в какой среде работаем
DATABASE_URL = os.getenv("DATABASE_URL")
IS_POSTGRES = DATABASE_URL and DATABASE_URL.startswith("postgresql")

# Для SQLite используем локальный файл
DB_NAME = "workouts.db"


def get_connection():
    """Возвращает соединение с БД (PostgreSQL или SQLite)"""
    if IS_POSTGRES:
        return psycopg2.connect(DATABASE_URL)
    else:
        return sqlite3.connect(DB_NAME)


def init_db():
    """Инициализирует базу данных (создаёт таблицы, если их нет)"""
    conn = get_connection()
    cur = conn.cursor()

    if IS_POSTGRES:
        # PostgreSQL синтаксис
        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                level TEXT DEFAULT 'beginner',
                total_points INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS exercises (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE,
                description TEXT,
                metric TEXT,
                points INTEGER,
                week INTEGER,
                difficulty TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS workouts (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                exercise_id INTEGER,
                complex_id INTEGER,
                result_value TEXT,
                video_link TEXT,
                comment TEXT,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_best BOOLEAN DEFAULT FALSE,
                type TEXT,
                metric TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS complexes (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE,
                description TEXT,
                type TEXT,
                points INTEGER
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS complex_exercises (
                id SERIAL PRIMARY KEY,
                complex_id INTEGER,
                exercise_id INTEGER,
                reps INTEGER,
                order_index INTEGER
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS challenges (
                id SERIAL PRIMARY KEY,
                name TEXT,
                description TEXT,
                target_type TEXT,
                target_id INTEGER,
                metric TEXT,
                target_value TEXT,
                start_date DATE,
                end_date DATE,
                bonus_points INTEGER,
                is_active BOOLEAN DEFAULT TRUE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_challenges (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                challenge_id INTEGER,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed BOOLEAN DEFAULT FALSE,
                completed_at TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_challenge_progress (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                challenge_id INTEGER,
                current_value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS achievements (
                id SERIAL PRIMARY KEY,
                name TEXT,
                description TEXT,
                condition_type TEXT,
                condition_value TEXT,
                icon TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_achievements (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                achievement_id INTEGER,
                earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS published_posts (
                id SERIAL PRIMARY KEY,
                type TEXT,
                item_id INTEGER,
                channel_id INTEGER,
                message_id INTEGER,
                published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS scoreboard (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                period TEXT,
                points INTEGER
            )
        """)

    else:
        # SQLite синтаксис (для локальной разработки)
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT, username TEXT, level TEXT DEFAULT 'beginner', total_points INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS exercises (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, description TEXT, metric TEXT, points INTEGER, week INTEGER, difficulty TEXT);
            CREATE TABLE IF NOT EXISTS workouts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, exercise_id INTEGER, complex_id INTEGER, result_value TEXT, video_link TEXT, comment TEXT, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_best BOOLEAN DEFAULT FALSE, type TEXT, metric TEXT);
            CREATE TABLE IF NOT EXISTS complexes (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, description TEXT, type TEXT, points INTEGER);
            CREATE TABLE IF NOT EXISTS complex_exercises (id INTEGER PRIMARY KEY AUTOINCREMENT, complex_id INTEGER, exercise_id INTEGER, reps INTEGER, order_index INTEGER);
            CREATE TABLE IF NOT EXISTS challenges (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, description TEXT, target_type TEXT, target_id INTEGER, metric TEXT, target_value TEXT, start_date DATE, end_date DATE, bonus_points INTEGER, is_active BOOLEAN DEFAULT TRUE);
            CREATE TABLE IF NOT EXISTS user_challenges (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, challenge_id INTEGER, joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, completed BOOLEAN DEFAULT FALSE, completed_at TIMESTAMP);
            CREATE TABLE IF NOT EXISTS user_challenge_progress (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, challenge_id INTEGER, current_value TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS achievements (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, description TEXT, condition_type TEXT, condition_value TEXT, icon TEXT);
            CREATE TABLE IF NOT EXISTS user_achievements (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, achievement_id INTEGER, earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS published_posts (id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, item_id INTEGER, channel_id INTEGER, message_id INTEGER, published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS scoreboard (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, period TEXT, points INTEGER);
        """)

    conn.commit()
    conn.close()

    # Добавляем базовые достижения
    init_achievements()


def init_achievements():
    """Добавляет базовые достижения, если их нет"""
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


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ДАННЫМИ ==========

def get_setting(key):
    """Получает настройку из таблицы settings"""
    conn = get_connection()
    cur = conn.cursor()
    if IS_POSTGRES:
        cur.execute("SELECT value FROM settings WHERE key = %s", (key,))
    else:
        cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def set_setting(key, value):
    """Сохраняет настройку в таблицу settings"""
    conn = get_connection()
    cur = conn.cursor()
    if IS_POSTGRES:
        cur.execute(
            "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            (key, value)
        )
    else:
        cur.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
    conn.commit()
    conn.close()


def add_user(user_id, first_name, last_name, username, level='beginner'):
    """Добавляет или обновляет пользователя"""
    conn = get_connection()
    cur = conn.cursor()
    if IS_POSTGRES:
        cur.execute(
            "INSERT INTO users (id, first_name, last_name, username, level) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (id) DO UPDATE SET first_name = EXCLUDED.first_name, last_name = EXCLUDED.last_name, username = EXCLUDED.username",
            (user_id, first_name, last_name, username, level)
        )
    else:
        cur.execute(
            "INSERT OR REPLACE INTO users (id, first_name, last_name, username, level) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, first_name, last_name, username, level)
        )
    conn.commit()
    conn.close()


def get_user_level(user_id):
    """Возвращает уровень пользователя"""
    conn = get_connection()
    cur = conn.cursor()
    if IS_POSTGRES:
        cur.execute("SELECT level FROM users WHERE id = %s", (user_id,))
    else:
        cur.execute("SELECT level FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 'beginner'


def set_user_level(user_id, level):
    """Устанавливает уровень пользователя"""
    conn = get_connection()
    cur = conn.cursor()
    if IS_POSTGRES:
        cur.execute(
            "UPDATE users SET level = %s WHERE id = %s",
            (level, user_id)
        )
    else:
        cur.execute(
            "UPDATE users SET level = ? WHERE id = ?",
            (level, user_id)
        )
    conn.commit()
    conn.close()
    return True


def get_exercises(active_only=True, week=None, difficulty=None):
    """Возвращает список упражнений"""
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

    if IS_POSTGRES:
        cur.execute(query, tuple(params))
    else:
        cur.execute(query, params)

    rows = cur.fetchall()
    conn.close()
    return rows


def get_all_exercises():
    """Возвращает все упражнения (7 полей: id, name, description, metric, points, week, difficulty)"""
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
            # SQLite вернул 6 полей (без description)
            result.append((row[0], row[1], "", row[2], row[3], row[4], row[5]))
        elif len(row) == 7:
            # PostgreSQL вернул 7 полей
            result.append(row)
        else:
            raise ValueError(f"Неверное количество полей в упражнении: {len(row)}")
    return result


def get_exercise_by_id(exercise_id):
    """Возвращает упражнение по ID"""
    conn = get_connection()
    cur = conn.cursor()
    if IS_POSTGRES:
        cur.execute("SELECT id, name, description, metric, points, week, difficulty FROM exercises WHERE id = %s", (exercise_id,))
    else:
        cur.execute("SELECT id, name, description, metric, points, week, difficulty FROM exercises WHERE id = ?", (exercise_id,))
    row = cur.fetchone()
    conn.close()
    return row


def add_exercise(name, description, metric, points, week=0, difficulty='beginner'):
    """Добавляет упражнение"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if IS_POSTGRES:
            cur.execute(
                "INSERT INTO exercises (name, description, metric, points, week, difficulty) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (name, description, metric, points, week, difficulty)
            )
        else:
            cur.execute(
                "INSERT INTO exercises (name, description, metric, points, week, difficulty) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (name, description, metric, points, week, difficulty)
            )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка добавления упражнения: {e}")
        return False
    finally:
        conn.close()


def delete_exercise(exercise_id):
    """Удаляет упражнение"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if IS_POSTGRES:
            cur.execute("DELETE FROM exercises WHERE id = %s", (exercise_id,))
        else:
            cur.execute("DELETE FROM exercises WHERE id = ?", (exercise_id,))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления упражнения: {e}")
        return False
    finally:
        conn.close()


# ========== ФУНКЦИИ ДЛЯ ТРЕНИРОВОК ==========

def add_workout(user_id, exercise_id=None, complex_id=None, result_value=None, video_link=None,
                user_level=None, comment=None, metric=None, notify_record_callback=None):
    """Добавляет тренировку и начисляет баллы"""
    conn = get_connection()
    cur = conn.cursor()

    # Определяем тип и баллы
    if exercise_id:
        ex = get_exercise_by_id(exercise_id)
        if not ex:
            conn.close()
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
        cur.execute(
            "INSERT INTO workouts (user_id, exercise_id, complex_id, result_value, video_link, comment, type, metric, date) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (user_id, exercise_id, complex_id, result_value, video_link, comment, workout_type, workout_metric, datetime.now())
        )
    else:
        cur.execute(
            "INSERT INTO workouts (user_id, exercise_id, complex_id, result_value, video_link, comment, type, metric, date) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, exercise_id, complex_id, result_value, video_link, comment, workout_type, workout_metric, datetime.now())
        )

    conn.commit()
    conn.close()

    # Начисляем баллы (через scoreboard)
    add_points_to_scoreboard(user_id, points)

    # Проверяем достижения
    new_achievements = check_and_award_achievements(user_id)

    # Уведомление (если нужно)
    if notify_record_callback:
        notify_record_callback(user_id, exercise_id or complex_id, result_value, workout_metric)

    return points, new_achievements


def get_user_workouts(user_id, limit=20):
    """Возвращает последние тренировки пользователя"""
    conn = get_connection()
    cur = conn.cursor()

    if IS_POSTGRES:
        cur.execute("""
            SELECT w.id, 
                   COALESCE(e.name, c.name) as name,
                   w.result_value, w.video_link, w.date, w.is_best, w.type, w.comment
            FROM workouts w
            LEFT JOIN exercises e ON w.exercise_id = e.id
            LEFT JOIN complexes c ON w.complex_id = c.id
            WHERE w.user_id = %s
            ORDER BY w.date DESC
            LIMIT %s
        """, (user_id, limit))
    else:
        cur.execute("""
            SELECT w.id, 
                   COALESCE(e.name, c.name) as name,
                   w.result_value, w.video_link, w.date, w.is_best, w.type, w.comment
            FROM workouts w
            LEFT JOIN exercises e ON w.exercise_id = e.id
            LEFT JOIN complexes c ON w.complex_id = c.id
            WHERE w.user_id = ?
            ORDER BY w.date DESC
            LIMIT ?
        """, (user_id, limit))

    rows = cur.fetchall()
    conn.close()
    return rows


# ========== ФУНКЦИИ ДЛЯ КОМПЛЕКСОВ ==========

def add_complex(name, description, type_, points):
    """Добавляет комплекс"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if IS_POSTGRES:
            cur.execute(
                "INSERT INTO complexes (name, description, type, points) VALUES (%s, %s, %s, %s) RETURNING id",
                (name, description, type_, points)
            )
            complex_id = cur.fetchone()[0]
        else:
            cur.execute(
                "INSERT INTO complexes (name, description, type, points) VALUES (?, ?, ?, ?)",
                (name, description, type_, points)
            )
            complex_id = cur.lastrowid
        conn.commit()
        return complex_id
    except Exception as e:
        logger.error(f"Ошибка добавления комплекса: {e}")
        return None
    finally:
        conn.close()


def get_all_complexes():
    """Возвращает все комплексы"""
    conn = get_connection()
    cur = conn.cursor()
    if IS_POSTGRES:
        cur.execute("SELECT id, name, description, type, points FROM complexes ORDER BY id")
    else:
        cur.execute("SELECT id, name, description, type, points FROM complexes ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return rows


def get_complex_by_id(complex_id):
    """Возвращает комплекс по ID"""
    conn = get_connection()
    cur = conn.cursor()
    if IS_POSTGRES:
        cur.execute("SELECT id, name, description, type, points FROM complexes WHERE id = %s", (complex_id,))
    else:
        cur.execute("SELECT id, name, description, type, points FROM complexes WHERE id = ?", (complex_id,))
    row = cur.fetchone()
    conn.close()
    return row


def add_complex_exercise(complex_id, exercise_id, reps):
    """Добавляет упражнение в комплекс"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if IS_POSTGRES:
            cur.execute(
                "INSERT INTO complex_exercises (complex_id, exercise_id, reps) VALUES (%s, %s, %s)",
                (complex_id, exercise_id, reps)
            )
        else:
            cur.execute(
                "INSERT INTO complex_exercises (complex_id, exercise_id, reps) VALUES (?, ?, ?)",
                (complex_id, exercise_id, reps)
            )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка добавления упражнения в комплекс: {e}")
        return False
    finally:
        conn.close()


def get_complex_exercises(complex_id):
    """Возвращает упражнения комплекса"""
    conn = get_connection()
    cur = conn.cursor()
    if IS_POSTGRES:
        cur.execute("""
            SELECT ce.id, ce.complex_id, e.id, e.name, ce.reps
            FROM complex_exercises ce
            JOIN exercises e ON ce.exercise_id = e.id
            WHERE ce.complex_id = %s
            ORDER BY ce.order_index
        """, (complex_id,))
    else:
        cur.execute("""
            SELECT ce.id, ce.complex_id, e.id, e.name, ce.reps
            FROM complex_exercises ce
            JOIN exercises e ON ce.exercise_id = e.id
            WHERE ce.complex_id = ?
            ORDER BY ce.order_index
        """, (complex_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


# ========== ФУНКЦИИ ДЛЯ РЕЙТИНГА ==========

def add_points_to_scoreboard(user_id, points, period='total'):
    """Добавляет баллы пользователю в scoreboard"""
    conn = get_connection()
    cur = conn.cursor()
    if IS_POSTGRES:
        cur.execute(
            "INSERT INTO scoreboard (user_id, period, points) VALUES (%s, %s, %s) "
            "ON CONFLICT (user_id, period) DO UPDATE SET points = scoreboard.points + EXCLUDED.points",
            (user_id, period, points)
        )
    else:
        cur.execute(
            "INSERT OR REPLACE INTO scoreboard (user_id, period, points) "
            "VALUES (?, ?, COALESCE((SELECT points FROM scoreboard WHERE user_id = ? AND period = ?), 0) + ?)",
            (user_id, period, user_id, period, points)
        )
    conn.commit()
    conn.close()


def get_user_scoreboard_total(user_id):
    """Возвращает общее количество баллов пользователя"""
    conn = get_connection()
    cur = conn.cursor()
    if IS_POSTGRES:
        cur.execute("SELECT points FROM scoreboard WHERE user_id = %s AND period = 'total'", (user_id,))
    else:
        cur.execute("SELECT points FROM scoreboard WHERE user_id = ? AND period = 'total'", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0


def get_leaderboard_from_scoreboard(period='total'):
    """Возвращает таблицу лидеров"""
    conn = get_connection()
    cur = conn.cursor()
    if IS_POSTGRES:
        cur.execute("""
            SELECT u.id, u.first_name, u.username, s.points
            FROM scoreboard s
            JOIN users u ON s.user_id = u.id
            WHERE s.period = %s
            ORDER BY s.points DESC
        """, (period,))
    else:
        cur.execute("""
            SELECT u.id, u.first_name, u.username, s.points
            FROM scoreboard s
            JOIN users u ON s.user_id = u.id
            WHERE s.period = ?
            ORDER BY s.points DESC
        """, (period,))
    rows = cur.fetchall()
    conn.close()
    return rows


# ========== ФУНКЦИИ ДЛЯ ЧЕЛЛЕНДЖЕЙ ==========

def add_challenge(name, description, target_type, target_id, metric, target_value,
                  start_date, end_date, bonus_points):
    """Добавляет челлендж"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if IS_POSTGRES:
            cur.execute("""
                INSERT INTO challenges (name, description, target_type, target_id, metric, target_value,
                                        start_date, end_date, bonus_points)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (name, description, target_type, target_id, metric, target_value, start_date, end_date, bonus_points))
        else:
            cur.execute("""
                INSERT INTO challenges (name, description, target_type, target_id, metric, target_value,
                                        start_date, end_date, bonus_points)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, description, target_type, target_id, metric, target_value, start_date, end_date, bonus_points))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка добавления челленджа: {e}")
        return False
    finally:
        conn.close()


def get_challenge_by_id(challenge_id):
    """Возвращает челлендж по ID"""
    conn = get_connection()
    cur = conn.cursor()
    if IS_POSTGRES:
        cur.execute("SELECT * FROM challenges WHERE id = %s", (challenge_id,))
    else:
        cur.execute("SELECT * FROM challenges WHERE id = ?", (challenge_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_challenges_by_status(status='active'):
    """Возвращает челленджи по статусу"""
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

    if IS_POSTGRES:
        cur.execute(f"SELECT * FROM challenges WHERE {condition} ORDER BY start_date", params)
    else:
        cur.execute(f"SELECT * FROM challenges WHERE {condition} ORDER BY start_date", params)

    rows = cur.fetchall()
    conn.close()
    return rows


def get_challenge_name(challenge_id):
    """Возвращает название челленджа"""
    conn = get_connection()
    cur = conn.cursor()
    if IS_POSTGRES:
        cur.execute("SELECT name FROM challenges WHERE id = %s", (challenge_id,))
    else:
        cur.execute("SELECT name FROM challenges WHERE id = ?", (challenge_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def join_challenge(user_id, challenge_id):
    """Добавляет пользователя в челлендж"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if IS_POSTGRES:
            cur.execute(
                "INSERT INTO user_challenges (user_id, challenge_id) VALUES (%s, %s) "
                "ON CONFLICT (user_id, challenge_id) DO NOTHING",
                (user_id, challenge_id)
            )
        else:
            cur.execute(
                "INSERT OR IGNORE INTO user_challenges (user_id, challenge_id) VALUES (?, ?)",
                (user_id, challenge_id)
            )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка присоединения к челленджу: {e}")
        return False
    finally:
        conn.close()


def leave_challenge(user_id, challenge_id):
    """Удаляет пользователя из челленджа"""
    conn = get_connection()
    cur = conn.cursor()
    if IS_POSTGRES:
        cur.execute("DELETE FROM user_challenges WHERE user_id = %s AND challenge_id = %s", (user_id, challenge_id))
        cur.execute("DELETE FROM user_challenge_progress WHERE user_id = %s AND challenge_id = %s", (user_id, challenge_id))
    else:
        cur.execute("DELETE FROM user_challenges WHERE user_id = ? AND challenge_id = ?", (user_id, challenge_id))
        cur.execute("DELETE FROM user_challenge_progress WHERE user_id = ? AND challenge_id = ?", (user_id, challenge_id))
    conn.commit()
    conn.close()


def get_user_challenges(user_id):
    """Возвращает челленджи пользователя"""
    conn = get_connection()
    cur = conn.cursor()
    if IS_POSTGRES:
        cur.execute("""
            SELECT c.id, c.target_type, c.target_id, c.target_value, c.metric, c.bonus_points
            FROM user_challenges uc
            JOIN challenges c ON uc.challenge_id = c.id
            WHERE uc.user_id = %s AND uc.completed = FALSE
        """, (user_id,))
    else:
        cur.execute("""
            SELECT c.id, c.target_type, c.target_id, c.target_value, c.metric, c.bonus_points
            FROM user_challenges uc
            JOIN challenges c ON uc.challenge_id = c.id
            WHERE uc.user_id = ? AND uc.completed = FALSE
        """, (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_user_challenges_with_details(user_id):
    """Возвращает челленджи пользователя с деталями"""
    conn = get_connection()
    cur = conn.cursor()
    if IS_POSTGRES:
        cur.execute("""
            SELECT c.id, c.name, c.target_type, c.target_id, c.metric, c.target_value, c.bonus_points,
                   c.start_date, c.end_date,
                   COALESCE(p.current_value, '0') as current_value,
                   COALESCE(e.name, cx.name) as target_name
            FROM user_challenges uc
            JOIN challenges c ON uc.challenge_id = c.id
            LEFT JOIN user_challenge_progress p ON c.id = p.challenge_id AND p.user_id = uc.user_id
            LEFT JOIN exercises e ON c.target_type = 'exercise' AND c.target_id = e.id
            LEFT JOIN complexes cx ON c.target_type = 'complex' AND c.target_id = cx.id
            WHERE uc.user_id = %s
        """, (user_id,))
    else:
        cur.execute("""
            SELECT c.id, c.name, c.target_type, c.target_id, c.metric, c.target_value, c.bonus_points,
                   c.start_date, c.end_date,
                   COALESCE(p.current_value, '0') as current_value,
                   COALESCE(e.name, cx.name) as target_name
            FROM user_challenges uc
            JOIN challenges c ON uc.challenge_id = c.id
            LEFT JOIN user_challenge_progress p ON c.id = p.challenge_id AND p.user_id = uc.user_id
            LEFT JOIN exercises e ON c.target_type = 'exercise' AND c.target_id = e.id
            LEFT JOIN complexes cx ON c.target_type = 'complex' AND c.target_id = cx.id
            WHERE uc.user_id = ?
        """, (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def update_challenge_progress(user_id, challenge_id, result_value):
    """Обновляет прогресс пользователя в челлендже"""
    conn = get_connection()
    cur = conn.cursor()
    if IS_POSTGRES:
        cur.execute("""
            INSERT INTO user_challenge_progress (user_id, challenge_id, current_value)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, challenge_id) DO UPDATE SET
                current_value = EXCLUDED.current_value,
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, challenge_id, result_value))
    else:
        cur.execute("""
            INSERT OR REPLACE INTO user_challenge_progress (user_id, challenge_id, current_value, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (user_id, challenge_id, result_value))
    conn.commit()
    conn.close()


def check_challenge_completion(user_id, challenge_id, target_value, metric):
    """Проверяет, завершён ли челлендж"""
    conn = get_connection()
    cur = conn.cursor()
    if IS_POSTGRES:
        cur.execute("SELECT current_value FROM user_challenge_progress WHERE user_id = %s AND challenge_id = %s",
                    (user_id, challenge_id))
    else:
        cur.execute("SELECT current_value FROM user_challenge_progress WHERE user_id = ? AND challenge_id = ?",
                    (user_id, challenge_id))
    row = cur.fetchone()
    conn.close()

    if not row:
        return False

    current = row[0]
    if metric == 'reps':
        return int(current) >= int(target_value)
    else:
        # Для времени нужно сравнивать секунды
        try:
            current_seconds = sum(int(x) * 60 ** i for i, x in enumerate(reversed(current.split(':'))))
            target_seconds = sum(int(x) * 60 ** i for i, x in enumerate(reversed(target_value.split(':'))))
            return current_seconds <= target_seconds
        except:
            return False


def complete_challenge(user_id, challenge_id):
    """Завершает челлендж и начисляет бонус"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Получаем бонус
        if IS_POSTGRES:
            cur.execute("SELECT bonus_points FROM challenges WHERE id = %s", (challenge_id,))
        else:
            cur.execute("SELECT bonus_points FROM challenges WHERE id = ?", (challenge_id,))
        row = cur.fetchone()
        bonus = row[0] if row else 0

        # Отмечаем челлендж как завершённый
        if IS_POSTGRES:
            cur.execute("""
                UPDATE user_challenges SET completed = TRUE, completed_at = CURRENT_TIMESTAMP
                WHERE user_id = %s AND challenge_id = %s
            """, (user_id, challenge_id))
        else:
            cur.execute("""
                UPDATE user_challenges SET completed = TRUE, completed_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND challenge_id = ?
            """, (user_id, challenge_id))

        # Начисляем бонус
        add_points_to_scoreboard(user_id, bonus)

        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка завершения челленджа: {e}")
        return False
    finally:
        conn.close()


# ========== ФУНКЦИИ ДЛЯ ДОСТИЖЕНИЙ ==========

def check_and_award_achievements(user_id):
    """Проверяет и выдаёт достижения"""
    conn = get_connection()
    cur = conn.cursor()

    # Получаем все достижения
    if IS_POSTGRES:
        cur.execute("SELECT id, name, description, condition_type, condition_value, icon FROM achievements")
    else:
        cur.execute("SELECT id, name, description, condition_type, condition_value, icon FROM achievements")
    achievements = cur.fetchall()

    # Получаем уже полученные достижения
    if IS_POSTGRES:
        cur.execute("SELECT achievement_id FROM user_achievements WHERE user_id = %s", (user_id,))
    else:
        cur.execute("SELECT achievement_id FROM user_achievements WHERE user_id = ?", (user_id,))
    earned = {row[0] for row in cur.fetchall()}

    # Получаем количество тренировок
    if IS_POSTGRES:
        cur.execute("SELECT COUNT(*) FROM workouts WHERE user_id = %s", (user_id,))
    else:
        cur.execute("SELECT COUNT(*) FROM workouts WHERE user_id = ?", (user_id,))
    workout_count = cur.fetchone()[0]

    # Получаем лучший результат
    if IS_POSTGRES:
        cur.execute("SELECT COUNT(*) FROM workouts WHERE user_id = %s AND is_best = TRUE", (user_id,))
    else:
        cur.execute("SELECT COUNT(*) FROM workouts WHERE user_id = ? AND is_best = TRUE", (user_id,))
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
                cur.execute(
                    "INSERT INTO user_achievements (user_id, achievement_id) VALUES (%s, %s)",
                    (user_id, ach_id)
                )
            else:
                cur.execute(
                    "INSERT INTO user_achievements (user_id, achievement_id) VALUES (?, ?)",
                    (user_id, ach_id)
                )
            new_achievements.append(ach)

    conn.commit()
    conn.close()
    return new_achievements


# ========== ФУНКЦИИ ДЛЯ ПУБЛИКАЦИЙ ==========

def save_published_post(post_type, item_id, channel_id, message_id):
    """Сохраняет опубликованный пост"""
    conn = get_connection()
    cur = conn.cursor()
    if IS_POSTGRES:
        cur.execute(
            "INSERT INTO published_posts (type, item_id, channel_id, message_id) VALUES (%s, %s, %s, %s)",
            (post_type, item_id, channel_id, message_id)
        )
    else:
        cur.execute(
            "INSERT INTO published_posts (type, item_id, channel_id, message_id) VALUES (?, ?, ?, ?)",
            (post_type, item_id, channel_id, message_id)
        )
    conn.commit()
    conn.close()


def get_published_post_by_message_id(message_id):
    """Получает опубликованный пост по ID сообщения"""
    conn = get_connection()
    cur = conn.cursor()
    if IS_POSTGRES:
        cur.execute("SELECT * FROM published_posts WHERE message_id = %s", (message_id,))
    else:
        cur.execute("SELECT * FROM published_posts WHERE message_id = ?", (message_id,))
    row = cur.fetchone()
    conn.close()
    return row


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def backup_database():
    """Создаёт резервную копию базы данных (только для SQLite)"""
    if not IS_POSTGRES:
        import shutil
        shutil.copy2(DB_NAME, "workouts_backup.db")
        logger.info("✅ Резервная копия базы создана: workouts_backup.db")


def recalculate_rankings(period_days=7):
    """Пересчитывает рейтинг (только для SQLite)"""
    # Для PostgreSQL этот функционал будет реализован отдельно
    if not IS_POSTGRES:
        logger.info("Рекомендуется настроить пересчёт рейтинга через cron")


def get_user_activity_calendar(user_id, year, month):
    """Возвращает календарь активности пользователя"""
    conn = get_connection()
    cur = conn.cursor()

    start_date = f"{year}-{month:02d}-01"
    # Определяем последний день месяца
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"

    if IS_POSTGRES:
        cur.execute("""
                    SELECT date, COUNT (*) as workouts
                    FROM workouts
                    WHERE user_id = %s
                      AND date >= %s
                      AND date
                        < %s
                    GROUP BY date
                    ORDER BY date
                    """, (user_id, start_date, end_date))
    else:
        cur.execute("""
                    SELECT date, COUNT (*) as workouts
                    FROM workouts
                    WHERE user_id = ?
                      AND date >= ?
                      AND date
                        < ?
                    GROUP BY date
                    ORDER BY date
                    """, (user_id, start_date, end_date))

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

    return result

def set_exercise_week(exercise_id, week):
    """Устанавливает неделю для упражнения"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if IS_POSTGRES:
            cur.execute("UPDATE exercises SET week = %s WHERE id = %s", (week, exercise_id))
        else:
            cur.execute("UPDATE exercises SET week = ? WHERE id = ?", (week, exercise_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка установки недели упражнения: {e}")
        return False
    finally:
        conn.close()

def set_exercise_points(exercise_id, points):
    """Устанавливает баллы для упражнения"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if IS_POSTGRES:
            cur.execute("UPDATE exercises SET points = %s WHERE id = %s", (points, exercise_id))
        else:
            cur.execute("UPDATE exercises SET points = ? WHERE id = ?", (points, exercise_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка установки баллов упражнения: {e}")
        return False
    finally:
        conn.close()


def get_user_stats(user_id, period=None):
    """Возвращает статистику пользователя (баллы и количество тренировок)"""
    conn = get_connection()
    cur = conn.cursor()

    # Получаем общее количество баллов
    total_points = get_user_scoreboard_total(user_id)

    # Получаем количество тренировок
    if period:
        if IS_POSTGRES:
            cur.execute("""
                        SELECT COUNT(*)
                        FROM workouts
                        WHERE user_id = %s AND date >= NOW() - INTERVAL '1 %s'
                        """, (user_id, period))
        else:
            cur.execute("""
                        SELECT COUNT(*)
                        FROM workouts
                        WHERE user_id = ? AND date >= datetime('now', '-1 ' || ?)
                        """, (user_id, period))
    else:
        if IS_POSTGRES:
            cur.execute("SELECT COUNT(*) FROM workouts WHERE user_id = %s", (user_id,))
        else:
            cur.execute("SELECT COUNT(*) FROM workouts WHERE user_id = ?", (user_id,))

    workout_count = cur.fetchone()[0]
    conn.close()

    return total_points, workout_count

def get_leaderboard(period=None, league=None):
    """Возвращает таблицу лидеров (совместимость со старым кодом)"""
    return get_leaderboard_from_scoreboard(period or 'total')


def get_active_challenges():
    """Возвращает активные челленджи (совместимость со старым кодом)"""
    return get_challenges_by_status('active')