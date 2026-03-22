"""Resolve input .xlsx/.xlsm files in a directory by filename prefix."""

from __future__ import annotations

from pathlib import Path

EXCEL_SUFFIXES = (".xlsx", ".xlsm")


def find_unique_by_prefix(
    input_dir: Path | str,
    prefix: str,
    *,
    label: str,
) -> Path:
    """
    Return the only ``.xlsx`` / ``.xlsm`` file in ``input_dir`` whose name starts
    with ``prefix`` (case-insensitive). ``label`` is used in error messages.
    """
    directory = Path(input_dir)
    if not directory.is_dir():
        raise FileNotFoundError(f"{label}: input directory does not exist: {directory.resolve()}")

    prefix_lower = prefix.lower()
    hits: list[Path] = []
    for p in directory.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() not in EXCEL_SUFFIXES:
            continue
        if p.name.lower().startswith(prefix_lower):
            hits.append(p)

    hits.sort(key=lambda x: x.name.lower())
    if not hits:
        raise FileNotFoundError(
            f"{label}: no {EXCEL_SUFFIXES} file starting with {prefix!r} in {directory.resolve()}"
        )
    if len(hits) > 1:
        names = ", ".join(p.name for p in hits)
        raise ValueError(
            f"{label}: multiple files match prefix {prefix!r} in {directory}: {names}. "
            "Keep only one or pass an explicit path."
        )
    return hits[0]


def find_unique_clarity_raw(
    input_dir: Path | str,
    *,
    label: str = "Clarity raw export",
) -> Path:
    """
    Like ``Clarity_Export*`` in ``input_dir``, but excludes files whose stem ends with
    ``_diary`` (enriched outputs named ``<stem>_diary.xlsx``).
    """
    directory = Path(input_dir)
    if not directory.is_dir():
        raise FileNotFoundError(f"{label}: input directory does not exist: {directory.resolve()}")

    prefix_lower = "clarity_export"
    hits: list[Path] = []
    for p in directory.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() not in EXCEL_SUFFIXES:
            continue
        if not p.name.lower().startswith(prefix_lower):
            continue
        if p.stem.lower().endswith("_diary"):
            continue
        hits.append(p)

    hits.sort(key=lambda x: x.name.lower())
    if not hits:
        raise FileNotFoundError(
            f"{label}: no raw {EXCEL_SUFFIXES} file starting with 'Clarity_Export' "
            f"(excluding *_diary) in {directory.resolve()}"
        )
    if len(hits) > 1:
        names = ", ".join(p.name for p in hits)
        raise ValueError(
            f"{label}: multiple raw Clarity files in {directory}: {names}. "
            "Keep only one or pass --clarity."
        )
    return hits[0]
