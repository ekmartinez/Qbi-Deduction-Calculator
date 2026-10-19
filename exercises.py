"""Problems 58-60 (QBI deduction). Run:  python exercises.py"""
from qbi import qbi_deduction

PROBLEMS = {
    "58a Roquan (attorney, TI $100,000)":
        dict(status="SNG", taxable_income=100_000, qbi=90_000, w2_wages=40_000, ubia=10_000, sstb=True),
    "58b Roquan (attorney, TI $300,000)":
        dict(status="SNG", taxable_income=300_000, qbi=90_000, w2_wages=40_000, ubia=10_000, sstb=True),
    "59a Katie (engineer)":
        dict(status="SNG", taxable_income=400_000, qbi=200_000, w2_wages=300_000, ubia=150_000),
    "59b Katie (engineer, QBI $400,000)":
        dict(status="SNG", taxable_income=350_000, qbi=400_000, w2_wages=300_000, ubia=150_000),
    "60a Felipe (technology consultant)":
        dict(status="SNG", taxable_income=500_000, qbi=600_000, w2_wages=100_000, ubia=200_000),
    "60b Felipe (investment broker = SSTB)":
        dict(status="SNG", taxable_income=500_000, qbi=600_000, w2_wages=100_000, ubia=200_000, sstb=True),
}

if __name__ == "__main__":
    for title, kwargs in PROBLEMS.items():
        print(f"\n### {title}")
        print(qbi_deduction(**kwargs).report())
