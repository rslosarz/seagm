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
from input_resolve import find_unique_by_prefix  # noqa: E402
from term import Term, print_run_footer, print_run_header, use_color  # noqa: E402

DIARY_PREFIX = "SEAGM"
CLARITY_PREFIX = "Clarity_Export"

CLARITY_TS_COL = TIMESTAMP_COL
DIARY_COLS = ["At Sea", "At Work", "Glucose Issue"]
SHEET_ENRICHED = "enriched"
SHEET_AT_SEA = "At see"
SHEET_AT_SEA_AT_WORK = "At see at work"
SHEET_ON_LAND = "On land"
SHEET_SUMMARY = "summary"


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


def _to_bool_state(x) -> bool | None:
    if pd.isna(x):
        return None
    if isinstance(x, (bool, int)):
        return bool(x)
    if isinstance(x, float):
        if pd.isna(x):
            return None
        if x == 1.0:
            return True
        if x == 0.0:
            return False
    s = str(x).strip().upper()
    if s in ("TRUE", "YES", "1"):
        return True
    if s in ("FALSE", "NO", "0"):
        return False
    return None


def _bool_mask(s: pd.Series, state: bool) -> pd.Series:
    target = state
    return s.map(_to_bool_state).map(lambda v: v is target)


def build_filtered_sheets(enriched: pd.DataFrame) -> dict[str, pd.DataFrame]:
    at_sea_mask = _bool_mask(enriched["At Sea"], True)
    at_work_mask = _bool_mask(enriched["At Work"], True)
    on_land_mask = _bool_mask(enriched["At Sea"], False)

    at_sea = enriched.loc[at_sea_mask].copy()
    at_sea_at_work = enriched.loc[at_sea_mask & at_work_mask].copy()
    on_land = enriched.loc[on_land_mask].copy()

    return {
        SHEET_AT_SEA: at_sea,
        SHEET_AT_SEA_AT_WORK: at_sea_at_work,
        SHEET_ON_LAND: on_land,
    }


def build_summary_sheet(
    *,
    total: int,
    on_land: int,
    at_sea: int,
    at_sea_at_work: int,
) -> pd.DataFrame:
    rows = [[""] * 7 for _ in range(11)]
    rows[1][2] = "all"
    rows[1][3] = "on land"
    rows[1][4] = "at sea"
    rows[1][5] = "at sea on duty"

    rows[2][1] = "Data lines"
    rows[2][2] = str(total)
    rows[2][3] = str(on_land)
    rows[2][4] = str(at_sea)
    rows[2][5] = str(at_sea_at_work)

    rows[5][2] = "Data lines"
    rows[5][3] = "% of all"

    rows[6][1] = "all"
    rows[6][2] = str(total)
    rows[6][3] = "100"

    rows[7][1] = "on land"
    rows[7][2] = str(on_land)
    rows[7][3] = "=C8*100/C7"

    rows[8][1] = "at sea"
    rows[8][2] = str(at_sea)
    rows[8][3] = "=C9*100/C7"

    rows[9][1] = "at sea on duty"
    rows[9][2] = str(at_sea_at_work)
    rows[9][3] = "=C10*100/C7"

    return pd.DataFrame(rows)


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
    p.add_argument(
        "--diary",
        "-d",
        default=None,
        help=f"Diary .xlsx path (default: sole file starting with {DIARY_PREFIX!r} under --input-dir)",
    )
    p.add_argument(
        "--clarity",
        "-c",
        default=None,
        help=f"Clarity export .xlsx path (default: sole file starting with {CLARITY_PREFIX!r} under --input-dir)",
    )
    p.add_argument(
        "--input-dir",
        default="input",
        help="Directory to search when -d and/or -c is omitted (default: input)",
    )
    p.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output .xlsx path (if omitted, use --output-dir and name like <Clarity_stem>_diary.xlsx)",
    )
    p.add_argument(
        "--output-dir",
        default=None,
        help="Write <Clarity_filename_stem>_diary.xlsx here (required if -o is omitted)",
    )
    p.add_argument("--no-color", action="store_true", help="Disable ANSI colors")
    args = p.parse_args()

    term = Term(use_color(no_color_flag=args.no_color))

    diary_path = (
        Path(args.diary)
        if args.diary is not None
        else find_unique_by_prefix(args.input_dir, DIARY_PREFIX, label="Diary")
    )
    clarity_path = (
        Path(args.clarity)
        if args.clarity is not None
        else find_unique_by_prefix(args.input_dir, CLARITY_PREFIX, label="Clarity export")
    )

    _require_excel_out(str(diary_path), "Diary")
    _require_excel_out(str(clarity_path), "Clarity")

    if args.output is not None:
        out_path = Path(args.output)
    elif args.output_dir is not None:
        out_dir = Path(args.output_dir)
        suffix = clarity_path.suffix.lower()
        if suffix not in (".xlsx", ".xlsm"):
            suffix = ".xlsx"
        out_path = out_dir / f"{clarity_path.stem}_diary{suffix}"
    else:
        p.error("Provide either --output (-o) or --output-dir")

    _require_excel_out(str(out_path), "Output")

    print_run_header(term, "Clarity enrich (merge diary)")
    print(f"  {term.dim('Diary:')}     {diary_path.name}")
    print(f"  {term.dim('Clarity:')}   {clarity_path.name}")
    print(f"  {term.dim('Output:')}    {out_path.name}")
    print()

    print(term.dim("  Loading diary…"))
    diary = load_clean_diary(str(diary_path))
    print(term.dim("  Loading Clarity export…"))
    clarity = pd.read_excel(clarity_path, engine="openpyxl")

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
            term.yellow(
                f"  Warning: first Clarity timestamp {first_clarity} is before first diary {first_diary}; "
                "those rows will have empty diary columns."
            ),
            file=sys.stderr,
        )

    print(term.dim("  Merging (merge_asof backward on timestamps)…"))
    enriched = enrich_clarity(clarity, diary)
    filtered = build_filtered_sheets(enriched)
    summary_df = build_summary_sheet(
        total=len(enriched),
        on_land=len(filtered[SHEET_ON_LAND]),
        at_sea=len(filtered[SHEET_AT_SEA]),
        at_sea_at_work=len(filtered[SHEET_AT_SEA_AT_WORK]),
    )

    print(term.dim("  Writing enriched workbook (enriched + 4 extra sheets)…"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        enriched.to_excel(writer, sheet_name=SHEET_ENRICHED, index=False)
        filtered[SHEET_AT_SEA].to_excel(writer, sheet_name=SHEET_AT_SEA, index=False)
        filtered[SHEET_AT_SEA_AT_WORK].to_excel(
            writer, sheet_name=SHEET_AT_SEA_AT_WORK, index=False
        )
        filtered[SHEET_ON_LAND].to_excel(writer, sheet_name=SHEET_ON_LAND, index=False)
        summary_df.to_excel(writer, sheet_name=SHEET_SUMMARY, index=False, header=False)

    n = len(enriched)
    with_ts = pd.to_datetime(enriched[CLARITY_TS_COL], errors="coerce").notna().sum()
    print()
    print(f"  {term.dim('Output rows:')}   {n:,}  ({term.dim('with timestamp:')} {int(with_ts):,})")
    print(
        f"  {term.dim('Segments:')}      "
        f"at sea={len(filtered[SHEET_AT_SEA]):,}, "
        f"at sea+work={len(filtered[SHEET_AT_SEA_AT_WORK]):,}, "
        f"on land={len(filtered[SHEET_ON_LAND]):,}"
    )
    print()
    print(term.green(term.bold("  ✓ DONE")))
    print(term.green(f"  Wrote {out_path.name}"))
    print_run_footer(term)


if __name__ == "__main__":
    main()
