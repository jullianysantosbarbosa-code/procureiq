"""Shared helpers for building small in-memory datasets in tests."""

from procureiq import db


def make_conn(records):
    """Create an in-memory database from (date, supplier, department, category, amount, days)."""
    conn = db.connect()
    with conn:
        for index, (day, supplier, department, category, amount, days) in enumerate(records, start=1):
            conn.execute(
                "INSERT INTO procurements VALUES (?, ?, ?, ?, ?, ?, ?)",
                (index, day, department, supplier, category, amount, days),
            )
    return conn
