"""
Database module for FitCalc bot
Handles user storage and calculation history
"""

import sqlite3
from datetime import datetime
from typing import Optional, Dict, List
import os

DB_PATH = os.getenv("DB_PATH", "fitcalc.db")


def init_db():
    """Initialize database with required tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS calculations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            gender TEXT NOT NULL,
            age INTEGER NOT NULL,
            weight REAL NOT NULL,
            height REAL NOT NULL,
            activity TEXT NOT NULL,
            goal TEXT NOT NULL,
            bmr REAL NOT NULL,
            tdee REAL NOT NULL,
            target_calories REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    
    conn.commit()
    conn.close()


def add_or_update_user(user_id: int, username: Optional[str], first_name: Optional[str]):
    """Add new user or update existing one."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO users (user_id, username, first_name)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name
    """, (user_id, username, first_name))
    
    conn.commit()
    conn.close()


def save_calculation(user_id: int, data: Dict):
    """Save a calculation to database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO calculations (
            user_id, gender, age, weight, height, 
            activity, goal, bmr, tdee, target_calories
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        data['gender'],
        data['age'],
        data['weight'],
        data['height'],
        data['activity'],
        data['goal'],
        data['bmr'],
        data['tdee'],
        data['target_calories']
    ))
    
    conn.commit()
    conn.close()


def get_user_stats() -> Dict:
    """Get overall statistics about users and calculations."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM calculations")
    total_calculations = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT AVG(age), AVG(weight), AVG(height) 
        FROM calculations
    """)
    avg_data = cursor.fetchone()
    
    cursor.execute("""
        SELECT goal, COUNT(*) as count
        FROM calculations
        GROUP BY goal
        ORDER BY count DESC
    """)
    goals = cursor.fetchall()
    
    cursor.execute("""
        SELECT activity, COUNT(*) as count
        FROM calculations
        GROUP BY activity
        ORDER BY count DESC
    """)
    activities = cursor.fetchall()
    
    conn.close()
    
    return {
        'total_users': total_users,
        'total_calculations': total_calculations,
        'avg_age': round(avg_data[0], 1) if avg_data[0] else 0,
        'avg_weight': round(avg_data[1], 1) if avg_data[1] else 0,
        'avg_height': round(avg_data[2], 1) if avg_data[2] else 0,
        'top_goals': goals,
        'top_activities': activities
    }


def get_user_history(user_id: int, limit: int = 5) -> List[Dict]:
    """Get calculation history for a specific user."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT age, weight, height, activity, goal, 
               target_calories, created_at
        FROM calculations
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ?
    """, (user_id, limit))
    
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for row in rows:
        history.append({
            'age': row[0],
            'weight': row[1],
            'height': row[2],
            'activity': row[3],
            'goal': row[4],
            'target_calories': row[5],
            'created_at': row[6]
        })
    
    return history