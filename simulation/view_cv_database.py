import sqlite3
from contextlib import contextmanager
from datetime import datetime

@contextmanager
def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def view_all_throws(db_path='cv_data.db'):
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            
            # Get total count of throws
            cursor.execute('SELECT COUNT(*) as count FROM throws')
            count = cursor.fetchone()['count']
            print(f"\nTotal throws in database: {count}")
            
            # Get all throws ordered by timestamp
            cursor.execute('''
                SELECT id, timestamp, score, multiplier, position_x, position_y
                FROM throws 
                ORDER BY timestamp DESC
                LIMIT 10
            ''')
            
            throws = cursor.fetchall()
            
            if not throws:
                print("\nNo throws found in database.")
                return
            
            print("\nMost recent 10 throws:")
            print("-" * 80)
            print(f"{'ID':4} | {'Timestamp':19} | {'Score':5} | {'Mult':4} | {'Total':5} | {'Position'}")
            print("-" * 80)
            
            for throw in throws:
                # Calculate total score
                total = throw['score'] * throw['multiplier']
                # Format position
                position = f"({throw['position_x']}, {throw['position_y']})"
                # Format timestamp
                timestamp = datetime.strptime(throw['timestamp'], '%Y-%m-%d %H:%M:%S')
                
                print(f"{throw['id']:4} | {timestamp:%Y-%m-%d %H:%M:%S} | {throw['score']:5} | {throw['multiplier']:4} | {total:5} | {position}")
            
            print("-" * 80)
            
    except sqlite3.Error as e:
        print(f"Error accessing database: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    view_all_throws()