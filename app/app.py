"""BusinessLink Marketplace - data viewer (Phase 1).

Read-only: connects as viewer_user. Credentials come from .streamlit/secrets.toml ([db] section)
or, when running in Docker, from environment variables.
"""
import os

import altair as alt
import pandas as pd
import streamlit as st
from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.engine import URL

st.set_page_config(page_title="BusinessLink Viewer", layout="wide")

PAGE_SIZE = 500
DOWNLOAD_LIMIT = 50_000
SERIES_COLOR = "#2a78d6"
TABLES = ["product_categories", "postal_geolocation", "buyer_organizations", "suppliers", "products",
          "supplier_product_catalog", "orders", "order_items", "payments", "reviews", "order_deliveries"]


ENV_NAMES = {"host": "DB_HOST", "port": "DB_PORT", "dbname": "DB_NAME",
             "user": "VIEWER_USER", "password": "VIEWER_PASSWORD"}


def _setting(key: str, default: str | None = None) -> str | None:
    """Environment first (Docker), then .streamlit/secrets.toml [db] (local run / Streamlit Cloud).

    st.secrets is only touched when the env var is missing: reading it without a secrets file
    makes Streamlit print an error on the page.
    """
    value = os.getenv(ENV_NAMES[key])
    if value:
        return value
    try:
        return st.secrets["db"][key]
    except Exception:
        return default


@st.cache_resource
def engine():
    url = URL.create("mysql+pymysql", host=_setting("host", "localhost"), port=int(_setting("port", "3306")),
                     database=_setting("dbname"), username=_setting("user"), password=_setting("password"),
                     query={"charset": "utf8mb4"})
    return create_engine(url, pool_pre_ping=True)


@st.cache_data(ttl=300, show_spinner=False)
def query(sql: str, params: dict | None = None) -> pd.DataFrame:
    stmt = text(sql)
    lists = [k for k, v in (params or {}).items() if isinstance(v, (list, tuple))]
    if lists:                                   # "IN :name" with a Python list
        stmt = stmt.bindparams(*(bindparam(k, expanding=True) for k in lists))
    with engine().connect() as conn:
        return pd.read_sql(stmt, conn, params=params or {})


@st.cache_data(ttl=300)
def table_columns(table: str) -> list[str]:
    df = query("SELECT column_name FROM information_schema.columns "
               "WHERE table_schema = DATABASE() AND table_name = :t ORDER BY ordinal_position", {"t": table})
    return df.iloc[:, 0].tolist()


@st.cache_data(ttl=300)
def primary_key(table: str) -> list[str]:
    df = query("""SELECT column_name FROM information_schema.key_column_usage
                  WHERE table_schema = DATABASE() AND table_name = :t AND constraint_name = 'PRIMARY'
                  ORDER BY ordinal_position""", {"t": table})
    return df.iloc[:, 0].tolist()


def q(name: str) -> str:
    """Quote an identifier that was already checked against the whitelist."""
    return "`" + name.replace("`", "``") + "`"


def build_where(table: str, search: str, column: str | None, value: str) -> tuple[str, dict]:
    parts, params = [], {}
    if search:
        all_cols = ", ".join(q(c) for c in table_columns(table))
        parts.append(f"CONCAT_WS('|', {all_cols}) LIKE :search")          # search across every column
        params["search"] = f"%{search}%"
    if column and value:
        parts.append(f"CAST({q(column)} AS CHAR) LIKE :value")              # case-insensitive collation
        params["value"] = f"%{value}%"
    return ("WHERE " + " AND ".join(parts)) if parts else "", params


# ------------------------------------------------------------------ header
st.title("BusinessLink Marketplace - data viewer")
st.caption("MySQL 8.4 · Synthetic B2B teaching adaptation of the Olist Brazilian e-commerce dataset (2016-2018). "
           "Amounts in BRL. Read-only view.")

try:
    counts = query(" UNION ALL ".join(f"SELECT '{t}' AS table_name, count(*) AS row_count FROM {q(t)}" for t in TABLES))
except Exception as e:
    st.error("Can't reach the database. Is it running (`docker compose up -d`) and loaded? "
             f"Details: {type(e).__name__}")
    st.stop()

tab_browse, tab_trend, tab_status = st.tabs(["Browse tables", "Monthly trend", "Load status"])

# ------------------------------------------------------------------ browse
with tab_browse:
    left, right = st.columns([1, 3])
    with left:
        table = st.selectbox("Table", TABLES, format_func=lambda t: f"{t}  ({int(counts.set_index('table_name').at[t, 'row_count']):,})")
        cols = table_columns(table)
        search = st.text_input("Search all columns", placeholder="e.g. SP, credit_card, BUY_248f")
        column = st.selectbox("Filter column", ["(none)"] + cols)
        value = st.text_input("contains", disabled=column == "(none)")
    where, params = build_where(table, search.strip(), None if column == "(none)" else column, value.strip())
    order_by = ", ".join(q(c) for c in primary_key(table)) or "1"

    matching = int(query(f"SELECT count(*) AS n FROM {q(table)} {where}", params)["n"].iloc[0])
    pages = max(1, -(-matching // PAGE_SIZE))
    with right:
        c1, c2 = st.columns([3, 1])
        c1.metric("Matching rows", f"{matching:,}")
        page = c2.number_input("Page", min_value=1, max_value=pages, value=1, step=1, help=f"{pages:,} pages")
        data = query(f"SELECT * FROM {q(table)} {where} ORDER BY {order_by} LIMIT :lim OFFSET :off",
                     {**params, "lim": PAGE_SIZE, "off": (page - 1) * PAGE_SIZE})
        st.dataframe(data, use_container_width=True, hide_index=True, height=520)
        st.caption(f"Showing rows {(page - 1) * PAGE_SIZE + 1:,}-{(page - 1) * PAGE_SIZE + len(data):,} of {matching:,}")

        if st.button(f"Prepare CSV of matching rows (max {DOWNLOAD_LIMIT:,})"):
            full = query(f"SELECT * FROM {q(table)} {where} ORDER BY {order_by} LIMIT :lim",
                         {**params, "lim": DOWNLOAD_LIMIT})
            st.download_button("Download CSV", full.to_csv(index=False).encode("utf-8"),
                               file_name=f"{table}.csv", mime="text/csv")

# ------------------------------------------------------------------ trend
with tab_trend:
    st.subheader("Orders and item sales by month")
    st.caption("Item sales = sum of order-line item prices, freight excluded. Each order line counts once "
               "(the source has no unit quantity). Months by purchase date.")
    monthly = query("""
        SELECT DATE_SUB(DATE(o.order_purchase_timestamp), INTERVAL DAY(o.order_purchase_timestamp) - 1 DAY) AS month,
               count(DISTINCT o.order_id) AS orders,
               CAST(COALESCE(SUM(i.item_price_brl), 0) AS DOUBLE) AS item_sales_brl
        FROM orders o LEFT JOIN order_items i ON i.order_id = o.order_id
        GROUP BY 1 ORDER BY 1""")
    statuses = query("SELECT DISTINCT order_status FROM orders ORDER BY 1")["order_status"].tolist()
    chosen = st.multiselect("Order status", statuses, default=statuses)
    if chosen and set(chosen) != set(statuses):
        monthly = query("""
            SELECT DATE_SUB(DATE(o.order_purchase_timestamp), INTERVAL DAY(o.order_purchase_timestamp) - 1 DAY) AS month,
                   count(DISTINCT o.order_id) AS orders,
                   CAST(COALESCE(SUM(i.item_price_brl), 0) AS DOUBLE) AS item_sales_brl
            FROM orders o LEFT JOIN order_items i ON i.order_id = o.order_id
            WHERE o.order_status IN :s GROUP BY 1 ORDER BY 1""", {"s": chosen})

    def line(df: pd.DataFrame, field: str, title: str, fmt: str) -> alt.Chart:
        base = alt.Chart(df).encode(x=alt.X("month:T", title=None, axis=alt.Axis(format="%b %Y", grid=False)))
        hover = alt.selection_point(fields=["month"], nearest=True, on="pointerover", empty=False)
        y = alt.Y(f"{field}:Q", title=title, axis=alt.Axis(format=fmt, gridColor="#e1e0d9"))
        tooltip = [alt.Tooltip("month:T", format="%B %Y", title="Month"), alt.Tooltip(f"{field}:Q", format=",.0f", title=title)]
        lines = base.mark_line(color=SERIES_COLOR, strokeWidth=2).encode(y=y)
        points = base.mark_point(color=SERIES_COLOR, filled=True, size=70).encode(
            y=y, opacity=alt.condition(hover, alt.value(1), alt.value(0)), tooltip=tooltip).add_params(hover)
        rule = base.mark_rule(color="#c3c2b7").encode(opacity=alt.condition(hover, alt.value(1), alt.value(0)))
        return (lines + points + rule).properties(height=280)

    if monthly.empty:
        st.info("No orders for this selection.")
    else:
        # Two measures with different scales -> two charts sharing the time axis, never one dual-axis chart.
        a, b = st.columns(2)
        a.altair_chart(line(monthly, "orders", "Orders", ",.0f"), use_container_width=True)
        b.altair_chart(line(monthly, "item_sales_brl", "Item sales (BRL)", "~s"), use_container_width=True)
        with st.expander("Table view"):
            st.dataframe(monthly, hide_index=True, use_container_width=True)

# ------------------------------------------------------------------ load status
with tab_status:
    st.subheader("Last ETL run per table")
    log = query("""SELECT table_name, run_id, status, rows_read, rows_loaded, rows_rejected, rows_flagged,
                          finished_at, message
                   FROM (SELECT l.*, ROW_NUMBER() OVER (PARTITION BY table_name ORDER BY started_at DESC) AS rn
                         FROM etl_load_log l) x
                   WHERE rn = 1""")
    if log.empty:
        st.warning("No ETL run recorded yet. Run: `docker compose run --rm etl python -m etl.load_data`")
    else:
        merged = counts.merge(log, on="table_name", how="left")
        merged["in DB = read - rejected"] = merged["row_count"] == merged["rows_read"] - merged["rows_rejected"]
        merged["order"] = merged["table_name"].map(TABLES.index)
        st.dataframe(merged.sort_values("order").drop(columns="order"), hide_index=True, use_container_width=True)
    st.subheader("Data-quality flags (rows loaded, worth a look)")
    flags = query("SELECT table_name, rule, count(*) AS flagged_rows FROM etl_dq_flags GROUP BY 1, 2 ORDER BY 1, 3 DESC")
    st.dataframe(flags, hide_index=True, use_container_width=True)
    if not flags.empty:
        pick = st.selectbox("Show flagged records for rule", flags["table_name"] + " / " + flags["rule"])
        t, r = pick.split(" / ", 1)
        st.dataframe(query("SELECT record_key, detail FROM etl_dq_flags WHERE table_name = :t AND rule = :r LIMIT 1000",
                           {"t": t, "r": r}), hide_index=True, use_container_width=True)
