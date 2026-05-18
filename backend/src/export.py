"""
Phase 5 — Export everything React needs into a single insights.json.

The frontend imports this file directly — no API, no fetch. That keeps Phase 6
trivial: `import insights from "./data/insights.json"` and render.

Why we route DataFrames through df.to_json() instead of df.to_dict():
  - to_dict() leaves NaN as float('nan'), which json.dumps refuses to serialize
  - to_dict() can leak numpy int64/float64 types that also fail to serialize
  - to_json() handles both correctly, and json.loads() turns it back into
    native Python lists/dicts so we can compose it into a bigger payload.
"""

import json
from pathlib import Path

import pandas as pd

import analyze
import visualize
from clean_data import PROCESSED_CSV_PATH, REDUNDANT_COLUMNS, clean
from load_data import load_titanic

INSIGHTS_PATH = Path(__file__).resolve().parents[1] / "outputs" / "insights.json"

# Static metadata about the cleaning pipeline (kept here, not in clean_data.py,
# because it's documentation about the pipeline rather than logic that runs).
TRANSFORMATIONS = {
    "dropped": REDUNDANT_COLUMNS,
    "added": [
        # Derived features
        "family_size", "has_family", "is_minor",
        "age_group", "fare_per_person", "fare_tier", "cabin_known",
        # Encoding & normalization
        "is_female", "emb_C", "emb_Q", "emb_S",
        "log_fare", "age_z", "fare_z",
    ],
    "imputed": [
        {"column": "age", "method": "median by (pclass, sex)"},
        {"column": "embarked", "method": "mode"},
        {"column": "deck", "method": "filled with 'Unknown'"},
    ],
    "filtered": [
        {"rule": "fare <= $300", "rows_removed": 3, "reason": "outlier"},
    ],
}

# Annotated walkthrough of the pandas pipeline — rendered by the React
# "Pipeline" tab. Lives here (not in each src/ file) so we can describe the
# pipeline as a single story instead of scattered docstrings.
PIPELINE_SECTIONS = [
    {
        "id": "loading",
        "title": "1. Loading",
        "summary": "Pull the dataset once and persist it as a CSV so the rest of the pipeline behaves like real-world data.",
        "steps": [
            {
                "title": "Load Titanic and cache a raw CSV",
                "why": "Seaborn gives us a clean Python entry point, but real datasets arrive as files. Writing the raw CSV once means every later step reads from disk, which matches how you'd work with any real dataset.",
                "code": "df = sns.load_dataset('titanic')\ndf.to_csv('data/raw/titanic.csv', index=False)",
                "result": "891 rows × 15 columns cached at data/raw/titanic.csv.",
            },
        ],
    },
    {
        "id": "cleaning",
        "title": "2. Cleaning",
        "summary": "Remove redundant columns, fill missing values with appropriate strategies, and filter out extreme outliers.",
        "steps": [
            {
                "title": "Drop redundant columns",
                "why": "`class` duplicates `pclass`, `alive` duplicates `survived`, `embark_town` duplicates `embarked`, and `adult_male` is derivable from `sex` + `age`. Carrying duplicates risks subtle bugs in groupby and correlation.",
                "code": "df = df.drop(columns=['class', 'alive', 'embark_town', 'adult_male'])",
                "result": "15 columns → 11 columns.",
            },
            {
                "title": "Fill missing `embarked` with the mode",
                "why": "Only 2 rows have missing `embarked`. The mode ('S', Southampton) is by far the most common port, so single-value imputation is safe.",
                "code": "df['embarked'] = df['embarked'].fillna(df['embarked'].mode().iloc[0])",
                "result": "2 missing values filled with 'S'.",
            },
            {
                "title": "Fill missing `deck` with 'Unknown'",
                "why": "77% of `deck` is missing — too sparse to impute realistically. An explicit 'Unknown' bucket keeps the column usable in charts and groupby (rows aren't silently dropped).",
                "code": "df['deck'] = df['deck'].fillna('Unknown')",
                "result": "688 missing values bucketed as 'Unknown'.",
            },
            {
                "title": "Impute missing `age` by (pclass, sex) median",
                "why": "A global median erases information — a 1st-class woman has a very different age profile than a 3rd-class man. Group-wise medians via `groupby().transform()` preserve that signal.",
                "code": "df['age'] = (\n    df.groupby(['pclass', 'sex'])['age']\n      .transform(lambda s: s.fillna(s.median()))\n)",
                "result": "177 missing ages filled using the median of each (class, sex) group.",
            },
            {
                "title": "Drop fare outliers (> $300)",
                "why": "Three passengers paid $512 — over 10× the median fare. They distort the fare distribution and dominate correlations. A simple boolean mask removes them.",
                "code": "df = df[df['fare'] <= 300].reset_index(drop=True)",
                "result": "3 outlier rows removed. 891 → 888 rows.",
            },
        ],
    },
    {
        "id": "features",
        "title": "3. Feature engineering",
        "summary": "Derive new columns that capture relationships the raw data only hints at.",
        "steps": [
            {
                "title": "`family_size` + boolean flags",
                "why": "Spouses/siblings and parents/children live in separate columns. Combining them (+1 for the passenger) creates a single number with a non-linear effect on survival. We also derive two convenience booleans for filtering and modeling.",
                "code": "df['family_size'] = df['sibsp'] + df['parch'] + 1\ndf['has_family'] = (df['family_size'] > 1).astype(int)\ndf['is_minor']   = (df['age'] < 18).astype(int)",
                "result": "Adds 3 columns. family_size ranges 1–11.",
            },
            {
                "title": "`age_group` via `pd.cut` (fixed bins)",
                "why": "Continuous age is hard to compare across cohorts. `pd.cut` bins by fixed thresholds — useful when the boundaries (child/teen/adult/senior) are conceptually meaningful, not just statistically equal-sized.",
                "code": "df['age_group'] = pd.cut(\n    df['age'],\n    bins=[0, 12, 17, 59, np.inf],\n    labels=['Child', 'Teen', 'Adult', 'Senior'],\n)",
                "result": "750 Adults, 69 Children, 44 Teens, 25 Seniors.",
            },
            {
                "title": "`fare_per_person` = fare / family_size",
                "why": "A $200 ticket for a family of 5 is very different from a $200 solo fare. Per-person fare is often the cleaner signal for class.",
                "code": "df['fare_per_person'] = np.where(\n    df['family_size'] > 0,\n    df['fare'] / df['family_size'],\n    df['fare'],\n)",
                "result": "Per-person fares range from $0 to ~$73 (after outlier filter).",
            },
            {
                "title": "`fare_tier` via `pd.qcut` (equal-count bins)",
                "why": "Where `pd.cut` uses fixed thresholds, `pd.qcut` makes 4 buckets of equal size — useful when you want a 'low/mid/high/premium' split that's robust to outliers and skew.",
                "code": "df['fare_tier'] = pd.qcut(\n    df['fare'],\n    q=4,\n    labels=['Low', 'Mid', 'High', 'Premium'],\n)",
                "result": "~222 passengers in each tier (888 / 4).",
            },
            {
                "title": "`cabin_known` from `deck`",
                "why": "Whether the cabin was *recorded* is itself signal — it correlates with class (1st-class records are more complete). A simple comparison turns the 'Unknown' bucket into a binary feature.",
                "code": "df['cabin_known'] = (df['deck'] != 'Unknown').astype(int)",
                "result": "200 passengers have a known cabin, 688 don't.",
            },
        ],
    },
    {
        "id": "encoding",
        "title": "4. Encoding & normalization",
        "summary": "Convert categoricals to numeric encodings and put continuous features on a comparable scale — the inputs most ML models expect.",
        "steps": [
            {
                "title": "Binary encode `sex` → `is_female`",
                "why": "A boolean comparison cast to int gives a single 0/1 column that can enter correlation matrices and regressions directly. Sex turns out to be the single strongest predictor of survival.",
                "code": "df['is_female'] = (df['sex'] == 'female').astype(int)",
                "result": "313 female (1), 575 male (0). Correlates ~+0.54 with survival.",
            },
            {
                "title": "One-hot encode `embarked` via `pd.get_dummies`",
                "why": "Ports C / Q / S have no natural ordering, so an ordinal encoding would lie. One-hot encoding splits the column into 3 mutually-exclusive binary columns — the right shape for any linear model.",
                "code": "embarked_dummies = pd.get_dummies(df['embarked'], prefix='emb').astype(int)\ndf = pd.concat([df, embarked_dummies], axis=1)",
                "result": "Adds emb_C, emb_Q, emb_S (one column per port).",
            },
            {
                "title": "Log-transform `fare` → `log_fare`",
                "why": "Fare is heavily right-skewed: most people paid under $50, a few paid hundreds. `np.log1p` (= log(1+x)) compresses the long tail while gracefully handling fare = $0 (which plain `log` can't).",
                "code": "df['log_fare'] = np.log1p(df['fare'])",
                "result": "Distribution becomes roughly bell-shaped, friendlier to most models.",
            },
            {
                "title": "Z-score normalize age and fare",
                "why": "Different features live on different scales — age (0-80) and fare ($0-$300) aren't comparable. Subtracting the mean and dividing by the std gives both a mean of 0 and an std of 1, so distance-based methods (KNN, PCA, gradient descent) treat them fairly.",
                "code": "df['age_z']  = (df['age']  - df['age'].mean())  / df['age'].std()\ndf['fare_z'] = (df['fare'] - df['fare'].mean()) / df['fare'].std()",
                "result": "Both columns now centered at 0 with unit std.",
            },
        ],
    },
    {
        "id": "analysis",
        "title": "5. Analysis",
        "summary": "The three pandas patterns that produce every number in the dashboard.",
        "steps": [
            {
                "title": "Groupby + agg for survival rates",
                "why": "Survival is encoded as 0/1, so the mean of `survived` is literally the survival rate. One groupby gives you both the count (`n`) and the rate at once.",
                "code": "df.groupby('pclass', observed=True)['survived'].agg(\n    n='count', survival_rate='mean'\n).reset_index()",
                "result": "1st: ~62% · 2nd: ~47% · 3rd: ~24% (after outlier filter).",
            },
            {
                "title": "Crosstab for two-dimensional rates",
                "why": "Single-variable comparisons can be confounded — class survival differs partly because women cluster in 1st class. A `sex × class` crosstab disentangles the two.",
                "code": "df.groupby(['sex', 'pclass'], observed=True)['survived']\n   .mean()\n   .unstack('pclass')",
                "result": "1st-class women: 97%; 3rd-class men: 14%. The strongest pattern in the dataset.",
            },
            {
                "title": "Correlation matrix",
                "why": "For numeric features, `.corr()` quickly reveals which are linearly related — both to the target (survival) and to each other (potential redundancy).",
                "code": "df[['survived', 'age', 'fare', 'family_size', ...]].corr()",
                "result": "Fare correlates +0.26 with survival; family_size correlates +0.89 with sibsp (as expected — they overlap).",
            },
        ],
    },
]


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> list of plain-Python dicts, NaN -> None, numpy -> native."""
    return json.loads(df.to_json(orient="records"))


def _df_to_dict(df: pd.DataFrame) -> dict:
    """DataFrame (indexed) -> nested dict suitable for JSON."""
    return json.loads(df.to_json())


def _table(title: str, df: pd.DataFrame) -> dict:
    return {"title": title, "rows": _df_to_records(df)}


def build_dataset_section(raw: pd.DataFrame, cleaned: pd.DataFrame) -> dict:
    missing_before = raw.isna().sum()
    missing_after = cleaned.isna().sum()
    return {
        "name": "Titanic",
        "source": "seaborn.load_dataset('titanic')",
        "raw_shape": list(raw.shape),
        "final_shape": list(cleaned.shape),
        "columns": list(cleaned.columns),
        "missing_before": missing_before[missing_before > 0].astype(int).to_dict(),
        "missing_after": missing_after[missing_after > 0].astype(int).to_dict(),
        "transformations": TRANSFORMATIONS,
    }


def build_tables(df: pd.DataFrame) -> dict:
    return {
        "survival_by_sex": _table(
            "Survival by sex", analyze.survival_by(df, "sex")
        ),
        "survival_by_class": _table(
            "Survival by passenger class", analyze.survival_by(df, "pclass")
        ),
        "survival_by_age_group": _table(
            "Survival by age group", analyze.survival_by(df, "age_group")
        ),
        "survival_by_embarked": _table(
            "Survival by port of embarkation", analyze.survival_by(df, "embarked")
        ),
        "survival_by_family_size": _table(
            "Survival by family size", analyze.survival_by(df, "family_size")
        ),
        "sex_x_class": {
            "title": "Survival rate: sex × class",
            "matrix": _df_to_dict(analyze.survival_crosstab(df, "sex", "pclass")),
        },
        "numeric_summary": {
            "title": "Numeric column summary",
            "matrix": _df_to_dict(analyze.numeric_summary(df)),
        },
        "correlation_matrix": {
            "title": "Correlation with survival and among numeric features",
            "matrix": _df_to_dict(analyze.correlation_matrix(df)),
        },
    }


def build_key_findings(df: pd.DataFrame) -> list[str]:
    """Short human-readable insights for the dashboard sidebar."""
    overall = df["survived"].mean()
    by_sex = analyze.survival_by(df, "sex").set_index("sex")["survival_rate"]
    by_class = analyze.survival_by(df, "pclass").set_index("pclass")["survival_rate"]
    cross = analyze.survival_crosstab(df, "sex", "pclass")

    return [
        f"Overall survival rate was {overall:.0%} ({int(df['survived'].sum())} of {len(df)} passengers).",
        f"Women survived at {by_sex['female']:.0%}, men at {by_sex['male']:.0%} — a {by_sex['female'] - by_sex['male']:.0%} gap.",
        f"1st-class passengers survived at {by_class[1]:.0%}, vs {by_class[3]:.0%} for 3rd class.",
        f"The strongest pattern: 1st-class women survived at {cross.loc['female', 1]:.0%}; 3rd-class men at {cross.loc['male', 3]:.0%}.",
        "Families of 2–4 survived better than singles or very large families — a non-linear effect.",
        "Fare correlates positively with survival (+0.26), mostly as a proxy for class.",
    ]


def build_payload(raw: pd.DataFrame, cleaned: pd.DataFrame) -> dict:
    charts = visualize.generate_all(cleaned)
    return {
        "dataset": build_dataset_section(raw, cleaned),
        "metrics": analyze.headline_metrics(cleaned),
        "tables": build_tables(cleaned),
        "key_findings": build_key_findings(cleaned),
        "charts": charts,
        "pipeline_sections": PIPELINE_SECTIONS,
    }


if __name__ == "__main__":
    raw = load_titanic()
    cleaned = pd.read_csv(PROCESSED_CSV_PATH) if PROCESSED_CSV_PATH.exists() else clean(raw)

    payload = build_payload(raw, cleaned)

    INSIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    INSIGHTS_PATH.write_text(json.dumps(payload, indent=2))

    rel = INSIGHTS_PATH.relative_to(Path.cwd())
    size_kb = INSIGHTS_PATH.stat().st_size / 1024
    print(f"Wrote {rel}  ({size_kb:.1f} KB)")
    print(f"  • {len(payload['metrics'])} headline metrics")
    print(f"  • {len(payload['tables'])} tables")
    print(f"  • {len(payload['key_findings'])} key findings")
    print(f"  • {len(payload['charts'])} charts")
    total_steps = sum(len(s["steps"]) for s in payload["pipeline_sections"])
    print(f"  • {len(payload['pipeline_sections'])} pipeline sections ({total_steps} steps)")
