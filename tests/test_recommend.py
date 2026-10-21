import importlib

import pytest

import build_dataset
import recommend


@pytest.fixture
def ds(tmp_path, monkeypatch):
    # Build the dataset in a temp dir, never in recommender/data/.
    monkeypatch.setattr(build_dataset, "DATA", tmp_path)
    monkeypatch.setattr(recommend, "DATA", tmp_path)
    return recommend.Dataset()


def test_dataset_is_reproducible(ds):
    assert len(ds.movie_ids) == 20
    assert ds.users == sorted(build_dataset.USERS)


def test_similar_never_lists_the_movie_itself(ds):
    rows = ds.similar_movies("Neon Circuit", 50)
    titles = [t for t, _ in rows]
    assert "Neon Circuit" not in titles
    assert len(titles) == 19


def test_user_lookup_is_case_insensitive(ds):
    assert ds.resolve_user("ava") == "Ava"
    assert ds.resolve_user("nobody") is None


def test_recommendations_exclude_rated_movies(ds):
    u = ds.u_index["Ava"]
    rated = {ds.titles[m] for j, m in enumerate(ds.movie_ids) if ds._rated_mask(u)[j]}
    for model in (ds.recommend_cf, ds.recommend_content):
        rows = model("Ava", 20)
        assert rows and not {t for t, _ in rows} & rated


@pytest.mark.parametrize("n", ["0", "-1", "x"])
def test_n_must_be_positive(n, capsys):
    with pytest.raises(SystemExit) as e:
        recommend.main(["similar", "Neon Circuit", "--n", n])
    assert e.value.code == 2


def test_importable_as_package_module(tmp_path, monkeypatch):
    # `import recommender.recommend` from the repo root must also find build_dataset.
    mod = importlib.import_module("recommender.recommend")
    monkeypatch.setattr(mod, "DATA", tmp_path)
    pkg_build = importlib.import_module("recommender.build_dataset")
    monkeypatch.setattr(pkg_build, "DATA", tmp_path)
    assert len(mod.Dataset().users) == 8
