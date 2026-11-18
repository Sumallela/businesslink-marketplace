"""BusinessLink ETL: CSV -> clean -> validate -> MySQL.

Examples (run inside Docker, see README):
    python -m etl.load_data --dry-run                 # check everything, write nothing
    python -m etl.load_data                           # load all 11 tables (re-runnable)
    python -m etl.load_data --table orders            # one table (its parents must already be loaded)
    python -m etl.load_data --file data/orders.csv    # one file; the table comes from the file name
    python -m etl.load_data --truncate                # empty every table, then full reload

How a table is loaded (one transaction per table; any error rolls the whole table back):
    INSERT ... VALUES (...), (...), ... AS new ON DUPLICATE KEY UPDATE col = new.col
    in batches of BATCH_SIZE rows. MySQL counts an unchanged row as 0 affected rows,
    so re-running with the same files reports "changed 0".
"""
import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from etl.clean import standardize_columns
from etl.config import DATA_DIR, REJECTS_DIR, connect, execute, fetchall, ident, transaction
from etl.mappings import TABLES, TABLES_BY_FILE, TABLES_BY_NAME, TableSpec
from etl.validate import SchemaError, ValidationResult, validate

log = logging.getLogger("etl")
BATCH_SIZE = 5_000


# ------------------------------------------------------------------ extract
def read_csv(path: Path) -> pd.DataFrame:
    """Everything as text, nothing turned into NaN by pandas guessing; quoted newlines are kept."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    return standardize_columns(df)


# ------------------------------------------------------------------ parent keys for FK checks
def parent_keys_for(spec: TableSpec, accepted_this_run: dict[str, pd.DataFrame], conn) -> dict[str, set[tuple]]:
    """Keys of each parent table: from this run's accepted rows if the parent was processed, else from the DB."""
    keys: dict[str, set[tuple]] = {}
    for fk in spec.foreign_keys:
        if fk.parent in accepted_this_run:
            frame = accepted_this_run[fk.parent][fk.parent_columns]
            keys[fk.parent] = set(frame.itertuples(index=False, name=None))
        else:
            cols = ", ".join(map(ident, fk.parent_columns))
            keys[fk.parent] = {tuple(r) for r in fetchall(conn, f"SELECT {cols} FROM {ident(fk.parent)}")}
            if not keys[fk.parent]:
                log.warning("parent table %s is empty - load it first", fk.parent)
    return keys


# ------------------------------------------------------------------ load
def batched_insert(conn, table: str, cols: list[str], rows: list[tuple], update_cols: list[str] | None) -> int:
    """Multi-row INSERT in batches. update_cols -> upsert those columns on a duplicate key.

    Returns affected rows (MySQL: 1 per insert, 2 per changed update, 0 per unchanged row).
    """
    if not rows:
        return 0
    col_list = ", ".join(map(ident, cols))
    one_row = "(" + ", ".join(["%s"] * len(cols)) + ")"
    suffix = ""
    if update_cols:
        suffix = " AS new ON DUPLICATE KEY UPDATE " + ", ".join(f"{ident(c)} = new.{ident(c)}" for c in update_cols)
    affected = 0
    with conn.cursor() as cur:
        for start in range(0, len(rows), BATCH_SIZE):
            batch = rows[start:start + BATCH_SIZE]
            sql = f"INSERT INTO {ident(table)} ({col_list}) VALUES " + ", ".join([one_row] * len(batch)) + suffix
            affected += cur.execute(sql, [v for row in batch for v in row])
    return affected


def upsert(conn, spec: TableSpec, df: pd.DataFrame) -> int:
    """Insert new rows, update changed ones.

    Returns MySQL's affected-rows counter: inserted + 2 x updated (unchanged rows count 0).
    First load -> equals the row count; re-run with the same files -> 0.
    """
    cols = list(spec.columns)
    non_key = [c for c in cols if c not in spec.primary_key] or cols[:1]   # key-only table: harmless self-update
    rows = list(df[cols].itertuples(index=False, name=None))
    return batched_insert(conn, spec.name, cols, rows, non_key)


def save_flags(conn, run_id: str, table: str, flags: pd.DataFrame) -> None:
    execute(conn, "DELETE FROM etl_dq_flags WHERE table_name = %s", (table,))   # keep latest run only
    rows = [(run_id, table, k, r, d or None) for k, r, d in flags[["record_key", "rule", "detail"]].itertuples(index=False, name=None)]
    batched_insert(conn, "etl_dq_flags", ["run_id", "table_name", "record_key", "rule", "detail"], rows, None)


def log_run(conn, run_id: str, spec: TableSpec, path: Path, result: ValidationResult | None,
            loaded: int, status: str, message: str, started: datetime) -> None:
    execute(conn,
            """INSERT INTO etl_load_log (run_id, table_name, source_file, rows_read, rows_loaded,
                   rows_rejected, rows_flagged, status, message, started_at, finished_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW()) AS new
               ON DUPLICATE KEY UPDATE status = new.status, message = new.message, finished_at = new.finished_at""",
            (run_id, spec.name, path.name, result.rows_read if result else None, loaded,
             len(result.rejects) if result else None, len(result.flags) if result else None,
             status, message[:2000], started))


def write_rejects(run_id: str, spec: TableSpec, result: ValidationResult) -> Path | None:
    if result.rejects.empty:
        return None
    REJECTS_DIR.mkdir(exist_ok=True)
    out = REJECTS_DIR / f"{spec.name}_{run_id}.csv"
    result.rejects.to_csv(out, index=False)
    return out


# ------------------------------------------------------------------ main
def select_tables(args) -> list[tuple[TableSpec, Path]]:
    if args.file:
        path = Path(args.file)
        spec = TABLES_BY_NAME[args.table[0]] if args.table else TABLES_BY_FILE.get(path.name)
        if spec is None:
            sys.exit(f"Can't tell which table {path.name} belongs to; add --table <name>")
        return [(spec, path)]
    wanted = args.table or [t.name for t in TABLES]
    unknown = set(wanted) - set(TABLES_BY_NAME)
    if unknown:
        sys.exit(f"Unknown table(s): {sorted(unknown)}. Valid: {[t.name for t in TABLES]}")
    return [(t, Path(args.data_dir) / t.file) for t in TABLES if t.name in wanted]   # always parent-first order


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--table", action="append", help="load only this table (repeatable)")
    p.add_argument("--file", help="load one CSV file (table from the file name, or --table)")
    p.add_argument("--data-dir", default=str(DATA_DIR))
    p.add_argument("--truncate", action="store_true", help="empty ALL tables first, then full reload")
    p.add_argument("--dry-run", action="store_true", help="validate only; write nothing to the database")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")

    plan = select_tables(args)
    if args.truncate and (args.table or args.file):
        sys.exit("--truncate empties every table, so it is only allowed for a full run (no --table/--file)")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    log.info("run %s%s: %s", run_id, " (DRY RUN)" if args.dry_run else "", ", ".join(s.name for s, _ in plan))
    summary: list[dict] = []
    accepted_this_run: dict[str, pd.DataFrame] = {}

    with connect("etl") as conn:
        if args.truncate and not args.dry_run:
            # DELETE children-first (etl_user has no DROP privilege, which MySQL's TRUNCATE needs)
            with transaction(conn):
                for t in reversed(TABLES):
                    execute(conn, f"DELETE FROM {ident(t.name)}")
                execute(conn, "DELETE FROM etl_dq_flags")
            log.info("emptied all %d tables", len(TABLES))

        for spec, path in plan:
            started, t0 = datetime.now(), time.perf_counter()
            result, loaded = None, 0
            try:
                raw = read_csv(path)
                result = validate(raw, spec, parent_keys_for(spec, accepted_this_run, conn))
                accepted_this_run[spec.name] = result.accepted
                rej_path = write_rejects(run_id, spec, result)
                if not args.dry_run:
                    with transaction(conn):
                        loaded = upsert(conn, spec, result.accepted)
                        save_flags(conn, run_id, spec.name, result.flags)
                        log_run(conn, run_id, spec, path, result, len(result.accepted), "ok", "", started)
                summary.append(dict(table=spec.name, read=result.rows_read, accepted=len(result.accepted),
                                    rejected=len(result.rejects), flagged=len(result.flags),
                                    changed=loaded if not args.dry_run else "-",
                                    secs=round(time.perf_counter() - t0, 1)))
                log.info("%-25s read %7d  accepted %7d  rejected %5d  flagged %5d  changed %s%s",
                         spec.name, result.rows_read, len(result.accepted), len(result.rejects),
                         len(result.flags), summary[-1]["changed"], f"  -> {rej_path}" if rej_path else "")
            except (SchemaError, FileNotFoundError) as e:
                log.error("%s: %s", spec.name, e)
                return _fail(conn, args, run_id, spec, path, result, started, str(e))
            except Exception as e:                       # the table's transaction is already rolled back
                log.exception("%s failed and was rolled back", spec.name)
                return _fail(conn, args, run_id, spec, path, result, started, f"{type(e).__name__}: {e}")

    print("\n" + pd.DataFrame(summary).to_string(index=False))
    print("\nDry run: nothing was written." if args.dry_run else "\nDone. Next: python -m etl.reconcile")
    return 0


def _fail(conn, args, run_id, spec, path, result, started, message) -> int:
    if not args.dry_run:
        log_run(conn, run_id, spec, path, result, 0, "failed", message, started)
    log.error("Stopped at %s - later tables depend on it. Fix the problem and re-run.", spec.name)
    return 1


if __name__ == "__main__":
    sys.exit(main())
