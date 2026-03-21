import sqlite3
import os

DB_FILE = "database.db" # Changed to relative path for cloud compatibility
# If running locally, it'll create in the working directory

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Create users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            name TEXT,
            game_name TEXT
        )
    ''')
    try:
        c.execute("ALTER TABLE users ADD COLUMN game_name TEXT")
    except sqlite3.OperationalError:
        pass
    # Create predictions table
    c.execute('''
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            match_id INTEGER,
            winner TEXT,
            orange_cap TEXT,
            purple_cap TEXT,
            multiplier_used BOOLEAN,
            group_id INTEGER,
            UNIQUE(email, match_id),
            FOREIGN KEY (email) REFERENCES users (email)
        )
    ''')
    conn.commit()
    # Create match_results table for scoring
    c.execute('''
        CREATE TABLE IF NOT EXISTS match_results (
            match_id INTEGER PRIMARY KEY,
            winner TEXT,
            orange_cap TEXT,
            orange_cap_rest TEXT,
            orange_cap_2nd TEXT,
            purple_cap TEXT,
            purple_cap_rest TEXT,
            oc_freehit_player TEXT,
            pc_freehit_player TEXT,
            group_id INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def create_or_get_user(email, name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (email, name) VALUES (?, ?)", (email, name))
    conn.commit()
    conn.close()

def save_prediction(email, match_id, winner, orange_cap, purple_cap, multiplier_used, group_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Upsert the prediction
    c.execute('''
        INSERT INTO predictions (email, match_id, winner, orange_cap, purple_cap, multiplier_used, group_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(email, match_id) DO UPDATE SET
            winner=excluded.winner,
            orange_cap=excluded.orange_cap,
            purple_cap=excluded.purple_cap,
            multiplier_used=excluded.multiplier_used,
            group_id=excluded.group_id
    ''', (email, match_id, winner, orange_cap, purple_cap, multiplier_used, group_id))
    conn.commit()
    conn.close()

def get_user_predictions(email):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
        SELECT match_id, winner, orange_cap, purple_cap, multiplier_used, group_id
        FROM predictions
        WHERE email = ?
    ''', (email,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def has_used_multiplier_in_group(email, group_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT 1 FROM predictions
        WHERE email = ? AND group_id = ? AND multiplier_used = 1
    ''', (email, group_id))
    row = c.fetchone()
    conn.close()
    return row is not None

def get_user(email):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def update_game_name(email, game_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET game_name = ? WHERE email = ?", (game_name, email))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT email, name, game_name FROM users WHERE game_name IS NOT NULL")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_match_predictions(match_id):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
        SELECT u.game_name, p.winner, p.orange_cap, p.purple_cap, p.multiplier_used
        FROM predictions p
        JOIN users u ON p.email = u.email
        WHERE p.match_id = ? AND u.game_name IS NOT NULL
    ''', (match_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def save_match_result(match_id, winner, orange_cap, orange_cap_rest, orange_cap_2nd, purple_cap, purple_cap_rest, oc_freehit_player, pc_freehit_player, group_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO match_results (match_id, winner, orange_cap, orange_cap_rest, orange_cap_2nd, purple_cap, purple_cap_rest, oc_freehit_player, pc_freehit_player, group_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(match_id) DO UPDATE SET
            winner=excluded.winner,
            orange_cap=excluded.orange_cap,
            orange_cap_rest=excluded.orange_cap_rest,
            orange_cap_2nd=excluded.orange_cap_2nd,
            purple_cap=excluded.purple_cap,
            purple_cap_rest=excluded.purple_cap_rest,
            oc_freehit_player=excluded.oc_freehit_player,
            pc_freehit_player=excluded.pc_freehit_player,
            group_id=excluded.group_id
    ''', (match_id, winner, orange_cap, orange_cap_rest, orange_cap_2nd, purple_cap, purple_cap_rest, oc_freehit_player, pc_freehit_player, group_id))
    conn.commit()
    conn.close()

def get_all_match_results():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM match_results")
    rows = c.fetchall()
    conn.close()
    return {row['match_id']: dict(row) for row in rows}

def get_all_predictions():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM predictions")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]
