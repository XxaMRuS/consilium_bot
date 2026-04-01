import sqlite3

conn = sqlite3.connect("workouts.db")
cur = conn.cursor()

# Проверяем, есть ли колонка is_active
cur.execute("PRAGMA table_info(exercises)")
columns = [col[1] for col in cur.fetchall()]

if 'is_active' not in columns:
    cur.execute("ALTER TABLE exercises ADD COLUMN is_active BOOLEAN DEFAULT 1")
    print("✅ Колонка is_active добавлена в exercises")
else:
    print("Колонка is_active уже есть")

# Также проверим таблицу complexes
cur.execute("PRAGMA table_info(complexes)")
columns = [col[1] for col in cur.fetchall()]

if 'is_active' not in columns:
    cur.execute("ALTER TABLE complexes ADD COLUMN is_active BOOLEAN DEFAULT 1")
    print("✅ Колонка is_active добавлена в complexes")
else:
    print("Колонка is_active уже есть в complexes")

conn.commit()
conn.close()
print("Готово!")