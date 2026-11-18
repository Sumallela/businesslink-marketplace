"""Cleaning: turn raw CSV text into tidy, typed-checked values.

Every value is read as text first (so '01001' keeps its leading zero). Each cast returns the cleaned
column plus a mask of values that were present but could not be parsed, so the caller decides whether
that row is rejected (required column) or kept with NULL and flagged (optional column).
"""
import re

import pandas as pd

_INT_TEXT = re.compile(r"^[+-]?\d+(\.0+)?$")


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """'Order ID ' -> 'order_id'."""
    out = df.copy()
    out.columns = [re.sub(r"\W+", "_", str(c).strip().lower()).strip("_") for c in out.columns]
    return out


def clean_text(s: pd.Series) -> pd.Series:
    """Trim whitespace; empty string -> NULL (None)."""
    s = s.astype("string").str.strip().replace("", pd.NA)
    return s.astype(object).where(s.notna(), None)


def cast_int(s: pd.Series) -> tuple[pd.Series, pd.Series]:
    """'40', '40.0' -> '40'. Returns (cleaned text, bad mask)."""
    s = clean_text(s)
    present = s.notna()
    ok = s.where(present, "").str.match(_INT_TEXT)
    bad = present & ~ok
    cleaned = s.where(present & ok).map(lambda v: str(int(float(v))) if isinstance(v, str) else None)
    return cleaned, bad


def cast_decimal(s: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Checks the text is a finite number but keeps the original text (no float rounding)."""
    s = clean_text(s)
    num = pd.to_numeric(s, errors="coerce")
    bad = s.notna() & (num.isna() | num.isin([float("inf"), float("-inf")]))
    return s.where(~bad, None), bad


def cast_timestamp(s: pd.Series) -> tuple[pd.Series, pd.Series]:
    """'2017-10-02 10:56:33' -> same text, normalised to ISO 'YYYY-MM-DD HH:MM:SS'."""
    s = clean_text(s)
    parsed = pd.to_datetime(s, errors="coerce", format="ISO8601")
    bad = s.notna() & parsed.isna()
    cleaned = parsed.dt.strftime("%Y-%m-%d %H:%M:%S").astype(object).where(parsed.notna(), None)
    return cleaned, bad


def cast_postal(s: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    """5-digit postal prefix. Returns (cleaned, bad mask, padded mask).

    A prefix that lost its leading zero (e.g. Excel turned '06273' into '6273') is padded back.
    """
    s = clean_text(s)
    present = s.notna()
    digits = s.where(present, "").str.fullmatch(r"\d{1,5}")
    bad = present & ~digits
    padded = present & digits & (s.where(present, "").str.len() < 5)
    cleaned = s.where(present & digits).map(lambda v: v.zfill(5) if isinstance(v, str) else None)
    return cleaned, bad, padded


def clean_frame(df: pd.DataFrame, columns: dict[str, str]) -> tuple[pd.DataFrame, dict[str, pd.Series], pd.Series]:
    """Clean every mapped column.

    Returns (clean df with only mapped columns, {column: bad-value mask}, mask of padded postal codes).
    """
    out = pd.DataFrame(index=df.index)
    bad: dict[str, pd.Series] = {}
    padded = pd.Series(False, index=df.index)
    for col, kind in columns.items():
        if kind == "text":
            out[col] = clean_text(df[col])
            continue
        if kind == "int":
            out[col], bad[col] = cast_int(df[col])
        elif kind == "decimal":
            out[col], bad[col] = cast_decimal(df[col])
        elif kind == "timestamp":
            out[col], bad[col] = cast_timestamp(df[col])
        elif kind == "postal":
            out[col], bad[col], padded = cast_postal(df[col])
        else:
            raise ValueError(f"unknown column kind {kind!r} for {col}")
    return out, bad, padded
