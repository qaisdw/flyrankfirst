import sqlite3
import random
from datetime import datetime, timedelta

def seed_database():
    # Connect to the built-in SQLite database
    conn = sqlite3.connect('report.db')
    cursor = conn.cursor()

    # Create the orders table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer TEXT,
            product TEXT,
            amount REAL,
            created_at DATE
        )
    ''')

    # Create the reports table to track generated PDFs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT,
            created_at DATE
        )
    ''')

    # Clean existing orders so running twice is safe and leaves one copy
    cursor.execute('DELETE FROM orders')

    products = ['Laptop', 'Mouse', 'Keyboard', 'Monitor', 'Desk', 'Chair']
    customers = ['Alice', 'Bob', 'Charlie', 'David', 'Eve', 'Frank']

    # Insert ~200 random orders
    for _ in range(200):
        customer = random.choice(customers)
        product = random.choice(products)
        amount = round(random.uniform(5.0, 200.0), 2)
        days_ago = random.randint(0, 30)
        created_at = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')

        cursor.execute(
            'INSERT INTO orders (customer, product, amount, created_at) VALUES (?, ?, ?, ?)',
            (customer, product, amount, created_at)
        )

    conn.commit()
    
    # Prove the row count
    cursor.execute('SELECT COUNT(*) FROM orders')
    count = cursor.fetchone()[0]
    print(f"Database seeded successfully with {count} orders.")
    
    conn.close()

if __name__ == '__main__':
    seed_database()