#!/usr/bin/env python3
"""Build diary_intervals.xlsx from SEAGM diary: row-by-row intervals for sea, work, glucose issues."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from diary_load import load_clean_diary  # noqa: E402
from input_resolve import find_unique_by_prefix  # noqa: E402
from term import Term, print_run_footer, print_run_header, use_color  # noqa: E402

DIARY_PREFIX = "SEAGM"


def _bool_to_diary_str(b: bool) -> str:
    return "TRUE" if b else "FALSE"


def _glucose_issue_key(raw: str) -> str | None:
    s = str(raw).strip()
    if not s or s.lower() == "none":
        return None
    return s.lower()


def build_intervals(diary: pd.DataFrame, *, gap: pd.Timedelta) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Single forward pass. Close interval ends at prev.ts on value change; if curr.ts - prev.ts > gap,
    close all open intervals at prev.ts and reopen from curr row.
    """
    if diary.empty:
        empty_sea = pd.DataFrame(columns=["start", "end", "at_sea"])
        empty_work = pd.DataFrame(columns=["start", "end", "at_work"])
        empty_iss = pd.DataFrame(columns=["start", "end", "issue"])
        return empty_sea, empty_work, empty_iss

    sea_rows: list[tuple[pd.Timestamp, pd.Timestamp, str]] = []
    work_rows: list[tuple[pd.Timestamp, pd.Timestamp, str]] = []
    issue_rows: list[tuple[pd.Timestamp, pd.Timestamp, str]] = []

    t0 = diary["ts"].iloc[0]
    sea_start, sea_val = t0, diary["At Sea"].iloc[0]
    work_start, work_val = t0, diary["At Work"].iloc[0]
    g0 = _glucose_issue_key(diary["Glucose Issue"].iloc[0])
    if g0 is None:
        issue_start: pd.Timestamp | None = None
        issue_label: str | None = None
    else:
        issue_start = t0
        issue_label = str(diary["Glucose Issue"].iloc[0]).strip()

    def close_sea(end: pd.Timestamp) -> None:
        sea_rows.append((sea_start, end, _bool_to_diary_str(sea_val)))

    def close_work(end: pd.Timestamp) -> None:
        work_rows.append((work_start, end, _bool_to_diary_str(work_val)))

    def close_issue(end: pd.Timestamp) -> None:
        nonlocal issue_start, issue_label
        if issue_start is not None and issue_label is not None:
            issue_rows.append((issue_start, end, issue_label))
            issue_start, issue_label = None, None

    def open_from_row(ts: pd.Timestamp, row: pd.Series) -> None:
        nonlocal sea_start, sea_val, work_start, work_val, issue_start, issue_label
        sea_start, sea_val = ts, row["At Sea"]
        work_start, work_val = ts, row["At Work"]
        g = _glucose_issue_key(row["Glucose Issue"])
        if g is None:
            issue_start, issue_label = None, None
        else:
            issue_start = ts
            issue_label = str(row["Glucose Issue"]).strip()

    for i in range(1, len(diary)):
        prev = diary.iloc[i - 1]
        curr = diary.iloc[i]
        prev_ts = prev["ts"]
        curr_ts = curr["ts"]
        step = curr_ts - prev_ts
        big_gap = step > gap

        if big_gap:
            close_sea(prev_ts)
            close_work(prev_ts)
            close_issue(prev_ts)
            open_from_row(curr_ts, curr)
            continue

        if curr["At Sea"] != sea_val:
            close_sea(prev_ts)
            sea_start, sea_val = curr_ts, curr["At Sea"]

        if curr["At Work"] != work_val:
            close_work(prev_ts)
            work_start, work_val = curr_ts, curr["At Work"]

        prev_g = _glucose_issue_key(prev["Glucose Issue"])
        curr_g = _glucose_issue_key(curr["Glucose Issue"])
        if curr_g != prev_g:
            close_issue(prev_ts)
            if curr_g is not None:
                issue_start = curr_ts
                issue_label = str(curr["Glucose Issue"]).strip()

    last_ts = diary["ts"].iloc[-1]
    close_sea(last_ts)
    close_work(last_ts)
    close_issue(last_ts)

    sea_df = pd.DataFrame(sea_rows, columns=["start", "end", "at_sea"])
    work_df = pd.DataFrame(work_rows, columns=["start", "end", "at_work"])
    issue_df = pd.DataFrame(issue_rows, columns=["start", "end", "issue"])
    return sea_df, work_df, issue_df


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--input",
        "-i",
        default=None,
        help=f"Diary .xlsx path (default: sole file starting with {DIARY_PREFIX!r} under --input-dir)",
    )
    p.add_argument(
        "--input-dir",
        default="input",
        help="Directory to search when -i is omitted (default: input)",
    )
    p.add_argument(
        "--output",
        "-o",
        required=True,
        help="Output workbook path (three sheets: at_sea, at_work, glucose_issues)",
    )
    p.add_argument(
        "--gap-hours",
        type=float,
        default=1.0,
        metavar="H",
        help="If consecutive diary rows differ by more than H hours, close all intervals at the earlier row (default: 1.0)",
    )
    p.add_argument("--no-color", action="store_true", help="Disable ANSI colors")
    args = p.parse_args()

    term = Term(use_color(no_color_flag=args.no_color))

    diary_path = (
        Path(args.input)
        if args.input is not None
        else find_unique_by_prefix(args.input_dir, DIARY_PREFIX, label="Diary")
    )
    out_path = Path(args.output)

    print_run_header(term, "Diary intervals (condense)")
    print(f"  {term.dim('Diary:')}     {diary_path.name}")
    print(f"  {term.dim('Output:')}    {out_path.name}")
    print(f"  {term.dim('Gap rule:')}  close all intervals if step exceeds {args.gap_hours:g} h")
    print()

    print(term.dim("  Loading & cleaning diary…"))
    gap = pd.Timedelta(hours=args.gap_hours)
    diary = load_clean_diary(str(diary_path))
    print(term.dim("  Building sea / work / glucose interval tables…"))
    sea, work, issues = build_intervals(diary, gap=gap)
    print(term.dim("  Writing workbook (3 sheets)…"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        sea.to_excel(writer, sheet_name="at_sea", index=False)
        work.to_excel(writer, sheet_name="at_work", index=False)
        issues.to_excel(writer, sheet_name="glucose_issues", index=False)

    print()
    print(f"  {term.dim('Diary rows:')}     {len(diary):,}")
    print(
        f"  {term.dim('Intervals:')}     "
        f"at_sea={len(sea):,}, at_work={len(work):,}, glucose_issues={len(issues):,}"
    )
    print()
    print(term.green(term.bold("  ✓ DONE")))
    print(term.green(f"  Wrote {out_path.name}"))
    print_run_footer(term)


if __name__ == "__main__":
    main()
