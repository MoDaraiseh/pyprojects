"""
Scraper for https://books.toscrape.com — a sandbox site built for practising
scraping (no robots.txt restrictions, static HTML, safe to hammer politely).

It walks all 50 catalogue pages, and for every book records:
    title, price (GBP), star rating, in-stock count, product-page URL, category

Output goes to both CSV and JSON next to this script.

    python scrape_books.py                 # all pages
    python scrape_books.py --max-pages 3    # just the first 3 (fast smoke test)
    python scrape_books.py --delay 0.5      # be gentler on the server
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://books.toscrape.com/"
CATALOGUE = urljoin(BASE, "catalogue/")
HERE = Path(__file__).parent
_RATING_WORDS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


@dataclass
class Book:
    title: str
    price: float
    rating: int
    in_stock: int
    category: str
    url: str


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "books-toscrape-practice-scraper/1.0 (educational)"})
    return s


def _is_retryable(exc: requests.RequestException) -> bool:
    # Retry network trouble, 5xx and 429; a 404 or 403 will not fix itself.
    resp = getattr(exc, "response", None)
    return resp is None or resp.status_code >= 500 or resp.status_code == 429


def get_soup(session: requests.Session, url: str, retries: int = 3) -> BeautifulSoup:
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            # Pass raw bytes so BeautifulSoup honours the page's <meta charset>;
            # the server sends no charset header, so resp.text would guess Latin-1.
            return BeautifulSoup(resp.content, "html.parser")
        except requests.RequestException as exc:
            if attempt == retries or not _is_retryable(exc):
                raise
            wait = 2 ** attempt
            print(f"  ! {exc} — retrying in {wait}s ({attempt}/{retries})", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError("unreachable")


def parse_price(text: str) -> float:
    # e.g. "£51.77" — strip everything that isn't a number or dot.
    return float(re.sub(r"[^\d.]", "", text))


def parse_stock(text: str) -> int:
    m = re.search(r"\((\d+) available\)", text)
    return int(m.group(1)) if m else 0


def scrape_detail(session: requests.Session, url: str) -> tuple[str, int]:
    """Return (category, in_stock) from a book's product page."""
    soup = get_soup(session, url)
    crumbs = soup.select("ul.breadcrumb li a")
    category = crumbs[-1].get_text(strip=True) if len(crumbs) >= 3 else "Unknown"
    availability = soup.select_one("p.availability")
    in_stock = parse_stock(availability.get_text(" ", strip=True)) if availability else 0
    return category, in_stock


def scrape(max_pages: int | None, delay: float, books: list[Book] | None = None) -> list[Book]:
    """Scrape into `books` (appending as it goes, so a caller keeps partial
    results if a network error interrupts the run)."""
    session = make_session()
    books = books if books is not None else []
    page = 1
    next_url = urljoin(CATALOGUE, "page-1.html")

    while next_url:
        if max_pages is not None and page > max_pages:
            break
        print(f"page {page}: {next_url}")
        soup = get_soup(session, next_url)

        for article in soup.select("article.product_pod"):
            link = article.select_one("h3 a")
            title = link["title"].strip()
            detail_url = urljoin(next_url, link["href"])
            price = parse_price(article.select_one("p.price_color").get_text())
            rating_cls = article.select_one("p.star-rating")["class"]
            rating = next((_RATING_WORDS[c] for c in rating_cls if c in _RATING_WORDS), 0)

            category, in_stock = scrape_detail(session, detail_url)
            books.append(Book(title, price, rating, in_stock, category, detail_url))
            time.sleep(delay)

        nxt = soup.select_one("li.next a")
        next_url = urljoin(next_url, nxt["href"]) if nxt else None
        page += 1
        time.sleep(delay)

    return books


def save(books: list[Book]) -> None:
    rows = [asdict(b) for b in books]
    (HERE / "books.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    with (HERE / "books.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(Book.__annotations__))
        writer.writeheader()
        writer.writerows(rows)


def summarise(books: list[Book]) -> None:
    if not books:
        print("No books scraped.")
        return
    total = sum(b.price for b in books)
    by_cat: dict[str, int] = {}
    for b in books:
        by_cat[b.category] = by_cat.get(b.category, 0) + 1
    avg_rating = sum(b.rating for b in books) / len(books)
    print("\n" + "=" * 48)
    print(f"books scraped     : {len(books)}")
    print(f"categories        : {len(by_cat)}")
    print(f"avg price         : £{total / len(books):.2f}")
    print(f"avg rating        : {avg_rating:.2f} / 5")
    cheapest = min(books, key=lambda b: b.price)
    dearest = max(books, key=lambda b: b.price)
    print(f"cheapest          : £{cheapest.price:.2f}  {cheapest.title[:40]}")
    print(f"most expensive    : £{dearest.price:.2f}  {dearest.title[:40]}")
    top3 = sorted(by_cat.items(), key=lambda kv: -kv[1])[:3]
    print("top categories    : " + ", ".join(f"{c} ({n})" for c, n in top3))
    print("=" * 48)
    print("wrote books.csv and books.json")


def positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected a whole number, got {text!r}") from None
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1, got {value}")
    return value


def non_negative_float(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected a number, got {text!r}") from None
    if not (0 <= value < float("inf")):
        raise argparse.ArgumentTypeError(f"must be 0 or more, got {text!r}")
    return value


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--max-pages", type=positive_int, default=None, help="limit number of catalogue pages")
    p.add_argument("--delay", type=non_negative_float, default=0.15, help="seconds to sleep between requests")
    args = p.parse_args(argv)

    books: list[Book] = []
    try:
        scrape(args.max_pages, args.delay, books)
    except requests.RequestException as exc:
        if books:
            save(books)
            summarise(books)
            print(f"(partial: stopped after {len(books)} books)", file=sys.stderr)
        sys.exit(f"network error: {exc}\n(are you offline? this scraper needs internet)")

    save(books)
    summarise(books)


if __name__ == "__main__":
    main()
