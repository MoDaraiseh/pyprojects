# pyprojects

Five small, self-contained Python projects in one repo. Each folder runs on its
own; the shared `pyproject.toml` pins the handful of dependencies.

| # | Folder | What it is | Extra deps |
|---|--------|------------|------------|
| 1 | [`automation/`](automation/) | File organizer + duplicate finder CLI | none (stdlib) |
| 2 | [`web_scraper/`](web_scraper/) | Scrapes `books.toscrape.com` to CSV/JSON | `requests`, `beautifulsoup4` |
| 3 | [`budget_tracker/`](budget_tracker/) | Personal-finance CLI on SQLite | none (stdlib) |
| 4 | [`recommender/`](recommender/) | Movie recommender: collaborative + content-based | `numpy` |
| 5 | [`app_clone/`](app_clone/) | `snip` — a Bitly-style URL shortener | `flask` |

## Setup

This repo uses [uv](https://docs.astral.sh/uv/). From the repo root:

```bash
uv sync
```

That creates `.venv/` with Python 3.14 and the dependencies. Then run anything
with `uv run python <path>`, e.g.:

```bash
uv run python automation/organize.py --help
uv run python budget_tracker/budget.py report
uv run python recommender/recommend.py recommend Ava
uv run python web_scraper/scrape_books.py --max-pages 3
uv run flask --app app_clone/app run --debug
```

Without uv: `python -m venv .venv`, activate it, `pip install requests
beautifulsoup4 numpy flask`, then use `python` instead of `uv run python`.

Each folder has its own `README.md` with details and example commands.

## Tests

```bash
uv run pytest
```

The tests in `tests/` run offline: the scraper is tested against small fake pages,
and every test uses temporary folders and databases, never your real files.

## Editor setup (VS Code)

Open **this folder** (File → Open Folder → `pyprojects`) so `.vscode/settings.json`
selects `.venv` as the interpreter. A copy of a file opened from anywhere else,
such as a GitHub download in your Temp folder, is checked against your system
Python. You then get "Import "flask"/"requests"/"bs4" could not be resolved"
warnings even though the project's `.venv` has them all.
