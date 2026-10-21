"""
budget — a single-file personal finance CLI backed by SQLite.

    python budget.py add -50.00 groceries "weekly shop"
    python budget.py add 2500 salary "September pay" --date 2026-09-01
    python budget.py list
    python budget.py list --month 2026-09 --category groceries
    python budget.py report
    python budget.py report --month 2026-09
    python budget.py budget set groceries 400
    python budget.py budget check --month 2026-09
    python budget.py delete 7

Amounts are positive for income, negative for spending. The database lives in
budget.db next to this script (override with --db or the BUDGET_DB env var).
Standard library only.
"""

from __future__ import annotations

import argparse
import math
import os
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

DEFAULT_DB = os.environ.get("BUDGET_DB", str(Path(__file__).parent / "budget.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       TEXT    NOT NULL,             -- ISO date, YYYY-MM-DD
    amount   REAL    NOT NULL,             -- + income, - expense
    category TEXT    NOT NULL,
    note     TEXT    NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS budgets (
    category TEXT PRIMARY KEY,
    monthly  REAL NOT NULL                 -- limit as a positive number
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def valid_month(text: str) -> str:
    try:
        # Normalise "2026-9" to "2026-09": filtering compares against substr(ts, 1, 7).
        return datetime.strptime(text, "%Y-%m").strftime("%Y-%m")
    except ValueError:
        raise argparse.ArgumentTypeError(f"month must look like 2026-09, got {text!r}") from None


def valid_amount(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"amount must be a number, got {text!r}") from None
    if not math.isfinite(value):
        raise argparse.ArgumentTypeError(f"amount must be a finite number, got {text!r}")
    value = round(value, 2)  # stored as cents-precision; avoids float drift in totals
    if value == 0:
        raise argparse.ArgumentTypeError("amount must not be zero")
    return value


def valid_limit(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"limit must be a number, got {text!r}") from None
    if not math.isfinite(value):
        raise argparse.ArgumentTypeError(f"limit must be a finite number, got {text!r}")
    return round(abs(value), 2)


def valid_category(text: str) -> str:
    text = text.strip().lower()
    if not text:
        raise argparse.ArgumentTypeError("category must not be blank")
    return text


def valid_date(text: str) -> str:
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError(f"date must look like 2026-09-01, got {text!r}") from None


def money(x: float) -> str:
    return f"{x:>12,.2f}"


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def cmd_add(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    ts = args.date or date.today().isoformat()
    cur = conn.execute(
        "INSERT INTO transactions (ts, amount, category, note) VALUES (?, ?, ?, ?)",
        (ts, args.amount, args.category, args.note or ""),
    )
    conn.commit()
    kind = "income" if args.amount > 0 else "expense"
    print(f"#{cur.lastrowid}  {ts}  {kind:<7} {money(args.amount)}  {args.category}")


def _filtered(conn, month, category):
    sql = "SELECT * FROM transactions WHERE 1=1"
    params: list = []
    if month:
        sql += " AND substr(ts, 1, 7) = ?"
        params.append(month)
    if category:
        sql += " AND category = ?"
        params.append(category.lower())
    sql += " ORDER BY ts, id"
    return conn.execute(sql, params).fetchall()


def cmd_list(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    rows = _filtered(conn, args.month, args.category)
    if not rows:
        print("no matching transactions")
        return
    print(f"{'id':>4}  {'date':<10}  {'amount':>12}  {'category':<14}  note")
    print("-" * 64)
    running = 0.0
    for r in rows:
        running += r["amount"]
        print(f"{r['id']:>4}  {r['ts']:<10}  {money(r['amount'])}  {r['category']:<14}  {r['note']}")
    print("-" * 64)
    print(f"{'':>4}  {'total':<10}  {money(running)}")


def cmd_report(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    rows = _filtered(conn, args.month, None)
    if not rows:
        print("no transactions to report on")
        return

    income = sum(r["amount"] for r in rows if r["amount"] > 0)
    expense = sum(-r["amount"] for r in rows if r["amount"] < 0)
    scope = f"for {args.month}" if args.month else "(all time)"

    print(f"Budget report {scope}")
    print("=" * 44)
    print(f"income   {money(income)}")
    print(f"expense  {money(-expense)}")
    print(f"net      {money(income - expense)}")

    spend_by_cat: dict[str, float] = {}
    for r in rows:
        if r["amount"] < 0:
            spend_by_cat[r["category"]] = spend_by_cat.get(r["category"], 0.0) + -r["amount"]

    if spend_by_cat:
        print("\nspending by category")
        print("-" * 44)
        biggest = max(spend_by_cat.values())
        for cat, amt in sorted(spend_by_cat.items(), key=lambda kv: -kv[1]):
            bar = "#" * round(20 * amt / biggest)
            pct = 100 * amt / expense if expense else 0
            print(f"{cat:<14} {money(-amt)}  {pct:5.1f}%  {bar}")


def cmd_budget(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    if args.action == "set":
        conn.execute(
            "INSERT INTO budgets (category, monthly) VALUES (?, ?) "
            "ON CONFLICT(category) DO UPDATE SET monthly = excluded.monthly",
            (args.category, args.limit),
        )
        conn.commit()
        print(f"budget for {args.category} set to {money(args.limit)} / month")
        return

    # action == "check"
    month = args.month or date.today().strftime("%Y-%m")
    budgets = conn.execute("SELECT category, monthly FROM budgets ORDER BY category").fetchall()
    if not budgets:
        print("no budgets set — try:  budget.py budget set groceries 400")
        return

    print(f"Budget check for {month}")
    print("=" * 58)
    print(f"{'category':<14}  {'spent':>12}  {'limit':>12}  status")
    print("-" * 58)
    for b in budgets:
        spent = conn.execute(
            "SELECT COALESCE(SUM(-amount), 0) FROM transactions "
            "WHERE category = ? AND amount < 0 AND substr(ts,1,7) = ?",
            (b["category"], month),
        ).fetchone()[0]
        limit = b["monthly"]
        remaining = limit - spent
        flag = "OK" if remaining >= 0 else f"OVER by {money(-remaining).strip()}"
        print(f"{b['category']:<14}  {money(spent)}  {money(limit)}  {flag}")


def cmd_delete(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    row = conn.execute("SELECT * FROM transactions WHERE id = ?", (args.id,)).fetchone()
    if not row:
        sys.exit(f"no transaction with id {args.id}")
    conn.execute("DELETE FROM transactions WHERE id = ?", (args.id,))
    conn.commit()
    print(f"deleted #{row['id']}  {row['ts']}  {money(row['amount'])}  {row['category']}")


# --------------------------------------------------------------------------- #
# arg parsing
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default=DEFAULT_DB, help="path to the SQLite database")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("add", help="record a transaction")
    a.add_argument("amount", type=valid_amount, help="positive = income, negative = expense")
    a.add_argument("category", type=valid_category)
    a.add_argument("note", nargs="?", default="")
    a.add_argument("--date", type=valid_date, help="YYYY-MM-DD (default: today)")
    a.set_defaults(func=cmd_add)

    l = sub.add_parser("list", help="list transactions")
    l.add_argument("--month", type=valid_month)
    l.add_argument("--category", type=valid_category)
    l.set_defaults(func=cmd_list)

    r = sub.add_parser("report", help="income/expense summary with a category breakdown")
    r.add_argument("--month", type=valid_month)
    r.set_defaults(func=cmd_report)

    b = sub.add_parser("budget", help="set or check monthly category budgets")
    b.add_argument("action", choices=["set", "check"])
    b.add_argument("category", nargs="?", type=valid_category)
    b.add_argument("limit", nargs="?", type=valid_limit)
    b.add_argument("--month", type=valid_month)
    b.set_defaults(func=cmd_budget)

    d = sub.add_parser("delete", help="delete a transaction by id")
    d.add_argument("id", type=int)
    d.set_defaults(func=cmd_delete)
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "budget" and args.action == "set" and (args.category is None or args.limit is None):
        sys.exit("usage: budget.py budget set <category> <limit>")

    conn = connect(args.db)
    try:
        args.func(conn, args)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
