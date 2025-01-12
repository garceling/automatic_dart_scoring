import sqlite3
from contextlib import contextmanager
import time
from datetime import datetime

@contextmanager
def get_db_connection_with_retry(max_attempts=5):
    conn = None
    attempts = 0
    while attempts < max_attempts:
        try:
            conn = sqlite3.connect('dartboard.db', timeout=20)
            conn.row_factory = sqlite3.Row
            yield conn
            break
        except sqlite3.OperationalError as e:
            attempts += 1
            if attempts == max_attempts:
                print(f"Failed to connect after {max_attempts} attempts")
                raise
            print(f"Database locked, attempt {attempts} of {max_attempts}. Retrying...")
            time.sleep(0.5)
        finally:
            if conn:
                conn.close()

def check_game_rooms():
    try:
        with get_db_connection_with_retry() as conn:
            cursor = conn.cursor()
            
            # Query rooms with player information
            cursor.execute('''
                SELECT 
                    r.id,
                    r.name,
                    r.room_status,
                    r.game_type,
                    r.double_out_required,
                    r.current_players,
                    r.max_players,
                    r.created_at,
                    p.username as creator,
                    COUNT(DISTINCT gp.player_id) as actual_players
                FROM GameRooms r
                LEFT JOIN Players p ON r.created_by = p.id
                LEFT JOIN Games g ON g.room_id = r.id
                LEFT JOIN GamePlayers gp ON gp.game_id = r.id
                GROUP BY r.id
                ORDER BY r.created_at DESC
            ''')
            
            rooms = cursor.fetchall()
            
            print("\n=== Game Rooms Status Report ===")
            print(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Total Rooms: {len(rooms)}\n")
            
            for room in rooms:
                print(f"Room: {room['name']} (ID: {room['id']})")
                print(f"├─ Status: {room['room_status']}")
                print(f"├─ Game Type: {room['game_type']}")
                print(f"├─ Double Out: {'Yes' if room['double_out_required'] else 'No'}")
                print(f"├─ Players: {room['current_players']}/{room['max_players']}")
                print(f"├─ Actual Players Connected: {room['actual_players']}")
                print(f"├─ Created By: {room['creator']}")
                print(f"└─ Created At: {room['created_at']}")
                print()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_game_rooms()
