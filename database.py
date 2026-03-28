import sqlite3
import logging
import json
import os
import calendar
import shutil
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DB_NAME = "workouts_test.db"
EXERCISES_JSON = "exercises.json"

def backup_database():
    """Создаёт резервную копию базы данных."""
    if os.path.exists(DB_NAME):
        backup_name = DB_NAME.replace('.db', '_backup.db')
        try:
            shutil.copy2(DB_NAME, backup_name)
            logger.info(f"✅ Резервная копия базы создана: {backup_name}")
        except Exception as e:
            logger.error(f"❌ Не удалось создать резервную копию: {e}")
    else:
        logger.info("База данных не найдена, резервная копия не создана.")

def init_db():
    """Инициализирует базу данных: создаёт все таблицы, если их нет."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # Таблица пользователей
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            level TEXT DEFAULT 'beginner',
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cur.fetchall()]
    if 'level' not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN level TEXT DEFAULT 'beginner'")
        logger.info("Колонка 'level' добавлена в users.")

    # Таблица для настроек бота
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    logger.info("Таблица 'settings' создана.")

    # Таблица для хранения системных настроек
    cur.execute("""
        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cur.execute("INSERT OR IGNORE INTO system_config (key, value) VALUES ('last_recalc', '0')")

    # Таблица scoreboard (рейтинг)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scoreboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            exercise_id INTEGER NOT NULL,
            period_start TIMESTAMP NOT NULL,
            period_end TIMESTAMP NOT NULL,
            rank INTEGER NOT NULL,
            points_awarded INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(exercise_id) REFERENCES exercises(id)
        )
    """)
    logger.info("Таблица 'scoreboard' создана.")

    # Таблица упражнений
    cur.execute("""
        CREATE TABLE IF NOT EXISTS exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            metric TEXT NOT NULL,
            points INTEGER DEFAULT 0,
            week INTEGER DEFAULT 0,
            difficulty TEXT DEFAULT 'beginner',
            is_active BOOLEAN DEFAULT 1
        )
    """)
    cur.execute("PRAGMA table_info(exercises)")
    columns = [col[1] for col in cur.fetchall()]
    if 'points' not in columns:
        cur.execute("ALTER TABLE exercises ADD COLUMN points INTEGER DEFAULT 0")
    if 'week' not in columns:
        cur.execute("ALTER TABLE exercises ADD COLUMN week INTEGER DEFAULT 0")
    if 'difficulty' not in columns:
        cur.execute("ALTER TABLE exercises ADD COLUMN difficulty TEXT DEFAULT 'beginner'")

    # Таблица комплексов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS complexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            type TEXT NOT NULL,
            points INTEGER DEFAULT 0,
            week INTEGER DEFAULT 0,
            difficulty TEXT DEFAULT 'beginner',
            is_active BOOLEAN DEFAULT 1
        )
    """)
    cur.execute("PRAGMA table_info(complexes)")
    columns = [col[1] for col in cur.fetchall()]
    if 'type' not in columns:
        cur.execute("ALTER TABLE complexes ADD COLUMN type TEXT DEFAULT 'for_time'")
        logger.info("Колонка 'type' добавлена в complexes.")

    # Таблица челленджей
    cur.execute("""
        CREATE TABLE IF NOT EXISTS challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            target_type TEXT NOT NULL,
            target_id INTEGER NOT NULL,
            metric TEXT NOT NULL,
            target_value TEXT NOT NULL,
            start_date TIMESTAMP NOT NULL,
            end_date TIMESTAMP NOT NULL,
            bonus_points INTEGER NOT NULL,
            is_active BOOLEAN DEFAULT 1
        )
    """)
    logger.info("Таблица 'challenges' создана.")

    # Таблица участия в челленджах
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_challenges (
            user_id INTEGER NOT NULL,
            challenge_id INTEGER NOT NULL,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed BOOLEAN DEFAULT 0,
            completed_at TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(challenge_id) REFERENCES challenges(id),
            PRIMARY KEY (user_id, challenge_id)
        )
    """)
    logger.info("Таблица 'user_challenges' создана.")

    # Таблица прогресса по челленджам
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_challenge_progress (
            user_id INTEGER NOT NULL,
            challenge_id INTEGER NOT NULL,
            current_value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(challenge_id) REFERENCES challenges(id),
            PRIMARY KEY (user_id, challenge_id)
        )
    """)
    logger.info("Таблица 'user_challenge_progress' создана.")

    # Таблица ачивок
    cur.execute("""
        CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            condition_type TEXT NOT NULL,
            condition_value TEXT NOT NULL,
            icon TEXT DEFAULT '🏆'
        )
    """)
    logger.info("Таблица 'achievements' создана.")

    # Таблица полученных ачивок пользователями
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_achievements (
            user_id INTEGER NOT NULL,
            achievement_id INTEGER NOT NULL,
            earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(achievement_id) REFERENCES achievements(id),
            PRIMARY KEY (user_id, achievement_id)
        )
    """)
    logger.info("Таблица 'user_achievements' создана.")

    # Добавляем стандартные ачивки, если их нет
    cur.execute("SELECT COUNT(*) FROM achievements")
    if cur.fetchone()[0] == 0:
        achievements_data = [
            ("Первая тренировка", "Запиши свою первую тренировку", "workout_count", "1", "🏅"),
            ("10 тренировок", "Выполни 10 тренировок", "workout_count", "10", "🏆"),
            ("Рекордсмен", "Установи новый личный рекорд в любом упражнении", "best_record", "1", "⭐"),
            ("Победитель челленджа", "Заверши любой челлендж", "challenge_completed", "1", "🎯"),
        ]
        cur.executemany("""
            INSERT INTO achievements (name, description, condition_type, condition_value, icon)
            VALUES (?, ?, ?, ?, ?)
        """, achievements_data)
        logger.info(f"Добавлено {len(achievements_data)} ачивок.")

    # Связь комплексов с упражнениями
    cur.execute("""
        CREATE TABLE IF NOT EXISTS complex_exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complex_id INTEGER NOT NULL,
            exercise_id INTEGER NOT NULL,
            reps INTEGER,
            weight REAL,
            time TEXT,
            order_index INTEGER NOT NULL,
            FOREIGN KEY(complex_id) REFERENCES complexes(id),
            FOREIGN KEY(exercise_id) REFERENCES exercises(id)
        )
    """)
    logger.info("Таблица 'complex_exercises' создана.")

    # Таблица тренировок
    cur.execute("""
        CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            exercise_id INTEGER NULL,
            complex_id INTEGER NULL,
            result_value TEXT NOT NULL,
            video_link TEXT NOT NULL,
            user_level TEXT NOT NULL,
            is_best BOOLEAN DEFAULT 0,
            comment TEXT,
            performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(exercise_id) REFERENCES exercises(id),
            FOREIGN KEY(complex_id) REFERENCES complexes(id)
        )
    """)
    cur.execute("PRAGMA table_info(workouts)")
    columns = [col[1] for col in cur.fetchall()]
    if 'user_level' not in columns:
        cur.execute("ALTER TABLE workouts ADD COLUMN user_level TEXT DEFAULT 'beginner'")
    if 'complex_id' not in columns:
        cur.execute("ALTER TABLE workouts ADD COLUMN complex_id INTEGER DEFAULT NULL")
    if 'is_best' not in columns:
        cur.execute("ALTER TABLE workouts ADD COLUMN is_best BOOLEAN DEFAULT 0")
    if 'comment' not in columns:
        cur.execute("ALTER TABLE workouts ADD COLUMN comment TEXT")

    # Таблица для опубликованных постов (комплексов и челленджей в канале)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS published_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    logger.info("Таблица 'published_posts' создана.")

    conn.commit()
    conn.close()
    logger.info("База данных инициализирована.")
    load_exercises_from_json_if_empty()

def load_exercises_from_json_if_empty():
    """Загружает упражнения из JSON-файла, если таблица упражнений пуста."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM exercises")
    count = cur.fetchone()[0]
    conn.close()
    if count == 0:
        if not os.path.exists(EXERCISES_JSON):
            logger.warning(f"Файл {EXERCISES_JSON} не найден, пропускаем автозагрузку.")
            return
        try:
            with open(EXERCISES_JSON, 'r', encoding='utf-8') as f:
                exercises = json.load(f)
        except Exception as e:
            logger.error(f"Ошибка чтения {EXERCISES_JSON}: {e}")
            return
        added = 0
        for ex in exercises:
            name = ex.get('name')
            metric = ex.get('metric')
            description = ex.get('description', '')
            points = ex.get('points', 0)
            week = ex.get('week', 0)
            difficulty = ex.get('difficulty', 'beginner')
            if add_exercise(name, description, metric, points, week, difficulty):
                added += 1
        logger.info(f"Автозагрузка: добавлено {added} упражнений из {EXERCISES_JSON}.")
    else:
        logger.info("В базе уже есть упражнения, автозагрузка пропущена.")

def add_workout(user_id, exercise_id=None, complex_id=None, result_value="", video_link="", user_level="beginner", comment=None, metric=None, notify_record_callback=None):
    """Добавляет тренировку в базу данных."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO workouts (user_id, exercise_id, complex_id, result_value, video_link, user_level, comment)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, exercise_id, complex_id, result_value, video_link, user_level, comment))
    workout_id = cur.lastrowid
    conn.commit()
    new_achievements = check_and_award_achievements(user_id, conn)
    if metric is not None and exercise_id is not None:
        update_personal_best(user_id, exercise_id, result_value, metric, conn, notify_record_callback)
    conn.close()
    return workout_id, new_achievements

def add_user(user_id, first_name, last_name, username, level='beginner'):
    """Добавляет или обновляет пользователя."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO users (user_id, first_name, last_name, username, level)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, first_name, last_name, username, level))
    conn.commit()
    conn.close()

def get_user_level(user_id):
    """Возвращает уровень пользователя."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT level FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 'beginner'

def set_user_level(user_id, new_level):
    """Устанавливает уровень пользователя."""
    if new_level not in ('beginner', 'pro'):
        return False
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE users SET level = ? WHERE user_id = ?", (new_level, user_id))
    conn.commit()
    conn.close()
    return True

def get_exercises(active_only=True, week=None, difficulty=None):
    """Возвращает список упражнений с фильтрацией."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    query = "SELECT id, name, metric, points, week, difficulty FROM exercises"
    conditions = []
    params = []
    if active_only:
        conditions.append("is_active = 1")
    if week is not None:
        conditions.append("(week = 0 OR week = ?)")
        params.append(week)
    if difficulty is not None:
        conditions.append("difficulty = ?")
        params.append(difficulty)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    cur.execute(query, params)
    exercises = cur.fetchall()
    conn.close()
    return exercises

def get_all_exercises():
    """Возвращает все упражнения."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, name, metric, points, week, difficulty FROM exercises ORDER BY name")
    exercises = cur.fetchall()
    conn.close()
    return exercises

def get_exercise_by_id(exercise_id):
    """Возвращает упражнение по ID."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, name, description, metric, points, week, difficulty FROM exercises WHERE id = ?", (exercise_id,))
    row = cur.fetchone()
    conn.close()
    return row

def update_personal_best(user_id, exercise_id, new_result, metric_type, conn=None, notify_record_callback=None):
    """Обновляет личный рекорд пользователя."""
    own_conn = False
    if conn is None:
        conn = sqlite3.connect(DB_NAME)
        own_conn = True
    cur = conn.cursor()
    cur.execute("""
        SELECT id, result_value FROM workouts
        WHERE user_id = ? AND exercise_id = ? AND is_best = 1
    """, (user_id, exercise_id))
    current_best = cur.fetchone()
    is_new_best = False
    if metric_type == 'reps':
        new_val = int(new_result)
        if current_best:
            old_val = int(current_best[1])
            if new_val > old_val:
                is_new_best = True
        else:
            is_new_best = True
    else:
        if current_best:
            if new_result < current_best[1]:
                is_new_best = True
        else:
            is_new_best = True
    if is_new_best:
        if current_best:
            cur.execute("UPDATE workouts SET is_best = 0 WHERE id = ?", (current_best[0],))
        cur.execute("""
            SELECT id FROM workouts
            WHERE user_id = ? AND exercise_id = ? AND result_value = ? AND is_best = 0
            ORDER BY id DESC LIMIT 1
        """, (user_id, exercise_id, new_result))
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE workouts SET is_best = 1 WHERE id = ?", (row[0],))
        conn.commit()
        if notify_record_callback:
            try:
                notify_record_callback(user_id, exercise_id, new_result, metric_type)
            except Exception as e:
                logger.error(f"Ошибка в notify_record_callback: {e}")
    if own_conn:
        conn.close()

def add_exercise(name, description, metric, points=0, week=0, difficulty='beginner'):
    """Добавляет новое упражнение."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO exercises (name, description, metric, points, week, difficulty)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, description, metric, points, week, difficulty))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    conn.close()
    return success

def delete_exercise(exercise_id):
    """Удаляет упражнение по ID."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM exercises WHERE id = ?", (exercise_id,))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def set_exercise_week(exercise_id, week):
    """Устанавливает неделю для упражнения."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE exercises SET week = ? WHERE id = ?", (week, exercise_id))
    conn.commit()
    conn.close()

def get_user_stats(user_id, period=None, level=None):
    """Возвращает статистику пользователя."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    query = """
        SELECT SUM(e.points), COUNT(w.id)
        FROM workouts w
        JOIN exercises e ON w.exercise_id = e.id
        WHERE w.user_id = ?
    """
    params = [user_id]
    if level is not None:
        query += " AND w.user_level = ?"
        params.append(level)
    if period:
        if period == 'day':
            query += " AND DATE(w.performed_at) = DATE('now')"
        elif period == 'week':
            query += " AND strftime('%W', w.performed_at) = strftime('%W', 'now') AND strftime('%Y', w.performed_at) = strftime('%Y', 'now')"
        elif period == 'month':
            query += " AND strftime('%m', w.performed_at) = strftime('%m', 'now') AND strftime('%Y', w.performed_at) = strftime('%Y', 'now')"
        elif period == 'year':
            query += " AND strftime('%Y', w.performed_at) = strftime('%Y', 'now')"
    cur.execute(query, params)
    result = cur.fetchone()
    conn.close()
    return result

def get_leaderboard(period=None, level=None, limit=10):
    """Возвращает таблицу лидеров."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    query = """
        SELECT u.user_id, u.first_name, u.username, SUM(e.points) as total
        FROM workouts w
        JOIN users u ON w.user_id = u.user_id
        JOIN exercises e ON w.exercise_id = e.id
        WHERE 1=1
    """
    params = []
    if level is not None:
        query += " AND w.user_level = ?"
        params.append(level)
    if period:
        if period == 'day':
            query += " AND DATE(w.performed_at) = DATE('now')"
        elif period == 'week':
            query += " AND strftime('%W', w.performed_at) = strftime('%W', 'now') AND strftime('%Y', w.performed_at) = strftime('%Y', 'now')"
        elif period == 'month':
            query += " AND strftime('%m', w.performed_at) = strftime('%m', 'now') AND strftime('%Y', w.performed_at) = strftime('%Y', 'now')"
        elif period == 'year':
            query += " AND strftime('%Y', w.performed_at) = strftime('%Y', 'now')"
    query += " GROUP BY u.user_id ORDER BY total DESC LIMIT ?"
    params.append(limit)
    cur.execute(query, params)
    results = cur.fetchall()
    conn.close()
    return results

def get_user_workouts(user_id, limit=20):
    """Возвращает последние тренировки пользователя."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            w.id,
            COALESCE(e.name, c.name) as name,
            w.result_value,
            w.video_link,
            w.performed_at,
            w.is_best,
            CASE WHEN w.exercise_id IS NOT NULL THEN 'упражнение' ELSE 'комплекс' END as type,
            w.comment
        FROM workouts w
        LEFT JOIN exercises e ON w.exercise_id = e.id
        LEFT JOIN complexes c ON w.complex_id = c.id
        WHERE w.user_id = ?
        ORDER BY w.performed_at DESC
        LIMIT ?
    """, (user_id, limit))
    rows = cur.fetchall()
    conn.close()
    return rows

def get_user_scoreboard_total(user_id):
    """Возвращает общее количество баллов пользователя из scoreboard."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT SUM(points_awarded) FROM scoreboard WHERE user_id = ?", (user_id,))
    total = cur.fetchone()[0]
    conn.close()
    return total or 0

def get_leaderboard_from_scoreboard(limit=10):
    """Возвращает таблицу лидеров из scoreboard."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT u.user_id, u.first_name, u.username, SUM(s.points_awarded) as total
        FROM scoreboard s
        JOIN users u ON s.user_id = u.user_id
        GROUP BY u.user_id
        ORDER BY total DESC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows

def recalculate_rankings(period_days=7):
    """Пересчитывает рейтинг за указанный период."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    start_date = datetime.now() - timedelta(days=period_days)
    exercises = get_all_exercises()
    for ex in exercises:
        ex_id = ex[0]
        metric = ex[2]
        if metric == 'reps':
            query = """
                SELECT user_id, MAX(CAST(result_value AS INTEGER)) as best
                FROM workouts
                WHERE exercise_id = ? AND performed_at >= ?
                GROUP BY user_id
                ORDER BY best DESC
            """
        else:
            query = """
                SELECT user_id, MIN(result_value) as best
                FROM workouts
                WHERE exercise_id = ? AND performed_at >= ?
                GROUP BY user_id
                ORDER BY best ASC
            """
        cur.execute(query, (ex_id, start_date))
        results = cur.fetchall()
        rankings = []
        for i, (user_id, best) in enumerate(results):
            if i == 0:
                points = 15
            elif i == 1:
                points = 10
            elif i == 2:
                points = 5
            else:
                points = 0
            rankings.append((user_id, ex_id, start_date, datetime.now(), i+1, points))
        cur.execute("DELETE FROM scoreboard WHERE exercise_id = ? AND period_start = ?", (ex_id, start_date))
        cur.executemany("""
            INSERT INTO scoreboard (user_id, exercise_id, period_start, period_end, rank, points_awarded)
            VALUES (?, ?, ?, ?, ?, ?)
        """, rankings)
    conn.commit()
    conn.close()
    logger.info(f"Рейтинг пересчитан за период с {start_date} по {datetime.now()}")

def get_last_recalc():
    """Возвращает дату последнего пересчёта рейтинга."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT value FROM system_config WHERE key = 'last_recalc'")
    row = cur.fetchone()
    conn.close()
    if row and row[0] != '0':
        return datetime.fromisoformat(row[0])
    return None

def set_last_recalc(date):
    """Устанавливает дату последнего пересчёта рейтинга."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE system_config SET value = ? WHERE key = 'last_recalc'", (date.isoformat(),))
    conn.commit()
    conn.close()

def add_complex(name, description, type_, points, week=0, difficulty='beginner'):
    """Добавляет новый комплекс."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO complexes (name, description, type, points, week, difficulty)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, description, type_, points, week, difficulty))
        complex_id = cur.lastrowid
        conn.commit()
        return complex_id
    except sqlite3.IntegrityError:
        logger.error(f"Комплекс с именем {name} уже существует.")
        return None
    finally:
        conn.close()

def add_complex_exercise(complex_id, exercise_id, reps, order_index=None):
    """Добавляет упражнение в комплекс."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if order_index is None:
        cur.execute("SELECT COALESCE(MAX(order_index), 0) + 1 FROM complex_exercises WHERE complex_id = ?", (complex_id,))
        order_index = cur.fetchone()[0]
    cur.execute("""
        INSERT INTO complex_exercises (complex_id, exercise_id, reps, order_index)
        VALUES (?, ?, ?, ?)
    """, (complex_id, exercise_id, reps, order_index))
    conn.commit()
    conn.close()

def get_all_complexes():
    """Возвращает все комплексы."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, name, description, type, points, week, difficulty FROM complexes ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return rows

def get_complex_by_id(complex_id):
    """Возвращает комплекс по ID."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, name, description, type, points, week, difficulty FROM complexes WHERE id = ?", (complex_id,))
    row = cur.fetchone()
    conn.close()
    return row

def get_complex_exercises(complex_id):
    """Возвращает упражнения комплекса."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT ce.id, ce.exercise_id, e.name, e.metric, ce.reps
        FROM complex_exercises ce
        JOIN exercises e ON ce.exercise_id = e.id
        WHERE ce.complex_id = ?
        ORDER BY ce.order_index
    """, (complex_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def add_challenge(name, description, target_type, target_id, metric, target_value, start_date, end_date, bonus_points):
    """Добавляет новый челлендж."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO challenges (name, description, target_type, target_id, metric, target_value, start_date, end_date, bonus_points)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, description, target_type, target_id, metric, target_value, start_date, end_date, bonus_points))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Ошибка при добавлении челленджа: {e}")
        return False
    finally:
        conn.close()

def get_active_challenges():
    """Возвращает активные челленджи."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT c.id, c.name, c.description, c.target_type, c.target_id, c.metric, c.target_value,
               c.start_date, c.end_date, c.bonus_points,
               CASE 
                   WHEN c.target_type = 'exercise' THEN e.name
                   WHEN c.target_type = 'complex' THEN cm.name
               END as target_name
        FROM challenges c
        LEFT JOIN exercises e ON c.target_type = 'exercise' AND c.target_id = e.id
        LEFT JOIN complexes cm ON c.target_type = 'complex' AND c.target_id = cm.id
        WHERE c.is_active = 1 AND date('now') BETWEEN date(c.start_date) AND date(c.end_date)
        ORDER BY c.start_date
    """)
    rows = cur.fetchall()
    conn.close()
    return rows

def join_challenge(user_id, challenge_id):
    """Присоединяет пользователя к челленджу."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO user_challenges (user_id, challenge_id)
            VALUES (?, ?)
        """, (user_id, challenge_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_challenge_by_id(challenge_id):
    """Возвращает челлендж по ID."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, target_type, target_id, metric, target_value, bonus_points
        FROM challenges
        WHERE id = ? AND is_active = 1 AND date('now') BETWEEN date(start_date) AND date(end_date)
    """, (challenge_id,))
    row = cur.fetchone()
    conn.close()
    return row

def update_challenge_progress(user_id, challenge_id, new_value):
    """Обновляет прогресс пользователя в челлендже."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO user_challenge_progress (user_id, challenge_id, current_value, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
    """, (user_id, challenge_id, new_value))
    conn.commit()
    conn.close()

def check_challenge_completion(user_id, challenge_id, target_value, metric):
    """Проверяет, завершён ли челлендж."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT current_value FROM user_challenge_progress
        WHERE user_id = ? AND challenge_id = ?
    """, (user_id, challenge_id))
    row = cur.fetchone()
    conn.close()
    if not row:
        return False
    current = row[0]
    if metric == 'reps':
        try:
            return int(current) >= int(target_value)
        except:
            return False
    else:
        return current <= target_value

def get_user_challenges(user_id):
    """Возвращает челленджи пользователя."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT c.id, c.target_type, c.target_id, c.target_value, c.metric, c.bonus_points
        FROM challenges c
        JOIN user_challenges uc ON c.id = uc.challenge_id
        WHERE uc.user_id = ? AND c.is_active = 1
          AND date('now') BETWEEN date(c.start_date) AND date(c.end_date)
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def complete_challenge(user_id, challenge_id):
    """Завершает челлендж и начисляет бонус."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    try:
        cur.execute("SELECT bonus_points FROM challenges WHERE id = ?", (challenge_id,))
        bonus = cur.fetchone()[0]
        cur.execute("""
            UPDATE user_challenges SET completed = 1, completed_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND challenge_id = ?
        """, (user_id, challenge_id))
        cur.execute("""
            INSERT INTO scoreboard (user_id, exercise_id, period_start, period_end, rank, points_awarded)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, -challenge_id, datetime.now(), datetime.now(), 0, bonus))
        conn.commit()
        check_and_award_achievements(user_id, conn)
        return True
    except Exception as e:
        logger.error(f"Ошибка при завершении челленджа: {e}")
        return False
    finally:
        conn.close()

def get_challenges_by_status(status='active'):
    """Возвращает челленджи по статусу."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if status == 'active':
        where = "c.is_active = 1 AND date('now') BETWEEN date(c.start_date) AND date(c.end_date)"
    elif status == 'past':
        where = "c.is_active = 1 AND date(c.end_date) < date('now')"
    elif status == 'future':
        where = "c.is_active = 1 AND date(c.start_date) > date('now')"
    else:
        where = "c.is_active = 1"
    cur.execute(f"""
        SELECT c.id, c.name, c.description, c.target_type, c.target_id, c.metric, c.target_value,
               c.start_date, c.end_date, c.bonus_points,
               CASE 
                   WHEN c.target_type = 'exercise' THEN e.name
                   WHEN c.target_type = 'complex' THEN cm.name
               END as target_name
        FROM challenges c
        LEFT JOIN exercises e ON c.target_type = 'exercise' AND c.target_id = e.id
        LEFT JOIN complexes cm ON c.target_type = 'complex' AND c.target_id = cm.id
        WHERE {where}
        ORDER BY c.start_date
    """)
    rows = cur.fetchall()
    conn.close()
    return rows

def get_setting(key):
    """Возвращает значение настройки."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def set_setting(key, value):
    """Устанавливает значение настройки."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_challenge_name(challenge_id):
    """Возвращает название челленджа."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT name FROM challenges WHERE id = ?", (challenge_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def get_user_challenges_with_details(user_id):
    """Возвращает челленджи пользователя с деталями."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT c.id, c.name, c.target_type, c.target_id, c.metric, c.target_value, c.bonus_points,
               c.start_date, c.end_date, COALESCE(p.current_value, '0') as current_value,
               CASE 
                   WHEN c.target_type = 'exercise' THEN e.name
                   WHEN c.target_type = 'complex' THEN cm.name
               END as target_name
        FROM challenges c
        JOIN user_challenges uc ON c.id = uc.challenge_id
        LEFT JOIN user_challenge_progress p ON c.id = p.challenge_id AND p.user_id = uc.user_id
        LEFT JOIN exercises e ON c.target_type = 'exercise' AND c.target_id = e.id
        LEFT JOIN complexes cm ON c.target_type = 'complex' AND c.target_id = cm.id
        WHERE uc.user_id = ? AND c.is_active = 1
          AND date('now') BETWEEN date(c.start_date) AND date(c.end_date)
        ORDER BY c.start_date
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def leave_challenge(user_id, challenge_id):
    """Выход из челленджа."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM user_challenges WHERE user_id = ? AND challenge_id = ?", (user_id, challenge_id))
    cur.execute("DELETE FROM user_challenge_progress WHERE user_id = ? AND challenge_id = ?", (user_id, challenge_id))
    conn.commit()
    conn.close()

def check_and_award_achievements(user_id, conn=None):
    """Проверяет и начисляет ачивки пользователю."""
    own_conn = False
    if conn is None:
        conn = sqlite3.connect(DB_NAME)
        own_conn = True
    cur = conn.cursor()
    cur.execute("SELECT id, name, description, condition_type, condition_value, icon FROM achievements")
    achievements = cur.fetchall()
    cur.execute("SELECT achievement_id FROM user_achievements WHERE user_id = ?", (user_id,))
    earned = {row[0] for row in cur.fetchall()}
    new_achievements = []
    for ach in achievements:
        ach_id, name, desc, cond_type, cond_value, icon = ach
        if ach_id in earned:
            continue
        if cond_type == 'workout_count':
            cur.execute("SELECT COUNT(*) FROM workouts WHERE user_id = ?", (user_id,))
            count = cur.fetchone()[0]
            if count >= int(cond_value):
                new_achievements.append(ach)
        elif cond_type == 'best_record':
            cur.execute("SELECT 1 FROM workouts WHERE user_id = ? AND is_best = 1 LIMIT 1", (user_id,))
            if cur.fetchone():
                new_achievements.append(ach)
        elif cond_type == 'challenge_completed':
            cur.execute("SELECT 1 FROM user_challenges WHERE user_id = ? AND completed = 1 LIMIT 1", (user_id,))
            if cur.fetchone():
                new_achievements.append(ach)
    for ach in new_achievements:
        ach_id, name, desc, cond_type, cond_value, icon = ach
        cur.execute("INSERT INTO user_achievements (user_id, achievement_id) VALUES (?, ?)", (user_id, ach_id))
        conn.commit()
    if own_conn:
        conn.close()
    return new_achievements

def get_user_activity_calendar(user_id, year, month):
    """Возвращает данные для календаря активности пользователя."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            DATE(performed_at) as day,
            COUNT(*) as workout_count,
            0 as record_count,
            SUM(result_value) as total_volume
        FROM workouts
        WHERE user_id = ? 
          AND strftime('%Y', performed_at) = ? 
          AND strftime('%m', performed_at) = ?
        GROUP BY DATE(performed_at)
    """, (user_id, str(year), f"{month:02d}"))
    rows = cursor.fetchall()
    conn.close()
    days_in_month = calendar.monthrange(year, month)[1]
    result = []
    for day in range(1, days_in_month + 1):
        day_str = f"{year}-{month:02d}-{day:02d}"
        found = False
        has_workout = False
        has_record = False
        total_volume = None
        for row in rows:
            if row[0] == day_str:
                found = True
                has_workout = row[1] > 0
                has_record = row[2] > 0
                total_volume = row[3] if row[3] else 0
                break
        if not found:
            has_workout = False
            has_record = False
            total_volume = None
        result.append((day, has_workout, has_record, total_volume))
    return result

def save_published_post(entity_type, entity_id, channel_id, message_id):
    """Сохраняет информацию о опубликованном посте."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT INTO published_posts (entity_type, entity_id, channel_id, message_id) VALUES (?, ?, ?, ?)", (entity_type, entity_id, channel_id, message_id))
    conn.commit()
    conn.close()

def get_published_post_by_message_id(message_id):
    """Возвращает информацию о посте по message_id."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT entity_type, entity_id, channel_id, message_id FROM published_posts WHERE message_id = ?", (message_id,))
    row = cur.fetchone()
    conn.close()
    return row