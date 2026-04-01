import sqlite3

conn = sqlite3.connect("workouts.db")
cur = conn.cursor()
cur.execute("PRAGMA table_info(users)")
columns = cur.fetchall()
print("Структура таблицы users:")
for col in columns:
    print(col)
conn.close()