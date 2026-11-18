"""Validation: decide, row by row, what is rejected and what is loaded with a flag.

Checks (instructions §5.3): required columns, primary-key uniqueness, duplicates, type validity,
foreign-key validity, value rules (CHECK constraints), plus data-quality flags.
"""
from dataclasses import dataclass

import pandas as pd

from etl.clean import clean_frame
from etl.mappings import TableSpec


class SchemaError(Exception):
    """The CSV does not have the columns the mapping expects - nothing can be loaded."""


@dataclass
class ValidationResult:
    accepted: pd.DataFrame        # rows to load
    rejects: pd.DataFrame         # raw-ish rows + 'reason' column
    flags: pd.DataFrame           # record_key, rule, detail (rows that ARE loaded)
    rows_read: int


def check_required_columns(df: pd.DataFrame, spec: TableSpec) -> None:
    missing = [c for c in spec.columns if c not in df.columns]
    if missing:
        raise SchemaError(f"{spec.file}: missing column(s) {missing}; found {list(df.columns)}")


def duplicate_key_mask(df: pd.DataFrame, key: list[str]) -> pd.Series:
    """True for every repeat of a key after its first appearance."""
    return df.duplicated(key, keep="first")


def orphan_mask(df: pd.DataFrame, columns: list[str], parent_keys: set[tuple]) -> pd.Series:
    """True where the FK value is present but not found among the parent's keys.

    A NULL FK is not an orphan (NOT NULL is checked separately as 'required').
    """
    present = df[columns].notna().all(axis=1)
    tuples = pd.Series(list(map(tuple, df[columns].itertuples(index=False, name=None))), index=df.index)
    return present & ~tuples.isin(parent_keys)


def record_key(df: pd.DataFrame, key: list[str]) -> pd.Series:
    return df[key].astype(str).agg("|".join, axis=1)


def validate(raw: pd.DataFrame, spec: TableSpec, parent_keys: dict[str, set[tuple]]) -> ValidationResult:
    """parent_keys: {parent table name: set of key tuples} for every FK in spec."""
    check_required_columns(raw, spec)
    df, bad_values, padded = clean_frame(raw, spec.columns)

    reasons = pd.Series([[] for _ in range(len(df))], index=df.index, dtype=object)
    flag_frames: list[pd.DataFrame] = []

    def reject(mask: pd.Series, reason: str) -> None:
        for i in mask[mask.fillna(False).astype(bool)].index:
            reasons.at[i].append(reason)

    def flag(mask: pd.Series, rule: str, detail: str = "") -> None:
        mask = mask.fillna(False).astype(bool)
        if mask.any():
            flag_frames.append(pd.DataFrame({"index": df.index[mask], "rule": rule, "detail": detail}))

    # 1. keys + required values
    for col in spec.primary_key:
        reject(df[col].isna(), f"missing primary key {col}")
    reject(duplicate_key_mask(df, spec.primary_key) & df[spec.primary_key].notna().all(axis=1),
           f"duplicate primary key ({', '.join(spec.primary_key)})")
    for col in spec.required:
        reject(df[col].isna() & ~bad_values.get(col, pd.Series(False, index=df.index)),
               f"missing required value {col}")

    # 2. types: bad value in a required/key column -> reject; elsewhere -> NULL + flag
    for col, mask in bad_values.items():
        if col in spec.required or col in spec.primary_key:
            reject(mask, f"invalid {spec.columns[col]} in {col}")
        else:
            flag(mask, f"invalid_{spec.columns[col]}_set_to_null", col)
    flag(padded, "postal_code_padded_to_5_digits")

    # 3. foreign keys
    for fk in spec.foreign_keys:
        reject(orphan_mask(df, fk.columns, parent_keys[fk.parent]),
               f"{'/'.join(fk.columns)} not found in {fk.parent}")

    # 4. value rules (mirror the CHECK constraints) and data-quality flags
    for reason, rule in spec.reject_rules:
        reject(rule(df), reason)
    for name, rule in spec.flag_rules:
        flag(rule(df), name)

    rejected = reasons.map(bool)
    rejects = raw.loc[rejected].copy()
    rejects["reason"] = reasons[rejected].map("; ".join)

    keys = record_key(df, spec.primary_key)
    if flag_frames:
        flags = pd.concat(flag_frames, ignore_index=True)
        flags = flags[~flags["index"].isin(df.index[rejected])]      # only rows that are loaded
        flags.insert(0, "record_key", keys.loc[flags["index"]].values)
        flags = flags.drop(columns="index").reset_index(drop=True)
    else:
        flags = pd.DataFrame(columns=["record_key", "rule", "detail"])

    return ValidationResult(accepted=df.loc[~rejected].reset_index(drop=True), rejects=rejects,
                            flags=flags, rows_read=len(df))
