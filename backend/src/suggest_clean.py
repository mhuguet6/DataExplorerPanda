"""
Cleaning-suggestion engine for arbitrary user-uploaded CSVs.

Given a DataFrame, returns a list of suggested cleaning steps. Each suggestion
is a dict the API can serialize to JSON and the frontend can display, accept
or reject. The same step schema is used for user-proposed custom steps so the
applier in `api.py` does not need to special-case suggestions vs custom.

Step schema:
    {
        "id": "<unique step id>",          # only present on suggestions
        "action": "<verb>",                # e.g. "impute_median"
        "column": "<col>" | None,
        "value": <any> | None,
        "reason": "<human-readable why>"
    }

Supported actions:
    drop_column           — remove a column entirely
    drop_duplicates       — remove duplicate rows
    impute_median         — numeric column: fill NaN with median
    impute_mean           — numeric column: fill NaN with mean
    impute_mode           — any column: fill NaN with most common value
    impute_value          — any column: fill NaN with provided `value`
    strip_whitespace      — string column: strip leading/trailing whitespace
    parse_dates           — string column: convert to datetime via pd.to_datetime
    filter_outliers_iqr   — numeric column: drop rows outside 1.5*IQR
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

HIGH_NULL_FRACTION = 0.70
IQR_MULTIPLIER = 1.5
DATE_PARSE_SAMPLE = 50
DATE_PARSE_THRESHOLD = 0.90


# ---------------------------------------------------------------------------
# Suggestion generation
# ---------------------------------------------------------------------------

def suggest(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Inspect `df` and produce an ordered list of cleaning suggestions."""
    suggestions: list[dict[str, Any]] = []
    n_rows = len(df)
    if n_rows == 0:
        return suggestions

    # Duplicates — check once, dataset-level
    dup_count = int(df.duplicated().sum())
    if dup_count > 0:
        suggestions.append({
            "action": "drop_duplicates",
            "column": None,
            "value": None,
            "reason": f"{dup_count} duplicate row(s) detected.",
        })

    for col in df.columns:
        s = df[col]
        null_count = int(s.isna().sum())
        null_frac = null_count / n_rows
        nunique = int(s.nunique(dropna=True))

        # Column-level: drop if mostly null or constant
        if null_frac >= HIGH_NULL_FRACTION:
            suggestions.append({
                "action": "drop_column",
                "column": col,
                "value": None,
                "reason": f"{null_frac:.0%} of values are missing.",
            })
            continue  # other suggestions on a doomed column are noise

        if nunique <= 1 and n_rows > 1:
            suggestions.append({
                "action": "drop_column",
                "column": col,
                "value": None,
                "reason": "Column has a single unique value (no signal).",
            })
            continue

        # Imputation
        if null_count > 0:
            if pd.api.types.is_numeric_dtype(s):
                median = s.median()
                suggestions.append({
                    "action": "impute_median",
                    "column": col,
                    "value": None,
                    "reason": (
                        f"{null_count} missing value(s); fill with median "
                        f"({median:.4g})."
                    ),
                })
            else:
                mode_vals = s.mode(dropna=True)
                mode_repr = repr(mode_vals.iloc[0]) if not mode_vals.empty else "<none>"
                suggestions.append({
                    "action": "impute_mode",
                    "column": col,
                    "value": None,
                    "reason": (
                        f"{null_count} missing value(s); fill with mode "
                        f"({mode_repr})."
                    ),
                })

        # String-only checks
        if pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s):
            non_null = s.dropna().astype(str)
            if not non_null.empty:
                stripped = non_null.str.strip()
                if (stripped != non_null).any():
                    suggestions.append({
                        "action": "strip_whitespace",
                        "column": col,
                        "value": None,
                        "reason": "Leading/trailing whitespace detected.",
                    })

                if _looks_like_dates(non_null):
                    suggestions.append({
                        "action": "parse_dates",
                        "column": col,
                        "value": None,
                        "reason": "Values look like dates; convert to datetime.",
                    })

        # Numeric outliers — only flag when count is meaningful
        if pd.api.types.is_numeric_dtype(s) and nunique > 4:
            lower, upper, outlier_count = _iqr_bounds(s)
            if outlier_count > 0:
                suggestions.append({
                    "action": "filter_outliers_iqr",
                    "column": col,
                    "value": None,
                    "reason": (
                        f"{outlier_count} value(s) outside "
                        f"[{lower:.4g}, {upper:.4g}] (1.5·IQR)."
                    ),
                })

    # Assign stable ids so the frontend can toggle them
    for i, step in enumerate(suggestions):
        step["id"] = f"s{i:02d}"
    return suggestions


# ---------------------------------------------------------------------------
# Step application
# ---------------------------------------------------------------------------

def apply_steps(
    df: pd.DataFrame, steps: list[dict[str, Any]]
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """
    Apply a list of steps in order, returning (cleaned_df, log).

    `log` records what actually happened for each step — rows affected, success,
    or skip reason. Steps that fail (e.g. column dropped twice) are skipped
    with a note rather than raising, so a bad custom step does not blow up
    the whole run.
    """
    out = df.copy()
    log: list[dict[str, Any]] = []

    for step in steps:
        action = step.get("action")
        column = step.get("column")
        value = step.get("value")
        entry: dict[str, Any] = {"action": action, "column": column}

        try:
            if action == "drop_column":
                if column not in out.columns:
                    entry["status"] = "skipped"
                    entry["detail"] = "column not present"
                else:
                    out = out.drop(columns=[column])
                    entry["status"] = "ok"
                    entry["detail"] = f"dropped column '{column}'"

            elif action == "drop_duplicates":
                before = len(out)
                out = out.drop_duplicates().reset_index(drop=True)
                entry["status"] = "ok"
                entry["detail"] = f"removed {before - len(out)} duplicate row(s)"

            elif action in {"impute_median", "impute_mean", "impute_mode", "impute_value"}:
                if column not in out.columns:
                    entry["status"] = "skipped"
                    entry["detail"] = "column not present"
                else:
                    n_before = int(out[column].isna().sum())
                    fill = _resolve_fill(out[column], action, value)
                    if fill is None:
                        entry["status"] = "skipped"
                        entry["detail"] = "no fill value available"
                    else:
                        out[column] = out[column].fillna(fill)
                        entry["status"] = "ok"
                        entry["detail"] = (
                            f"filled {n_before} NaN(s) in '{column}' with {fill!r}"
                        )

            elif action == "strip_whitespace":
                if column not in out.columns:
                    entry["status"] = "skipped"
                    entry["detail"] = "column not present"
                else:
                    out[column] = out[column].astype(str).str.strip()
                    entry["status"] = "ok"
                    entry["detail"] = f"stripped whitespace in '{column}'"

            elif action == "parse_dates":
                if column not in out.columns:
                    entry["status"] = "skipped"
                    entry["detail"] = "column not present"
                else:
                    parsed = pd.to_datetime(out[column], errors="coerce")
                    n_failed = int(parsed.isna().sum() - out[column].isna().sum())
                    out[column] = parsed
                    entry["status"] = "ok"
                    entry["detail"] = (
                        f"parsed '{column}' as datetime"
                        + (f"; {n_failed} value(s) became NaT" if n_failed > 0 else "")
                    )

            elif action == "filter_outliers_iqr":
                if column not in out.columns or not pd.api.types.is_numeric_dtype(out[column]):
                    entry["status"] = "skipped"
                    entry["detail"] = "column not numeric or missing"
                else:
                    lower, upper, _ = _iqr_bounds(out[column])
                    before = len(out)
                    mask = out[column].between(lower, upper) | out[column].isna()
                    out = out[mask].reset_index(drop=True)
                    entry["status"] = "ok"
                    entry["detail"] = (
                        f"dropped {before - len(out)} outlier row(s) in '{column}'"
                    )

            else:
                entry["status"] = "skipped"
                entry["detail"] = f"unknown action '{action}'"

        except Exception as exc:  # pragma: no cover — log instead of crash
            entry["status"] = "error"
            entry["detail"] = f"{type(exc).__name__}: {exc}"

        log.append(entry)

    return out, log


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iqr_bounds(s: pd.Series) -> tuple[float, float, int]:
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - IQR_MULTIPLIER * iqr
    upper = q3 + IQR_MULTIPLIER * iqr
    outliers = int(((s < lower) | (s > upper)).sum())
    return float(lower), float(upper), outliers


def _looks_like_dates(non_null: pd.Series) -> bool:
    sample = non_null.head(DATE_PARSE_SAMPLE)
    parsed = pd.to_datetime(sample, errors="coerce")
    return parsed.notna().mean() >= DATE_PARSE_THRESHOLD


def _resolve_fill(s: pd.Series, action: str, value: Any) -> Any:
    if action == "impute_value":
        return value
    if action == "impute_median" and pd.api.types.is_numeric_dtype(s):
        return float(s.median()) if s.notna().any() else None
    if action == "impute_mean" and pd.api.types.is_numeric_dtype(s):
        return float(s.mean()) if s.notna().any() else None
    if action == "impute_mode":
        modes = s.mode(dropna=True)
        return modes.iloc[0] if not modes.empty else None
    return None
