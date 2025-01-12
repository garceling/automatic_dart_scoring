import sqlite3
from contextlib import contextmanager
from datetime import datetime

DB_FILE = 'dartboard.db'

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.commit()
        conn.close()

def table_exists(cursor, table_name):
    cursor.execute('''
        SELECT count(name) FROM sqlite_master 
        WHERE type='table' AND name=?
    ''', (table_name,))
    return cursor.fetchone()[0] > 0

def print_room_status(cursor):
    if not table_exists(cursor, 'GameRooms'):
        print("No GameRooms table exists yet")
        return

    cursor.execute('''
        SELECT r.name, r.room_status, r.game_type, r.current_players,
               p.username as creator, r.created_at
        FROM GameRooms r
        JOIN Players p ON r.created_by = p.id
    ''')
    rooms = cursor.fetchall()

    if not rooms:
        print("No rooms found in database")
        return

    print("\nCurrent Rooms Status:")
    print("-" * 80)
    for room in rooms:
        print(f"Room: {room['name']}")
        print(f"Status: {room['room_status']}")
        print(f"Type: {room['game_type']}")
        print(f"Players: {room['current_players']}")
        print(f"Created by: {room['creator']}")
        print(f"Created at: {room['created_at']}")
        print("-" * 40)

def cleanup_rooms():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            print("\nCurrent room status before cleanup:")
            print_room_status(cursor)
            
            # Delete game-related data in the correct order
            tables_to_clean = ['GameRounds', 'GamePlayers', 'Games', 'GameRooms']
            
            for table in tables_to_clean:
                if table_exists(cursor, table):
                    cursor.execute(f'SELECT COUNT(*) as count FROM {table}')
                    count = cursor.fetchone()['count']
                    print(f"\nDeleting {count} records from {table}...")
                    cursor.execute(f'DELETE FROM {table}')
                    print(f"Reset sequence for {table}")
                    cursor.execute('DELETE FROM sqlite_sequence WHERE name=?', (table,))
                else:
                    print(f"\nTable {table} does not exist, skipping...")
            
            conn.commit()
            print("\nCleanup completed successfully!")
            
    except sqlite3.Error as e:
        print(f"\nAn error occurred: {e}")
        return False
    
    return True

if __name__ == '__main__':
    print("Starting cleanup of all game rooms...")
    print("=" * 80)
    if cleanup_rooms():
        print("\nAll rooms have been deleted successfully.")
        print("Player accounts have been preserved.")
    else:
        print("\nError during cleanup process.")
