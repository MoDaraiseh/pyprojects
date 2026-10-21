import pytest

import app as snip


@pytest.fixture
def client():
    snip.app.config["TESTING"] = True
    return snip.app.test_client()


def shorten(client, **payload):
    return client.post("/api/shorten", json=payload)


@pytest.mark.parametrize("body", [[1], "x", 5, None])
def test_non_object_json_is_400(client, body):
    r = client.post("/api/shorten", json=body)
    assert r.status_code == 400


@pytest.mark.parametrize("payload", [{"url": 123}, {"url": None}, {"url": "example.com", "alias": 7}])
def test_wrong_types_are_400(client, payload):
    assert shorten(client, **payload).status_code == 400


@pytest.mark.parametrize("url", ["exa mple.com/x", "https://example.com/a\nb", "javascript:alert(1)",
                                 "ftp://example.com", "localhost"])
def test_invalid_urls_rejected(client, url):
    assert shorten(client, url=url).status_code == 400


def test_uppercase_alias_allowed_and_redirects(client):
    r = shorten(client, url="example.com/launch", alias="Launch2026")
    assert r.status_code == 201, r.get_json()
    r = client.get("/Launch2026", headers={"Referer": "https://ref.example/" + "x" * 1000})
    assert r.status_code == 302 and r.headers["Location"] == "https://example.com/launch"
    with snip.app.app_context():
        ref = snip.get_db().execute("SELECT referrer FROM clicks WHERE code='Launch2026'").fetchone()[0]
    assert len(ref) == 300


def test_taken_and_reserved_aliases(client):
    assert shorten(client, url="example.com", alias="taken-one").status_code == 201
    r = shorten(client, url="example.com", alias="taken-one")
    assert r.status_code == 400 and "already taken" in r.get_json()["error"]
    assert shorten(client, url="example.com", alias="API").status_code == 400


def test_generated_code_and_stats(client):
    r = shorten(client, url="https://example.com/x")
    code = r.get_json()["code"]
    assert len(code) == 6
    client.get(f"/{code}")
    assert b"1 click" in client.get(f"/{code}/stats").data


def test_unknown_code_404(client):
    assert client.get("/does-not-exist").status_code == 404


def test_form_shows_error_for_bad_url(client):
    r = client.post("/", data={"url": "not a url"})
    assert r.status_code == 200 and b"valid http(s) URL" in r.data
