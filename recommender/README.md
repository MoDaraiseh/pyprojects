# 4 · recommender — movie recommendation engine

Two recommendation models, both written from scratch with `numpy`.

```bash
uv run python recommender/recommend.py users
uv run python recommender/recommend.py recommend Ava
uv run python recommender/recommend.py recommend Ava --model content --n 10
uv run python recommender/recommend.py similar "Neon Circuit"
```

## The dataset

`build_dataset.py` generates `data/movies.csv` (20 films with genres) and
`data/ratings.csv` on first run — fully offline and seeded, so results are
reproducible. Ratings aren't random: every user has hidden per-genre affinities,
and each rating is that affinity plus a little Gaussian noise. That gives both
models real signal to recover.

## Models

**Item-based collaborative filtering** (`--model cf`, default)
Mean-centre each user's ratings, take cosine similarity between movie columns,
then predict an unseen movie's rating as the similarity-weighted average of the
user's own ratings. "People with your taste also liked…"

**Content-based** (`--model content`)
Build a taste profile = sum of each rated movie's genre vector weighted by how
far the rating sits above the midpoint (3). Rank unseen movies by cosine
similarity to that profile. Works even for a user with no taste-neighbours.

`similar` exposes the raw item–item cosine matrix.

## Files

- `recommend.py` — models + CLI
- `build_dataset.py` — synthetic data generator (run directly, or `from build_dataset import build`; `recommend.py` calls it automatically when `data/` is missing)
