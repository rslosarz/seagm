#!/usr/bin/env python3
"""Fill At Sea / At Work / Glucose Issue on Clarity export using diary timestamps (merge_asof backward)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from diary_load import TIMESTAMP_COL, load_clean_diary  # noqa: E402

CLARITY_TS_COL = TIMESTAMP_COL
DIARY_COLS = ["At Sea", "At Work", "Glucose Issue"]


def _bool_diary_format(s: pd.Series) -> pd.Series:
    """Diary bools -> TRUE/FALSE strings."""

    def one(x):
        if pd.isna(x):
            return ""
        if x is True:
            return "TRUE"
        if x is False:
            return "FALSE"
        return str(x)

    return s.map(one)


def _require_excel_out(path: str, label: str) -> None:
    suf = Path(path).suffix.lower()
    if suf not in (".xlsx", ".xlsm"):
        raise ValueError(f"{label} must be .xlsx or .xlsm, got {path!r}")


def enrich_clarity(clarity: pd.DataFrame, diary: pd.DataFrame) -> pd.DataFrame:
    """merge_asof backward; diary columns renamed to avoid _x/_y clashes."""
    out = clarity.copy()
    for c in DIARY_COLS:
        if c not in out.columns:
            out[c] = ""
        out[c] = out[c].astype(object).where(out[c].notna(), "")

    d = diary.rename(
        columns={
            "ts": "_diary_ts",
            "At Sea": "_d_sea",
            "At Work": "_d_work",
            "Glucose Issue": "_d_issue",
        }
    ).copy()
    d["_d_sea"] = _bool_diary_format(d["_d_sea"])
    d["_d_work"] = _bool_diary_format(d["_d_work"])
    d["_d_issue"] = d["_d_issue"].astype(str)

    out["_row_order"] = range(len(out))
    out["_merge_ts"] = pd.to_datetime(out[CLARITY_TS_COL], errors="coerce")

    sorted_df = out.sort_values("_merge_ts", na_position="last").copy()
    sorted_df["_diary_ts"] = pd.NaT
    sorted_df["_d_sea"] = ""
    sorted_df["_d_work"] = ""
    sorted_df["_d_issue"] = ""

    valid = sorted_df["_merge_ts"].notna()
    merge_exclude = {"_diary_ts", "_d_sea", "_d_work", "_d_issue"}
    if valid.any():
        left_cols = [c for c in sorted_df.columns if c not in merge_exclude]
        sub = sorted_df.loc[valid, left_cols]
        m = pd.merge_asof(
            sub,
            d,
            left_on="_merge_ts",
            right_on="_diary_ts",
            direction="backward",
        )
        sorted_df.loc[valid, "_diary_ts"] = m["_diary_ts"].values
        sorted_df.loc[valid, "_d_sea"] = m["_d_sea"].values
        sorted_df.loc[valid, "_d_work"] = m["_d_work"].values
        sorted_df.loc[valid, "_d_issue"] = m["_d_issue"].values

    merged = sorted_df.sort_values("_row_order")

    for c in DIARY_COLS:
        if c not in merged.columns:
            merged[c] = ""

    has_match = merged["_merge_ts"].notna() & merged["_diary_ts"].notna()
    merged.loc[has_match, "At Sea"] = merged.loc[has_match, "_d_sea"].values
    merged.loc[has_match, "At Work"] = merged.loc[has_match, "_d_work"].values
    merged.loc[has_match, "Glucose Issue"] = merged.loc[has_match, "_d_issue"].values

    drop_cols = [
        "_row_order",
        "_merge_ts",
        "_diary_ts",
        "_d_sea",
        "_d_work",
        "_d_issue",
    ]
    merged = merged.drop(columns=[c for c in drop_cols if c in merged.columns])
    return merged


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--diary", "-d", required=True, help="Diary .xlsx path")
    p.add_argument("--clarity", "-c", required=True, help="Clarity export .xlsx path")
    p.add_argument("--output", "-o", required=True, help="Output .xlsx path")
    args = p.parse_args()

    _require_excel_out(args.diary, "Diary")
    _require_excel_out(args.clarity, "Clarity")
    _require_excel_out(args.output, "Output")

    diary = load_clean_diary(args.diary)
    clarity = pd.read_excel(args.clarity, engine="openpyxl")

    if CLARITY_TS_COL not in clarity.columns:
        raise KeyError(
            f"Clarity file missing {CLARITY_TS_COL!r}; columns: {list(clarity.columns)}"
        )
    for c in DIARY_COLS:
        if c not in clarity.columns:
            clarity[c] = ""

    first_clarity = pd.to_datetime(clarity[CLARITY_TS_COL], errors="coerce").min()
    first_diary = diary["ts"].min()
    if pd.notna(first_clarity) and first_clarity < first_diary:
        print(
            f"Warning: first Clarity timestamp {first_clarity} is before first diary {first_diary}; "
            "those rows will have empty diary columns.",
            file=sys.stderr,
        )

    enriched = enrich_clarity(clarity, diary)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    enriched.to_excel(out_path, index=False, engine="openpyxl")


if __name__ == "__main__":
    main()
