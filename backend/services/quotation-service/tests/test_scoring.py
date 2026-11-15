from decimal import Decimal as D

from app.scoring import WEIGHTS, Candidate, score


def cand(key, total, lead, *, currency="INR", complete=True, comp=None, terms=None, order=0):
    return Candidate(key, currency, D(total), lead, complete, comp, terms, order)


def test_the_weights_are_explicit_and_add_up_to_100():
    assert WEIGHTS == {"price": 40, "delivery": 20, "compliance": 25, "terms": 15} and sum(WEIGHTS.values()) == 100


def test_price_and_delivery_scores_are_relative_to_the_best_in_the_same_currency():
    s = score([cand("a", "94800.00", 14), cand("b", "90600.00", 21)])
    assert s["b"].price == D("100.00") and s["a"].price == D("95.57")  # 100 x 90600 / 94800
    assert s["a"].delivery == D("100.00") and s["b"].delivery == D("66.67")  # 100 x 14 / 21
    assert s["b"].lowest_price and not s["a"].lowest_price and s["a"].fastest and not s["b"].fastest


def test_the_overall_score_exists_only_when_all_four_parts_do():
    s = score([cand("a", "94800.00", 14, comp=8, terms=6), cand("b", "90600.00", 21, comp=7)])
    assert s["a"].total == D("87.23")  # (40 x 95.57 + 20 x 100 + 25 x 80 + 15 x 60) / 100 = 87.228
    assert s["b"].total is None and s["b"].missing == ["terms score"]  # not guessed
    assert s["a"].rank == 1 and s["b"].rank is None


def test_full_scores_and_ranking():
    s = score([cand("a", "94800.00", 14, comp=8, terms=6), cand("b", "90600.00", 21, comp=7, terms=9)])
    assert s["b"].total == D("84.33") and [s["a"].rank, s["b"].rank] == [1, 2]
    assert str(s["a"].compliance) == "80.00" and str(s["a"].terms) == "60.00"  # 0 to 10 counted as 0 to 100, always two decimals


def test_an_incomplete_quotation_gets_no_calculated_scores_and_does_not_set_the_benchmark():
    s = score([cand("full", "100.00", 10, comp=5, terms=5), cand("partial", "10.00", 1, complete=False, comp=9, terms=9)])
    assert s["partial"].price is None and s["partial"].delivery is None and s["partial"].total is None and "Some items are not quoted" in s["partial"].missing
    assert s["full"].price == D("100.00") and s["full"].delivery == D("100.00") and s["full"].rank == 1 and s["partial"].rank is None


def test_currencies_are_never_mixed():
    s = score([cand("inr1", "1000.00", 10, comp=5, terms=5), cand("inr2", "2000.00", 10, comp=5, terms=5), cand("usd", "5.00", 10, currency="USD", comp=5, terms=5)])
    assert s["usd"].price == D("100.00") and s["usd"].rank == 1  # alone in its currency
    assert s["inr1"].price == D("100.00") and s["inr2"].price == D("50.00") and [s["inr1"].rank, s["inr2"].rank] == [1, 2]


def test_zero_totals_do_not_divide_by_zero():
    s = score([cand("free", "0.00", 5), cand("paid", "50.00", 5)])
    assert s["free"].price == D("100.00") and s["paid"].price == D("0.00")
    assert score([cand("a", "0.00", 5), cand("b", "0.00", 5)])["b"].price == D("100.00")


def test_ties_are_ordered_by_lower_total_then_earlier_submission():
    same = score([cand("late", "100.00", 10, comp=5, terms=5, order=2), cand("early", "100.00", 10, comp=5, terms=5, order=1)])
    assert same["early"].rank == 1 and same["late"].rank == 2


def test_scores_are_deterministic_and_round_half_up():
    inputs = [cand("a", "3.00", 3, comp=5, terms=5), cand("b", "2.00", 7, comp=5, terms=5)]
    assert {k: v.total for k, v in score(inputs).items()} == {k: v.total for k, v in score(list(reversed(inputs))).items()}
    assert score([cand("a", "3.00", 1), cand("b", "2.00", 1)])["a"].price == D("66.67")  # 66.666...


def test_a_single_quotation_scores_100_for_price_and_delivery():
    s = score([cand("only", "10.00", 3, comp=10, terms=10)])
    assert s["only"].total == D("100.00") and s["only"].rank == 1
