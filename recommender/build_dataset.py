"""
Generate a small, reproducible synthetic movie-ratings dataset.

Ratings are not random noise: each user is given hidden affinities for a few
genres, and their rating for a film is that affinity plus a little noise. That
gives collaborative filtering and the content model real structure to find.

Run directly to (re)build, or just import build() — recommend.py calls it
automatically when data/ is missing.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

DATA = Path(__file__).parent / "data"
SEED = 20260907

MOVIES = [
    ("Neon Circuit", ["Sci-Fi", "Action"]),
    ("The Last Harvest", ["Drama"]),
    ("Comet Road", ["Sci-Fi", "Drama"]),
    ("Paper Lanterns", ["Romance", "Drama"]),
    ("Deadline City", ["Action", "Thriller"]),
    ("Whisker Wars", ["Animation", "Comedy"]),
    ("The Quiet Ledger", ["Thriller", "Drama"]),
    ("Galaxy Brunch", ["Comedy", "Sci-Fi"]),
    ("Iron Meridian", ["Action", "Adventure"]),
    ("Salt & Static", ["Romance", "Comedy"]),
    ("Underlight", ["Horror", "Thriller"]),
    ("The Cartographer", ["Adventure", "Drama"]),
    ("Foxglove", ["Horror", "Drama"]),
    ("Ping Pong Dynasty", ["Comedy", "Sport"]),
    ("Orbital Decay", ["Sci-Fi", "Thriller"]),
    ("Marigold Street", ["Romance", "Drama"]),
    ("Titanium Hearts", ["Action", "Romance"]),
    ("The Long Commute", ["Comedy", "Drama"]),
    ("Basilisk", ["Horror", "Action"]),
    ("Northbound", ["Adventure", "Drama"]),
]

USERS = ["Ava", "Ben", "Cleo", "Dan", "Eve", "Finn", "Gia", "Hugo"]


def build() -> None:
    rng = random.Random(SEED)
    DATA.mkdir(exist_ok=True)

    all_genres = sorted({g for _, gs in MOVIES for g in gs})

    with (DATA / "movies.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["movie_id", "title", "genres"])
        for i, (title, genres) in enumerate(MOVIES, 1):
            w.writerow([i, title, "|".join(genres)])

    # hidden per-user genre affinity in [-1.5, 1.5]
    affinity = {
        u: {g: rng.uniform(-1.5, 1.5) for g in all_genres} for u in USERS
    }

    with (DATA / "ratings.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["user", "movie_id", "rating"])
        for u in USERS:
            # each user rates 60-85% of the catalogue
            k = rng.randint(int(0.6 * len(MOVIES)), int(0.85 * len(MOVIES)))
            for mid in rng.sample(range(1, len(MOVIES) + 1), k):
                genres = MOVIES[mid - 1][1]
                base = 3.0 + sum(affinity[u][g] for g in genres) / len(genres)
                score = base + rng.gauss(0, 0.4)
                rating = min(5.0, max(1.0, round(score * 2) / 2))  # clamp to 1..5, .5 steps
                w.writerow([u, mid, rating])

    print(f"wrote {DATA/'movies.csv'} ({len(MOVIES)} movies)")
    print(f"wrote {DATA/'ratings.csv'}")


if __name__ == "__main__":
    build()
