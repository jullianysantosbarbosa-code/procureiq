"""SQLite storage layer: schema creation and validated CSV import."""

from __future__ import annotations

import csv
import sqlite3
from datetime import date
from pathlib import Path

REQUIRED_COLUMNS = {
    "id",
    "date",
    "department",
    "supplier",
    "category",
    "amount_eur",
    "processing_days",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS procurements (
    id              INTEGER PRIMARY KEY,
    date            TEXT    NOT NULL,
    department      TEXT    NOT NULL,
    supplier        TEXT    NOT NULL,
    category        TEXT    NOT NULL,
    amount_eur      REAL    NOT NULL CHECK (amount_eur >= 0),
    processing_days INTEGER NOT NULL CHECK (processing_days >= 0)
);
CREATE INDEX IF NOT EXISTS idx_procurements_supplier ON procurements (supplier);
CREATE INDEX IF NOT EXISTS idx_procurements_date ON procurements (date);
"""


def connect(path: str = ":memory:") -> sqlite3.Connection:
    """Open a database and make sure the schema exists."""
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def _parse_row(line_number: int, raw: dict) -> tuple:
    """Validate one CSV record and convert it to database types."""
    try:
        row_id = int(raw["id"])
        date.fromisoformat(raw["date"])
        amount = float(raw["amount_eur"])
        days = int(raw["processing_days"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"line {line_number}: invalid value ({exc})") from exc

    if amount < 0 or days < 0:
        raise ValueError(f"line {line_number}: amount and processing days must be >= 0")

    for field in ("department", "supplier", "category"):
        if not (raw[field] or "").strip():
            raise ValueError(f"line {line_number}: '{field}' must not be empty")

    return (
        row_id,
        raw["date"],
        raw["department"].strip(),
        raw["supplier"].strip(),
        raw["category"].strip(),
        amount,
        days,
    )


def load_csv(conn: sqlite3.Connection, csv_path: str | Path) -> int:
    """Replace the table contents with the validated rows of ``csv_path``.

    Nothing is written if any row is invalid. Returns the number of rows loaded.
    """
    with Path(csv_path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"missing columns: {', '.join(sorted(missing))}")
        # Line 1 is the header, so data starts on line 2.
        rows = [_parse_row(n, raw) for n, raw in enumerate(reader, start=2)]

    with conn:
        conn.execute("DELETE FROM procurements")
        conn.executemany(
            "INSERT INTO procurements VALUES (?, ?, ?, ?, ?, ?, ?)", rows
        )
    return len(rows)
