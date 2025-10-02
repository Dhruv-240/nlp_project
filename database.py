
import sqlite3
import bcrypt

def create_connection():
    """Creates a database connection."""
    conn = sqlite3.connect('users.db')
    return conn

def create_table(conn):
    """Creates the users table if it doesn't exist."""
    try:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            )
        """)
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error creating table: {e}")

def add_user(conn, username, password):
    """Adds a new user to the database with an encrypted password."""
    try:
        c = conn.cursor()
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Username already exists
    except sqlite3.Error as e:
        print(f"Error adding user: {e}")
        return False

def check_user(conn, username, password):
    """Checks if a user exists and the password is correct."""
    try:
        c = conn.cursor()
        c.execute("SELECT password FROM users WHERE username = ?", (username,))
        stored_password_hash = c.fetchone()
        if stored_password_hash:
            return bcrypt.checkpw(password.encode('utf-8'), stored_password_hash[0])
        return False
    except sqlite3.Error as e:
        print(f"Error checking user: {e}")
        return False
