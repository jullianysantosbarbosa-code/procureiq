"""Synthetic procurement data generator.

Most purchases are small and a few are large, as in real spending data.

All data is fictional: no real suppliers, contracts or government records are
used. The generator is deterministic for a given seed, and it deliberately
injects a few split purchases and spending outliers so the red-flag detection
has something realistic to find.
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

FIELDNAMES = [
    "id",
    "date",
    "department",
    "supplier",
    "category",
    "amount_eur",
    "processing_days",
]

# category -> (min amount, max amount, min processing days, max processing days)
CATEGORIES = {
    "IT Services": (2_000, 48_000, 12, 45),
    "Consulting": (5_000, 90_000, 20, 70),
    "Facilities": (500, 30_000, 7, 30),
    "Training": (300, 12_000, 5, 25),
    "Office Supplies": (100, 4_000, 2, 10),
}

DEPARTMENTS = ["Finance", "Operations", "HR", "Legal", "IT"]

SUPPLIERS = {
    "Northwind Digital": 18,
    "Liffey Consulting Group": 16,
    "Atlas Cloud Services": 14,
    "Emerald Facilities Ltd": 12,
    "Harbour Office Supplies": 10,
    "Celtic Training Partners": 8,
    "Orion Analytics": 8,
    "Greenfield Maintenance": 6,
    "Bluebell Stationery": 5,
    "Shamrock Logistics": 3,
}


def generate_rows(
    n: int = 600,
    seed: int = 42,
    start: date = date(2024, 1, 1),
    days: int = 730,
) -> list[dict]:
    """Return ``n`` fictional procurement records, sorted by date."""
    rng = random.Random(seed)
    suppliers = list(SUPPLIERS)
    weights = list(SUPPLIERS.values())
    rows: list[dict] = []

    for _ in range(n):
        category = rng.choice(list(CATEGORIES))
        low, high, d_min, d_max = CATEGORIES[category]
        rows.append(
            {
                "date": start + timedelta(days=rng.randrange(days)),
                "department": rng.choice(DEPARTMENTS),
                "supplier": rng.choices(suppliers, weights)[0],
                "category": category,
                "amount_eur": round(rng.triangular(low, high, low + (high - low) * 0.15), 2),
                "processing_days": rng.randint(d_min, d_max),
            }
        )

    # Injected scenario 1: purchases split into pieces just under 50,000 EUR.
    for _ in range(3):
        supplier = rng.choice(suppliers[:6])
        department = rng.choice(DEPARTMENTS)
        first = start + timedelta(days=rng.randrange(days - 30))
        for step in range(3):
            rows.append(
                {
                    "date": first + timedelta(days=step * rng.randint(2, 6)),
                    "department": department,
                    "supplier": supplier,
                    "category": "IT Services",
                    "amount_eur": round(rng.uniform(19_000, 24_000), 2),
                    "processing_days": rng.randint(3, 8),
                }
            )

    # Injected scenario 2: office-supply purchases far above the usual range.
    for _ in range(3):
        rows.append(
            {
                "date": start + timedelta(days=rng.randrange(days)),
                "department": rng.choice(DEPARTMENTS),
                "supplier": "Harbour Office Supplies",
                "category": "Office Supplies",
                "amount_eur": round(rng.uniform(26_000, 38_000), 2),
                "processing_days": rng.randint(2, 6),
            }
        )

    rows.sort(key=lambda r: (r["date"], r["supplier"]))
    for index, row in enumerate(rows, start=1):
        row["id"] = index
        row["date"] = row["date"].isoformat()
    return rows


def write_csv(rows: list[dict], path: str | Path) -> None:
    """Write rows to ``path`` using the standard ProcureIQ column order."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
