# Load runbook — step by step

How to load the 11 CSV files into the local MySQL 8.4 database. Run every command from the project folder
in a terminal (PowerShell or Git Bash). Docker Desktop must be running.

> Git Bash only: put `MSYS_NO_PATHCONV=1` in front of `docker compose run ...` commands, or Git Bash
> rewrites the paths. PowerShell doesn't need it.

## Step 0 — one-time setup
| # | Do | Check |
|---|---|---|
| 0.1 | Copy the 11 CSVs from the course package into `data/` | `data/` lists 11 `.csv` files |
| 0.2 | `copy .env.example .env`, then put your own passwords in `.env` (get the team's from the team lead, never by git) | `.env` exists, is not in `git status` |
| 0.3 | `docker compose build` | ends with `Built` |
| 0.4 | `docker compose up -d db` | `docker compose ps` shows `businesslink-db ... (healthy)` |

On its **first** start the database runs `sql/01_schema.sql` (11 tables + 2 audit tables) and
`sql/02_users.sh` (creates `etl_user` and `viewer_user`). If you change those files later, see "Start over" below.

## Step 1 — dry run (checks everything, writes nothing)
```
MSYS_NO_PATHCONV=1 docker compose run --rm etl python -X utf8 -m etl.load_data --dry-run
```
Expect: every table `rejected 0`. Flags are fine (rows that load but need a look).
If anything is rejected, open `rejects/<table>_<run>.csv` — the `reason` column says why.

## Step 2 — load, parents first
```
MSYS_NO_PATHCONV=1 docker compose run --rm etl python -X utf8 -m etl.load_data
```
Order (automatic): product_categories → postal_geolocation → buyer_organizations → suppliers → products →
supplier_product_catalog → orders → order_items → payments → reviews → order_deliveries.
Each table is one transaction: if it fails, that table is rolled back and the run stops (children need it).
About 4 minutes for ~600k rows (MySQL performance profile).

## Step 3 — prove it is re-runnable
Run Step 2 again. Expect `changed 0` on every table.

## Step 4 — reconcile
```
MSYS_NO_PATHCONV=1 docker compose run --rm etl python -X utf8 -m etl.reconcile
```
Writes `docs/RECONCILIATION.md` (CSV rows vs rejected vs DB rows + 3 spot-checked rows per table) and
`docs/DATA_QUALITY.md` (flags per rule + cross-table checks). Expect `ALL OK`.

## Step 5 — open the viewer
```
docker compose up -d app
```
Open http://localhost:8501 → tabs *Browse tables*, *Monthly trend*, *Load status*.

## Other runs
| Need | Command |
|---|---|
| One table again (its parents already loaded) | `MSYS_NO_PATHCONV=1 docker compose run --rm etl python -X utf8 -m etl.load_data --table payments` |
| A corrected file | `MSYS_NO_PATHCONV=1 docker compose run --rm etl python -X utf8 -m etl.load_data --file data/payments.csv` |
| Empty everything and reload | `MSYS_NO_PATHCONV=1 docker compose run --rm etl python -X utf8 -m etl.load_data --truncate` |
| Unit tests | `MSYS_NO_PATHCONV=1 docker compose run --rm etl python -X utf8 -m pytest -q` |
| MySQL shell (admin) | `docker exec -it businesslink-db mysql -uroot -p"$MYSQL_ROOT_PASSWORD" businesslink` |

## Start over (wipes the database)
```
docker compose down -v      # -v deletes the data volume
docker compose up -d db     # re-creates schema + users from sql/
```
Then Steps 1–4 again.

## Last result (2026-11-17)
| table | CSV rows | rejected | in DB | flagged |
|---|---:|---:|---:|---:|
| product_categories | 74 | 0 | 74 | 0 |
| postal_geolocation | 19,015 | 0 | 19,015 | 0 |
| buyer_organizations | 96,096 | 0 | 96,096 | 268 |
| suppliers | 3,095 | 0 | 3,095 | 7 |
| products | 32,951 | 0 | 32,951 | 616 |
| supplier_product_catalog | 34,448 | 0 | 34,448 | 0 |
| orders | 99,441 | 0 | 99,441 | 1,617 |
| order_items | 112,650 | 0 | 112,650 | 383 |
| payments | 103,886 | 0 | 103,886 | 14 |
| reviews | 99,224 | 0 | 99,224 | 1,603 |
| order_deliveries | 99,441 | 0 | 99,441 | 0 |
