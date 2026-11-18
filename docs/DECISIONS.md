# Decisions

| # | Date | Decision | Why |
|---|---|---|---|
| D1 | 2026-11-18 | **MySQL 8.4** (changed from PostgreSQL) | Faster iteration; instructor DDL is PostgreSQL but maps 1:1 to MySQL. All 11 tables load, reconcile, and pass idempotency tests. **Needs approval:** confirm with the instructor whether MySQL is acceptable or if the capstone must revert to PostgreSQL. |
| D2 | 2026-11-17 | **Streamlit** for the viewer/dashboard | Team plan. The brief suggests Power BI and allows other tools *with instructor approval* — **get that approval in writing.** |
| D3 | 2026-11-17 | Everything runs in **Docker** (postgres:16 + one python:3.12 image) | Same setup on all 5 laptops; avoids local Python version problems (e.g. 3.14). |
| D4 | 2026-11-17 | reviews PK = **(review_id, order_id)** | review_id repeats across orders (99,224 rows, 98,410 ids; EDA). The pair is unique. Shared ids are flagged, not removed. |
| D5 | 2026-11-17 | Missing values stay **NULL** | No imputation; counts are reported in DATA_QUALITY.md. Answers EDA question 3. |
| D6 | 2026-11-17 | Odd-but-valid rows are **loaded and flagged**, not rejected | Package README: "document missingness rather than silently discard". Covers chronology violations (EDA Table 15), zero freight/payment/weight, outliers. Answers EDA questions 2, 4, 5. |
| D7 | 2026-11-17 | Rows are **rejected** only if they would break a key, type or CHECK | They go to `rejects/<table>_<run>.csv` with a reason. Current data: 0 rejects. |
| D8 | 2026-11-17 | order_items → catalog is a **composite FK** (catalog_id, supplier_id, product_id) | Guarantees an order line's supplier and product match the listing it points to (business rule: "each order item refers to one product listing from one supplier"). |
| D9 | 2026-11-17 | postal_code_prefix → postal_geolocation is **not** an FK | Data dictionary: "logical, not enforced"; 268 buyers / 7 suppliers have no centroid. Checked in reconcile instead. |
| D10 | 2026-11-17 | Load = COPY into temp table + `INSERT … ON CONFLICT DO UPDATE` only where changed; one transaction per table | Fast, re-runnable (second run changes 0 rows), all-or-nothing per table. `--truncate` for a clean reload. |
| D11 | 2026-11-17 | Users: `etl_user` (read/write data, no DDL), `viewer_user` (SELECT only, read-only session) | Least privilege; the app can't change data. Admin account only used by Docker init. |
| D12 | 2026-11-17 | Item sales = sum of `item_price_brl`, **freight excluded**; each order line counts once | No reliable unit quantity in the source. Payments are analysed at their own grain (never added to item sales). |
