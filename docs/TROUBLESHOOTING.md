# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `failed to connect to the docker API ... dockerDesktopLinuxEngine` | Docker Desktop not running | Start Docker Desktop, wait for "Engine running", retry |
| `Bind for 127.0.0.1:3306 failed: port is already allocated` | A local MySQL is already using 3306 | Stop it, or change the left side of `"127.0.0.1:3306:3306"` in docker-compose.yml to e.g. `3307` and set `DB_PORT=3307` in `.env` |
| Same for `8501` | Another Streamlit is running | Stop it or change the app port mapping |
| `Access denied for user 'etl_user'@'...'` | `.env` passwords changed **after** the database was first created (users are only created on first start) | `docker compose down -v` then `docker compose up -d db` (wipes data — reload after) |
| `Table 'businesslink.orders' doesn't exist` | Database volume created before `sql/` existed, or the init failed | `docker logs businesslink-db`; then `docker compose down -v` and start again |
| `parent table X is empty - load it first` then rejects "not found in X" | Ran `--table child` before its parents | Run the full load (no `--table`) |
| `--truncate empties every table...` | `--truncate` is only for full reloads | Drop `--table`/`--file`, or run without `--truncate` |
| `SchemaError: missing column(s)` | CSV header changed / wrong file | Compare the header with `etl/mappings.py` |
| `UnicodeDecodeError` | File saved in a non-UTF-8 encoding (e.g. re-saved from Excel) | Use the original CSV from the package, or re-save as "CSV UTF-8" |
| Postal codes like `6273` | Excel dropped the leading zero | The ETL pads it back to `06273` and flags it (`postal_code_padded_to_5_digits`) |
| Git Bash: `python: can't open file 'C:/Program Files/Git/...'` | Git Bash path rewriting | Prefix the command with `MSYS_NO_PATHCONV=1`, or use PowerShell |
| Viewer: "Can't reach the database" | db container stopped, or not loaded | `docker compose up -d db app`; run the load |
| Viewer shows old numbers after a reload | Queries are cached for 5 minutes | Press `C` in the app (clear cache) and `R` (rerun) |
| `cannot execute INSERT in a read-only transaction` | Expected: viewer_user is read-only | Use the ETL for writes |
