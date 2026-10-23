"""Command-line interface for ProcureIQ."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Sequence

from . import analytics, db, generate


def format_table(headers: Sequence[str], rows: Sequence[Sequence], right: Sequence[int] = ()) -> str:
    """Render rows as a plain-text table. ``right`` lists right-aligned columns."""
    cells = [[str(c) for c in row] for row in rows]
    widths = [
        max(len(h), *(len(r[i]) for r in cells)) if cells else len(h)
        for i, h in enumerate(headers)
    ]

    def line(values: Sequence[str]) -> str:
        parts = [
            v.rjust(widths[i]) if i in right else v.ljust(widths[i])
            for i, v in enumerate(values)
        ]
        return "  ".join(parts).rstrip()

    out = [line(headers), line(["-" * w for w in widths])]
    out.extend(line(r) for r in cells)
    return "\n".join(out)


def money(value: float) -> str:
    return f"{value:,.2f}"


def _load(csv_path: str):
    conn = db.connect()
    db.load_csv(conn, csv_path)
    return conn


def _emit(args: argparse.Namespace, data, table: str) -> None:
    print(json.dumps(data, indent=2) if args.json else table)


def cmd_generate(args: argparse.Namespace) -> None:
    rows = generate.generate_rows(n=args.rows, seed=args.seed)
    generate.write_csv(rows, args.out)
    print(f"Wrote {len(rows)} synthetic procurement records to {args.out}")


def cmd_suppliers(args: argparse.Namespace) -> None:
    data = analytics.spend_by_supplier(_load(args.csv), limit=args.top)
    table = format_table(
        ["Supplier", "Spend (EUR)", "Orders", "Share %"],
        [(d["supplier"], money(d["total_eur"]), d["count"], d["share_pct"]) for d in data],
        right=(1, 2, 3),
    )
    _emit(args, data, table)


def cmd_monthly(args: argparse.Namespace) -> None:
    data = analytics.monthly_spend(_load(args.csv))
    table = format_table(
        ["Month", "Spend (EUR)", "Orders"],
        [(d["month"], money(d["total_eur"]), d["count"]) for d in data],
        right=(1, 2),
    )
    _emit(args, data, table)


def cmd_lead_times(args: argparse.Namespace) -> None:
    data = analytics.lead_times_by_category(_load(args.csv))
    table = format_table(
        ["Category", "Orders", "Median days", "Mean days", "Max days"],
        [
            (d["category"], d["count"], f'{d["median_days"]:.1f}', f'{d["mean_days"]:.1f}', d["max_days"])
            for d in data
        ],
        right=(1, 2, 3, 4),
    )
    _emit(args, data, table)


def cmd_flags(args: argparse.Namespace) -> None:
    flags = analytics.find_split_purchases(
        _load(args.csv), threshold=args.threshold, window_days=args.window
    )
    data = [asdict(f) for f in flags]
    if not flags:
        table = "No possible split purchases found."
    else:
        table = format_table(
            ["Supplier", "Department", "Category", "From", "To", "Orders", "Total (EUR)"],
            [
                (f.supplier, f.department, f.category, f.start, f.end, f.count, money(f.total_eur))
                for f in flags
            ],
            right=(5, 6),
        )
    _emit(args, data, table)


def cmd_outliers(args: argparse.Namespace) -> None:
    flags = analytics.find_outliers(_load(args.csv), k=args.k)
    data = [asdict(f) for f in flags]
    if not flags:
        table = "No unusual purchases found."
    else:
        table = format_table(
            ["ID", "Date", "Supplier", "Category", "Amount (EUR)", "Upper fence (EUR)"],
            [
                (f.id, f.date, f.supplier, f.category, money(f.amount_eur), money(f.upper_fence_eur))
                for f in flags
            ],
            right=(0, 4, 5),
        )
    _emit(args, data, table)


def cmd_summary(args: argparse.Namespace) -> None:
    conn = _load(args.csv)
    count, total, first, last = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(amount_eur), 0), MIN(date), MAX(date) FROM procurements"
    ).fetchone()
    top = analytics.spend_by_supplier(conn, limit=3)
    splits = analytics.find_split_purchases(conn)
    outliers = analytics.find_outliers(conn)
    summary = {
        "records": count,
        "total_spend_eur": round(total, 2),
        "period": [first, last],
        "top_suppliers": top,
        "possible_split_purchases": len(splits),
        "unusual_purchases": len(outliers),
    }
    lines = [
        f"Records:            {count}",
        f"Period:             {first} to {last}",
        f"Total spend (EUR):  {money(total)}",
        "Top suppliers:      " + ", ".join(f"{t['supplier']} ({t['share_pct']}%)" for t in top),
        f"Possible split purchases: {len(splits)}",
        f"Unusual purchases:        {len(outliers)}",
    ]
    _emit(args, summary, "\n".join(lines))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="procureiq",
        description="Analyse procurement data: spend, lead times and red flags.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="create a synthetic dataset")
    gen.add_argument("--rows", type=int, default=600)
    gen.add_argument("--seed", type=int, default=42)
    gen.add_argument("--out", default="data/sample_procurements.csv")
    gen.set_defaults(func=cmd_generate)

    def with_csv(name: str, help_text: str, func) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("csv", help="path to a procurement CSV file")
        p.add_argument("--json", action="store_true", help="print JSON instead of a table")
        p.set_defaults(func=func)
        return p

    with_csv("summary", "headline numbers for a dataset", cmd_summary)
    sup = with_csv("suppliers", "spend by supplier", cmd_suppliers)
    sup.add_argument("--top", type=int, default=10)
    with_csv("monthly", "spend per month", cmd_monthly)
    with_csv("lead-times", "processing time by category", cmd_lead_times)
    flg = with_csv("flags", "detect possible split purchases", cmd_flags)
    flg.add_argument("--threshold", type=float, default=50_000, help="approval threshold in EUR")
    flg.add_argument("--window", type=int, default=30, help="window in days")
    out = with_csv("outliers", "detect unusually high purchases", cmd_outliers)
    out.add_argument("--k", type=float, default=3.0, help="IQR multiplier for the upper fence")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0
