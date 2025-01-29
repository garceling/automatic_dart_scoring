import sqlite3

def fix_gamerounds():
    conn = sqlite3.connect('dartboard.db')
    cursor = conn.cursor()
    
    # Drop the existing table
    cursor.execute('DROP TABLE IF EXISTS GameRounds')
    
    # Create the table with all required columns
    cursor.execute('''
        CREATE TABLE GameRounds (
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

    # Recreate the index
    cursor.execute('''
        CREATE INDEX idx_gamerounds_game_player ON GameRounds (game_id, player_id)
    ''')

    conn.commit()
    conn.close()

if __name__ == "__main__":
    fix_gamerounds()
    print("GameRounds table fixed successfully!")
