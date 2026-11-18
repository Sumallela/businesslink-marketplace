# PLAN.md — BusinessLink B2B Marketplace: MySQL + Python ETL + Streamlit

Last updated: 2026-11-17 · **Wave 1 / Phase 1: DONE (local, MySQL 8.4)**

## 0. Inputs
| Input | Used for |
|---|---|
| Team plan (`project_plan.md`) | Python ETL, Streamlit viewer, read-only app user, security rules, Azure later |
| Project Instructions (docx) | Business rules, required entities, ETL + DQ checks (§5.2–5.3), 15+ SQL, star schema, 4 dashboard pages, rubric |
| Team EDA (docx) | Missing values, duplicate review_id, chronology violations, 5 open questions (answered in docs/DECISIONS.md D4–D6) |
| Team ERD (png) | Column types and relationships |
| Capstone overview (pptx) | 10-week roadmap, checkpoints W3 / W5 / W8, 12 deliverables |
| Course package (`docs/source/`) | 11 CSVs, DDL (Postgres), star schema, data dictionary, expected counts |

## 1. Confirmed decisions (details: docs/DECISIONS.md)
- **MySQL 8.4 in local Docker**; Streamlit viewer (needs instructor approval vs Power BI). *Note: Course package expects PostgreSQL — decision on whether to revert pending (D1 in DECISIONS.md).*
- ETL written from scratch in Python (pandas + PyMySQL); no sample script was supplied.
- All 74 product_categories rows loaded (summary said 71 — docs/ASSUMPTIONS.md #1).
- Project folder: `C:\Users\rkmal\source\businesslink-marketplace`.

## 2. Waves
| Wave | Scope | Course weeks | Status |
|---|---|---|---|
| **1 — Local foundation** | Docker MySQL 8.4, schema, Python ETL, load + reconcile, Streamlit viewer | W2–W5 | ✅ done locally |
| 2 — SQL portfolio | 15+ business queries (joins, CTEs, subqueries, window, LAG), views, extra indexes; question / SQL / output / interpretation each | W6 | next |
| 3 — Star schema + dashboard | dim_date/buyer/supplier/product/category/geography; fact_order_item, fact_payment, fact_delivery (grain stated, no double counting) built from the operational tables; 4 Streamlit pages (Overview, Supplier, Buyer, Product & Order) | W7–W8 | |
| 4 — Shared cloud | Hosted PostgreSQL (e.g. Azure Database for PostgreSQL Flexible Server — verify free/student terms first), SSL, same users, Streamlit Community Cloud, budget alert, teardown | when the team needs shared access | |
| 5 — Findings + final | 5+ recommendations, ERD/normalization write-up, final report, demo script | W9–W10 | |

## 3. Wave 1 / Phase 1 — what was built
- [x] **1.1 Repo scaffold** — folder layout, `.gitignore` (.env, secrets, data CSVs, rejects), `.env.example`, `requirements.txt`, git repo initialised (nothing committed yet)
- [x] **1.2 Docker** — `mysql:8.4` on 127.0.0.1:3306 with healthcheck + volume; one `python:3.12-slim` image for ETL and app
- [x] **1.3 Schema** — `sql/01_schema.sql`: 11 tables from the instructor DDL + NOT NULL / CHECK / UNIQUE, reviews PK (review_id, order_id), composite FK order_items → catalog, 10+ indexes, 2 audit tables (etl_load_log, etl_dq_flags)
- [x] **1.3b Users** — `sql/02_users.sh`: etl_user (data read/write, no DDL), viewer_user (SELECT only, read-only session — tested: INSERT refused)
- [x] **1.4 ETL** — `etl/`: read as text → clean (trim, ''→NULL, casts, ISO timestamps, postal zero-pad) → validate (required cols, PK dupes, types, FKs, CHECK rules) → rejects CSV with reason / flags table → INSERT ... ON DUPLICATE KEY UPDATE + upsert, one transaction per table, parent-first; CLI `--table --file --truncate --dry-run`
- [x] **1.4b Tests** — 11 pytest tests for clean + validate (pass with MySQL)
- [x] **1.5 Load + verify** — dry run → load (600,321 rows, ~4 min) → re-run changes 0 rows (idempotent) → `etl.reconcile`: all 11 tables reconcile, 3/3 spot checks each; cross-table checks in docs/DATA_QUALITY.md
- [x] **1.6 Streamlit viewer** — http://localhost:8501: table picker with counts, search all columns, column filter, 500-row pages, CSV download (≤50k), monthly orders + item-sales charts (status filter, table view), load status + DQ flags drill-down; connects as viewer_user
- [x] **1.7 Docs** — README, docs/LOAD_RUNBOOK.md (step-by-step load), DECISIONS (D1: MySQL vs Postgres), ASSUMPTIONS, TROUBLESHOOTING, RECONCILIATION, DATA_QUALITY

### Phase 1 definition of done
- [x] `docker compose up -d db` → healthy, 11 tables, 2 users
- [x] Dry run passes; full load completes; re-run is idempotent
- [x] docs/RECONCILIATION.md: every table reconciled
- [x] viewer_user cannot write
- [x] Streamlit shows all 11 tables, charts, CSV download (headless AppTest: no errors)
- [x] pytest green; `.env` and CSVs ignored by git
- [ ] Each teammate follows README from scratch on their own laptop (do at the W5 checkpoint)
- [ ] Instructor approval for Streamlit in place of Power BI

## 4. Data-quality findings from the load (input for the W5 checkpoint)
- 0 rejected rows; 4,508 flags (loaded, noted): 1,609 order chronology violations + 8 delivered-without-date; 1,603 reviews sharing a review_id; 383 zero-freight lines; 268 buyers / 7 suppliers without coordinates; 616 product flags (610 missing name/description/photo, 4 zero weight, 2 missing dimensions); 14 payment flags (9 zero amount, 3 type "not_defined", 2 zero installments).
- 775 orders without lines, 1 without payment, 249 with payment ≠ items + freight (> R$1), 547 orders with >1 review.
- Full lists: docs/DATA_QUALITY.md, and the *Load status* tab of the viewer.

## 5. Security rules (always)
- `.env` / `secrets.toml` never committed; passwords shared privately; rotate if leaked.
- The app uses the read-only user only. DB port bound to localhost only.
