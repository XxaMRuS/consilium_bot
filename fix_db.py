import sqlite3
from datetime import datetime

conn = sqlite3.connect("workouts.db")
cur = conn.cursor()

# Проверяем, есть ли колонка performed_at
cur.execute("PRAGMA table_info(workouts)")
columns = [col[1] for col in cur.fetchall()]

if 'performed_at' not in columns:
    # Добавляем колонку без DEFAULT
    cur.execute("ALTER TABLE workouts ADD COLUMN performed_at TIMESTAMP")
    print("✅ Колонка performed_at добавлена")

    # Заполняем существующие строки текущей датой
    now = datetime.now().isoformat()
    cur.execute("UPDATE workouts SET performed_at = ? WHERE performed_at IS NULL", (now,))
    print(f"✅ Заполнено {cur.rowcount} строк")

    # Теперь можно добавить DEFAULT для новых строк
    # SQLite не поддерживает ALTER DEFAULT, но можно создать триггер
    cur.execute("""
                CREATE TRIGGER IF NOT EXISTS set_workout_date
        AFTER INSERT ON workouts
                BEGIN
                UPDATE workouts
                SET performed_at = CURRENT_TIMESTAMP
                WHERE id = NEW.id
                  AND performed_at IS NULL;
                END;
                """)
    print("✅ Триггер для авто-заполнения даты создан")
else:
    print("Колонка performed_at уже есть")

conn.commit()
conn.close()
print("Готово!")