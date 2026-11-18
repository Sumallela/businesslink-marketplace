"""Which CSV goes into which table, column types, keys and checks - in load order.

Column kinds:
  text       trimmed; empty string -> NULL
  int        whole number ("40.0" is accepted and becomes 40)
  decimal    any number; the original text is kept so NUMERIC gets the exact value
  timestamp  'YYYY-MM-DD HH:MM:SS' (or a date)
  postal     5-digit postal prefix; shorter digit strings are left-padded with zeros (and flagged)

reject_rules -> the row is NOT loaded; written to rejects/<table>_<run>.csv with the reason.
flag_rules   -> the row IS loaded; a note goes to etl_audit.dq_flags for the data-quality report.
"""
from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

Rule = tuple[str, Callable[[pd.DataFrame], pd.Series]]


@dataclass
class ForeignKey:
    columns: list[str]
    parent: str
    parent_columns: list[str]


@dataclass
class TableSpec:
    name: str
    file: str
    columns: dict[str, str]
    primary_key: list[str]
    required: list[str] = field(default_factory=list)
    foreign_keys: list[ForeignKey] = field(default_factory=list)
    reject_rules: list[Rule] = field(default_factory=list)
    flag_rules: list[Rule] = field(default_factory=list)


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce")


def _ts(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_datetime(df[col], errors="coerce")


def _negative(*cols: str) -> Rule:
    return (f"negative value in {'/'.join(cols)}",
            lambda df: pd.concat([_num(df, c) < 0 for c in cols], axis=1).any(axis=1))


def _zero(col: str) -> Rule:
    return (f"zero_{col}", lambda df: _num(df, col) == 0)


def _before(later: str, earlier: str) -> Rule:
    """Flag rows where `later` happened before `earlier` (only when both are present)."""
    return (f"{later}_before_{earlier}", lambda df: _ts(df, later) < _ts(df, earlier))


GEO_COLUMNS = {
    "city": "text", "state": "text", "postal_code_prefix": "postal",
    "latitude": "decimal", "longitude": "decimal",
}
GEO_FLAGS: list[Rule] = [
    ("missing_coordinates", lambda df: df["latitude"].isna() | df["longitude"].isna()),
]
ORDER_TIMESTAMPS = ["order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
                    "order_delivered_customer_date", "order_estimated_delivery_date"]

TABLES: list[TableSpec] = [
    TableSpec(
        name="product_categories", file="product_categories.csv",
        columns={"category_id": "text", "category_name_source": "text", "category_name_english": "text"},
        primary_key=["category_id"],
    ),
    TableSpec(
        name="postal_geolocation", file="postal_geolocation.csv",
        columns={"postal_code_prefix": "postal", "latitude": "decimal", "longitude": "decimal",
                 "city": "text", "state": "text"},
        primary_key=["postal_code_prefix"],
        reject_rules=[("latitude/longitude out of range",
                       lambda df: (_num(df, "latitude").abs() > 90) | (_num(df, "longitude").abs() > 180))],
    ),
    TableSpec(
        name="buyer_organizations", file="buyer_organizations.csv",
        columns={"buyer_org_id": "text", "buyer_org_name": "text", "industry": "text",
                 "organization_size": "text", **GEO_COLUMNS, "source_customer_unique_id": "text"},
        primary_key=["buyer_org_id"], required=["buyer_org_name"],
        reject_rules=[("organization_size not Micro/Small/Medium/Large",
                       lambda df: df["organization_size"].notna()
                       & ~df["organization_size"].isin(["Micro", "Small", "Medium", "Large"]))],
        flag_rules=GEO_FLAGS,
    ),
    TableSpec(
        name="suppliers", file="suppliers.csv",
        columns={"supplier_id": "text", "supplier_name": "text", "supplier_segment": "text",
                 "supplier_size": "text", **GEO_COLUMNS},
        primary_key=["supplier_id"], required=["supplier_name"],
        reject_rules=[("supplier_size not Small/Medium/Large",
                       lambda df: df["supplier_size"].notna()
                       & ~df["supplier_size"].isin(["Small", "Medium", "Large"]))],
        flag_rules=GEO_FLAGS,
    ),
    TableSpec(
        name="products", file="products.csv",
        columns={"product_id": "text", "category_id": "text", "source_name_length": "int",
                 "source_description_length": "int", "photo_count": "int", "weight_g": "decimal",
                 "length_cm": "decimal", "height_cm": "decimal", "width_cm": "decimal"},
        primary_key=["product_id"],
        foreign_keys=[ForeignKey(["category_id"], "product_categories", ["category_id"])],
        reject_rules=[_negative("source_name_length", "source_description_length", "photo_count",
                                "weight_g", "length_cm", "height_cm", "width_cm")],
        flag_rules=[("missing_category", lambda df: df["category_id"].isna()),
                    ("missing_name_description_photo", lambda df: df["photo_count"].isna()),
                    ("missing_weight_or_dimensions",
                     lambda df: df[["weight_g", "length_cm", "height_cm", "width_cm"]].isna().any(axis=1)),
                    _zero("weight_g")],
    ),
    TableSpec(
        name="supplier_product_catalog", file="supplier_product_catalog.csv",
        columns={"catalog_id": "text", "supplier_id": "text", "product_id": "text",
                 "list_price_brl": "decimal", "availability_status": "text", "quantity_available": "int",
                 "listing_status": "text", "historical_order_item_count": "int", "currency": "text",
                 "price_basis": "text"},
        primary_key=["catalog_id"], required=["supplier_id", "product_id", "currency"],
        foreign_keys=[ForeignKey(["supplier_id"], "suppliers", ["supplier_id"]),
                      ForeignKey(["product_id"], "products", ["product_id"])],
        reject_rules=[_negative("list_price_brl", "quantity_available", "historical_order_item_count"),
                      ("currency is not BRL", lambda df: df["currency"] != "BRL"),
                      ("duplicate supplier_id + product_id listing",
                       lambda df: df.duplicated(["supplier_id", "product_id"], keep="first"))],
    ),
    TableSpec(
        name="orders", file="orders.csv",
        columns={"order_id": "text", "buyer_org_id": "text", "order_status": "text",
                 **{c: "timestamp" for c in ORDER_TIMESTAMPS}},
        primary_key=["order_id"], required=["buyer_org_id", "order_status", "order_purchase_timestamp"],
        foreign_keys=[ForeignKey(["buyer_org_id"], "buyer_organizations", ["buyer_org_id"])],
        # The six chronology comparisons from the team EDA (Table 15)
        flag_rules=[_before("order_approved_at", "order_purchase_timestamp"),
                    _before("order_delivered_carrier_date", "order_purchase_timestamp"),
                    _before("order_delivered_customer_date", "order_purchase_timestamp"),
                    _before("order_delivered_carrier_date", "order_approved_at"),
                    _before("order_delivered_customer_date", "order_approved_at"),
                    _before("order_delivered_customer_date", "order_delivered_carrier_date"),
                    ("delivered_without_customer_date",
                     lambda df: (df["order_status"] == "delivered") & df["order_delivered_customer_date"].isna())],
    ),
    TableSpec(
        name="order_items", file="order_items.csv",
        columns={"order_line_id": "text", "order_id": "text", "order_item_id": "int", "catalog_id": "text",
                 "supplier_id": "text", "product_id": "text", "shipping_limit_date": "timestamp",
                 "item_price_brl": "decimal", "freight_value_brl": "decimal", "currency": "text"},
        primary_key=["order_line_id"],
        required=["order_id", "order_item_id", "catalog_id", "supplier_id", "product_id",
                  "item_price_brl", "freight_value_brl", "currency"],
        foreign_keys=[ForeignKey(["order_id"], "orders", ["order_id"]),
                      ForeignKey(["catalog_id", "supplier_id", "product_id"], "supplier_product_catalog",
                                 ["catalog_id", "supplier_id", "product_id"])],
        reject_rules=[_negative("item_price_brl", "freight_value_brl"),
                      ("order_item_id below 1", lambda df: _num(df, "order_item_id") < 1),
                      ("currency is not BRL", lambda df: df["currency"] != "BRL"),
                      ("duplicate order_id + order_item_id",
                       lambda df: df.duplicated(["order_id", "order_item_id"], keep="first"))],
        flag_rules=[_zero("freight_value_brl"), _zero("item_price_brl")],
    ),
    TableSpec(
        name="payments", file="payments.csv",
        columns={"payment_id": "text", "order_id": "text", "payment_sequential": "int",
                 "payment_type": "text", "payment_installments": "int", "payment_amount_brl": "decimal"},
        primary_key=["payment_id"],
        required=["order_id", "payment_sequential", "payment_type", "payment_amount_brl"],
        foreign_keys=[ForeignKey(["order_id"], "orders", ["order_id"])],
        reject_rules=[_negative("payment_installments", "payment_amount_brl"),
                      ("payment_sequential below 1", lambda df: _num(df, "payment_sequential") < 1),
                      ("duplicate order_id + payment_sequential",
                       lambda df: df.duplicated(["order_id", "payment_sequential"], keep="first"))],
        flag_rules=[_zero("payment_amount_brl"), _zero("payment_installments"),
                    ("payment_type_not_defined", lambda df: df["payment_type"] == "not_defined")],
    ),
    TableSpec(
        name="reviews", file="reviews.csv",
        columns={"review_id": "text", "order_id": "text", "review_score": "int",
                 "review_comment_title": "text", "review_comment_message": "text",
                 "review_creation_date": "timestamp", "review_answer_timestamp": "timestamp"},
        primary_key=["review_id", "order_id"], required=["review_score"],
        foreign_keys=[ForeignKey(["order_id"], "orders", ["order_id"])],
        reject_rules=[("review_score not between 1 and 5",
                       lambda df: ~_num(df, "review_score").between(1, 5))],
        flag_rules=[("review_id_shared_by_several_orders",
                     lambda df: df.duplicated("review_id", keep=False)),
                    _before("review_answer_timestamp", "review_creation_date")],
    ),
    TableSpec(
        name="order_deliveries", file="order_deliveries.csv",
        columns={"order_id": "text", "order_status": "text", "order_delivered_carrier_date": "timestamp",
                 "order_delivered_customer_date": "timestamp", "order_estimated_delivery_date": "timestamp",
                 "delivery_record_basis": "text"},
        primary_key=["order_id"], required=["order_status"],
        foreign_keys=[ForeignKey(["order_id"], "orders", ["order_id"])],
        # Late delivery is a business measure (dashboard), not a data-quality problem, so it is not flagged.
        # Consistency with orders is checked after the load (etl/reconcile.py).
    ),
]

TABLES_BY_NAME = {t.name: t for t in TABLES}
TABLES_BY_FILE = {t.file: t for t in TABLES}
