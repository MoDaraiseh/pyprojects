"""
snip — a minimal Bitly-style URL shortener built with Flask + SQLite.

  * paste a long URL, get a short code (or pick your own custom alias)
  * visiting /<code> 302-redirects and records a click (time, referrer, UA)
  * /<code>/stats shows the click count and a recent-visits table
  * JSON API:  POST /api/shorten  {"url": "...", "alias": "..."}

Run:
    uv run flask --app app run --debug      # http://127.0.0.1:5000
    # or:  uv run python app.py

The database is snip.db next to this file (override with SNIP_DB).
"""

from __future__ import annotations

import os
import secrets
import sqlite3
import string
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from flask import (Flask, abort, g, jsonify, redirect, render_template,
                   request, url_for)

DB_PATH = os.environ.get("SNIP_DB", str(Path(__file__).parent / "snip.db"))
ALPHABET = string.ascii_lowercase + string.digits  # generated codes
ALIAS_CHARS = set(string.ascii_letters + string.digits + "-_")  # custom aliases
RESERVED = {"api", "static", "favicon.ico"}

app = Flask(__name__)


# --------------------------------------------------------------------------- #
# database helpers
# --------------------------------------------------------------------------- #
def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc: object) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS links (
            code       TEXT PRIMARY KEY,
            target     TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS clicks (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            code     TEXT NOT NULL REFERENCES links(code) ON DELETE CASCADE,
            ts       TEXT NOT NULL,
            referrer TEXT,
            ua       TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_clicks_code ON clicks(code);
        """
    )
    db.commit()
    db.close()


# --------------------------------------------------------------------------- #
# core logic
# --------------------------------------------------------------------------- #
def normalise_url(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    raw = raw.strip()
    # Reject embedded whitespace/control characters (not a valid URL, and they
    # would end up in the Location header of the redirect).
    if not raw or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in raw):
        return None
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    if "." not in parsed.netloc:
        return None
    return raw


def is_valid_alias(alias: str) -> bool:
    return (
        1 <= len(alias) <= 32
        and alias.lower() not in RESERVED
        and all(c in ALIAS_CHARS for c in alias)
    )


def generate_code(db: sqlite3.Connection, length: int = 6) -> str:
    for _ in range(20):
        code = "".join(secrets.choice(ALPHABET) for _ in range(length))
        if db.execute("SELECT 1 FROM links WHERE code = ?", (code,)).fetchone() is None:
            return code
    return generate_code(db, length + 1)


def create_link(raw_url: object, alias: object) -> tuple[str | None, str | None]:
    """Return (code, error). Exactly one is not None."""
    target = normalise_url(raw_url)
    if target is None:
        return None, "That doesn't look like a valid http(s) URL."
    if alias is not None and not isinstance(alias, str):
        return None, "Alias must be a string."

    db = get_db()
    alias = (alias or "").strip()
    if alias and not is_valid_alias(alias):
        return None, "Alias must be 1-32 chars: letters, digits, - or _."

    for _ in range(5):
        code = alias or generate_code(db)
        try:
            db.execute(
                "INSERT INTO links (code, target, created_at) VALUES (?, ?, ?)",
                (code, target, datetime.now(timezone.utc).isoformat(timespec="seconds")),
            )
            db.commit()
            return code, None
        except sqlite3.IntegrityError:
            # Someone else claimed this code between our check and insert.
            db.rollback()
            if alias:
                return None, f"The alias {alias!r} is already taken."
    return None, "Could not allocate a short code; please try again."


# --------------------------------------------------------------------------- #
# routes
# --------------------------------------------------------------------------- #
@app.route("/", methods=["GET", "POST"])
def index():
    short_url = error = None
    if request.method == "POST":
        code, error = create_link(request.form.get("url", ""), request.form.get("alias") or None)
        if code:
            short_url = request.host_url.rstrip("/") + url_for("follow", code=code)

    db = get_db()
    recent = db.execute(
        """SELECT l.code, l.target, l.created_at, COUNT(c.id) AS clicks
           FROM links l LEFT JOIN clicks c ON c.code = l.code
           GROUP BY l.code ORDER BY l.created_at DESC, l.rowid DESC LIMIT 10"""
    ).fetchall()
    return render_template("index.html", short_url=short_url, error=error,
                           recent=recent, host=request.host_url.rstrip("/"))


@app.route("/<code>")
def follow(code: str):
    if code in RESERVED:
        abort(404)
    db = get_db()
    row = db.execute("SELECT target FROM links WHERE code = ?", (code,)).fetchone()
    if row is None:
        abort(404)
    db.execute(
        "INSERT INTO clicks (code, ts, referrer, ua) VALUES (?, ?, ?, ?)",
        (code, datetime.now(timezone.utc).isoformat(timespec="seconds"),
         (request.referrer or "")[:300] or None, request.user_agent.string[:300]),
    )
    db.commit()
    return redirect(row["target"], code=302)


@app.route("/<code>/stats")
def stats(code: str):
    db = get_db()
    link = db.execute("SELECT * FROM links WHERE code = ?", (code,)).fetchone()
    if link is None:
        abort(404)
    clicks = db.execute(
        "SELECT ts, referrer, ua FROM clicks WHERE code = ? ORDER BY ts DESC LIMIT 50",
        (code,),
    ).fetchall()
    total = db.execute("SELECT COUNT(*) FROM clicks WHERE code = ?", (code,)).fetchone()[0]
    return render_template("stats.html", link=link, clicks=clicks, total=total,
                           host=request.host_url.rstrip("/"))


@app.post("/api/shorten")
def api_shorten():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error='Send a JSON object like {"url": "...", "alias": "..."}.'), 400
    code, error = create_link(payload.get("url", ""), payload.get("alias"))
    if error:
        return jsonify(error=error), 400
    return jsonify(
        code=code,
        short_url=request.host_url.rstrip("/") + url_for("follow", code=code),
        stats_url=request.host_url.rstrip("/") + url_for("stats", code=code),
    ), 201


@app.errorhandler(404)
def not_found(_e: object):
    return render_template("404.html"), 404


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=True)
