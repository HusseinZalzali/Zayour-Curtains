import os
import sqlite3

def setup_database():
    # Delete the existing database file if it exists
    if os.path.exists('workshop.db'):
        os.remove('workshop.db')
        print("Existing database deleted. Starting fresh setup...")

    # Connect to the SQLite database
    conn = sqlite3.connect('workshop.db')
    cursor = conn.cursor()

    # Create Workers Table with Roles
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Workers (
        WorkerID INTEGER PRIMARY KEY AUTOINCREMENT,
        Name TEXT NOT NULL,
        PhoneNumber TEXT,
        Role TEXT NOT NULL,
        Salary REAL NOT NULL,
        StartDate DATE NOT NULL
    )
    ''')

    # Create Workshop Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Workshop (
        WorkshopID INTEGER PRIMARY KEY AUTOINCREMENT,
        Location TEXT NOT NULL,
        CustomerName TEXT NOT NULL,
        PhoneNumber TEXT NOT NULL,
        Details TEXT,
        Type TEXT,
        WorkerID INTEGER,
        RequestDate DATE,
        DoneDate DATE,
        CostOnMe REAL,
        CostOnCustomer REAL,
        Status TEXT,
        Notes TEXT,
        IncludesRails TEXT,
        FOREIGN KEY (WorkerID) REFERENCES Workers(WorkerID)
    )
    ''')

    # Create Payments Table for Tracking دفعات
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Payments (
        PaymentID INTEGER PRIMARY KEY AUTOINCREMENT,
        WorkshopID INTEGER,
        PaymentDate DATE,
        Amount REAL,
        Notes TEXT,
        FOREIGN KEY (WorkshopID) REFERENCES Workshop(WorkshopID)
    )
    ''')

    # Create Photos Table to Store Images
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Photos (
        PhotoID INTEGER PRIMARY KEY AUTOINCREMENT,
        WorkshopID INTEGER,
        Photo BLOB,
        FOREIGN KEY (WorkshopID) REFERENCES Workshop(WorkshopID)
    )
    ''')

    # Create Transactions Table to Store Images
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Transactions (
    TransactionID INTEGER PRIMARY KEY AUTOINCREMENT,
    TransactionType TEXT NOT NULL, 
    Amount REAL NOT NULL,       
    Date DATE NOT NULL DEFAULT CURRENT_DATE,
    Category TEXT,               
    Notes TEXT                     
    );
    ''')

    # Create WorkshopWorkers Table 
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS WorkshopWorkers (
    ID INTEGER PRIMARY KEY AUTOINCREMENT,
    WorkshopID INTEGER NOT NULL,
    WorkerID INTEGER NOT NULL,
    FOREIGN KEY (WorkshopID) REFERENCES Workshop(WorkshopID) ON DELETE CASCADE,
    FOREIGN KEY (WorkerID) REFERENCES Workers(WorkerID) ON DELETE CASCADE
    );

    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS WorkshopTypes (
    ID INTEGER PRIMARY KEY AUTOINCREMENT,
    WorkshopID INTEGER NOT NULL,
    Type TEXT NOT NULL,
    FOREIGN KEY (WorkshopID) REFERENCES Workshop(WorkshopID) ON DELETE CASCADE
    );


    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS WorkshopPhotos (
    PhotoID INTEGER PRIMARY KEY AUTOINCREMENT,
    WorkshopID INTEGER NOT NULL,
    PhotoPath TEXT NOT NULL, -- Path to the photo file
    Caption TEXT,            -- Optional caption for the photo
    FOREIGN KEY (WorkshopID) REFERENCES Workshop(WorkshopID) ON DELETE CASCADE
);


    ''')



    # Commit the changes and close the connection
    conn.commit()
    conn.close()
    print("Database setup completed successfully.")

if __name__ == '__main__':
    setup_database()
