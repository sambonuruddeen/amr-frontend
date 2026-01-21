import mysql.connector
import logging

# MySQL Database Settings (Copied from app.py)
DB_HOST = "localhost"
DB_PORT = 3306
DB_NAME = "jed_data"
DB_USER = "root"
DB_PASSWORD = ""

def get_db_connection():
    conn = mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    return conn

def apply_updates():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # 1. Customers Table
        print("Creating 'customers' table...")
        cur.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            account_number VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(255),
            phone VARCHAR(50),
            address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # 2. Add customer_id to feeder_details (linking Meter to Customer)
        # Check if column exists first to avoid error on re-run
        print("Checking 'feeder_details' for 'customer_id' column...")
        cur.execute("SHOW COLUMNS FROM feeder_details LIKE 'customer_id'")
        result = cur.fetchone()
        if not result:
            print("Adding 'customer_id' column to 'feeder_details'...")
            cur.execute('''
            ALTER TABLE feeder_details 
            ADD COLUMN customer_id INT,
            ADD CONSTRAINT fk_feeder_customer FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
            ''')
        else:
            print("'customer_id' column already exists.")

        # 3. Tariffs Table
        print("Creating 'tariffs' table...")
        cur.execute('''
        CREATE TABLE IF NOT EXISTS tariffs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL, -- e.g., 'Residential Band A', 'Commercial Band B'
            band VARCHAR(50), -- To link with 'band' in feeder_details
            rate_per_kwh DECIMAL(10, 2) NOT NULL,
            effective_date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # 4. Bills Table
        print("Creating 'bills' table...")
        cur.execute('''
        CREATE TABLE IF NOT EXISTS bills (
            id INT AUTO_INCREMENT PRIMARY KEY,
            meter_serial_number VARCHAR(255) NOT NULL,
            customer_id INT,
            tariff_id INT,
            billing_period_start DATE NOT NULL,
            billing_period_end DATE NOT NULL,
            total_kwh DECIMAL(10, 2) NOT NULL,
            tariff_rate_applied DECIMAL(10, 2) NOT NULL,
            total_amount DECIMAL(15, 2) NOT NULL,
            status ENUM('Generated', 'Sent', 'Paid', 'Overdue') DEFAULT 'Generated',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (tariff_id) REFERENCES tariffs(id)
        )
        ''')

        conn.commit()
        print("Database schema updated successfully!")

    except Exception as e:
        print(f"Error applying updates: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    apply_updates()
