# BusinessLink ETL Process - Quick Guide

## Executive Summary

The BusinessLink ETL automates the process of importing marketplace data from CSV files into MySQL:

| Phase | Input | Output | Status |
|-------|-------|--------|--------|
| **Extract** | CSV files in `data/` | Raw data as text | 11 tables |
| **Clean** | Raw text values | Typed, standardized values | Type conversion |
| **Validate** | Cleaned data | Accepted rows + rejects + flags | Quality checks |
| **Load** | Valid rows | Data in MySQL | Upsert (insert/update) |

**Key Features:**
- ✅ **Re-runnable** - Safe to run multiple times with same files
- ✅ **Traceable** - Every load logged with run ID, row counts, errors
- ✅ **Non-destructive** - Rejects archived, previous data preserved on rollback
- ✅ **Transactional** - One transaction per table (all-or-nothing per table)

**Process Flow:**
```
CSV Files → Extract → Clean → Validate → Load → MySQL Database
                        ↓
                   (Rejects & Flags tracked)
```

---

## What is ETL?

ETL (Extract, Transform, Load) is the process of moving data from CSV files into the MySQL database. The BusinessLink ETL reads marketplace data, cleans it, validates quality, and loads it into tables in the correct dependency order. The process is **re-runnable** — running it multiple times with the same files is safe and idempotent.

---

## The Four Steps

### 1. Extract: Read CSV Files

The ETL reads CSV files from the `data/` directory. Each file corresponds to one table (e.g., `orders.csv` → `orders` table). Files are read with all columns as text to preserve original values and prevent data loss from automatic type guessing.

### 2. Clean: Standardize Data

Raw values are converted to the correct type based on the mapping:
- **text**: Trimmed, empty strings become NULL
- **int**: Whole numbers (40.0 → 40)
- **decimal**: Exact numeric values (preserves precision)
- **timestamp**: Date/time parsing
- **postal**: 5-digit postal codes (pads shorter codes like 123 → 00123)

Type conversion errors don't immediately reject rows — they're flagged for review if the column isn't required.

### 3. Validate: Quality Checks

Each row is checked against three categories of rules:

**Reject Rules** (row is not loaded):
- Missing primary keys or required fields
- Duplicate primary keys within the file
- Type conversion failures in required/key columns
- Foreign key doesn't exist in parent table (orphan)
- Business rule violations (e.g., negative prices, delivery before purchase)

**Flag Rules** (row is loaded but marked for review):
- Missing optional coordinates
- Zero quantity orders
- Invalid postal codes (but not fatal)
- Timestamp inconsistencies

**Rejected rows** are saved to `rejects/<table>_<run>.csv` for manual review. **Flagged rows** are stored in the `etl_dq_flags` table for quality reporting.

### 4. Load: Insert into MySQL

Valid rows are inserted using an **upsert** (insert or update) strategy:
```sql
INSERT INTO table (...) VALUES (...), (...), ...
  ON DUPLICATE KEY UPDATE col = VALUES(col)
```

**Key features:**
- **New rows**: Inserted
- **Existing rows (unchanged)**: No change (MySQL returns 0)
- **Existing rows (changed)**: Updated (MySQL returns 2)
- **Idempotent**: Re-running with same files shows "0 changed"
- **Transaction safety**: One transaction per table — all rows succeed or the entire table rolls back

---

## Load Order

Tables are loaded in dependency order so foreign keys reference existing data:

1. `product_categories`, `postal_geolocation`, `buyer_organizations`, `suppliers` (no dependencies)
2. `products` (needs `product_categories`)
3. `supplier_product_catalog` (needs `suppliers`, `products`)
4. `orders` (needs `buyer_organizations`)
5. `order_items`, `payments`, `reviews` (need `orders`)
6. `order_deliveries` (needs `orders`, `suppliers`)

---

## Running the ETL

### Command Examples

```bash
# Test everything without loading
docker compose run --rm etl python -m etl.load_data --dry-run

# Load all 11 tables
docker compose run --rm etl python -m etl.load_data

# Load only one table
docker compose run --rm etl python -m etl.load_data --table orders

# Load from specific file
docker compose run --rm etl python -m etl.load_data --file data/orders.csv

# Full reload (truncate and reload)
docker compose run --rm etl python -m etl.load_data --truncate

# Check data quality
docker compose run --rm etl python -m etl.reconcile
```

---

## Monitoring Results

### Check Load Status
```sql
SELECT table_name, status, rows_loaded, rows_rejected, finished_at
FROM etl_load_log
ORDER BY finished_at DESC LIMIT 10;
```

### View Quality Issues
```sql
SELECT rule, COUNT(*) as count
FROM etl_dq_flags
WHERE run_id = (SELECT MAX(run_id) FROM etl_load_log)
GROUP BY rule ORDER BY count DESC;
```

### Review Rejected Rows
```bash
cat rejects/orders_<run>.csv  # Shows reason column
```

---

## Key Principles

1. **Safe to Repeat**: Running the same load twice is harmless
2. **Transaction Per Table**: Either all rows of a table load, or none do
3. **Data Quality First**: Validation separates fixable issues (flags) from blocking issues (rejects)
4. **Traceable**: Every load is logged with run ID, timestamp, and results
5. **Non-Destructive**: Rejected rows are archived, not deleted; previous data unchanged on rollback

---

## Typical Workflow

1. Place CSV file(s) in `data/` directory
2. Run `--dry-run` to validate without loading
3. Review any rejected rows in `rejects/` directory
4. Fix issues in source CSV if needed
5. Run actual load with `python -m etl.load_data`
6. Check `etl_load_log` and `etl_dq_flags` for results
7. Investigate flagged rows and decide if action needed

The ETL is designed for reliability and visibility — every step is logged, every failure is explained, and every load is repeatable.
