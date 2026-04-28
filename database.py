import sqlite3
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "crm.db"
CSV_PATH = BASE_DIR / "contacts.csv"

CONTACT_COLUMNS = [
    "name",
    "email",
    "phone",
    "property_interest",
    "budget",
    "last_contact_days_ago",
    "deal_stage",
    "notes",
]


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        phone TEXT,
        property_interest TEXT,
        budget INTEGER,
        last_contact_days_ago INTEGER,
        deal_stage TEXT,
        notes TEXT
    )
    """)

    cursor.execute("PRAGMA table_info(contacts)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    migrations = {
        "email": "ALTER TABLE contacts ADD COLUMN email TEXT",
        "phone": "ALTER TABLE contacts ADD COLUMN phone TEXT",
        "property_interest": "ALTER TABLE contacts ADD COLUMN property_interest TEXT",
        "budget": "ALTER TABLE contacts ADD COLUMN budget INTEGER",
        "last_contact_days_ago": "ALTER TABLE contacts ADD COLUMN last_contact_days_ago INTEGER",
        "deal_stage": "ALTER TABLE contacts ADD COLUMN deal_stage TEXT",
        "notes": "ALTER TABLE contacts ADD COLUMN notes TEXT",
    }
    for column, statement in migrations.items():
        if column not in existing_columns:
            cursor.execute(statement)

    conn.commit()
    conn.close()


def load_data():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM contacts", conn)
    conn.close()
    if "id" in df.columns:
        df = df.drop(columns=["id"])
    return df


def insert_contacts(df):
    missing = [column for column in CONTACT_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    contacts = df[CONTACT_COLUMNS].copy()
    contacts["budget"] = pd.to_numeric(contacts["budget"], errors="coerce").fillna(0).astype(int)
    contacts["last_contact_days_ago"] = (
        pd.to_numeric(contacts["last_contact_days_ago"], errors="coerce")
        .fillna(0)
        .astype(int)
    )

    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM contacts")
    contacts.to_sql("contacts", conn, if_exists="append", index=False)
    conn.commit()
    conn.close()


def seed_from_csv(csv_path=CSV_PATH):
    init_db()
    df = pd.read_csv(csv_path)
    insert_contacts(df)
    return df


def ensure_seed_data():
    init_db()
    df = load_data()
    if df.empty and CSV_PATH.exists():
        return seed_from_csv()
    return df


if __name__ == "__main__":
    seeded = seed_from_csv()
    print(f"Seeded {len(seeded)} contacts into {DB_PATH}")
