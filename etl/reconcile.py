"""After a load: prove the database matches the files, and run cross-table consistency checks.

    python -m etl.reconcile

Writes:
    docs/RECONCILIATION.md  expected (package summary) vs CSV rows vs rejected vs rows in the DB, + spot checks
    docs/DATA_QUALITY.md    flag counts per rule + post-load consistency checks
"""
import json
import logging
import sys
from datetime import datetime
from decimal import Decimal

import pandas as pd
from etl.config import DOCS_DIR, PROJECT_ROOT, connect, fetchall, ident
from etl.load_data import read_csv
from etl.mappings import TABLES, TableSpec
from etl.validate import validate, record_key

log = logging.getLogger("reconcile")
SUMMARY_JSON = PROJECT_ROOT / "docs" / "source" / "04_transformation_summary.json"
SPOT_CHECKS_PER_TABLE = 3

# (name, what it means, SQL returning one count). 0 is the ideal unless the note says otherwise.
CONSISTENCY_CHECKS = [
    ("orders_without_items", "Orders with no order line (often canceled/unavailable orders in the source).",
     "SELECT count(*) FROM orders o WHERE NOT EXISTS (SELECT 1 FROM order_items i WHERE i.order_id = o.order_id)"),
    ("orders_without_payments", "Orders with no payment record.",
     "SELECT count(*) FROM orders o WHERE NOT EXISTS (SELECT 1 FROM payments p WHERE p.order_id = o.order_id)"),
    ("orders_without_delivery_record", "Orders missing their 1:1 order_deliveries row.",
     "SELECT count(*) FROM orders o WHERE NOT EXISTS (SELECT 1 FROM order_deliveries d WHERE d.order_id = o.order_id)"),
    ("payment_total_differs_from_items_plus_freight",
     "Orders whose payments differ from item price + freight by more than R$1.00 "
     "(installment interest/vouchers can explain this; do NOT add payments to item sales).",
     """WITH i AS (SELECT order_id, sum(item_price_brl + freight_value_brl) v FROM order_items GROUP BY order_id),
             p AS (SELECT order_id, sum(payment_amount_brl) v FROM payments GROUP BY order_id)
        SELECT count(*) FROM i JOIN p USING (order_id) WHERE abs(i.v - p.v) > 1.00"""),
    ("delivery_record_differs_from_order", "order_deliveries status/dates not equal to the same order's values.",
     """SELECT count(*) FROM orders o JOIN order_deliveries d USING (order_id)
        WHERE NOT ((o.order_status, o.order_delivered_carrier_date, o.order_delivered_customer_date,
               o.order_estimated_delivery_date)
          <=> (d.order_status, d.order_delivered_carrier_date, d.order_delivered_customer_date,
               d.order_estimated_delivery_date))"""),
    ("order_line_listing_mismatch", "Order lines whose supplier/product differ from their catalog listing "
     "(enforced by the composite foreign key, so must be 0).",
     """SELECT count(*) FROM order_items i JOIN supplier_product_catalog c USING (catalog_id)
        WHERE NOT ((i.supplier_id, i.product_id) <=> (c.supplier_id, c.product_id))"""),
    ("buyer_postal_prefix_not_in_geolocation", "Buyers whose postal prefix has no centroid (logical link, not an FK).",
     """SELECT count(*) FROM buyer_organizations b WHERE b.postal_code_prefix IS NOT NULL
        AND NOT EXISTS (SELECT 1 FROM postal_geolocation g WHERE g.postal_code_prefix = b.postal_code_prefix)"""),
    ("supplier_postal_prefix_not_in_geolocation", "Suppliers whose postal prefix has no centroid.",
     """SELECT count(*) FROM suppliers s WHERE s.postal_code_prefix IS NOT NULL
        AND NOT EXISTS (SELECT 1 FROM postal_geolocation g WHERE g.postal_code_prefix = s.postal_code_prefix)"""),
    ("orders_with_more_than_one_review", "Orders carrying more than one review record.",
     "SELECT count(*) FROM (SELECT order_id FROM reviews GROUP BY order_id HAVING count(*) > 1) x"),
    ("products_listed_by_multiple_suppliers", "Informational: products offered by 2+ suppliers.",
     "SELECT count(*) FROM (SELECT product_id FROM supplier_product_catalog GROUP BY product_id HAVING count(*) > 1) x"),
]


def _same(kind: str, csv_value, db_value, scale: int | None) -> bool:
    if csv_value is None or db_value is None:
        return csv_value is None and db_value is None
    if kind == "int":
        return int(csv_value) == int(db_value)
    if kind == "decimal":
        tol = Decimal("0.5") * Decimal(10) ** -(scale or 0) if scale is not None else Decimal("1e-9")
        return abs(Decimal(csv_value) - Decimal(db_value)) <= tol
    if kind == "timestamp":
        return pd.Timestamp(csv_value) == pd.Timestamp(db_value)
    return str(csv_value).strip() == str(db_value).strip()


def spot_check(conn, spec: TableSpec, accepted: pd.DataFrame) -> tuple[int, list[str]]:
    scales = dict(fetchall(conn,
        "SELECT column_name, numeric_scale FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name = %s", (spec.name,)))
    sample = accepted.sample(min(SPOT_CHECKS_PER_TABLE, len(accepted)), random_state=42)
    problems: list[str] = []
    cols = list(spec.columns)
    where = " AND ".join(f"{ident(k)} = %s" for k in spec.primary_key)
    query = f"SELECT {', '.join(map(ident, cols))} FROM {ident(spec.name)} WHERE {where}"
    for _, row in sample.iterrows():
        found = fetchall(conn, query, [row[k] for k in spec.primary_key])
        db_row = found[0] if found else None
        key = "|".join(str(row[k]) for k in spec.primary_key)
        if db_row is None:
            problems.append(f"{key}: not found in DB")
            continue
        for col, db_val in zip(cols, db_row):
            if not _same(spec.columns[col], row[col], db_val, scales.get(col)):
                problems.append(f"{key}.{col}: CSV={row[col]!r} DB={db_val!r}")
    return len(sample), problems


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    expected = json.loads(SUMMARY_JSON.read_text())["counts"] if SUMMARY_JSON.exists() else {}
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows, spot_lines, all_ok = [], [], True
    accepted_by_table: dict[str, pd.DataFrame] = {}

    with connect("etl") as conn:
        for spec in TABLES:
            raw = read_csv(PROJECT_ROOT / "data" / spec.file)
            parents = {fk.parent: set(accepted_by_table[fk.parent][fk.parent_columns]
                                      .itertuples(index=False, name=None)) for fk in spec.foreign_keys}
            result = validate(raw, spec, parents)
            accepted_by_table[spec.name] = result.accepted
            db_count = fetchall(conn, f"SELECT count(*) FROM {ident(spec.name)}")[0][0]
            db_keys = {tuple(r) for r in fetchall(
                conn, f"SELECT {', '.join(map(ident, spec.primary_key))} FROM {ident(spec.name)}")}
            missing = set(record_key(result.accepted, spec.primary_key)) - {"|".join(map(str, k)) for k in db_keys}
            ok = db_count == len(result.accepted) and not missing
            checked, problems = spot_check(conn, spec, result.accepted)
            all_ok &= ok and not problems
            exp = expected.get(spec.name)
            rows.append({
                "table": spec.name, "expected (package)": exp if exp is not None else "-",
                "CSV rows": result.rows_read, "rejected": len(result.rejects),
                "expected in DB": len(result.accepted), "in DB": db_count,
                "match": "yes" if ok else "NO", "spot check": f"{checked - len(problems) if not problems else 'FAIL'}/{checked}",
            })
            spot_lines += [f"- `{spec.name}`: {p}" for p in problems]
            if exp is not None and exp != result.rows_read:
                spot_lines.append(f"- `{spec.name}`: the CSV has {result.rows_read} rows, the package summary says {exp}"
                                  " - all CSV rows were processed; see docs/ASSUMPTIONS.md")
            log.info("%-25s CSV %7d  rejected %4d  DB %7d  %s", spec.name, result.rows_read,
                     len(result.rejects), db_count, "OK" if ok else "MISMATCH")

        checks = [(n, d, fetchall(conn, q)[0][0]) for n, d, q in CONSISTENCY_CHECKS]
        flags = pd.DataFrame(fetchall(conn,
            "SELECT table_name, rule, count(*) FROM etl_dq_flags GROUP BY 1, 2 ORDER BY 1, 3 DESC"),
            columns=["table", "rule", "rows flagged"])
        last_run = fetchall(conn, "SELECT max(run_id) FROM etl_load_log WHERE status = 'ok'")[0][0]

    (DOCS_DIR / "RECONCILIATION.md").write_text(
        f"# Reconciliation report\n\nGenerated {now} by `python -m etl.reconcile` (last ETL run `{last_run}`).\n\n"
        "Rule: **in DB = CSV rows - rejected**, and every accepted primary key is present. Each table also has "
        f"{SPOT_CHECKS_PER_TABLE} random rows compared value-by-value with the CSV.\n\n"
        f"{_md(pd.DataFrame(rows))}\n\n"
        f"**Overall: {'all tables reconcile' if all_ok else 'MISMATCHES FOUND - see below'}**\n\n"
        "## Notes and problems\n\n" + ("\n".join(spot_lines) if spot_lines else "None.") + "\n",
        encoding="utf-8")
    (DOCS_DIR / "DATA_QUALITY.md").write_text(
        f"# Data-quality report (ETL output)\n\nGenerated {now} by `python -m etl.reconcile`.\n\n"
        "**Rejected** rows are not loaded (see `rejects/`). **Flagged** rows are loaded, and the note sits in "
        "`etl_dq_flags` so the app and SQL can show or exclude them.\n\n"
        "## Flags by rule (rows loaded, needs attention)\n\n"
        f"{_md(flags) if not flags.empty else 'No flags.'}\n\n"
        "## Post-load consistency checks\n\n"
        f"{_md(pd.DataFrame(checks, columns=['check', 'meaning', 'count']))}\n",
        encoding="utf-8")
    print(f"\n{pd.DataFrame(rows).to_string(index=False)}\n")
    for n, _, c in checks:
        print(f"  {n:50s} {c}")
    print(f"\nWrote docs/RECONCILIATION.md and docs/DATA_QUALITY.md - {'ALL OK' if all_ok else 'MISMATCHES FOUND'}")
    return 0 if all_ok else 1


def _md(df: pd.DataFrame) -> str:
    """Markdown table without needing the 'tabulate' package."""
    head = "| " + " | ".join(map(str, df.columns)) + " |"
    sep = "|" + "|".join("---" for _ in df.columns) + "|"
    body = ["| " + " | ".join(str(v).replace("|", "/") for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join([head, sep, *body])


if __name__ == "__main__":
    sys.exit(main())
