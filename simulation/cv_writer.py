import sqlite3
from datetime import datetime
from contextlib import contextmanager
from flask_socketio import SocketIO
from darts_cv_simulation import DartDetection
import threading
import time

class CVDatabaseWriter:
    def __init__(self, db_path='cv_data.db'):
        self.db_path = db_path
        self.socketio = SocketIO()
        self.dart_detector = DartDetection(self.socketio)
        
        # Initialize database
        self.setup_database()
        
        # Setup event handlers
        self.socketio.on_event('dart_detected', self.handle_dart_detection)
        
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
            
            # Create throws table
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
            
    def handle_dart_detection(self, data):
        """Handle the dart_detected event from DartDetection"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Extract data
                score = data['score']
                multiplier = data['multiplier']
                position = data['position']
                
                # Insert throw data
                cursor.execute('''
                    INSERT INTO throws (score, multiplier, position_x, position_y)
                    VALUES (?, ?, ?, ?)
                ''', (score, multiplier, position[0], position[1]))
                
                conn.commit()
                print(f"Recorded throw: Score={score}, Multiplier={multiplier}")
                
        except sqlite3.Error as e:
            print(f"Database error: {e}")
        except Exception as e:
            print(f"Error handling dart detection: {e}")

def main():
    # Create the database writer
    db_writer = CVDatabaseWriter()
    
    # Initialize the dart detector
    db_writer.dart_detector.initialize()
    
    try:
        # Start the dart detection
        print("Starting dart detection simulation...")
        db_writer.dart_detector.start()
        
        # Keep the script running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping dart detection...")
        db_writer.dart_detector.stop()
        print("Dart detection stopped.")

if __name__ == "__main__":
    main()