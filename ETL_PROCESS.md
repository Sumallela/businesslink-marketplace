# BusinessLink ETL Loading Process

## Overview

The BusinessLink ETL (Extract, Transform, Load) process reads CSV files, cleans and validates the data, and loads it into the MySQL database. The process is designed to be re-runnable and handles data quality issues gracefully by separating rejected rows from flagged rows.

**Key Principle:** One transaction per table - either all rows in a table succeed or the entire table is rolled back on error.

---

## Architecture

### Data Flow

```
CSV Files
   ↓
Extract (read_csv)
   ↓
Clean (standardize_columns, clean_frame)
   ↓
Validate (reject_rules, flag_rules, FK checks)
   ├─→ Accepted Rows → Load into MySQL (upsert)
   ├─→ Rejected Rows → rejects/<table>_<run>.csv
   └─→ Flagged Rows → etl_dq_flags table
   ↓
Log Results (etl_load_log table)
```

### File Organization

```
etl/
├── load_data.py       # Main ETL orchestrator
├── config.py          # Database connection & utilities
├── clean.py           # Data cleaning & standardization
├── validate.py        # Data validation logic
├── mappings.py        # Table specs, column types, rules
└── reconcile.py       # Post-load verification
```

---

## Load Order & Table Dependencies

Tables are loaded in dependency order (foreign keys must reference existing parent tables):

```
1. product_categories          (no dependencies)
2. postal_geolocation          (no dependencies)
3. buyer_organizations         (no dependencies)
4. suppliers                   (no dependencies)
5. products                    (FK: category_id → product_categories)
6. supplier_product_catalog    (FK: supplier_id → suppliers, product_id → products)
7. orders                      (FK: buyer_id → buyer_organizations)
8. order_items                 (FK: order_id → orders, product_id → products)
9. payments                    (FK: order_id → orders)
10. reviews                    (FK: order_id → orders, product_id → products)
11. order_deliveries           (FK: order_id → orders, supplier_id → suppliers)
```

---

## Detailed Process Steps

### 1. Extract: Read CSV Files

**Function:** `read_csv(path: Path) → pd.DataFrame`

```python
df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
```

**Key Settings:**
- **dtype=str:** Everything starts as text to preserve original values
- **keep_default_na=False:** Prevents pandas from interpreting values like "NA" as missing
- **encoding="utf-8-sig":** Handles UTF-8 with BOM (Windows Excel exports)

**Output:** DataFrame with all columns as strings, ready for cleaning

---

### 2. Clean: Standardize & Type Conversion

**Functions:**
- `standardize_columns(df)` - Normalize column names (lowercase, remove spaces)
- `clean_frame(raw, columns)` - Type conversion and value normalization

**Column Types:**

| Type | Behavior | Example |
|------|----------|---------|
| **text** | Trimmed; empty string → NULL | "  Hello  " → "Hello" |
| **int** | Whole number; "40.0" → 40 | "123", "123.0" |
| **decimal** | Exact numeric; keeps original precision | "19.99", "9.5" |
| **timestamp** | YYYY-MM-DD HH:MM:SS or date | "2023-01-15 14:30:00" |
| **postal** | 5-digit postal code prefix | "12345" (pads "123" → "00123") |

**Output:** `(cleaned_df, bad_values_dict, padded_dict)`

- **cleaned_df:** DataFrame with typed columns (NaN for unparseable values)
- **bad_values_dict:** Mask of rows with type conversion errors
- **padded_dict:** Mask of postal codes that were zero-padded

---

### 3. Validate: Quality Checks

**Function:** `validate(raw, spec, parent_keys) → ValidationResult`

#### 3.1 Structural Validation

**Check 1: Required Columns**
```python
raise SchemaError if CSV is missing expected columns
```

**Check 2: Primary Key Integrity**
- Missing primary key values → **REJECT**
- Duplicate primary keys within the file → **REJECT**

**Check 3: Required Fields**
- Missing required column value → **REJECT** (unless it failed type conversion)

#### 3.2 Type Validation

```python
if bad_value in (required_column or primary_key):
    → REJECT with "invalid <type> in <column>"
else:
    → Allow NULL + FLAG with type error
```

**Example:** 
- "abc" in an int column → If column is required: REJECT; Otherwise: NULL + FLAG

#### 3.3 Foreign Key Validation

**Function:** `orphan_mask(df, columns, parent_keys) → pd.Series`

```python
Checks if FK values exist in parent table
- NULL FK → NOT an orphan (checked separately as 'required')
- FK present but not in parent → REJECT
```

**Load Strategy:**
1. If parent table loaded in this run → Use accepted rows from memory (faster)
2. Otherwise → Query parent table from database

#### 3.4 Business Rules

**Reject Rules:** Row is not loaded
```python
Examples:
- Negative values in monetary fields
- Order delivery date before purchase date
- Invalid status values
```

**Flag Rules:** Row is loaded but marked for review
```python
Examples:
- Missing coordinates (but address is valid)
- Zero quantity in an order item
- Price zero (possible promotion)
```

**Result:**
```
rejects/        → rows that failed validation + reason
etl_dq_flags    → rows that passed but have quality notes
```

---

### 4. Load: Upsert into MySQL

**Function:** `upsert(conn, spec, df) → int`

#### 4.1 Upsert Strategy

```sql
INSERT INTO table_name (...) VALUES (...), (...), ...
  AS new ON DUPLICATE KEY UPDATE 
  col1 = new.col1, col2 = new.col2, ...
```

**Behavior:**
- **New row:** Inserted
- **Existing row (same primary key), unchanged:** No change (MySQL returns 0)
- **Existing row, changed values:** Updated (MySQL returns 2)

**Idempotent:** Re-running with same files shows "changed 0" (safe to repeat)

#### 4.2 Batching

**Batch Size:** 5,000 rows per INSERT statement

```python
for start in range(0, len(rows), BATCH_SIZE):
    batch = rows[start:start+5000]
    INSERT ... VALUES (...), ..., (...)
```

**Benefit:** Reduces network round-trips, MySQL query cache efficiency

#### 4.3 Transaction Handling

```python
with transaction(conn):
    batched_insert(...)
# If any error occurs → entire table rolled back
# If success → committed
```

---

### 5. Log & Report

#### 5.1 Execution Log

**Table:** `etl_load_log`

```
run_id              UUID for this ETL execution
table_name          Which table was loaded
source_file         Which CSV was used
rows_read           Total rows in CSV
rows_loaded         Rows inserted/updated
rows_rejected       Rows that failed validation
rows_flagged        Rows loaded but have quality flags
status              SUCCESS, PARTIAL, ERROR
message             Error details if status != SUCCESS
started_at          Timestamp
finished_at         Timestamp
```

**Query Recent Loads:**
```sql
SELECT * FROM etl_load_log 
ORDER BY started_at DESC 
LIMIT 10;
```

#### 5.2 Data Quality Flags

**Table:** `etl_dq_flags`

```
run_id              ETL execution ID
table_name          Which table
record_key          Pipe-separated primary key values
rule                Which rule was flagged
detail              Additional context
```

**Data Quality Report:**
```sql
SELECT table_name, rule, COUNT(*) as count
FROM etl_dq_flags
WHERE run_id = 'latest'
GROUP BY table_name, rule
ORDER BY count DESC;
```

#### 5.3 Reject Files

**Location:** `rejects/<table>_<run>.csv`

```
<all columns from original CSV> + reason column
```

**Use:** Manual review and correction before re-load

---

## Command Line Usage

### Basic Commands

```bash
# 1. Dry run - check everything, write nothing
docker compose run --rm etl python -m etl.load_data --dry-run

# 2. Full load - all 11 tables (re-runnable)
docker compose run --rm etl python -m etl.load_data

# 3. Load single table (parent tables must exist)
docker compose run --rm etl python -m etl.load_data --table orders

# 4. Load single file (table name inferred from filename)
docker compose run --rm etl python -m etl.load_data --file data/orders.csv

# 5. Truncate all tables and reload
docker compose run --rm etl python -m etl.load_data --truncate

# 6. Post-load reconciliation
docker compose run --rm etl python -m etl.reconcile
```

### Options

```
--dry-run           Validate without loading (safe to test)
--table <name>      Load only this table
--file <path>       Load only this file
--truncate          TRUNCATE all tables first (full reload)
--log-level DEBUG   Verbose logging
```

---

## Workflow Examples

### Scenario 1: Initial Load

```bash
# 1. Check everything first
docker compose run --rm etl python -m etl.load_data --dry-run

# 2. Load all tables
docker compose run --rm etl python -m etl.load_data

# 3. Check for quality issues
docker compose run --rm etl python -m etl.reconcile
```

### Scenario 2: Update Existing Data

```bash
# 1. Put corrected orders.csv in data/ directory

# 2. Test the file
docker compose run --rm etl python -m etl.load_data --dry-run --table orders

# 3. Load only the orders table (re-runs the upsert)
docker compose run --rm etl python -m etl.load_data --table orders

# 4. Check if any rows were rejected
# Review: rejects/orders_<run>.csv
```

### Scenario 3: Fix Quality Issues

```bash
# 1. Identify flagged rows
SELECT * FROM etl_dq_flags 
WHERE run_id = (SELECT MAX(run_id) FROM etl_load_log);

# 2. Update source data in data/<table>.csv

# 3. Reload the table
docker compose run --rm etl python -m etl.load_data --table <name>
```

### Scenario 4: Incremental Updates

```bash
# New data arrives each day
# CSV contains only new + changed rows

# Just run:
docker compose run --rm etl python -m etl.load_data --table orders

# ETL will:
# - Insert new order rows
# - Update changed order rows (same ID, different values)
# - Leave unchanged rows as-is
```

---

## Error Handling & Recovery

### Validation Errors (Safe)

**Cause:** Rows fail validation checks

**Result:**
- Rows written to `rejects/<table>_<run>.csv`
- Table load continues with valid rows
- **No data loss** - can review and re-load

**Recovery:**
```bash
# Fix the rejected rows in the CSV
# Re-run the load
docker compose run --rm etl python -m etl.load_data --table orders
```

### Database Errors (Transaction Rollback)

**Cause:** SQL execution fails (constraint violation, connection lost, etc.)

**Result:**
- Entire table is rolled back
- Status logged as ERROR
- **Previous data unchanged** - table state before the load

**Recovery:**
```bash
# Fix the underlying issue (CSV data, database constraints, etc.)
# Re-run the load
docker compose run --rm etl python -m etl.load_data --table orders
```

### Missing Parent Table

**Cause:** FK references parent table that hasn't been loaded

**Result:**
- Warning logged: "parent table X is empty - load it first"
- All child rows rejected: "orphan foreign key"

**Recovery:**
```bash
# Load parent first
docker compose run --rm etl python -m etl.load_data --table product_categories

# Then load child
docker compose run --rm etl python -m etl.load_data --table products
```

---

## Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| Read CSV (100k rows) | ~2s | Pandas I/O |
| Clean & validate | ~5s | Type conversion + rules |
| Insert batch (5k rows) | ~1s | MySQL round-trip |
| Full 11-table load | ~30s | Depends on data size |
| Reusable if unchanged | <5s | Only validation, no DB writes |

---

## Monitoring & Troubleshooting

### Check Load Status

```sql
-- Latest load for each table
SELECT table_name, status, rows_loaded, rows_rejected, finished_at
FROM etl_load_log
WHERE (table_name, started_at) IN (
  SELECT table_name, MAX(started_at)
  FROM etl_load_log
  GROUP BY table_name
)
ORDER BY finished_at DESC;
```

### Find Recent Errors

```sql
SELECT run_id, table_name, status, message, finished_at
FROM etl_load_log
WHERE status != 'SUCCESS'
ORDER BY finished_at DESC
LIMIT 10;
```

### View Quality Flags

```sql
SELECT rule, COUNT(*) as count
FROM etl_dq_flags
WHERE run_id = (SELECT MAX(run_id) FROM etl_load_log)
GROUP BY rule
ORDER BY count DESC;
```

### Check Row Counts

```sql
-- Expected row counts (adjust based on your data)
SELECT 'suppliers' as table_name, COUNT(*) as count FROM suppliers
UNION ALL SELECT 'products', COUNT(*) FROM products
UNION ALL SELECT 'orders', COUNT(*) FROM orders
UNION ALL SELECT 'order_items', COUNT(*) FROM order_items;
```

---

## Best Practices

1. **Always Dry Run First**
   ```bash
   docker compose run --rm etl python -m etl.load_data --dry-run
   ```

2. **Review Rejects Before Re-running**
   ```bash
   cat rejects/orders_<run>.csv  # Check what failed
   ```

3. **Monitor Load Log**
   ```bash
   docker compose run --rm etl python -m etl.reconcile
   ```

4. **Keep Data Files Clean**
   - Remove duplicates before loading
   - Ensure required columns are populated
   - Use consistent date/time formats

5. **Schedule Regular Loads**
   - If new data arrives daily: `0 2 * * * docker compose run --rm etl load_data`
   - Or use `--truncate` weekly for full refresh

6. **Archive Rejected Files**
   ```bash
   mv rejects/ rejects_$(date +%Y%m%d)/
   ```

---

## Debugging

### Enable Verbose Logging

```bash
docker compose run --rm etl python -m etl.load_data --log-level DEBUG
```

### Test Single Row

Create a test CSV with one row and load it:

```bash
docker compose run --rm etl python -m etl.load_data --file data/test_orders.csv --dry-run
```

### Check Column Mapping

```python
# In Python REPL:
from etl.mappings import TABLES_BY_NAME
spec = TABLES_BY_NAME['orders']
print(spec.columns)
print(spec.primary_key)
print(spec.foreign_keys)
```

---

## Migration & Cloud Deployment

### After Moving to Aiven Cloud

The ETL process works the same way - it only needs the database connection:

```bash
# Update .env with Aiven credentials
DB_HOST=your-aiven-host.aivencloud.com
DB_PORT=23951
DB_USER=etl_user
DB_PASSWORD=...

# Then run as normal
docker compose run --rm etl python -m etl.load_data
```

**Note:** Aiven connection is slower than local Docker, so batches may take slightly longer.

---

## See Also

- [README.md](README.md) - Project overview
- [etl/config.py](etl/config.py) - Database connection utilities
- [etl/mappings.py](etl/mappings.py) - Table specifications and rules
- [etl/validate.py](etl/validate.py) - Validation logic details
