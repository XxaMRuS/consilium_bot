import sqlite3

conn = sqlite3.connect('workouts.db')
conn.execute('''
    CREATE TABLE IF NOT EXISTS prize_pool (
        id INTEGER PRIMARY KEY,
        entity_type TEXT,
        entity_id INTEGER,
        total_points INTEGER,
        distribution TEXT DEFAULT "70,20,10",
        is_distributed BOOLEAN DEFAULT 0
    )
''')
conn.commit()
conn.close()
print('Таблица prize_pool создана')