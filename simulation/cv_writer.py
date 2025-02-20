import sqlite3
from datetime import datetime
from contextlib import contextmanager
from darts_cv_simulation import DartDetection
import time

class CVDatabaseWriter:
    def __init__(self, db_path='cv_data.db'):
        self.db_path = db_path
        self.dart_detector = DartDetection()
        self.setup_database()

    @contextmanager
    def get_db_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def setup_database(self):
        """Create the database and necessary tables if they don't exist"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS throws (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    score INTEGER NOT NULL,
                    multiplier INTEGER NOT NULL,
                    position_x REAL,
                    position_y REAL
                )
            ''')
            conn.commit()

    def record_throw(self, throw_data):
        """Record a throw to the database"""
        if not throw_data:
            return

        score, multiplier, position = throw_data
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO throws (score, multiplier, position_x, position_y)
                    VALUES (?, ?, ?, ?)
                ''', (score, multiplier, position[0], position[1]))
                conn.commit()
                print(f"Recorded throw: Score={score}, Multiplier={multiplier}")
        except sqlite3.Error as e:
            print(f"Database error: {e}")
        except Exception as e:
            print(f"Error recording throw: {e}")

def main():
    # Create the database writer
    db_writer = CVDatabaseWriter()
    
    # Initialize the dart detector
    print("Initializing dart detection simulation...")
    db_writer.dart_detector.initialize()
    
    try:
        # Start the dart detection
        print("Starting dart detection simulation...")
        db_writer.dart_detector.start()
        
        # Main loop
        while True:
            # Get and record next throw
            throw = db_writer.dart_detector.get_next_throw()
            if throw:
                db_writer.record_throw(throw)
            
    except KeyboardInterrupt:
        print("\nStopping dart detection...")
        db_writer.dart_detector.stop()
        print("Dart detection stopped.")

if __name__ == "__main__":
    main()