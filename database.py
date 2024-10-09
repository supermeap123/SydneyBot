# database.py
import sqlite3
import threading
import shutil
import os
from config import logger

db_lock = threading.Lock()
DATABASE_FILE = 'user_preferences.db'

def init_database():
    with db_lock:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        # Create user preferences table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id INTEGER PRIMARY KEY,
                message_prefix TEXT
            )
        ''')
        # Create probabilities table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS probabilities (
                guild_id TEXT,
                channel_id TEXT,
                reply_probability REAL DEFAULT 0.1,
                reaction_probability REAL DEFAULT 0.2,
                PRIMARY KEY (guild_id, channel_id)
            )
        ''')
        conn.commit()
        conn.close()
        logger.info("Database initialized.")

def load_user_preference(user_id):
    """Load user preferences."""
    with db_lock:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT message_prefix FROM user_preferences WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None

def save_user_preference(user_id, message_prefix):
    """Save user preferences."""
    with db_lock:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute('REPLACE INTO user_preferences (user_id, message_prefix) VALUES (?, ?)', (user_id, message_prefix))
        conn.commit()
        conn.close()

def backup_database():
    """Create a backup of the database file."""
    with db_lock:
        backup_file = f"{DATABASE_FILE}.bak"
        shutil.copy(DATABASE_FILE, backup_file)
    logger.info("Database backup created.")

def load_probabilities(guild_id, channel_id):
    """Load reply and reaction probabilities."""
    with db_lock:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT reply_probability, reaction_probability 
            FROM probabilities 
            WHERE guild_id = ? AND channel_id = ?
        ''', (guild_id, str(channel_id)))
        result = cursor.fetchone()
        conn.close()
        if result:
            reply_probability, reaction_probability = result
        else:
            reply_probability, reaction_probability = 0.1, 0.2  # Default values
        return reply_probability, reaction_probability

def save_probabilities(guild_id, channel_id, reply_probability=None, reaction_probability=None):
    """Save reply and reaction probabilities."""
    current_reply_prob, current_reaction_prob = load_probabilities(guild_id, channel_id)
    reply_probability = reply_probability if reply_probability is not None else current_reply_prob
    reaction_probability = reaction_probability if reaction_probability is not None else current_reaction_prob
    with db_lock:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO probabilities (guild_id, channel_id, reply_probability, reaction_probability)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, channel_id) DO UPDATE SET
                reply_probability = excluded.reply_probability,
                reaction_probability = excluded.reaction_probability
        ''', (guild_id, str(channel_id), reply_probability, reaction_probability))
        conn.commit()
        conn.close()