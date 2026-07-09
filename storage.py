# storage.py
#
# Minimal SQLite storage - one file, no server needed. Good enough for an
# MVP up to several thousand users. Migrate to Postgres later if you scale.
#
# NOTE ON MIGRATION: this version adds new columns (foods_json, note,
# insight) to support multi-food results. init_db() adds them safely with
# ALTER TABLE if they don't already exist, so this is safe to deploy on
# top of an already-running database (like your live Railway instance)
# without losing existing data or crashing on startup.

import json
import sqlite3
from datetime import datetime, timedelta

DB_PATH = "calories.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            food_name_kurdish TEXT,
            food_name_english TEXT,
            kcal INTEGER,
            protein_g INTEGER,
            carbs_g INTEGER,
            fat_g INTEGER,
            confidence TEXT,
            matched_glossary INTEGER,
            feedback TEXT,
            created_at TEXT NOT NULL
        )
        """
    )

    # Safe migration: add any columns that didn't exist in earlier versions
    # of this table (e.g. on an already-deployed database) without touching
    # existing data.
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(meals)")}
    new_columns = {
        "foods_json": "TEXT",
        "note_kurdish": "TEXT",
        "insight_kurdish": "TEXT",
    }
    for col, col_type in new_columns.items():
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE meals ADD COLUMN {col} {col_type}")

    conn.commit()
    conn.close()


def log_meal(user_id: int, result: dict) -> int:
    """
    Inserts a meal (one row per photo, possibly containing several foods)
    and returns its row id (used for feedback buttons).
    """
    foods = result.get("foods", [])
    food_summary = "، ".join(f["name_kurdish"] for f in foods) or "نەناسراو"
    any_matched = any(f.get("matched_glossary") for f in foods)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        """
        INSERT INTO meals (user_id, food_name_kurdish, food_name_english,
                            kcal, protein_g, carbs_g, fat_g, confidence,
                            matched_glossary, feedback, created_at,
                            foods_json, note_kurdish, insight_kurdish)
        VALUES (?, ?, '', ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)
        """,
        (
            user_id,
            food_summary,
            result.get("total_kcal", 0),
            result.get("total_protein_g", 0),
            result.get("total_carbs_g", 0),
            result.get("total_fat_g", 0),
            result.get("confidence", "نزم"),
            int(bool(any_matched)),
            datetime.utcnow().isoformat(),
            json.dumps(foods, ensure_ascii=False),
            result.get("note_kurdish", ""),
            result.get("insight_kurdish", ""),
        ),
    )
    conn.commit()
    meal_id = cur.lastrowid
    conn.close()
    return meal_id


def set_feedback(meal_id: int, feedback: str):
    """feedback is 'correct' or 'wrong'."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE meals SET feedback = ? WHERE id = ?", (feedback, meal_id))
    conn.commit()
    conn.close()


def get_meal(meal_id: int) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute("SELECT * FROM meals WHERE id = ?", (meal_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_wrong_feedback_log(limit: int = 100) -> list[dict]:
    """
    Pulls recent 'wrong' feedback so you can review them and decide what
    to add or fix in kurdish_foods.py.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        """
        SELECT * FROM meals WHERE feedback = 'wrong'
        ORDER BY created_at DESC LIMIT ?
        """,
        (limit,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_total_since(user_id: int, since: datetime) -> dict:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        """
        SELECT COALESCE(SUM(kcal), 0), COALESCE(SUM(protein_g), 0),
               COALESCE(SUM(carbs_g), 0), COALESCE(SUM(fat_g), 0)
        FROM meals WHERE user_id = ? AND created_at >= ?
        """,
        (user_id, since.isoformat()),
    )
    kcal, protein, carbs, fat = cur.fetchone()
    conn.close()
    return {"kcal": kcal, "protein_g": protein, "carbs_g": carbs, "fat_g": fat}


def get_today_total(user_id: int) -> dict:
    since = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return get_total_since(user_id, since)


def get_week_total(user_id: int) -> dict:
    since = datetime.utcnow() - timedelta(days=7)
    return get_total_since(user_id, since)


def get_meal_count_today(user_id: int) -> int:
    since = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "SELECT COUNT(*) FROM meals WHERE user_id = ? AND created_at >= ?",
        (user_id, since.isoformat()),
    )
    count = cur.fetchone()[0]
    conn.close()
    return count
