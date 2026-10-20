# Qualified Business Income (QBI) Deduction Calculator

A Python calculator for the Section 199A qualified business income deduction,
built to solve and verify US Federal Taxation textbook problems.

It follows the statutory order of operations and prints every step, so you can
compare each line against a textbook solution.

## Features

- W-2 wage / UBIA limitation, including the phase-in range
- SSTB (specified service trade or business) handling, with the applicable
  percentage applied to QBI, wages and property inside the phase-in range
- Multiple businesses, with losses netted against profitable ones
- Qualified REIT dividends and PTP income
- QBI and REIT/PTP loss carryforwards
- Overall cap of 20% of taxable income less net capital gain
- 2026 rules: $75,000 / $150,000 phase-in range and the $400 minimum deduction
- Thresholds for tax years 2018 to 2026
- `Decimal` arithmetic, so there are no floating point surprises

## Requirements

Python 3.13 or later. The calculator uses only the standard library.
[uv](https://docs.astral.sh/uv/) is used for development.

## Usage

### One business (the typical textbook problem)

```python
from qbi import qbi_deduction

result = qbi_deduction(
    "SNG",
    taxable_income=500_000,
    qbi=600_000,
    w2_wages=100_000,
    ubia=200_000,
    sstb=False,           # False = QTB (default); set True for an SSTB
)

print(result.deduction)   # Decimal('50000.00')
print(result.report())    # step by step work
```

### Several businesses

```python
from qbi import Business, compute_qbi_deduction

result = compute_qbi_deduction(
    "MFJ",
    380_000,
    [
        Business(150_000, w2_wages=40_000, ubia=200_000, name="Shop"),
        Business(30_000, sstb=True, name="Consulting"),
    ],
    reit_ptp_income=5_000,
    net_capital_gain=10_000,
)
print(result.report())
```

### Parameters

| Parameter | Meaning |
|---|---|
| `taxable_income` | Taxable income **before** the QBI deduction |
| `qbi` | Net business income, after the deductible part of self-employment tax |
| `w2_wages` | Your share of W-2 wages paid by the business |
| `ubia` | Unadjusted basis immediately after acquisition of qualified property |
| `sstb` | `True` for a specified service trade or business |
| `net_capital_gain` | Net capital gain plus qualified dividends |
| `tax_year` | Defaults to the latest year in the table |

### SSTB vs. QTB: how to set the `sstb` flag

The calculator does not classify businesses. You decide, and pass the result as
`sstb=True` or `sstb=False`.

A **qualified trade or business (QTB)** is any trade or business (other than
being an employee) that is **not** a **specified service trade or business
(SSTB)**. So there is no separate QTB list: if the business is not on the SSTB
list, it is a QTB, and `sstb=False` (the default) is correct.

**SSTB fields** (Section 199A(d)(2)): health, law, accounting, actuarial
science, performing arts, consulting, athletics, financial services, brokerage
services, investing and investment management, trading, dealing in securities,
partnership interests or commodities, and any business whose principal asset
is the reputation or skill of its owners or employees.

**Not SSTBs:** engineering, architecture, manufacturing, retail, construction,
real estate, restaurants and similar businesses.

The label only matters when taxable income is above the threshold:

| Taxable income | QTB (`sstb=False`) | SSTB (`sstb=True`) |
|---|---|---|
| At or below the threshold | 20% of QBI | 20% of QBI (same as a QTB) |
| Inside the phase-in range | W-2/UBIA limit phases in | QBI, wages and UBIA are first reduced by the applicable percentage, then the limit phases in |
| Above the range | Lesser of 20% of QBI or the W-2/UBIA limit | $0 |

Examples from the exercises: an attorney or an investment broker is an SSTB
(`sstb=True`), while an engineer or a technology consultant treated as a
regular business is a QTB (`sstb=False`).

Two rules can change the classification and are **not** modeled, so apply them
yourself before choosing the flag: the de minimis rule (not an SSTB if SSTB
activity is under 10% of gross receipts, or 5% above $25 million) and the
related-business rule (a business that provides 80% or more of its property or
services to a commonly owned SSTB is part of that SSTB). See Treas. Reg.
Sec. 1.199A-5.

### Filing status codes

| Code | Status |
|---|---|
| `SNG` | Single |
| `MFJ` | Married filing jointly |
| `MFS` | Married filing separately |
| `QSS` | Qualifying surviving spouse |
| `HOH` | Head of household |

Codes are case-insensitive. Only MFJ uses the joint threshold amounts.

## Exercises and tests

```bash
uv run python exercises.py   # problems 58-60 with full reports
uv run pytest -q             # test suite
```

## Updating for a new tax year

Add one line to the `YEARS` table in `qbi.py` when the IRS publishes the new
threshold amounts:

```python
2027: YearParams(threshold_single, threshold_joint, range_single, range_joint, ...),
```

## Known limitations

- Whether the 2026 $400 minimum deduction is also capped by taxable income has
  not been verified. It is applied as a flat $400 when the taxpayer has at
  least $1,000 of QBI from businesses where they materially participate.
- Aggregation elections, the trust and estate rules, and cooperative
  (Section 199A(g)) deductions are not modeled.
- The SSTB de minimis and related-business rules are not modeled. Classify the
  business first, then set the `sstb` flag.

## Disclaimer

This project is for study and verification. It is not tax advice. Check results
against the current Code, regulations and IRS guidance before relying on them.
