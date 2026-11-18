# Reconciliation report

Generated 2026-11-18 03:51 by `python -m etl.reconcile` (last ETL run `20261118_035150`).

Rule: **in DB = CSV rows - rejected**, and every accepted primary key is present. Each table also has 3 random rows compared value-by-value with the CSV.

| table | expected (package) | CSV rows | rejected | expected in DB | in DB | match | spot check |
|---|---|---|---|---|---|---|---|
| product_categories | 71 | 74 | 0 | 74 | 74 | yes | 3/3 |
| postal_geolocation | 19015 | 19015 | 0 | 19015 | 19015 | yes | 3/3 |
| buyer_organizations | 96096 | 96096 | 0 | 96096 | 96096 | yes | 3/3 |
| suppliers | 3095 | 3095 | 0 | 3095 | 3095 | yes | 3/3 |
| products | 32951 | 32951 | 0 | 32951 | 32951 | yes | 3/3 |
| supplier_product_catalog | 34448 | 34448 | 0 | 34448 | 34448 | yes | 3/3 |
| orders | 99441 | 99441 | 0 | 99441 | 99441 | yes | 3/3 |
| order_items | 112650 | 112650 | 0 | 112650 | 112650 | yes | 3/3 |
| payments | 103886 | 103886 | 0 | 103886 | 103886 | yes | 3/3 |
| reviews | 99224 | 99224 | 0 | 99224 | 99224 | yes | 3/3 |
| order_deliveries | 99441 | 99441 | 0 | 99441 | 99441 | yes | 3/3 |

**Overall: all tables reconcile**

## Notes and problems

- `product_categories`: the CSV has 74 rows, the package summary says 71 - all CSV rows were processed; see docs/ASSUMPTIONS.md
