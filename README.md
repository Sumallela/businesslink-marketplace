# BusinessLink Marketplace — database, ETL and viewer

Capstone project: a MySQL 8.4 database for a fictional B2B marketplace, a Python ETL that loads the 11 supplied CSV
files, and a Streamlit app to look at the data. Everything runs in Docker on your own laptop.

Data: synthetic B2B teaching adaptation of the *Olist Brazilian E-Commerce Public Dataset* (Kaggle, CC BY-NC-SA 4.0).
The source transactions are historical B2C orders (2016–2018), amounts in BRL — see `docs/ASSUMPTIONS.md`.

## What's where
| Path | What |
|---|---|
| `PLAN.md` | Waves and phases, what's done |
| `docker-compose.yml` | `db` (MySQL 8.4), `etl` (Python, run on demand), `app` (Streamlit) |
| `sql/01_schema.sql` | Tables, keys, constraints, indexes, audit tables (`etl_load_log`, `etl_dq_flags`) |
| `sql/02_users.sh` | `etl_user` (read/write) and `viewer_user` (read-only) |
| `etl/` | `mappings.py` (file→table rules) · `clean.py` · `validate.py` · `load_data.py` (CLI) · `reconcile.py` |
| `app/app.py` | Streamlit viewer |
| `docs/` | Runbook, decisions, assumptions, reconciliation + data-quality reports, troubleshooting; `docs/source/` = course package files |
| `tests/` | pytest for cleaning + validation |

## Setup (first time, ~10 minutes)
1. Install **Docker Desktop** and **Git**. Start Docker Desktop.
2. Clone the repo and open a terminal in the folder.
3. Copy the 11 CSV files from the course package into `data/` (they are not in git — 105 MB).
4. `copy .env.example .env` (PowerShell) or `cp .env.example .env` (Git Bash) and fill in the passwords.
   **Get the team passwords from the team lead in private chat — never commit `.env`.**
5. Build and start the database:
   ```
   docker compose build
   docker compose up -d db
   ```
6. Load the data — follow **[docs/LOAD_RUNBOOK.md](docs/LOAD_RUNBOOK.md)** (dry run → load → reconcile).
7. Start the viewer: `docker compose up -d app` → open **http://localhost:8501**.

Stop everything: `docker compose down` (data is kept). Wipe the database: `docker compose down -v`.

## Team workflow
- `main` is protected: work on a feature branch, open a pull request, one teammate reviews, then merge.
- Never commit `.env`, `.streamlit/secrets.toml`, `data/*.csv` or `rejects/` (already in `.gitignore`).
- Problems? See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).
