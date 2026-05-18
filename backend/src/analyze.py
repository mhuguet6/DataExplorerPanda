"""
Phase 3 — Exploratory analysis.

Every function here returns a DataFrame or dict — never prints, never plots.
That separation lets Phase 4 (charts) and Phase 5 (JSON export) reuse the
same numbers without re-computing them, and makes the functions trivially
testable.
"""

from pathlib import Path

import pandas as pd

from clean_data import PROCESSED_CSV_PATH, clean
from load_data import load_titanic


# ---------------------------------------------------------------------------
# Group-by analyses
# ---------------------------------------------------------------------------

def survival_by(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Survival rate and passenger count grouped by a single column.

    Returns a DataFrame with columns [<column>, n, survival_rate], sorted by
    the group so output is stable across runs.
    """
    grouped = (
        df.groupby(column, observed=True)["survived"]
        .agg(n="count", survival_rate="mean")
        .reset_index()
        .sort_values(column)
    )
    grouped["survival_rate"] = grouped["survival_rate"].round(3)
    return grouped


def survival_crosstab(df: pd.DataFrame, row: str, col: str) -> pd.DataFrame:
    """Cross-tab of survival rate for two categorical dimensions.

    e.g. survival_crosstab(df, "sex", "pclass") shows the famous
    "1st-class women survived, 3rd-class men didn't" pattern.
    """
    return (
        df.groupby([row, col], observed=True)["survived"]
        .mean()
        .round(3)
        .unstack(col)
    )


# ---------------------------------------------------------------------------
# Filtering queries
# ---------------------------------------------------------------------------

def children_traveling_alone(df: pd.DataFrame) -> pd.DataFrame:
    """Children (<18) with no siblings/spouse/parents on board."""
    mask = (df["age"] < 18) & (df["family_size"] == 1)
    return df.loc[mask, ["age", "sex", "pclass", "fare", "survived"]].reset_index(drop=True)


def top_fares(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """The n highest-paying passengers and whether they survived."""
    return (
        df.nlargest(n, "fare")[["sex", "age", "pclass", "fare", "survived"]]
        .reset_index(drop=True)
    )


def large_families(df: pd.DataFrame, min_size: int = 5) -> pd.DataFrame:
    """Aggregate stats for passengers in families of `min_size` or more."""
    big = df[df["family_size"] >= min_size]
    return (
        big.groupby("family_size", observed=True)
        .agg(n=("survived", "count"), survival_rate=("survived", "mean"))
        .round(3)
        .reset_index()
    )


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------

# Continuous numeric cols — used by numeric_summary (mean/std/quartiles).
NUMERIC_COLS = ["age", "fare", "fare_per_person", "log_fare", "family_size", "sibsp", "parch"]

# Cols included in the correlation matrix. We add binary features here because
# their correlations are meaningful (e.g. is_female ↔ survived) even though
# their describe() output isn't.
CORRELATION_COLS = NUMERIC_COLS + ["is_female", "is_minor", "cabin_known", "has_family"]


def headline_metrics(df: pd.DataFrame) -> dict:
    """Single-number metrics suitable for a dashboard 'key metrics' row."""
    return {
        "total_passengers": int(len(df)),
        "survival_rate": round(df["survived"].mean(), 3),
        "avg_age": round(df["age"].mean(), 1),
        "avg_fare": round(df["fare"].mean(), 2),
        "pct_female": round((df["sex"] == "female").mean(), 3),
        "pct_first_class": round((df["pclass"] == 1).mean(), 3),
    }


def numeric_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Describe() restricted to the numeric columns we actually care about."""
    return df[NUMERIC_COLS].describe().round(2)


def correlation_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Pearson correlations among numeric + binary features (incl. survived)."""
    cols = ["survived"] + [c for c in CORRELATION_COLS if c in df.columns]
    return df[cols].corr().round(3)


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def _load() -> pd.DataFrame:
    """Read the processed CSV if it exists, otherwise build it on the fly."""
    if PROCESSED_CSV_PATH.exists():
        return pd.read_csv(PROCESSED_CSV_PATH)
    return clean(load_titanic())


if __name__ == "__main__":
    df = _load()

    print("=" * 60)
    print("Headline metrics")
    print("=" * 60)
    for k, v in headline_metrics(df).items():
        print(f"  {k:20s} {v}")

    print("\n── Survival rate by sex ──")
    print(survival_by(df, "sex").to_string(index=False))

    print("\n── Survival rate by pclass ──")
    print(survival_by(df, "pclass").to_string(index=False))

    print("\n── Survival rate by age_group ──")
    print(survival_by(df, "age_group").to_string(index=False))

    print("\n── Survival rate by embarked port ──")
    print(survival_by(df, "embarked").to_string(index=False))

    print("\n── Survival rate by family_size ──")
    print(survival_by(df, "family_size").to_string(index=False))

    print("\n── Sex × Class survival rates ──")
    print(survival_crosstab(df, "sex", "pclass").to_string())

    print("\n── Children traveling alone (first 10) ──")
    print(children_traveling_alone(df).head(10).to_string(index=False))

    print("\n── Top 5 fares ──")
    print(top_fares(df, n=5).to_string(index=False))

    print("\n── Large families (>=5) ──")
    print(large_families(df).to_string(index=False))

    print("\n── Numeric summary ──")
    print(numeric_summary(df).to_string())

    print("\n── Correlation matrix ──")
    print(correlation_matrix(df).to_string())
