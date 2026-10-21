# 5 · app_clone — `snip`, a Bitly-style URL shortener

A working clone of the core of Bitly: shorten a link, share the short code,
track the clicks. Flask + SQLite, server-rendered templates, ~200 lines.

```bash
uv run flask --app app_clone/app run --debug     # http://127.0.0.1:5000
# or
uv run python app_clone/app.py
```

## Features

- **Shorten** any http(s) URL; bare domains like `example.com/x` are accepted and
  `https://` is added.
- **Custom aliases** (`/launch`) or a random 6-char code; collisions are retried,
  reserved words (`api`, `static`, …) are blocked.
- `GET /<code>` → **302 redirect**, logging timestamp, referrer and user-agent.
- `GET /<code>/stats` → click count + a recent-visits table.
- **JSON API**: `POST /api/shorten` with `{"url": "...", "alias": "..."}` →
  `201 {code, short_url, stats_url}`.
- Home page lists the 10 most recent links with live click counts.
- Custom 404 for unknown codes.

## Layout

```
app_clone/
├── app.py               # routes, validation, SQLite access
└── templates/
    ├── base.html        # layout + inline CSS (light/dark aware)
    ├── index.html       # shorten form + recent links
    ├── stats.html       # per-link analytics
    └── 404.html
```

## Data model

`links(code PK, target, created_at)` and
`clicks(id, code FK→links ON DELETE CASCADE, ts, referrer, ua)`.
The DB is `snip.db` next to `app.py` (override with `$SNIP_DB`); it's created
automatically on startup.

## Try the API

```bash
curl -s -X POST localhost:5000/api/shorten \
  -H 'content-type: application/json' \
  -d '{"url":"https://example.com/a/very/long/path","alias":"demo"}'
curl -si localhost:5000/demo | grep -i location
```
