import sqlite3
import os
import datetime

DB_FILE = 'pharmaday.db'

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

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
    
    # Check if default admin user exists
    cur.execute('SELECT COUNT(*) FROM users')
    if cur.fetchone()[0] == 0:
        # Create default admin user (username: 1, password: 1)
        from passlib.hash import pbkdf2_sha256
        # 기본 관리자 계정 생성
        cur.execute('SELECT * FROM users WHERE username = ?', ('1',))
        if not cur.fetchone():
            cur.execute(
                'INSERT INTO users (username, password_hash) VALUES (?, ?)',
                ('1', pbkdf2_sha256.hash('1'))
            )
        
        # 디버그용 계정 생성
        cur.execute('SELECT * FROM users WHERE username = ?', ('pharmmaker',))
        if not cur.fetchone():
            cur.execute(
                'INSERT INTO users (username, password_hash) VALUES (?, ?)',
                ('pharmmaker', pbkdf2_sha256.hash('pharmmaker123'))
            )
    
    conn.commit()
    conn.close()

# Initialize database when module is imported
init_db()
