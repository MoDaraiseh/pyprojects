"""Offline scraper tests: a fake session serves tiny HTML pages; no network."""
import argparse

import pytest
import requests

import scrape_books as sb

LIST_PAGE = """<html><head><meta charset="utf-8"></head><body>
<article class="product_pod">
  <h3><a href="book_1/index.html" title="A Light in the Attic">A Light...</a></h3>
  <p class="star-rating Three"></p><p class="price_color">£51.77</p>
</article>
{next}
</body></html>"""
DETAIL_PAGE = """<html><head><meta charset="utf-8"></head><body>
<ul class="breadcrumb"><li><a href="/">Home</a></li><li><a href="/books">Books</a></li>
<li><a href="/poetry">Poetry</a></li></ul>
<p class="availability">In stock (22 available)</p></body></html>"""


class FakeResponse:
    def __init__(self, body: str, status: int = 200):
        self.content = body.encode("utf-8")
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


class FakeSession:
    def __init__(self, pages: int = 3, fail_on: str | None = None, status: int = 200):
        self.pages, self.fail_on, self.status = pages, fail_on, status
        self.calls: list[str] = []

    def get(self, url, timeout):
        self.calls.append(url)
        if self.fail_on and self.fail_on in url:
            if self.status == 0:
                raise requests.ConnectionError("offline")
            return FakeResponse("", self.status)
        if "book_" in url:
            return FakeResponse(DETAIL_PAGE)
        n = int(url.rsplit("page-", 1)[1].split(".")[0])
        nxt = f'<li class="next"><a href="page-{n + 1}.html">next</a></li>' if n < self.pages else ""
        return FakeResponse(LIST_PAGE.format(next=nxt))


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(sb.time, "sleep", lambda s: None)


def test_parses_book_with_utf8_pound_sign(monkeypatch):
    monkeypatch.setattr(sb, "make_session", lambda: FakeSession(pages=1))
    [book] = sb.scrape(None, 0)
    assert book == sb.Book("A Light in the Attic", 51.77, 3, 22, "Poetry",
                           "https://books.toscrape.com/catalogue/book_1/index.html")


def test_max_pages_limits_pages(monkeypatch):
    session = FakeSession(pages=5)
    monkeypatch.setattr(sb, "make_session", lambda: session)
    assert len(sb.scrape(1, 0)) == 1
    assert sum("page-" in u for u in session.calls) == 1


@pytest.mark.parametrize("bad", ["0", "-3", "x"])
def test_max_pages_must_be_positive(bad):
    with pytest.raises(argparse.ArgumentTypeError):
        sb.positive_int(bad)


@pytest.mark.parametrize("bad", ["-0.5", "nan", "inf"])
def test_delay_must_be_non_negative(bad):
    with pytest.raises(argparse.ArgumentTypeError):
        sb.non_negative_float(bad)


def test_404_is_not_retried():
    session = FakeSession(fail_on="page-1", status=404)
    with pytest.raises(requests.HTTPError):
        sb.get_soup(session, "https://books.toscrape.com/catalogue/page-1.html")
    assert len(session.calls) == 1


def test_503_is_retried():
    session = FakeSession(fail_on="page-1", status=503)
    with pytest.raises(requests.HTTPError):
        sb.get_soup(session, "https://books.toscrape.com/catalogue/page-1.html", retries=3)
    assert len(session.calls) == 3


def test_partial_results_saved_on_network_error(monkeypatch, tmp_path):
    monkeypatch.setattr(sb, "HERE", tmp_path)
    monkeypatch.setattr(sb, "make_session", lambda: FakeSession(pages=3, fail_on="page-2", status=0))
    with pytest.raises(SystemExit):
        sb.main(["--delay", "0"])
    assert "A Light in the Attic" in (tmp_path / "books.json").read_text(encoding="utf-8")
