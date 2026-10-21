import argparse

import pytest

import budget


def run(tmp_path, *args):
    budget.main(["--db", str(tmp_path / "b.db"), *args])


def test_month_is_normalised():
    assert budget.valid_month("2026-9") == "2026-09"
    assert budget.valid_month("2026-09") == "2026-09"
    with pytest.raises(argparse.ArgumentTypeError):
        budget.valid_month("2026-13")


def test_unpadded_month_finds_transactions(tmp_path, capsys):
    run(tmp_path, "add", "-10", "food", "--date", "2026-09-05")
    capsys.readouterr()
    run(tmp_path, "list", "--month", "2026-9")
    assert "food" in capsys.readouterr().out


@pytest.mark.parametrize("bad", ["nan", "inf", "-inf", "1e400", "0", "abc"])
def test_bad_amounts_rejected(bad):
    with pytest.raises(argparse.ArgumentTypeError):
        budget.valid_amount(bad)


def test_amount_rounded_to_cents():
    assert budget.valid_amount("10.005") in (10.0, 10.01)
    assert budget.valid_amount("-82.40") == -82.4


def test_bad_amount_is_a_clean_usage_error(tmp_path, capsys):
    with pytest.raises(SystemExit) as e:
        run(tmp_path, "add", "nan", "food")
    assert e.value.code == 2
    assert "finite" in capsys.readouterr().err


def test_blank_category_rejected():
    with pytest.raises(argparse.ArgumentTypeError):
        budget.valid_category("   ")
    assert budget.valid_category(" Groceries ") == "groceries"


def test_budget_check_flags_overspend(tmp_path, capsys):
    run(tmp_path, "add", "-450", "Groceries", "--date", "2026-09-02")
    run(tmp_path, "budget", "set", "groceries", "400")
    capsys.readouterr()
    run(tmp_path, "budget", "check", "--month", "2026-09")
    assert "OVER by 50.00" in capsys.readouterr().out


def test_report_totals(tmp_path, capsys):
    run(tmp_path, "add", "2500", "salary", "--date", "2026-09-01")
    run(tmp_path, "add", "-0.1", "misc", "--date", "2026-09-01")
    run(tmp_path, "add", "-0.2", "misc", "--date", "2026-09-01")
    capsys.readouterr()
    run(tmp_path, "report", "--month", "2026-09")
    out = capsys.readouterr().out
    assert "2,499.70" in out and "-0.30" in out
