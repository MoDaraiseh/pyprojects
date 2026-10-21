"""
A small movie recommendation engine.

Two independent models, both from scratch with numpy:

  * item-based collaborative filtering  — "people who rated these films like you
    also liked ..."  (cosine similarity between mean-centred rating vectors)
  * content-based                       — "more films with the genres you rate
    highly"           (cosine similarity between genre vectors, weighted by
    your own ratings)

The dataset (data/ratings.csv + data/movies.csv) is generated on first run by
build_dataset.py so the demo is fully offline and reproducible.

    python recommend.py users
    python recommend.py recommend "Ava"
    python recommend.py recommend "Ava" --model content --n 10
    python recommend.py similar "Neon Circuit"
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

DATA = Path(__file__).parent / "data"


# --------------------------------------------------------------------------- #
# loading
# --------------------------------------------------------------------------- #
class Dataset:
    def __init__(self) -> None:
        movies_csv = DATA / "movies.csv"
        ratings_csv = DATA / "ratings.csv"
        if not (movies_csv.exists() and ratings_csv.exists()):
            try:  # imported as recommender.recommend
                from .build_dataset import build
            except ImportError:  # run as a script: recommender/ is on sys.path
                from build_dataset import build
            build()

        self.movie_ids: list[int] = []
        self.titles: dict[int, str] = {}
        self.genres: dict[int, list[str]] = {}
        with movies_csv.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                mid = int(row["movie_id"])
                self.movie_ids.append(mid)
                self.titles[mid] = row["title"]
                self.genres[mid] = row["genres"].split("|")

        with ratings_csv.open(encoding="utf-8") as fh:
            rating_rows = list(csv.DictReader(fh))
        self.users: list[str] = sorted({r["user"] for r in rating_rows})

        self.u_index = {u: i for i, u in enumerate(self.users)}
        self.m_index = {m: j for j, m in enumerate(self.movie_ids)}
        self.all_genres = sorted({g for gs in self.genres.values() for g in gs})

        # user x movie rating matrix, NaN where unrated
        self.R = np.full((len(self.users), len(self.movie_ids)), np.nan)
        for r in rating_rows:
            self.R[self.u_index[r["user"]], self.m_index[int(r["movie_id"])]] = float(r["rating"])

        # movie x genre indicator matrix
        self.G = np.zeros((len(self.movie_ids), len(self.all_genres)))
        gi = {g: k for k, g in enumerate(self.all_genres)}
        for mid, gs in self.genres.items():
            for g in gs:
                self.G[self.m_index[mid], gi[g]] = 1.0

    # ----------------------------------------------------------------------- #
    def _rated_mask(self, u: int) -> np.ndarray:
        return ~np.isnan(self.R[u])

    def item_similarity(self) -> np.ndarray:
        """Cosine similarity between movies over mean-centred user ratings."""
        R = self.R.copy()
        user_mean = np.nanmean(R, axis=1, keepdims=True)
        centred = np.where(np.isnan(R), 0.0, R - user_mean)
        norms = np.linalg.norm(centred, axis=0)
        norms[norms == 0] = 1e-9
        sim = (centred.T @ centred) / np.outer(norms, norms)
        np.fill_diagonal(sim, 0.0)
        return sim

    # ----------------------------------------------------------------------- #
    def recommend_cf(self, user: str, n: int) -> list[tuple[str, float]]:
        u = self.u_index[user]
        sim = self.item_similarity()
        mask = self._rated_mask(u)
        user_mean = np.nanmean(self.R[u])
        centred = np.where(mask, self.R[u] - user_mean, 0.0)

        scores = sim @ centred
        weight = np.abs(sim) @ mask.astype(float)
        weight[weight == 0] = 1e-9
        pred = user_mean + scores / weight
        pred[mask] = -np.inf  # don't recommend what they've already seen

        order = [j for j in np.argsort(pred)[::-1] if np.isfinite(pred[j])][:n]
        return [(self.titles[self.movie_ids[j]], float(pred[j])) for j in order]

    def recommend_content(self, user: str, n: int) -> list[tuple[str, float]]:
        u = self.u_index[user]
        mask = self._rated_mask(u)
        ratings = self.R[u][mask]
        liked = self.G[mask]

        # taste profile: genre vector weighted by how far each rating is above 3
        prefs = (liked * (ratings - 3.0)[:, None]).sum(axis=0)
        pnorm = np.linalg.norm(prefs) or 1e-9
        gnorm = np.linalg.norm(self.G, axis=1)
        gnorm[gnorm == 0] = 1e-9
        sim = (self.G @ prefs) / (gnorm * pnorm)
        sim[mask] = -np.inf

        order = [j for j in np.argsort(sim)[::-1] if np.isfinite(sim[j])][:n]
        return [(self.titles[self.movie_ids[j]], float(sim[j])) for j in order]

    def similar_movies(self, title: str, n: int) -> list[tuple[str, float]]:
        match = self._resolve_title(title)
        j = self.m_index[match]
        sim = self.item_similarity()[j]
        order = [k for k in np.argsort(sim)[::-1] if k != j][:n]  # never "similar to itself"
        return [(self.titles[self.movie_ids[k]], float(sim[k])) for k in order]

    def resolve_user(self, name: str) -> str | None:
        if name in self.u_index:
            return name
        matches = [u for u in self.users if u.lower() == name.lower()]
        return matches[0] if len(matches) == 1 else None

    def _resolve_title(self, title: str) -> int:
        lowered = title.lower()
        exact = [m for m in self.movie_ids if self.titles[m].lower() == lowered]
        if exact:
            return exact[0]
        partial = [m for m in self.movie_ids if lowered in self.titles[m].lower()]
        if len(partial) == 1:
            return partial[0]
        if not partial:
            sys.exit(f"no movie matching {title!r}")
        sys.exit("ambiguous title; did you mean:\n  " +
                 "\n  ".join(self.titles[m] for m in partial))


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _print_table(header: str, rows: list[tuple[str, float]]) -> None:
    print(header)
    print("-" * max(len(header), 40))
    for i, (title, score) in enumerate(rows, 1):
        print(f"{i:>2}. {title:<34} {score:6.3f}")


def positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected a whole number, got {text!r}")
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1, got {value}")
    return value


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("users", help="list users in the dataset")
    rec = sub.add_parser("recommend", help="recommend movies for a user")
    rec.add_argument("user")
    rec.add_argument("--model", choices=["cf", "content"], default="cf")
    rec.add_argument("--n", type=positive_int, default=5)
    sim = sub.add_parser("similar", help="movies similar to a given title")
    sim.add_argument("title")
    sim.add_argument("--n", type=positive_int, default=5)
    args = p.parse_args(argv)

    ds = Dataset()

    if args.command == "users":
        for u in ds.users:
            seen = int(np.sum(~np.isnan(ds.R[ds.u_index[u]])))
            print(f"  {u:<10} rated {seen} movies")
        return

    if args.command == "recommend":
        user = ds.resolve_user(args.user)
        if user is None:
            sys.exit(f"unknown user {args.user!r}; known: {', '.join(ds.users)}")
        if args.model == "cf":
            rows = ds.recommend_cf(user, args.n)
            _print_table(f"Collaborative-filtering picks for {user}", rows)
        else:
            rows = ds.recommend_content(user, args.n)
            _print_table(f"Content-based picks for {user}", rows)
        if not rows:
            print(f"{user} has rated every movie; nothing left to recommend.")
        return

    if args.command == "similar":
        rows = ds.similar_movies(args.title, args.n)
        _print_table(f"Movies similar to {args.title!r}", rows)


if __name__ == "__main__":
    main()
