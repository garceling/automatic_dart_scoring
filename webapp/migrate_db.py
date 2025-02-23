import sqlite3
from contextlib import contextmanager

@contextmanager
def get_db_connection():
    conn = None
    try:
        conn = sqlite3.connect('dartboard.db')
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        if conn:
            conn.close()

def add_score_before_columns():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Add the new columns
        try:
            cursor.execute('''
                ALTER TABLE GameRounds 
                ADD COLUMN score_before_throw1 INTEGER
            ''')
            print("Added score_before_throw1 column")
            
            cursor.execute('''
                ALTER TABLE GameRounds 
                ADD COLUMN score_before_throw2 INTEGER
            ''')
            print("Added score_before_throw2 column")
            
            cursor.execute('''
                ALTER TABLE GameRounds 
                ADD COLUMN score_before_throw3 INTEGER
            ''')
            print("Added score_before_throw3 column")
            
            # Commit the changes
            conn.commit()
            print("Successfully added all columns")
            
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"Column already exists: {e}")
            else:
                raise

if __name__ == "__main__":
    print("Starting database migration...")
    add_score_before_columns()
    print("Database migration completed")