import sqlite3
import os
import datetime
import sys

# PyInstaller 경로 대응
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_FILE = os.path.join(BASE_DIR, 'pharmaday.db')

def dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

def adapt_date(val):
    return val.strftime('%Y-%m-%d')

def convert_date(val):
    try:
        return datetime.datetime.strptime(val.decode(), '%Y-%m-%d').date()
    except (ValueError, AttributeError):
        return val

def adapt_datetime(val):
    return val.isoformat()

def convert_datetime(val):
    try:
        return datetime.datetime.fromisoformat(val.decode())
    except (ValueError, AttributeError):
        return val

def get_connection():
    sqlite3.register_adapter(datetime.date, adapt_date)
    sqlite3.register_converter('DATE', convert_date)
    sqlite3.register_adapter(datetime.datetime, adapt_datetime)
    sqlite3.register_converter('DATETIME', convert_datetime)
    conn = sqlite3.connect(DB_FILE, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # Create daily_reports table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS daily_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE UNIQUE NOT NULL,
            total_sales INTEGER,
            prescription_count INTEGER,
            notes TEXT,
            is_holiday BOOLEAN,
            is_manual_holiday BOOLEAN
        )
    ''')

    # Create users table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 기본 계정 삽입
    cur.execute('SELECT COUNT(*) FROM users')
    if cur.fetchone()[0] == 0:
        from passlib.hash import pbkdf2_sha256
        accounts = [
            ('1', pbkdf2_sha256.hash('1')),
            ('pharmmaker', pbkdf2_sha256.hash('pharmmaker123'))
        ]
        for username, hashval in accounts:
            cur.execute('SELECT * FROM users WHERE username = ?', (username,))
            if not cur.fetchone():
                cur.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, hashval))

    conn.commit()
    conn.close()

# 앱 실행 시 자동 DB 초기화
init_db()
