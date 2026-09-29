import pytest

from khabeer import calc
from khabeer.tools import safe_output_path


def test_vat_exclusive_and_inclusive():
    assert calc.vat(1000, 15) == {"net": 1000.0, "vat": 150.0, "gross": 1150.0, "rate_percent": 15}
    r = calc.vat(1150, 15, inclusive=True)
    assert (r["net"], r["vat"]) == (1000.0, 150.0)


def test_straight_line_depreciation():
    s = calc.depreciation_schedule(10000, 1000, 3)["schedule"]
    assert [row["depreciation"] for row in s] == [3000.0, 3000.0, 3000.0]
    assert s[-1]["book_value_end"] == 1000.0


@pytest.mark.parametrize("method", ["declining_balance", "sum_of_years"])
def test_accelerated_methods_end_at_salvage(method):
    s = calc.depreciation_schedule(50000, 5000, 5, method)["schedule"]
    assert s[-1]["book_value_end"] == 5000.0
    assert s[0]["depreciation"] > s[-1]["depreciation"]


def test_sum_of_years_first_year():
    s = calc.depreciation_schedule(15000, 0, 5, "sum_of_years")["schedule"]
    assert s[0]["depreciation"] == 5000.0  # 5/15 of the base


def test_loan_amortization():
    r = calc.loan_amortization(100000, 12, 12)
    assert r["monthly_payment"] == 8884.88
    assert r["schedule"][-1]["balance"] == 0.0
    assert calc.loan_amortization(1200, 0, 12)["monthly_payment"] == 100.0


def test_investment_appraisal():
    r = calc.investment_appraisal(10, [-1000, 500, 500, 500])
    assert r["npv"] == 243.43
    assert r["irr_percent"] == 23.38
    assert r["payback_years"] == 2.0
    assert calc.irr([100, 200]) is None


def test_break_even():
    r = calc.break_even(10000, 50, 30)
    assert r["units"] == 500.0 and r["revenue"] == 25000.0
    with pytest.raises(ValueError):
        calc.break_even(100, 10, 10)


def test_ratios_skip_missing_inputs():
    r = calc.financial_ratios(current_assets=200, current_liabilities=100, inventory=50)
    assert r == {"current_ratio": 2.0, "quick_ratio": 1.5, "cash_ratio": 0.0}


def test_journal_entry():
    ok = calc.check_journal_entry([
        {"account": "الصندوق", "debit": 1150, "credit": 0},
        {"account": "المبيعات", "debit": 0, "credit": 1000},
        {"account": "ضريبة القيمة المضافة المستحقة", "debit": 0, "credit": 150},
    ])
    assert ok["balanced"]
    bad = calc.check_journal_entry([
        {"account": "الصندوق", "debit": 100, "credit": 0},
        {"account": "المبيعات", "debit": 0, "credit": 90},
    ])
    assert not bad["balanced"] and "unbalanced by 10" in bad["problems"][0]


def test_concrete_quantity():
    r = calc.concrete_quantity(2, 2, 0.5, count=4, waste_percent=5, unit_price=100)
    assert r["net_m3"] == 8.0 and r["with_waste_m3"] == 8.4 and r["estimated_cost"] == 840.0


def test_save_file_rejects_escape():
    with pytest.raises(ValueError):
        safe_output_path("../evil.txt")
    with pytest.raises(ValueError):
        safe_output_path("/etc/passwd")
    assert safe_output_path("site/index.html").name == "index.html"
