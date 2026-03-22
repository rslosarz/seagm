"""Load and normalize SEAGM diary from Excel (.xlsx / .xlsm) only."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

TIMESTAMP_COL = "Timestamp (YYYY-MM-DDThh:mm:ss)"


def _parse_bool_cell(x):
    """Diary bools from Excel: bool, 0/1, or TRUE/FALSE strings."""
    if pd.isna(x):
        return pd.NA
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        if x == 1:
            return True
        if x == 0:
            return False
        return pd.NA
    if isinstance(x, (float, np.floating)):
        if x == 1.0:
            return True
        if x == 0.0:
            return False
        return pd.NA
    u = str(x).upper().strip()
    if u == "TRUE":
        return True
    if u == "FALSE":
        return False
    return pd.NA


def _parse_bool_series(s: pd.Series) -> pd.Series:
    return s.map(_parse_bool_cell)


def load_clean_diary(path: str) -> pd.DataFrame:
    """
    Return sorted rows: ts, At Sea (bool), At Work (bool), Glucose Issue (str).
    Drops metadata rows (no timestamp), non-YES Submitted, unparseable bools.
    """
    p = Path(path)
    suf = p.suffix.lower()
    if suf not in (".xlsx", ".xlsm"):
        raise ValueError(f"Diary must be .xlsx or .xlsm, got {path!r}")

    raw = pd.read_excel(path, engine="openpyxl")

    if TIMESTAMP_COL not in raw.columns:
        raise KeyError(
            f"Expected column {TIMESTAMP_COL!r} in {path!r}, got {list(raw.columns)}"
        )

    df = raw.copy()
    df["ts"] = pd.to_datetime(df[TIMESTAMP_COL], errors="coerce")
    df = df.dropna(subset=["ts"])

    sub = df["Submitted"].astype(str).str.upper().str.strip() == "YES"
    df = df.loc[sub].copy()

    df["At Sea"] = _parse_bool_series(df["At Sea"])
    df["At Work"] = _parse_bool_series(df["At Work"])
    df = df.dropna(subset=["At Sea", "At Work"])

    df["Glucose Issue"] = df["Glucose Issue"].astype(str).str.strip()

    df = df.sort_values("ts").reset_index(drop=True)
    return df[["ts", "At Sea", "At Work", "Glucose Issue"]]
