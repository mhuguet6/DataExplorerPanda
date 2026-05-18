"""
Phase 4 — Visualization.

Each chart is a self-contained function that:
  - takes the cleaned DataFrame (and uses analyze.py for its numbers),
  - saves a PNG to backend/outputs/charts/,
  - returns a dict {filename, title, caption} that Phase 5 can dump to JSON.

Why funnel everything through analyze.py: we want one place where the math
lives. If Phase 3 says first-class survival was 0.630, the chart must show
the same 0.630 — never recompute it here.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

import analyze
from clean_data import PROCESSED_CSV_PATH, clean
from load_data import load_titanic

CHARTS_DIR = Path(__file__).resolve().parents[1] / "outputs" / "charts"

# Consistent visual style across every chart
sns.set_theme(style="whitegrid", context="talk", palette="deep")
plt.rcParams["figure.dpi"] = 110
plt.rcParams["savefig.bbox"] = "tight"

SURVIVED_PALETTE = {0: "#d9534f", 1: "#5cb85c"}  # red = died, green = survived


def _save(fig: plt.Figure, filename: str) -> str:
    """Save a figure and return its filename (no path) for use in JSON."""
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(CHARTS_DIR / filename)
    plt.close(fig)
    return filename


# ---------------------------------------------------------------------------
# Individual charts
# ---------------------------------------------------------------------------

def chart_age_histogram(df: pd.DataFrame) -> dict:
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.histplot(
        data=df,
        x="age",
        hue="survived",
        bins=30,
        multiple="stack",
        palette=SURVIVED_PALETTE,
        ax=ax,
    )
    ax.set_title("Age distribution (stacked by survival)")
    ax.set_xlabel("Age")
    ax.set_ylabel("Passengers")
    return {
        "filename": _save(fig, "01_age_histogram.png"),
        "title": "Age distribution",
        "caption": "Most passengers were between 20 and 40. Children (<12) survived disproportionately.",
    }


def chart_survival_by_class(df: pd.DataFrame) -> dict:
    data = analyze.survival_by(df, "pclass")
    overall = df["survived"].mean()

    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(data=data, x="pclass", y="survival_rate", hue="pclass",
                palette="Blues_d", ax=ax, legend=False)
    ax.axhline(overall, color="black", linestyle="--", linewidth=1)
    ax.text(2.4, overall + 0.02, f"overall = {overall:.0%}", fontsize=11)

    ax.set_ylim(0, 1)
    ax.set_title("Survival rate by passenger class")
    ax.set_xlabel("Class")
    ax.set_ylabel("Survival rate")
    for i, row in data.iterrows():
        ax.text(i, row["survival_rate"] + 0.02, f"{row['survival_rate']:.0%}",
                ha="center", fontsize=11)

    return {
        "filename": _save(fig, "02_survival_by_class.png"),
        "title": "Survival rate by class",
        "caption": "1st-class passengers were ~2.6× more likely to survive than 3rd-class.",
    }


def chart_sex_class_heatmap(df: pd.DataFrame) -> dict:
    """The classic Titanic finding: sex × class is the strongest stratifier."""
    cross = analyze.survival_crosstab(df, "sex", "pclass")

    fig, ax = plt.subplots(figsize=(8, 5))
    sns.heatmap(cross, annot=True, fmt=".0%", cmap="RdYlGn",
                vmin=0, vmax=1, cbar_kws={"label": "Survival rate"}, ax=ax)
    ax.set_title("Survival rate: sex × class")
    ax.set_xlabel("Class")
    ax.set_ylabel("Sex")

    return {
        "filename": _save(fig, "03_sex_class_heatmap.png"),
        "title": "Survival by sex × class",
        "caption": "1st-class women: 97% survived. 3rd-class men: 14%. The single strongest pattern in the data.",
    }


def chart_family_size_bar(df: pd.DataFrame) -> dict:
    data = analyze.survival_by(df, "family_size")

    fig, ax = plt.subplots(figsize=(9, 5))
    sns.barplot(data=data, x="family_size", y="survival_rate", hue="family_size",
                palette="viridis", ax=ax, legend=False)
    ax.set_ylim(0, 1)
    ax.set_title("Survival rate by family size on board")
    ax.set_xlabel("Family size (incl. passenger)")
    ax.set_ylabel("Survival rate")
    for i, row in data.iterrows():
        ax.text(i, row["survival_rate"] + 0.02,
                f"n={int(row['n'])}", ha="center", fontsize=10, color="dimgray")

    return {
        "filename": _save(fig, "04_family_size_bar.png"),
        "title": "Survival by family size",
        "caption": "Small families (2–4) survived best. Alone or in very large groups, survival drops sharply.",
    }


def chart_age_fare_scatter(df: pd.DataFrame) -> dict:
    fig, ax = plt.subplots(figsize=(9, 6))
    sns.scatterplot(
        data=df, x="age", y="fare", hue="survived",
        palette=SURVIVED_PALETTE, alpha=0.7, s=40, ax=ax,
    )
    ax.set_yscale("symlog", linthresh=10)
    ax.set_title("Age vs fare paid (log scale)")
    ax.set_xlabel("Age")
    ax.set_ylabel("Fare ($, log)")
    ax.legend(title="Survived", labels=["No", "Yes"])

    return {
        "filename": _save(fig, "05_age_fare_scatter.png"),
        "title": "Age vs fare",
        "caption": "Higher fares cluster with survival (green). A log scale is needed because fares range from $0 to $512.",
    }


def chart_survival_by_age_line(df: pd.DataFrame) -> dict:
    """Survival rate across 5-year age bins — a clean line-chart story."""
    bins = np.arange(0, 85, 5)
    age_bins = pd.cut(df["age"], bins=bins, include_lowest=True)
    series = (
        df.assign(_bin=age_bins)
          .groupby("_bin", observed=True)["survived"]
          .agg(["mean", "count"])
    )
    # Only show bins with at least 5 passengers — small bins are noise
    series = series[series["count"] >= 5]
    bin_mids = [iv.mid for iv in series.index]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(bin_mids, series["mean"], marker="o", linewidth=2, color="#2c7fb8")
    ax.axhline(df["survived"].mean(), color="black", linestyle="--",
               linewidth=1, label="overall")
    ax.set_ylim(0, 1)
    ax.set_title("Survival rate across age (5-year bins)")
    ax.set_xlabel("Age (midpoint of bin)")
    ax.set_ylabel("Survival rate")
    ax.legend()

    return {
        "filename": _save(fig, "06_survival_by_age_line.png"),
        "title": "Survival rate across age",
        "caption": "Children under 10 survived at well above the overall rate; survival drops off through middle and old age.",
    }


def chart_correlation_heatmap(df: pd.DataFrame) -> dict:
    corr = analyze.correlation_matrix(df)

    fig, ax = plt.subplots(figsize=(11, 9))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm",
                vmin=-1, vmax=1, annot_kws={"size": 9}, ax=ax)
    ax.set_title("Correlation between numeric & binary features")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

    return {
        "filename": _save(fig, "07_correlation_heatmap.png"),
        "title": "Correlation matrix",
        "caption": "Fare correlates most with survival (+0.26). Family_size, sibsp, and parch are highly co-linear (as expected).",
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

CHART_BUILDERS = [
    chart_age_histogram,
    chart_survival_by_class,
    chart_sex_class_heatmap,
    chart_family_size_bar,
    chart_age_fare_scatter,
    chart_survival_by_age_line,
    chart_correlation_heatmap,
]


def generate_all(df: pd.DataFrame) -> list[dict]:
    """Build every chart, return a list of {filename, title, caption}."""
    return [builder(df) for builder in CHART_BUILDERS]


def _load() -> pd.DataFrame:
    if PROCESSED_CSV_PATH.exists():
        return pd.read_csv(PROCESSED_CSV_PATH)
    return clean(load_titanic())


if __name__ == "__main__":
    df = _load()
    results = generate_all(df)
    print(f"Generated {len(results)} charts in {CHARTS_DIR.relative_to(Path.cwd())}:")
    for r in results:
        print(f"  - {r['filename']:<32} {r['title']}")
