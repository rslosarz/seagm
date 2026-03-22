# Insulina — SEAGM diary + Dexcom Clarity (XLSX)

Tools to:

1. **Build `diary_intervals.xlsx`** from the study diary (5-minute rows → interval sheets for At Sea, At Work, and glucose-issue episodes).
2. **Enrich the Clarity workbook** by filling `At Sea`, `At Work`, and `Glucose Issue` on each row that has a CGM timestamp.

**Formats:** diary, Clarity input, and all script outputs are **`.xlsx`** (or `.xlsm`). There is no CSV path in these scripts.

## Requirements

- **Python** 3.10+ (`python3` on your `PATH`).
- **GNU Make** (optional; commands below work without it).

## Quick start

```bash
make setup    # one-time: .venv + pip install -r requirements.txt
make all      # diary_intervals.xlsx + Clarity_with_diary.xlsx
```

Outputs under `output/`:

| Output | Path |
|--------|------|
| Interval workbook (sheets: at_sea, at_work, glucose_issues) | `output/diary_intervals.xlsx` |
| Clarity + diary columns | `output/Clarity_with_diary.xlsx` |

## Interval rules (`condense_diary.py`)

Rows are read in **time order** (after the usual cleaning: valid timestamp, `Submitted == YES`, parseable `At Sea` / `At Work`).

- **At Sea / At Work:** start a new interval when the boolean **changes** from one row to the next. The previous interval **ends** at the **previous** row’s timestamp; the new one **starts** at the **current** row’s timestamp.
- **Glucose Issue:** `none` (case-insensitive) means no episode. A new episode starts when the label becomes non-`none`, and ends when it returns to `none` or the label **changes**. Ends use the **previous** row’s timestamp; starts use the **current** row’s (same pattern as sea/work).
- **Gap:** if `current_ts - previous_ts` is **greater than** `GAP_HOURS` (default **1.0** hour), **all** open intervals (sea, work, and any glucose episode) are **closed** at the previous timestamp, then new intervals are opened from the **current** row’s values.

The last row closes any still-open intervals at its timestamp.

Override the gap in Make: `make condense GAP_HOURS=2` or use `--gap-hours` on the script.

## Enrichment (`enrich_clarity.py`)

Enrichment uses the **diary workbook rows** (5-minute state) and `merge_asof` backward on timestamps — **not** the interval sheets. The interval file is a separate human-readable summary.

Large Clarity files may be slow or memory-heavy when written with `to_excel`; that is expected for full exports.

## Makefile targets

| Target | Description |
|--------|-------------|
| `make help` | Summary of targets and defaults |
| `make setup` / `make install` | Create `.venv` and install dependencies |
| `make condense` | Run `scripts/condense_diary.py` |
| `make enrich` | Run `scripts/enrich_clarity.py` |
| `make all` | `condense` then `enrich` |
| `make clean-output` | Delete `output/` |

Default inputs: `DIARY=SEAGM_03_diary.xlsx`, `CLARITY=Clarity_Export_SeaGM03_JF_2026-03-11_162431.xlsx`. Override: `make all DIARY=other.xlsx CLARITY=other_clarity.xlsx`.

## Manual commands

```bash
python scripts/condense_diary.py -i SEAGM_03_diary.xlsx -o output/diary_intervals.xlsx --gap-hours 1

python scripts/enrich_clarity.py \
  -d SEAGM_03_diary.xlsx \
  -c Clarity_Export_SeaGM03_JF_2026-03-11_162431.xlsx \
  -o output/Clarity_with_diary.xlsx
```

## Dependencies

- **pandas** — data alignment (`merge_asof`).
- **openpyxl** — Excel read/write.

## Diary columns

Expected column: `Timestamp (YYYY-MM-DDThh:mm:ss)`, plus `Submitted`, `At Sea`, `At Work`, `Glucose Issue`. Metadata rows without a timestamp are skipped.

## Data handling

Do not commit identifiable health data to a public repository unless your study protocol allows it.
