# 2 · web_scraper — books.toscrape.com

Scrapes every book from <https://books.toscrape.com> (a sandbox site made for
practising scraping) and writes `books.csv` + `books.json`.

```bash
uv run python web_scraper/scrape_books.py                # all 50 pages (~1000 books)
uv run python web_scraper/scrape_books.py --max-pages 3  # quick smoke test
uv run python web_scraper/scrape_books.py --delay 0.5    # gentler on the server
```

## Fields captured

`title`, `price` (GBP, float), `rating` (1–5), `in_stock` (count), `category`,
`url` (product page).

## Notes

- Walks catalogue pagination by following the "next" link — no hard-coded page
  count.
- Visits each product page for the real category and stock number.
- `requests.Session` for connection reuse; exponential-backoff retry on transient
  network errors; a descriptive `User-Agent`; a configurable politeness `--delay`.
- Output files are UTF-8 (the `£` sign may render as `?` in a Windows terminal,
  but it is correct in the files).
- Needs an internet connection; prints a clear message if offline.
