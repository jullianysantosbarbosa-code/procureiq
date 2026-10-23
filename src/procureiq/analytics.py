"""Analytics queries and red-flag detection on the procurements table."""

from __future__ import annotations

import sqlite3
import statistics
from dataclasses import dataclass, field
from datetime import date
from itertools import groupby


def spend_by_supplier(conn: sqlite3.Connection, limit: int = 10) -> list[dict]:
    """Total spend per supplier, largest first, with each supplier's share."""
    grand_total = conn.execute(
        "SELECT COALESCE(SUM(amount_eur), 0) FROM procurements"
    ).fetchone()[0]
    rows = conn.execute(
        """
        SELECT supplier, SUM(amount_eur) AS total, COUNT(*) AS n
        FROM procurements
        GROUP BY supplier
        ORDER BY total DESC, supplier
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [
        {
            "supplier": supplier,
            "total_eur": round(total, 2),
            "count": count,
            "share_pct": round(100 * total / grand_total, 1) if grand_total else 0.0,
        }
        for supplier, total, count in rows
    ]


def monthly_spend(conn: sqlite3.Connection) -> list[dict]:
    """Total spend and number of procurements per calendar month."""
    rows = conn.execute(
        """
        SELECT strftime('%Y-%m', date) AS month, SUM(amount_eur), COUNT(*)
        FROM procurements
        GROUP BY month
        ORDER BY month
        """
    ).fetchall()
    return [
        {"month": month, "total_eur": round(total, 2), "count": count}
        for month, total, count in rows
    ]


def lead_times_by_category(conn: sqlite3.Connection) -> list[dict]:
    """Processing time statistics per category, slowest (by median) first."""
    rows = conn.execute(
        "SELECT category, processing_days FROM procurements ORDER BY category"
    ).fetchall()
    result = []
    for category, group in groupby(rows, key=lambda r: r[0]):
        days = [r[1] for r in group]
        result.append(
            {
                "category": category,
                "count": len(days),
                "median_days": float(statistics.median(days)),
                "mean_days": round(statistics.mean(days), 1),
                "max_days": max(days),
            }
        )
    return sorted(result, key=lambda r: (-r["median_days"], r["category"]))


@dataclass
class SplitPurchaseFlag:
    """A cluster of small purchases that together cross the approval threshold."""

    supplier: str
    department: str
    category: str
    start: str
    end: str
    count: int
    total_eur: float
    ids: list[int] = field(default_factory=list)


def find_split_purchases(
    conn: sqlite3.Connection,
    threshold: float = 50_000,
    window_days: int = 30,
) -> list[SplitPurchaseFlag]:
    """Flag possible contract splitting.

    For each supplier, department and category, look for two or more purchases
    that are each below ``threshold`` but fall within ``window_days`` of each
    other and together reach the threshold. Clusters do not overlap.

    A flag is a prompt for a human to review, not proof of wrongdoing.
    """
    rows = conn.execute(
        """
        SELECT id, date, supplier, department, category, amount_eur
        FROM procurements
        WHERE amount_eur < ?
        ORDER BY supplier, department, category, date, id
        """,
        (threshold,),
    ).fetchall()

    flags: list[SplitPurchaseFlag] = []
    for (supplier, department, category), group in groupby(
        rows, key=lambda r: (r[2], r[3], r[4])
    ):
        items = [(r[0], date.fromisoformat(r[1]), r[5]) for r in group]
        i = 0
        while i < len(items):
            j, total = i, 0.0
            while j < len(items) and (items[j][1] - items[i][1]).days <= window_days:
                total += items[j][2]
                j += 1
            if j - i >= 2 and total >= threshold:
                cluster = items[i:j]
                flags.append(
                    SplitPurchaseFlag(
                        supplier=supplier,
                        department=department,
                        category=category,
                        start=cluster[0][1].isoformat(),
                        end=cluster[-1][1].isoformat(),
                        count=len(cluster),
                        total_eur=round(total, 2),
                        ids=[c[0] for c in cluster],
                    )
                )
                i = j
            else:
                i += 1
    return sorted(flags, key=lambda f: -f.total_eur)


@dataclass
class OutlierFlag:
    """A purchase far above the usual spend for its category."""

    id: int
    date: str
    supplier: str
    category: str
    amount_eur: float
    upper_fence_eur: float


def find_outliers(
    conn: sqlite3.Connection, k: float = 3.0, min_group: int = 8
) -> list[OutlierFlag]:
    """Flag unusually high purchases using Tukey's fences.

    The upper fence is ``Q3 + k * IQR`` per category. The quartile-based rule is
    robust: extreme values do not distort the threshold the way they would with
    a mean and standard deviation. Categories with fewer than ``min_group``
    records are skipped because the quartiles would be unreliable.
    """
    rows = conn.execute(
        """
        SELECT id, date, supplier, category, amount_eur
        FROM procurements
        ORDER BY category, id
        """
    ).fetchall()

    flags: list[OutlierFlag] = []
    for category, group in groupby(rows, key=lambda r: r[3]):
        records = list(group)
        if len(records) < min_group:
            continue
        q1, _, q3 = statistics.quantiles([r[4] for r in records], n=4)
        fence = q3 + k * (q3 - q1)
        for rec_id, rec_date, supplier, _, amount in records:
            if amount > fence:
                flags.append(
                    OutlierFlag(rec_id, rec_date, supplier, category, amount, round(fence, 2))
                )
    return sorted(flags, key=lambda f: -f.amount_eur)
