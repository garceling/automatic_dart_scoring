import sqlite3
from sqlite3 import Error
from tabulate import tabulate  # For nice table formatting
from datetime import datetime

def view_database_contents():
    try:
        # Connect to database
        conn = sqlite3.connect('dartboard.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get list of all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        for table in tables:
            table_name = table[0]
            print(f"\n=== Contents of {table_name} table ===")
            
            # Get all rows from the table
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            
            if rows:
                # Get column names
                columns = [description[0] for description in cursor.description]
                
                # Convert rows to list of dicts for better readability
                formatted_rows = []
                for row in rows:
                    formatted_row = []
                    for item in row:
                        # Convert timestamps if present
                        if isinstance(item, str) and item.count('-') == 2 and 'T' in item:
                            try:
                                dt = datetime.fromisoformat(item)
                                item = dt.strftime('%Y-%m-%d %H:%M:%S')
                            except ValueError:
                                pass
                        formatted_row.append(item)
                    formatted_rows.append(formatted_row)
                
                # Print table using tabulate
                print(tabulate(formatted_rows, headers=columns, tablefmt="grid"))
            else:
                print("No data in table")
            
            print("\n")  # Add space between tables
            
    except Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("Viewing database contents...")
    view_database_contents()
