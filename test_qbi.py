from decimal import Decimal as D

import pytest

from qbi import Business, FilingStatus, compute_qbi_deduction, qbi_deduction
from exercises import PROBLEMS


@pytest.mark.parametrize("title, expected", [
    ("58a", "18000.00"), ("58b", "0.00"), ("59a", "40000.00"),
    ("59b", "70000.00"), ("60a", "50000.00"), ("60b", "0.00"),
])
def test_textbook_problems(title, expected):
    kwargs = next(v for k, v in PROBLEMS.items() if k.startswith(title))
    assert qbi_deduction(**kwargs).deduction == D(expected)


def test_below_threshold_uses_taxable_income_cap():
    # 20% of QBI = 40,000 but 20% x (100,000 - 50,000) = 10,000
    r = qbi_deduction("SNG", 100_000, 200_000, net_capital_gain=50_000)
    assert r.deduction == D("10000.00")


def test_phase_in_non_sstb_2021():
    # 50% through the range: 20,000 - (20,000 - 10,000) * 50% = 15,000
    r = qbi_deduction("SNG", 189_900, 100_000, w2_wages=20_000, tax_year=2021)
    assert r.deduction == D("15000.00")


def test_phase_in_limit_larger_than_qbi_does_not_increase_deduction():
    # The old code had a bug here: it could ADD to the deduction.
    r = qbi_deduction("SNG", 189_900, 10_000, w2_wages=100_000, tax_year=2021)
    assert r.deduction == D("2000.00")


def test_phase_in_sstb_2021():
    r = qbi_deduction("SNG", 189_900, 100_000, w2_wages=40_000, sstb=True, tax_year=2021)
    assert r.deduction == D("10000.00")


def test_mfj_uses_joint_threshold():
    assert qbi_deduction("MFJ", 300_000, 100_000, tax_year=2025).deduction == D("20000.00")
    assert qbi_deduction("SNG", 300_000, 100_000, tax_year=2025).deduction == D("0.00")


def test_loss_netting_and_carryforward():
    r = compute_qbi_deduction("SNG", 100_000,
                              [Business(100_000, name="A"), Business(-40_000, name="B")])
    assert r.deduction == D("12000.00")
    r = compute_qbi_deduction("SNG", 100_000, [Business(-40_000)])
    assert r.deduction == D("0.00") and r.qbi_loss_carryforward == D("40000.00")


def test_reit_component_ignores_wage_limit():
    r = compute_qbi_deduction("SNG", 500_000, [], reit_ptp_income=10_000)
    assert r.deduction == D("2000.00")


def test_minimum_deduction_only_from_2026():
    assert qbi_deduction("SNG", 50_000, 1_500, tax_year=2026).deduction == D("400.00")
    assert qbi_deduction("SNG", 50_000, 1_500, tax_year=2025).deduction == D("300.00")


def test_bad_inputs():
    with pytest.raises(ValueError):
        FilingStatus.parse("martian")
    with pytest.raises(ValueError):
        qbi_deduction("SNG", 1, 1, tax_year=1999)
