"""
Phase 1 — Data loading.

Loads the Titanic dataset from seaborn and saves a raw copy to disk so the rest
of the pipeline (cleaning, analysis, viz) always reads from a CSV — same flow
you'd use for a real-world dataset.
"""

from pathlib import Path

import pandas as pd
import seaborn as sns

RAW_CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "titanic.csv"


def load_titanic(force_refresh: bool = False) -> pd.DataFrame:
    """Load the Titanic dataset.

    On first run (or when force_refresh=True), pulls it from seaborn and writes
    it to backend/data/raw/titanic.csv. On later runs, reads that CSV directly.
    """
    if RAW_CSV_PATH.exists() and not force_refresh:
        return pd.read_csv(RAW_CSV_PATH)

    df = sns.load_dataset("titanic")
    RAW_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(RAW_CSV_PATH, index=False)
    return df


def overview(df: pd.DataFrame) -> None:
    """Print a quick snapshot of the dataset."""
    print("=" * 60)
    print(f"Shape:   {df.shape[0]} rows × {df.shape[1]} columns")
    print("=" * 60)

    print("\nColumns & dtypes:")
    print(df.dtypes.to_string())

    print("\nFirst 5 rows:")
    print(df.head().to_string())

    print("\nMissing values per column:")
    missing = df.isna().sum()
    print(missing[missing > 0].to_string() or "  (none)")

    print("\nNumeric summary:")
    print(df.describe().to_string())


if __name__ == "__main__":
    df = load_titanic()
    overview(df)
