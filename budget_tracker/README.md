# 3 · budget_tracker — personal-finance CLI

A single-file expense/income tracker backed by SQLite. Standard library only.
Amounts are **positive for income, negative for spending**. The database is
`budget.db` next to the script (override with `--db` or `$BUDGET_DB`).

```bash
uv run python budget_tracker/budget.py add 2500 salary "Sept pay" --date 2026-09-01
uv run python budget_tracker/budget.py add -82.40 groceries "weekly shop"
uv run python budget_tracker/budget.py list --month 2026-09 --category groceries
uv run python budget_tracker/budget.py report --month 2026-09
uv run python budget_tracker/budget.py budget set groceries 400
uv run python budget_tracker/budget.py budget check --month 2026-09
uv run python budget_tracker/budget.py delete 6
```

## Commands

| command | does |
|---------|------|
| `add AMOUNT CATEGORY [NOTE] [--date YYYY-MM-DD]` | record a transaction |
| `list [--month YYYY-MM] [--category X]` | filtered ledger with a running total |
| `report [--month YYYY-MM]` | income/expense/net + an ASCII bar breakdown by category |
| `budget set CATEGORY LIMIT` | set a monthly spending limit |
| `budget check [--month YYYY-MM]` | compare spend vs. limit per category, flag overspend |
| `delete ID` | remove a transaction |

## Design

- Schema created on connect via `executescript` (`IF NOT EXISTS`), so first run
  just works.
- `budgets` uses `INSERT … ON CONFLICT DO UPDATE` (SQLite upsert).
- Month filtering is `substr(ts,1,7) = '2026-09'` — no date library needed at
  query time.
- `argparse` sub-commands, each wired to a `cmd_*` function via `set_defaults`.
