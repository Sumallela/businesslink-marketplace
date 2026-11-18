"""Database settings, read from .env (or from Docker's environment, which wins), and small DB helpers."""
import os
from contextlib import contextmanager
from pathlib import Path

import pymysql
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=False)

DATA_DIR = PROJECT_ROOT / "data"
REJECTS_DIR = PROJECT_ROOT / "rejects"
DOCS_DIR = PROJECT_ROOT / "docs"


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is not set - copy .env.example to .env and fill it in")
    return value


def connect(role: str = "etl") -> pymysql.connections.Connection:
    """Open a connection as the ETL (read-write) or viewer (read-only) user.

    autocommit is on, so nothing stays half-done by accident; multi-statement work uses `transaction()`.
    The password is passed as a keyword, never built into a printable string.
    """
    prefix = {"etl": "ETL", "viewer": "VIEWER"}[role]
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=_require("DB_NAME"),
        user=_require(f"{prefix}_USER"),
        password=_require(f"{prefix}_PASSWORD"),
        charset="utf8mb4",
        autocommit=True,
        connect_timeout=10,
    )


@contextmanager
def transaction(conn):
    """All-or-nothing block: commit on success, roll back on any error."""
    conn.begin()
    try:
        yield
    except BaseException:
        conn.rollback()
        raise
    conn.commit()


def ident(name: str) -> str:
    """Quote a table/column name (names come from etl/mappings.py, never from user input)."""
    return "`" + name.replace("`", "``") + "`"


def fetchall(conn, sql: str, params=None) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def execute(conn, sql: str, params=None) -> int:
    """Run one statement; returns affected rows."""
    with conn.cursor() as cur:
        return cur.execute(sql, params)
