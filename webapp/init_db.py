import sqlite3

def init_db():
    conn = sqlite3.connect('dartboard.db')
    cursor = conn.cursor()

    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS GameRooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_by INTEGER NOT NULL,
            game_type INTEGER NOT NULL DEFAULT 501,
            double_out_required BOOLEAN NOT NULL DEFAULT 1,
            is_private BOOLEAN NOT NULL DEFAULT 0,
            room_password TEXT,
            current_players INTEGER NOT NULL DEFAULT 1,
            max_players INTEGER NOT NULL DEFAULT 4,
            room_status TEXT NOT NULL DEFAULT 'waiting',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES Players(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            game_status TEXT NOT NULL DEFAULT 'waiting',
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            current_player_position INTEGER DEFAULT 0,
            FOREIGN KEY (room_id) REFERENCES GameRooms(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS GamePlayers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            player_position INTEGER NOT NULL,
            current_score INTEGER NOT NULL,
            FOREIGN KEY (game_id) REFERENCES GameRooms(id),
            FOREIGN KEY (player_id) REFERENCES Players(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS GameRounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            round_number INTEGER NOT NULL,
            throw1_score INTEGER,
            throw1_multiplier INTEGER,
            throw2_score INTEGER,
            throw2_multiplier INTEGER,
            throw3_score INTEGER,
            throw3_multiplier INTEGER,
            score_before_throw1 INTEGER,
            score_before_throw2 INTEGER,
            score_before_throw3 INTEGER,
            is_bust BOOLEAN NOT NULL DEFAULT 0,
            round_total INTEGER DEFAULT 0,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (game_id) REFERENCES Games(id),
            FOREIGN KEY (player_id) REFERENCES Players(id)
        )
    ''')

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully!")
