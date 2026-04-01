import sqlite3

conn = sqlite3.connect("workouts.db")
cur = conn.cursor()

cur.execute("""
    CREATE TABLE IF NOT EXISTS reply_states (
        user_id INTEGER PRIMARY KEY,
        reply_to_message_id INTEGER,
        channel_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

conn.commit()
conn.close()
print("✅ Таблица reply_states создана")