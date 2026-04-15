# Insulina — SEAGM diary + Dexcom Clarity (XLSX)

Tools to:

1. **Build `diary_intervals.xlsx`** from the study diary (5-minute rows → interval sheets for At Sea, At Work, and glucose-issue episodes).
2. **Enrich the Clarity workbook** by filling `At Sea`, `At Work`, and `Glucose Issue` on each row that has a CGM timestamp.

**Formats:** diary, Clarity input, and all script outputs are **`.xlsx`** (or `.xlsm`). There is no CSV path in these scripts.

## Requirements

- **Python** 3.10+ (`python3` on your `PATH`).
- **GNU Make** (optional; commands below work without it).

## Input layout

Place workbooks in **`input/`** (or set `INPUT_DIR` in Make / `--input-dir` on the CLI):

| Role | Filename rule |
|------|----------------|
| Study diary | Exactly **one** `.xlsx` / `.xlsm` whose name **starts with** `SEAGM` (case-insensitive). |
| Dexcom Clarity export | Exactly **one** `.xlsx` / `.xlsm` whose name **starts with** `Clarity_Export`. |

If more than one file matches a prefix, the script exits with an error listing matches — keep a single file per prefix or pass explicit paths (`-i`, `-d`, `-c`).

## Quick start

```bash
make setup    # one-time: .venv + pip install -r requirements.txt
# copy diary and Clarity .xlsx into input/
make run-all  # condense + enrich + verify (diary_intervals + enriched Clarity in output/)
```

Outputs under `output/`:

| Output | Path |
|--------|------|
| Interval workbook (sheets: `at_sea`, `at_work`, `glucose_issues`) | `output/diary_intervals.xlsx` |
| Clarity + diary workbook | `output/<Clarity_filename_stem>_diary.xlsx` (same base name as the Clarity input, plus `_diary` before the extension) |

## Interval rules (`condense_diary.py`)

Rows are read in **time order** (after the usual cleaning: valid timestamp, `Submitted == YES`, parseable `At Sea` / `At Work`).

- **At Sea / At Work:** start a new interval when the boolean **changes** from one row to the next. The previous interval **ends** at the **previous** row’s timestamp; the new one **starts** at the **current** row’s timestamp.
- **Glucose Issue:** `none` (case-insensitive) means no episode. A new episode starts when the label becomes non-`none`, and ends when it returns to `none` or the label **changes**. Ends use the **previous** row’s timestamp; starts use the **current** row’s (same pattern as sea/work).
- **Gap:** if `current_ts - previous_ts` is **greater than** `GAP_HOURS` (default **1.0** hour), **all** open intervals (sea, work, and any glucose episode) are **closed** at the previous timestamp, then new intervals are opened from the **current** row’s values.

The last row closes any still-open intervals at its timestamp.

Override the gap in Make: `make condense GAP_HOURS=2` or use `--gap-hours` on the script.

## Enrichment (`enrich_clarity.py`)

Enrichment uses the **diary workbook rows** (5-minute state) and `merge_asof` backward on timestamps — **not** the interval sheets. The interval file is a separate human-readable summary.

The enriched output workbook now contains 5 sheets:

- `enriched` (full enriched Clarity table),
- `At see` (`At Sea == TRUE`),
- `At see at work` (`At Sea == TRUE` and `At Work == TRUE`),
- `On land` (`At Sea == FALSE`),
- `summary` (aggregate layout matching `example.csv`, with `% of all` as Excel formulas).

Large Clarity files may be slow or memory-heavy when written with `to_excel`; that is expected for full exports.

## Makefile targets

| Target | Description |
|--------|-------------|
| `make help` | Summary of targets and defaults |
| `make setup` / `make install` | Create `.venv` and install dependencies |
| `make condense` | Run `scripts/condense_diary.py` |
| `make enrich` | Run `scripts/enrich_clarity.py` |
| `make verify` | Recompute enrich from `input/` and compare to `<Clarity_stem>_diary.xlsx` in `output/` |
| `make run-all` | `condense`, then `enrich`, then `verify` |
| `make clean-output` | Delete `output/` |

Variable **`INPUT_DIR`** (default `input`): where prefixed files are discovered. Example: `make run-all INPUT_DIR=/path/to/data`.

**Terminal output:** `condense`, `enrich`, and `verify` use the same style (banner, dim step lines, green **DONE** / **PASSED** or red **FAILED**). ANSI colors apply when stdout is a TTY; set `NO_COLOR=1` or pass `--no-color` on any script to disable. During verify, progress bars only run on a TTY (main row compare plus extra-sheet validation); use `--no-progress` to turn them off.

## Verify enriched Clarity (`verify_enrich.py`)

**`make verify`** loads the raw Clarity file and the SEAGM diary from `input/`, recomputes the same `merge_asof` merge as `enrich_clarity.py`, and checks all sheets in the enriched workbook (default: `<Clarity_stem>_diary.xlsx`). Use it after `make enrich`, or rely on **`make run-all`**, which ends with verify.

Expected sheets in the enriched workbook:

- `enriched` — full enriched Clarity table.
- `At see` — rows where `At Sea` is TRUE.
- `At see at work` — rows where both `At Sea` and `At Work` are TRUE.
- `On land` — rows where `At Sea` is FALSE.
- `summary` — aggregate layout matching the style from `example.csv`.

Exit codes: **`0`** — all checks match; **`1`** — mismatches (sample lines printed in the report, including extra sheets); **`2`** — enriched file missing (short error on stderr).

Override paths: `python scripts/verify_enrich.py -d diary.xlsx -c raw.xlsx -e out/enriched.xlsx`.

## Manual commands

Auto-pick from `input/`:

```bash
python scripts/condense_diary.py --input-dir input -o output/diary_intervals.xlsx --gap-hours 1

python scripts/enrich_clarity.py --input-dir input --output-dir output
# writes output/<Clarity_filename_stem>_diary.xlsx (see table above)
```

Explicit paths (optional):

```bash
python scripts/condense_diary.py -i path/to/diary.xlsx -o output/diary_intervals.xlsx
python scripts/enrich_clarity.py -d path/to/diary.xlsx -c path/to/clarity.xlsx -o output/custom_name.xlsx
```

## Dependencies

- **pandas** — data alignment (`merge_asof`).
- **openpyxl** — Excel read/write.

## Diary columns

Expected column: `Timestamp (YYYY-MM-DDThh:mm:ss)`, plus `Submitted`, `At Sea`, `At Work`, `Glucose Issue`. Metadata rows without a timestamp are skipped.

## Data handling

By default, files under `input/` and `output/` are gitignored (the directories stay in the repo with `.gitkeep`). Do not commit identifiable health data to a public repository unless your study protocol allows it.
