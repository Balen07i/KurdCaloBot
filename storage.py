# storage.py
#
# Minimal SQLite storage - one file, no server needed, no paid services.
# Good enough for an MVP up to several thousand users.
#
# Tables:
#   meals       - one row per photo analyzed (unchanged from before)
#   users       - profile, targets, and onboarding/correction conversation
#                 state (kept in the DB, not memory, so it survives restarts)
#   corrections - user-submitted fixes, reused as extra glossary context
#                 for every future photo (this is the "free learning" loop)
#
# All ALTER TABLE migrations are additive and safe to run on top of an
# already-deployed database - existing data is never touched or dropped.

import json
import sqlite3
from datetime import datetime, timedelta

DB_PATH = "calories.db"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    # WAL mode lets reads and writes happen concurrently instead of
    # blocking each other - free improvement for multiple simultaneous
    # users, no behavior change otherwise.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def _add_missing_columns(conn, table: str, columns: dict):
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    for col, col_type in columns.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")


def init_db():
    conn = _connect()

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
    _add_missing_columns(
        conn, "meals",
        {"foods_json": "TEXT", "note_kurdish": "TEXT", "insight_kurdish": "TEXT"},
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            age INTEGER,
            sex TEXT,
            height_cm REAL,
            weight_kg REAL,
            goal TEXT,
            activity_level TEXT,
            bmr INTEGER,
            tdee INTEGER,
            target_kcal INTEGER,
            target_protein_g INTEGER,
            target_carbs_g INTEGER,
            target_fat_g INTEGER,
            onboarding_step TEXT,
            pending_correction_meal_id INTEGER,
            created_at TEXT
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            wrong_name TEXT,
            correct_name_kurdish TEXT,
            created_at TEXT NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()


# --- Meals ---------------------------------------------------------------

def log_meal(user_id: int, result: dict) -> int:
    """Inserts a meal (one row per photo) and returns its row id."""
    foods = result.get("foods", [])
    food_summary = "، ".join(f["name_kurdish"] for f in foods) or "نەناسراو"
    any_matched = any(f.get("matched_glossary") for f in foods)

    conn = _connect()
    cur = conn.execute(
        """
        INSERT INTO meals (user_id, food_name_kurdish, food_name_english,
                            kcal, protein_g, carbs_g, fat_g, confidence,
                            matched_glossary, feedback, created_at,
                            foods_json, note_kurdish, insight_kurdish)
        VALUES (?, ?, '', ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)
        """,
        (
            user_id, food_summary,
            result.get("total_kcal", 0), result.get("total_protein_g", 0),
            result.get("total_carbs_g", 0), result.get("total_fat_g", 0),
            result.get("confidence", "نزم"), int(bool(any_matched)),
            datetime.utcnow().isoformat(),
            json.dumps(foods, ensure_ascii=False),
            result.get("note_kurdish", ""), result.get("insight_kurdish", ""),
        ),
    )
    conn.commit()
    meal_id = cur.lastrowid
    conn.close()
    return meal_id


def set_feedback(meal_id: int, feedback: str):
    conn = _connect()
    conn.execute("UPDATE meals SET feedback = ? WHERE id = ?", (feedback, meal_id))
    conn.commit()
    conn.close()


def get_meal(meal_id: int) -> dict | None:
    conn = _connect()
    row = conn.execute("SELECT * FROM meals WHERE id = ?", (meal_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_wrong_feedback_log(limit: int = 100) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM meals WHERE feedback = 'wrong' ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _totals_between(user_id: int, start: datetime, end: datetime) -> dict:
    conn = _connect()
    row = conn.execute(
        """
        SELECT COALESCE(SUM(kcal), 0), COALESCE(SUM(protein_g), 0),
               COALESCE(SUM(carbs_g), 0), COALESCE(SUM(fat_g), 0), COUNT(*)
        FROM meals WHERE user_id = ? AND created_at >= ? AND created_at < ?
        """,
        (user_id, start.isoformat(), end.isoformat()),
    ).fetchone()
    conn.close()
    kcal, protein, carbs, fat, count = row
    return {"kcal": kcal, "protein_g": protein, "carbs_g": carbs, "fat_g": fat, "meal_count": count}


def get_today_total(user_id: int) -> dict:
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return _totals_between(user_id, start, start + timedelta(days=1))


def get_week_total(user_id: int) -> dict:
    start = datetime.utcnow() - timedelta(days=7)
    return _totals_between(user_id, start, datetime.utcnow() + timedelta(minutes=1))


def get_month_total(user_id: int) -> dict:
    start = datetime.utcnow() - timedelta(days=30)
    return _totals_between(user_id, start, datetime.utcnow() + timedelta(minutes=1))


def get_meal_count_today(user_id: int) -> int:
    return get_today_total(user_id)["meal_count"]


def get_recent_meals(user_id: int, limit: int = 10) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM meals WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def reset_user_history(user_id: int):
    conn = _connect()
    conn.execute("DELETE FROM meals WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


# --- User profile & onboarding state -------------------------------------

def get_user(user_id: int) -> dict | None:
    conn = _connect()
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def ensure_user(user_id: int):
    """Creates a blank user row if one doesn't exist yet. Safe to call anytime."""
    conn = _connect()
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, created_at) VALUES (?, ?)",
        (user_id, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def set_onboarding_step(user_id: int, step: str | None):
    ensure_user(user_id)
    conn = _connect()
    conn.execute(
        "UPDATE users SET onboarding_step = ? WHERE user_id = ?", (step, user_id)
    )
    conn.commit()
    conn.close()


def update_user_fields(user_id: int, **fields):
    ensure_user(user_id)
    conn = _connect()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(
        f"UPDATE users SET {set_clause} WHERE user_id = ?",
        (*fields.values(), user_id),
    )
    conn.commit()
    conn.close()


def has_complete_profile(user_id: int) -> bool:
    user = get_user(user_id)
    return bool(user and user.get("target_kcal"))


def set_pending_correction(user_id: int, meal_id: int | None):
    ensure_user(user_id)
    conn = _connect()
    conn.execute(
        "UPDATE users SET pending_correction_meal_id = ? WHERE user_id = ?",
        (meal_id, user_id),
    )
    conn.commit()
    conn.close()


# --- Corrections (the free "learning" loop) -------------------------------

def save_correction(user_id: int, wrong_name: str, correct_name_kurdish: str):
    conn = _connect()
    conn.execute(
        """
        INSERT INTO corrections (user_id, wrong_name, correct_name_kurdish, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, wrong_name, correct_name_kurdish, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_all_corrections(limit: int = 200) -> list[dict]:
    """
    Returns recent corrections across all users. These get folded into the
    glossary context sent to Gemini on every request, so a mistake fixed
    once by one user quietly improves recognition for everyone afterward
    - entirely free, no retraining, no external service.
    """
    conn = _connect()
    rows = conn.execute(
        "SELECT DISTINCT wrong_name, correct_name_kurdish FROM corrections "
        "ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
