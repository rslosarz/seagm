#!/usr/bin/env python3
"""
Recompute Clarity + diary merge and compare to the enriched workbook on disk.

Exits 0 if At Sea / At Work / Glucose Issue match row-by-row; otherwise prints
mismatches and exits 1.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import enrich_clarity as ec  # noqa: E402
from diary_load import load_clean_diary  # noqa: E402
from input_resolve import find_unique_by_prefix, find_unique_clarity_raw  # noqa: E402
from term import Term, print_run_footer, print_run_header, use_color  # noqa: E402

DIARY_PREFIX = "SEAGM"


def _norm_cell(x) -> str:
    if x is None:
        return ""
    if isinstance(x, float) and pd.isna(x):
        return ""
    s = str(x).strip()
    if s.lower() == "nan":
        return ""
    return s


def _norm_diary_value(col: str, x) -> str:
    """Match enrich output semantics: bools and 0/1 as TRUE/FALSE; strings uppercased for sea/work."""
    if col in ("At Sea", "At Work"):
        if isinstance(x, (bool, np.bool_)):
            return "TRUE" if x else "FALSE"
        if isinstance(x, (int, np.integer)):
            if x == 1:
                return "TRUE"
            if x == 0:
                return "FALSE"
        if isinstance(x, (float, np.floating)) and not pd.isna(x):
            if x == 1.0:
                return "TRUE"
            if x == 0.0:
                return "FALSE"
        u = _norm_cell(x).upper()
        if u in ("TRUE", "FALSE"):
            return u
        return _norm_cell(x)
    return _norm_cell(x)


@dataclass
class VerifyOutcome:
    exit_code: int
    total_rows: int = 0
    ok_rows: int = 0
    bad_rows: int = 0
    row_count_mismatch: bool = False
    mismatch_lines: list[str] = field(default_factory=list)


def verify(
    *,
    diary_path: Path,
    clarity_raw_path: Path,
    enriched_path: Path,
    max_report: int,
    term: Term,
    show_progress: bool,
) -> VerifyOutcome:
    def say(msg: str = "") -> None:
        print(msg)

    print_run_header(term, "Clarity × diary enrich verify")
    say(f"  {term.dim('Diary:')}     {diary_path.name}")
    say(f"  {term.dim('Clarity:')}   {clarity_raw_path.name}")
    say(f"  {term.dim('Enriched:')}  {enriched_path.name}")
    say()

    say(term.dim("  Recomputing merge from diary + raw Clarity…"))
    diary = load_clean_diary(str(diary_path))
    clarity = pd.read_excel(clarity_raw_path, engine="openpyxl")
    for c in ec.DIARY_COLS:
        if c not in clarity.columns:
            clarity[c] = ""

    expected = ec.enrich_clarity(clarity, diary)
    say(term.dim("  Loading enriched workbook…"))
    actual = pd.read_excel(enriched_path, engine="openpyxl")

    if len(expected) != len(actual):
        say()
        say(term.red(term.bold("  ✗ FAILED")))
        say(
            term.red(
                f"  Row count mismatch: expected {len(expected)} (raw Clarity), "
                f"got {len(actual)} in enriched file."
            )
        )
        print_run_footer(term)
        return VerifyOutcome(exit_code=1, row_count_mismatch=True)

    total = len(expected)
    bad_rows = 0
    lines_printed = 0
    mismatch_lines: list[str] = []
    last_pct = -1

    for i in range(total):
        row_issues: list[tuple[str, str, str]] = []
        for col in ec.DIARY_COLS:
            e = _norm_diary_value(col, expected.iloc[i][col])
            a = _norm_diary_value(col, actual.iloc[i][col])
            if e != a:
                row_issues.append((col, e, a))
        if row_issues:
            bad_rows += 1
            ts = expected.iloc[i].get(ec.CLARITY_TS_COL, "")
            for col, e, a in row_issues:
                if lines_printed < max_report:
                    mismatch_lines.append(
                        f"  row {i} ts={ts!r} {col!r}: expected {e!r}, file has {a!r}"
                    )
                    lines_printed += 1

        # Progress only on a real TTY so logs (make, pipes) stay short.
        if show_progress and total >= 50 and sys.stdout.isatty():
            pct = 100 * (i + 1) // total
            if pct != last_pct:
                bar_w = 24
                filled = int(bar_w * (i + 1) / total)
                bar = "█" * filled + "░" * (bar_w - filled)
                if term.enabled:
                    msg = f"\r  {term.cyan('Comparing')}{term.dim('…')} [{bar}] {pct:>3}%"
                else:
                    msg = f"\r  Comparing... [{bar}] {pct:>3}%"
                print(msg, end="", flush=True)
                last_pct = pct

    if show_progress and total >= 50 and sys.stdout.isatty():
        print()

    ok_rows = total - bad_rows
    pct_ok = (100.0 * ok_rows / total) if total else 100.0

    say()
    say(f"  {term.dim('Rows checked:')}  {total:,}")
    ok_part = term.green(f"{ok_rows:,} ok") if bad_rows == 0 else f"{ok_rows:,} ok"
    fail_part = term.red(f"{bad_rows:,} failed") if bad_rows else term.dim("0 failed")
    say(f"  {term.dim('Match rate:')}   {pct_ok:>6.2f}%  ({ok_part}, {fail_part})")
    say()

    if bad_rows:
        say(term.yellow(term.bold(f"  Sample mismatches (up to {max_report} lines):")))
        for ln in mismatch_lines:
            say(term.red(ln))
        if lines_printed >= max_report:
            say(term.dim(f"  … (stopped after {max_report} lines; more may exist)"))
        say()
        say(term.red(term.bold("  ✗ FAILED")))
        print_run_footer(term)
        return VerifyOutcome(
            exit_code=1,
            total_rows=total,
            ok_rows=ok_rows,
            bad_rows=bad_rows,
            mismatch_lines=mismatch_lines,
        )

    say(term.green(term.bold("  ✓ PASSED")))
    say(term.green(f"  Enriched file matches recomputed diary merge ({total:,} rows)."))
    print_run_footer(term)
    return VerifyOutcome(exit_code=0, total_rows=total, ok_rows=ok_rows, bad_rows=0)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-dir", default="input", help="Diary + raw Clarity (default: input)")
    p.add_argument("--output-dir", default="output", help="Enriched workbook (default: output)")
    p.add_argument("--diary", "-d", default=None, help="Diary .xlsx (default: discover SEAGM*)")
    p.add_argument("--clarity", "-c", default=None, help="Raw Clarity .xlsx (default: Clarity_Export*, not *_diary)")
    p.add_argument("--enriched", "-e", default=None, help="Enriched .xlsx (default: <clarity_stem>_diary.xlsx in output-dir)")
    p.add_argument(
        "--max-report",
        type=int,
        default=30,
        metavar="N",
        help="Max mismatch lines to print (default: 30)",
    )
    p.add_argument("--no-color", action="store_true", help="Disable ANSI colors")
    p.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable the comparing progress bar",
    )
    args = p.parse_args()

    term = Term(use_color(no_color_flag=args.no_color))

    diary_path = (
        Path(args.diary)
        if args.diary is not None
        else find_unique_by_prefix(args.input_dir, DIARY_PREFIX, label="Diary")
    )
    clarity_raw_path = (
        Path(args.clarity)
        if args.clarity is not None
        else find_unique_clarity_raw(args.input_dir)
    )

    if args.enriched is not None:
        enriched_path = Path(args.enriched)
    else:
        enriched_path = Path(args.output_dir) / f"{clarity_raw_path.stem}_diary{clarity_raw_path.suffix}"

    if not enriched_path.is_file():
        print(term.red(f"Enriched file not found: {enriched_path}"), file=sys.stderr)
        return 2

    outcome = verify(
        diary_path=diary_path,
        clarity_raw_path=clarity_raw_path,
        enriched_path=enriched_path,
        max_report=args.max_report,
        term=term,
        show_progress=not args.no_progress,
    )
    return outcome.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
