# BusinessLink Marketplace

A complete data platform for a B2B marketplace: MySQL database, Python ETL pipeline, and interactive Streamlit viewer. Everything runs locally in Docker with zero external dependencies.

**Version:** 1.0  
**Status:** Production-ready  
**Data:** 240K+ marketplace transactions across 11 tables

---

## What It Does

**BusinessLink** is a data analytics platform for a fictional B2B marketplace with:

- **Database:** MySQL 8.4 with 11 tables (products, suppliers, orders, payments, reviews, deliveries, and more)
- **ETL Pipeline:** Python-based data import with validation, quality checks, and comprehensive logging
- **Data Viewer:** Interactive Streamlit web app for exploring marketplace data
- **Quality Assurance:** Automatic detection of data quality issues with detailed audit trails

Perfect for learning data engineering, analytics, or as a foundation for marketplace analytics applications.

---

## Quick Start

### Prerequisites
- **Docker Desktop** (with Docker Compose)
- **Git** (optional, if cloning from repository)

### Installation (5 minutes)

1. **Clone or download the repository:**
   ```bash
   git clone https://github.com/yourusername/businesslink-marketplace.git
   cd businesslink-marketplace
   ```

2. **Configure environment variables:**
   ```bash
   # Copy the template
   cp .env.example .env    # Mac/Linux
   # or
   copy .env.example .env  # Windows
   
   # Edit .env and change the passwords to something secure
   nano .env               # or use your editor
   ```

3. **Start the database:**
   ```bash
   docker compose up -d db
   ```
   Wait 10-15 seconds for the database to initialize.

4. **Load sample data (optional):**
   ```bash
   docker compose run --rm etl python -m etl.load_data
   ```
   This loads 11 CSV files with ~240K marketplace records. First load takes ~30 seconds.

5. **Start the viewer:**
   ```bash
   docker compose up -d app
   ```
   Open **http://localhost:8501** in your browser.

---

## Usage

### View Data
Navigate to **http://localhost:8501** to explore:
- Product catalog and categories
- Supplier information
- Orders and delivery status
- Payments and reviews
- Geographic data

### Load or Update Data

**Check data without loading:**
```bash
docker compose run --rm etl python -m etl.load_data --dry-run
```

**Load all tables:**
```bash
docker compose run --rm etl python -m etl.load_data
```

**Load specific table:**
```bash
docker compose run --rm etl python -m etl.load_data --table orders
```

**Check data quality:**
```bash
docker compose run --rm etl python -m etl.reconcile
```

### Database Access

Connect to MySQL directly:
```bash
# From your terminal
mysql -h 127.0.0.1 -u viewer_user -p
# Password: (from .env VIEWER_PASSWORD)

# Then query
USE businesslink;
SELECT COUNT(*) FROM orders;
```

---

## Project Structure

```
├── README.md                    # This file
├── docker-compose.yml           # Docker services definition
├── requirements.txt             # Python dependencies
│
├── app/
│   └── app.py                  # Streamlit viewer
│
├── etl/                         # Data import pipeline
│   ├── load_data.py           # Main ETL orchestrator (CLI)
│   ├── config.py              # Database connection
│   ├── clean.py               # Data cleaning & standardization
│   ├── validate.py            # Data validation & quality checks
│   ├── mappings.py            # Table schemas & rules
│   └── reconcile.py           # Post-load verification
│
├── sql/
│   ├── 01_schema.sql          # Table definitions
│   └── 02_users.sh            # Database users setup
│
├── data/                        # CSV files (not in git)
│   ├── product_categories.csv
│   ├── suppliers.csv
│   ├── orders.csv
│   └── ...
│
├── tests/                       # Test suite
│   ├── test_clean.py
│   ├── test_validate.py
│   └── conftest.py
│
└── docs/
    ├── ASSUMPTIONS.md          # Data assumptions
    ├── DECISIONS.md            # Design decisions
    ├── LOAD_RUNBOOK.md         # ETL operation guide
    ├── TROUBLESHOOTING.md      # Common issues & fixes
    ├── DATA_QUALITY.md         # Data quality report
    └── RECONCILIATION.md       # Reconciliation checks

ETL_PROCESS.md                  # Comprehensive ETL documentation
ETL_QUICK_GUIDE.md             # Quick reference guide
```

---

## Documentation

| Document | Purpose |
|----------|---------|
| **[ETL_QUICK_GUIDE.md](ETL_QUICK_GUIDE.md)** | 5-minute overview of the ETL process |
| **[ETL_PROCESS.md](ETL_PROCESS.md)** | Complete ETL reference (architecture, validation, monitoring) |
| **[docs/LOAD_RUNBOOK.md](docs/LOAD_RUNBOOK.md)** | Step-by-step data loading instructions |
| **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** | Solutions to common problems |
| **[docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md)** | Data assumptions and transformations |

---

## Architecture

### Three-Service Stack

1. **db** (MySQL 8.4)
   - 11 production tables
   - Audit tables for ETL tracking (`etl_load_log`, `etl_dq_flags`)
   - Runs on port 3306 (localhost only)

2. **etl** (Python 3.11 + pandas)
   - Data extraction, cleaning, validation
   - Runs on-demand via CLI
   - Comprehensive logging and reject file generation

3. **app** (Streamlit)
   - Interactive web interface
   - Read-only database access
   - Runs on port 8501

### Data Flow

```
CSV Files
    ↓
Extract (read_csv)
    ↓
Clean (type conversion, standardization)
    ↓
Validate (quality checks, FK validation)
    ├─→ Accepted Rows → Insert into MySQL
    ├─→ Rejected Rows → rejects/<table>.csv
    └─→ Flagged Rows → etl_dq_flags table
    ↓
Audit (etl_load_log, reconciliation)
```

---

## Managing Services

```bash
# Start all services
docker compose up -d

# Stop all services (keeps data)
docker compose down

# View logs
docker compose logs -f app        # Streamlit logs
docker compose logs -f db         # Database logs
docker compose logs -f etl        # ETL logs

# Delete all data (database reset)
docker compose down -v

# Rebuild images
docker compose build
```

---

## Data Quality

The ETL process automatically detects data issues:

- **Rejected rows:** Fail validation checks (missing keys, type errors, FK violations)
- **Flagged rows:** Loaded but marked for review (data quality concerns)
- **Audit trail:** Every load is logged with row counts, errors, and timestamps

View quality reports:
```bash
docker compose run --rm etl python -m etl.reconcile
```

This generates `docs/DATA_QUALITY.md` and `docs/RECONCILIATION.md` with detailed findings.

---

## Deployment to Cloud

The project is designed for local development but can be deployed to cloud:

### Aiven Cloud MySQL

Update `.env` to point to your Aiven instance:
```env
DB_HOST=your-instance.aivencloud.com
DB_PORT=23951
DB_NAME=businesslink
VIEWER_USER=avnadmin
VIEWER_PASSWORD=your-password
```

Then run:
```bash
docker compose run --rm etl python -m etl.load_data
docker compose up -d app
```

---

## Testing

Run the test suite:
```bash
docker compose run --rm etl pytest tests/ -v
```

Tests cover:
- Data cleaning (type conversion, standardization)
- Data validation (constraints, business rules)

---

## Troubleshooting

**Port 3306 or 8501 already in use?**
```bash
# Edit docker-compose.yml and change port mappings
# Or kill existing containers
docker compose down
```

**Database won't start?**
```bash
# Reset everything
docker compose down -v
docker compose up -d db
```

**Data won't load?**
```bash
# Dry run to see errors
docker compose run --rm etl python -m etl.load_data --dry-run

# Check rejected rows
cat rejects/orders_*.csv
```

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for more solutions.

---

## Data Source

Data is a synthetic B2B adaptation of the **Olist Brazilian E-Commerce Dataset** (Kaggle, CC BY-NC-SA 4.0):
- **Period:** 2016–2018
- **Volume:** 240K+ transactions
- **Currency:** Brazilian Real (BRL)
- **Adaptation:** B2C → B2B marketplace scenario
- **Purpose:** Educational and analytical use

See [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md) for details on data transformations.

---

## Development

### Add a New Feature

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make changes and test: `docker compose run --rm etl pytest tests/`
3. Commit: `git commit -m "feat: add my feature"`
4. Push: `git push origin feature/my-feature`
5. Open a pull request

### Environment

- Python 3.11
- MySQL 8.4
- Streamlit 1.x
- pandas, PyMySQL

---

## License

This project uses the Olist Brazilian E-Commerce Dataset (CC BY-NC-SA 4.0). The B2B adaptation and all code are provided as-is for educational and research purposes.

---

## Support

For issues, questions, or contributions:
1. Check [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
2. Review the [ETL_QUICK_GUIDE.md](ETL_QUICK_GUIDE.md)
3. Open an issue on GitHub

---

## Version History

- **v1.0** (2026-11-23) — Initial release
  - 11 production tables with 240K+ marketplace records
  - Python ETL with validation and quality checks
  - Streamlit viewer with interactive exploration
  - Comprehensive documentation and audit trails
