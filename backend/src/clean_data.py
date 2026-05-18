"""
Phase 2 — Cleaning, row filtering, feature engineering, encoding.

Reads the raw CSV produced by load_data.py, applies a deterministic
transformation pipeline, and writes the result to
backend/data/processed/titanic_clean.csv.

The pipeline is organized into three layers:
  1. Cleaning      — drop redundant cols, fill/impute missing values, filter outliers.
  2. Feature eng.  — derive new columns from existing ones (family_size, fare_tier, ...).
  3. Encoding/norm — get_dummies for embarked, binary for sex, z-scores, log transforms.

Design notes:
- We impute `age` using the median of each (pclass, sex) group — a 1st-class
  woman has a very different age profile than a 3rd-class man, so a global
  median would smear that signal out.
- `deck` is ~77% missing, so we don't try to impute it — we keep the column as
  a categorical with an explicit "Unknown" bucket. That way charts can still
  show the "we don't know" group instead of silently dropping rows.
- We drop the 3 fare outliers (>= $300) so distributions and correlations
  aren't dominated by a tiny tail.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from load_data import load_titanic

PROCESSED_CSV_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "processed" / "titanic_clean.csv"
)

REDUNDANT_COLUMNS = ["class", "alive", "embark_town", "adult_male"]
FARE_OUTLIER_THRESHOLD = 300


# ---------------------------------------------------------------------------
# Cleaning
# ---------------------------------------------------------------------------

def impute_age(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing ages with the median age of the (pclass, sex) group."""
    df = df.copy()
    df["age"] = df.groupby(["pclass", "sex"])["age"].transform(
        lambda s: s.fillna(s.median())
    )
    return df


def filter_fare_outliers(df: pd.DataFrame, threshold: float = FARE_OUTLIER_THRESHOLD) -> pd.DataFrame:
    """Drop rows whose fare exceeds the outlier threshold."""
    return df[df["fare"] <= threshold].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Feature engineering — derive columns from existing ones
# ---------------------------------------------------------------------------

def add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Family aggregation
    df["family_size"] = df["sibsp"] + df["parch"] + 1
    df["has_family"] = (df["family_size"] > 1).astype(int)
    df["is_minor"] = (df["age"] < 18).astype(int)

    # Age binning — fixed thresholds via pd.cut
    df["age_group"] = pd.cut(
        df["age"],
        bins=[0, 12, 17, 59, np.inf],
        labels=["Child", "Teen", "Adult", "Senior"],
    )

    # Fare features
    df["fare_per_person"] = np.where(
        df["family_size"] > 0, df["fare"] / df["family_size"], df["fare"]
    )

    # Fare binning — equal-count quartiles via pd.qcut (contrast with pd.cut)
    df["fare_tier"] = pd.qcut(
        df["fare"], q=4, labels=["Low", "Mid", "High", "Premium"]
    )

    # Cabin presence
    df["cabin_known"] = (df["deck"] != "Unknown").astype(int)

    return df


# ---------------------------------------------------------------------------
# Encoding & normalization
# ---------------------------------------------------------------------------

def encode_and_normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Binary encode sex
    df["is_female"] = (df["sex"] == "female").astype(int)

    # One-hot encode embarked port -> emb_C, emb_Q, emb_S
    embarked_dummies = pd.get_dummies(df["embarked"], prefix="emb").astype(int)
    df = pd.concat([df, embarked_dummies], axis=1)

    # Log-transform fare (skewed positive) — log1p handles fare=0 gracefully
    df["log_fare"] = np.log1p(df["fare"]).round(3)

    # Z-score normalize age and fare
    df["age_z"] = ((df["age"] - df["age"].mean()) / df["age"].std()).round(3)
    df["fare_z"] = ((df["fare"] - df["fare"].mean()) / df["fare"].std()).round(3)

    return df


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------

def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Run the full cleaning pipeline."""
    df = df.copy()

    df["embarked"] = df["embarked"].fillna(df["embarked"].mode().iloc[0])
    df["deck"] = df["deck"].fillna("Unknown")
    df = impute_age(df)
    df = filter_fare_outliers(df)
    df = df.drop(columns=REDUNDANT_COLUMNS, errors="ignore")
    df = add_derived_features(df)
    df = encode_and_normalize(df)

    return df


def summary(df: pd.DataFrame) -> None:
    """Print a quick snapshot of the cleaned dataset."""
    print("=" * 60)
    print(f"Cleaned shape: {df.shape[0]} rows × {df.shape[1]} columns")
    print("=" * 60)

    print("\nRemaining missing values:")
    missing = df.isna().sum()
    print(missing[missing > 0].to_string() or "  (none)")

    new_cols = [
        "family_size", "has_family", "is_minor", "age_group",
        "fare_per_person", "fare_tier", "cabin_known", "is_female",
        "emb_C", "emb_Q", "emb_S", "log_fare", "age_z", "fare_z",
    ]
    available = [c for c in new_cols if c in df.columns]
    print("\nSample of engineered columns:")
    print(df[available].head(6).to_string())


if __name__ == "__main__":
    raw = load_titanic()
    cleaned = clean(raw)

    PROCESSED_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(PROCESSED_CSV_PATH, index=False)
    print(f"Wrote {PROCESSED_CSV_PATH.relative_to(Path.cwd())}\n")

    summary(cleaned)
