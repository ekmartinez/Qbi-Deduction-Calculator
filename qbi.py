"""
qbi.py - Section 199A Qualified Business Income (QBI) deduction calculator.

Quick use (one business):

    from qbi import qbi_deduction
    result = qbi_deduction("SNG", taxable_income=500_000, qbi=600_000,
                           w2_wages=100_000, ubia=200_000)
    print(result.report())      # step by step work
    print(result.deduction)     # Decimal('50000.00')

Several businesses / REIT dividends / loss carryforwards:

    from qbi import Business, compute_qbi_deduction
    result = compute_qbi_deduction(
        "MFJ", 380_000,
        [Business(150_000, w2_wages=40_000, ubia=200_000, name="Shop"),
         Business(30_000, sstb=True, name="Consulting")],
        reit_ptp_income=5_000,
    )

Every amount is handled with Decimal, so there are no float rounding surprises.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Iterable, Union

Money = Union[Decimal, int, float, str]

CENT = Decimal("0.01")
QBI_RATE = Decimal("0.20")
WAGE_RATE = Decimal("0.50")          # 50% of W-2 wages
WAGE_PLUS_RATE = Decimal("0.25")     # 25% of W-2 wages ...
UBIA_RATE = Decimal("0.025")         # ... + 2.5% of UBIA of qualified property


# --------------------------------------------------------------------------- #
# Yearly parameters
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class YearParams:
    threshold_single: int
    threshold_joint: int
    range_single: int = 50_000
    range_joint: int = 100_000
    min_deduction: int = 0       # Sec. 199A(i), new in 2026
    min_qbi: int = 0


# Threshold amounts are indexed for inflation. The phase-in range was widened to
# $75,000 / $150,000 and a $400 minimum deduction was added starting in 2026 (OBBBA).
# ADD A NEW LINE HERE EVERY YEAR when the IRS publishes the new amounts.
YEARS: dict[int, YearParams] = {
    2018: YearParams(157_500, 315_000),
    2019: YearParams(160_700, 321_400),
    2020: YearParams(163_300, 326_600),
    2021: YearParams(164_900, 329_800),
    2022: YearParams(170_050, 340_100),
    2023: YearParams(182_100, 364_200),
    2024: YearParams(191_950, 383_900),
    2025: YearParams(197_300, 394_600),
    2026: YearParams(201_750, 403_500, 75_000, 150_000, min_deduction=400, min_qbi=1_000),
}
DEFAULT_TAX_YEAR = max(YEARS)


# --------------------------------------------------------------------------- #
# Helpers and enums
# --------------------------------------------------------------------------- #
def _d(value: Money) -> Decimal:
    """Convert int/float/str/Decimal to Decimal ('$1,000' and '1,000' are accepted)."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, str):
        value = value.replace(",", "").replace("$", "").strip()
    return Decimal(str(value))


def _money(x: Decimal) -> str:
    return f"${x:,.2f}"


def _cents(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


class FilingStatus(Enum):
    SINGLE = "Single"
    MFJ = "Married filing jointly"
    MFS = "Married filing separately"
    HOH = "Head of household"
    QSS = "Qualifying surviving spouse"

    @classmethod
    def parse(cls, value: Union[str, "FilingStatus"]) -> "FilingStatus":
        if isinstance(value, cls):
            return value
        key = str(value).strip().upper().replace("_", " ")
        aliases = {
            "SNG": cls.SINGLE,
            "MFJ": cls.MFJ,
            "MFS": cls.MFS,
            "HOH": cls.HOH,
            "QSS": cls.QSS,
        }
        try:
            return aliases[key]
        except KeyError:
            raise ValueError(f"Unknown filing status: {value!r}") from None

    @property
    def joint_amounts(self) -> bool:
        """Only MFJ uses the doubled amounts; everybody else uses the 'single' amounts."""
        return self is FilingStatus.MFJ


class Zone(Enum):
    BELOW = "At or below threshold (no W-2/UBIA limit, no SSTB restriction)"
    PHASE_IN = "Inside phase-in range (limits partially apply)"
    ABOVE = "Above phase-in range (limits fully apply; SSTB gets zero)"


# --------------------------------------------------------------------------- #
# Input / output models
# --------------------------------------------------------------------------- #
@dataclass
class Business:
    """One qualified trade or business (sole proprietorship, or your share of a
    partnership / S corporation)."""
    qbi: Money                          # net of the deductible half of SE tax, SE health ins., retirement plan
    w2_wages: Money = 0                 # your allocable share
    ubia: Money = 0                     # unadjusted basis immediately after acquisition of qualified property
    sstb: bool = False                  # specified service trade or business (law, health, accounting, consulting,
                                        # financial services/brokerage, performing arts, athletics, etc.)
    name: str = "Business"
    materially_participates: bool = True  # only matters for the 2026+ minimum deduction

    def __post_init__(self) -> None:
        self.qbi, self.w2_wages, self.ubia = _d(self.qbi), _d(self.w2_wages), _d(self.ubia)
        if self.w2_wages < 0 or self.ubia < 0:
            raise ValueError("W-2 wages and UBIA cannot be negative.")


@dataclass
class BusinessResult:
    name: str
    sstb: bool
    qbi_original: Decimal
    qbi: Decimal                # after SSTB reduction and loss netting
    w2_wages: Decimal           # after SSTB reduction
    ubia: Decimal               # after SSTB reduction
    twenty_pct_qbi: Decimal
    wage_limit_a: Decimal       # 50% of W-2 wages
    wage_limit_b: Decimal       # 25% of W-2 wages + 2.5% of UBIA
    wage_limit: Decimal         # greater of a and b
    allowed: Decimal            # QBI component of this business


@dataclass
class QBIResult:
    tax_year: int
    status: FilingStatus
    taxable_income: Decimal
    net_capital_gain: Decimal
    threshold: Decimal
    upper_limit: Decimal
    zone: Zone
    phase_in_pct: Decimal               # (TI - threshold) / range, between 0 and 1
    applicable_pct: Decimal             # 1 - phase_in_pct, used for SSTBs
    businesses: list[BusinessResult] = field(default_factory=list)
    combined_qbi_amount: Decimal = Decimal(0)
    reit_ptp_component: Decimal = Decimal(0)
    tentative_deduction: Decimal = Decimal(0)
    taxable_income_limit: Decimal = Decimal(0)
    deduction: Decimal = Decimal(0)
    minimum_deduction_applied: bool = False
    qbi_loss_carryforward: Decimal = Decimal(0)        # to next year
    reit_ptp_loss_carryforward: Decimal = Decimal(0)   # to next year

    def report(self) -> str:
        w = 58
        line = "-" * w

        def row(label: str, amount: str) -> str:
            return f"  {label:<{w - 16}}{amount:>14}"

        out = [
            line,
            f"QBI DEDUCTION  (tax year {self.tax_year}, {self.status.value})",
            line,
            row("Taxable income before QBI deduction", _money(self.taxable_income)),
            row("Net capital gain + qualified dividends", _money(self.net_capital_gain)),
            row("Threshold amount", _money(self.threshold)),
            row("Top of phase-in range", _money(self.upper_limit)),
            f"  Zone: {self.zone.value}",
        ]
        if self.zone is Zone.PHASE_IN:
            out.append(row("Phase-in percentage", f"{self.phase_in_pct:.2%}"))
        for b in self.businesses:
            out += ["", f"{b.name}{'  [SSTB]' if b.sstb else ''}"]
            if b.qbi != b.qbi_original:
                out.append(row("QBI as originally reported", _money(b.qbi_original)))
                out.append(row("QBI after SSTB % / loss netting", _money(b.qbi)))
            else:
                out.append(row("QBI", _money(b.qbi)))
            out.append(row("(1) 20% of QBI", _money(b.twenty_pct_qbi)))
            if self.zone is not Zone.BELOW and b.qbi > 0:
                out.append(row("    50% of W-2 wages", _money(b.wage_limit_a)))
                out.append(row("    25% of W-2 + 2.5% of UBIA", _money(b.wage_limit_b)))
                out.append(row("(2) W-2 wage / UBIA limit (greater)", _money(b.wage_limit)))
            out.append(row("QBI component", _money(b.allowed)))
        out += [
            "",
            row("Combined QBI amount", _money(self.combined_qbi_amount)),
            row("+ 20% of REIT dividends / PTP income", _money(self.reit_ptp_component)),
            row("Tentative deduction", _money(self.tentative_deduction)),
            row("20% x (taxable income - net capital gain)", _money(self.taxable_income_limit)),
        ]
        if self.minimum_deduction_applied:
            out.append("  ** $400 minimum deduction applied (Sec. 199A(i)) **")
        out += [
            line,
            row("QBI DEDUCTION (lesser of the two)", _money(self.deduction)),
            line,
        ]
        if self.qbi_loss_carryforward:
            out.append(f"  QBI loss carried to next year: {_money(self.qbi_loss_carryforward)}")
        if self.reit_ptp_loss_carryforward:
            out.append(f"  REIT/PTP loss carried to next year: {_money(self.reit_ptp_loss_carryforward)}")
        return "\n".join(out)

    __str__ = report


# --------------------------------------------------------------------------- #
# Core calculation
# --------------------------------------------------------------------------- #
def compute_qbi_deduction(
    status: Union[str, FilingStatus],
    taxable_income: Money,
    businesses: Union[Business, Iterable[Business]],
    *,
    net_capital_gain: Money = 0,
    reit_ptp_income: Money = 0,
    qbi_loss_carryforward: Money = 0,
    reit_ptp_loss_carryforward: Money = 0,
    tax_year: int = DEFAULT_TAX_YEAR,
) -> QBIResult:
    """
    Compute the Sec. 199A deduction.

    taxable_income      Taxable income BEFORE the QBI deduction.
    net_capital_gain    Net capital gain plus qualified dividends (excluded from the 20% income cap).
    reit_ptp_income     Qualified REIT dividends + qualified PTP income.
    *_loss_carryforward Positive numbers: losses carried from prior years.
    """
    if tax_year not in YEARS:
        raise ValueError(f"No parameters for {tax_year}. Add them to YEARS (known: {min(YEARS)}-{max(YEARS)}).")
    params = YEARS[tax_year]
    status = FilingStatus.parse(status)
    if isinstance(businesses, Business):
        businesses = [businesses]
    businesses = list(businesses)

    ti = _d(taxable_income)
    ncg = _d(net_capital_gain)
    prior_loss = abs(_d(qbi_loss_carryforward))
    prior_reit_loss = abs(_d(reit_ptp_loss_carryforward))

    # --- Threshold, range and zone -------------------------------------------------
    joint = status.joint_amounts
    threshold = Decimal(params.threshold_joint if joint else params.threshold_single)
    rng = Decimal(params.range_joint if joint else params.range_single)
    upper = threshold + rng

    if ti <= threshold:
        zone, phase_in = Zone.BELOW, Decimal(0)
    elif ti < upper:
        zone, phase_in = Zone.PHASE_IN, (ti - threshold) / rng
    else:
        zone, phase_in = Zone.ABOVE, Decimal(1)
    applicable = Decimal(1) - phase_in

    # --- Step 1: SSTB reduction (QBI, wages and UBIA all scaled by applicable %) -----
    adjusted = []
    for b in businesses:
        pct = applicable if (b.sstb and zone is not Zone.BELOW) else Decimal(1)
        adjusted.append((b, b.qbi * pct, b.w2_wages * pct, b.ubia * pct))

    # --- Step 2: net losses against income from the other businesses ------------------
    # Losses (current-year and carryforward) reduce each profitable business pro rata.
    total_pos = sum((q for _, q, _, _ in adjusted if q > 0), Decimal(0))
    total_loss = sum((-q for _, q, _, _ in adjusted if q < 0), Decimal(0)) + prior_loss
    keep = (max(total_pos - total_loss, Decimal(0)) / total_pos) if total_pos > 0 else Decimal(0)
    loss_cf_out = max(total_loss - total_pos, Decimal(0))

    # --- Step 3: per-business QBI component --------------------------------------------
    results: list[BusinessResult] = []
    for b, qbi, w2, ubia in adjusted:
        qbi_net = qbi * keep if qbi > 0 else Decimal(0)
        twenty = qbi_net * QBI_RATE
        lim_a = w2 * WAGE_RATE
        lim_b = w2 * WAGE_PLUS_RATE + ubia * UBIA_RATE
        limit = max(lim_a, lim_b)

        if zone is Zone.BELOW or twenty <= limit:
            allowed = twenty
        elif zone is Zone.PHASE_IN:
            allowed = twenty - (twenty - limit) * phase_in
        else:
            allowed = limit

        results.append(BusinessResult(b.name, b.sstb, b.qbi, qbi_net, w2, ubia,
                                      twenty, lim_a, lim_b, limit, allowed))

    combined = sum((r.allowed for r in results), Decimal(0))

    # --- Step 4: REIT dividends / PTP income component (no wage limit) -----------------
    reit_net = _d(reit_ptp_income) - prior_reit_loss
    reit_component = max(reit_net, Decimal(0)) * QBI_RATE
    reit_loss_cf_out = max(-reit_net, Decimal(0))

    # --- Step 5: overall taxable income cap ---------------------------------------------
    tentative = combined + reit_component
    ti_limit = max(ti - ncg, Decimal(0)) * QBI_RATE
    deduction = min(tentative, ti_limit)

    # --- Step 6: $400 minimum deduction (2026 and later) --------------------------------
    # Needs >= $1,000 of QBI from businesses where the taxpayer materially participates.
    # NOTE: I did not verify whether the statute also caps this minimum by taxable income.
    min_applied = False
    if params.min_deduction:
        active_qbi = sum((q for (b, q, _, _) in adjusted if b.materially_participates), Decimal(0))
        if active_qbi >= params.min_qbi and deduction < params.min_deduction:
            deduction, min_applied = Decimal(params.min_deduction), True

    return QBIResult(
        tax_year=tax_year, status=status, taxable_income=ti, net_capital_gain=ncg,
        threshold=threshold, upper_limit=upper, zone=zone,
        phase_in_pct=phase_in, applicable_pct=applicable, businesses=results,
        combined_qbi_amount=_cents(combined), reit_ptp_component=_cents(reit_component),
        tentative_deduction=_cents(tentative), taxable_income_limit=_cents(ti_limit),
        deduction=_cents(deduction), minimum_deduction_applied=min_applied,
        qbi_loss_carryforward=_cents(loss_cf_out), reit_ptp_loss_carryforward=_cents(reit_loss_cf_out),
    )


def qbi_deduction(
    status: Union[str, FilingStatus],
    taxable_income: Money,
    qbi: Money,
    w2_wages: Money = 0,
    ubia: Money = 0,
    sstb: bool = False,
    net_capital_gain: Money = 0,
    tax_year: int = DEFAULT_TAX_YEAR,
) -> QBIResult:
    """Shortcut for the common textbook case: one business."""
    return compute_qbi_deduction(
        status, taxable_income, Business(qbi, w2_wages, ubia, sstb),
        net_capital_gain=net_capital_gain, tax_year=tax_year,
    )
