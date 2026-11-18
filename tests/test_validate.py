import pandas as pd
import pytest

from etl.mappings import TABLES_BY_NAME
from etl.validate import SchemaError, duplicate_key_mask, orphan_mask, validate


def _orders(rows):
    cols = ["order_id", "buyer_org_id", "order_status", "order_purchase_timestamp", "order_approved_at",
            "order_delivered_carrier_date", "order_delivered_customer_date", "order_estimated_delivery_date"]
    return pd.DataFrame(rows, columns=cols, dtype=str)


def test_duplicate_key_mask_keeps_first():
    df = pd.DataFrame({"k": ["a", "b", "a", "a"]})
    assert duplicate_key_mask(df, ["k"]).tolist() == [False, False, True, True]


def test_orphan_mask_ignores_nulls():
    df = pd.DataFrame({"fk": ["p1", "zz", None]})
    assert orphan_mask(df, ["fk"], {("p1",)}).tolist() == [False, True, False]


def test_missing_column_is_a_schema_error():
    with pytest.raises(SchemaError):
        validate(pd.DataFrame({"order_id": ["1"]}), TABLES_BY_NAME["orders"], {"buyer_organizations": set()})


def test_orders_rejects_and_flags():
    raw = _orders([
        ["o1", "b1", "delivered", "2017-10-02 10:00:00", "2017-10-02 11:00:00",
         "2017-10-01 09:00:00", "2017-10-10 10:00:00", "2017-10-18 00:00:00"],   # carrier before approval -> flag
        ["o1", "b1", "delivered", "2017-10-02 10:00:00", "", "", "", ""],          # duplicate PK -> reject
        ["o2", "nobody", "shipped", "2017-10-02 10:00:00", "", "", "", ""],        # unknown buyer -> reject
        ["o3", "b1", "shipped", "not a date", "", "", "", ""],                     # bad required date -> reject
        ["o4", "b1", "delivered", "2017-10-02 10:00:00", "", "", "", ""],          # delivered w/o date -> flag
    ])
    res = validate(raw, TABLES_BY_NAME["orders"], {"buyer_organizations": {("b1",)}})

    assert res.accepted["order_id"].tolist() == ["o1", "o4"]
    assert res.rejects["reason"].tolist() == [
        "duplicate primary key (order_id)",
        "buyer_org_id not found in buyer_organizations",
        "invalid timestamp in order_purchase_timestamp",
    ]
    flagged = set(map(tuple, res.flags[["record_key", "rule"]].values))
    assert ("o1", "order_delivered_carrier_date_before_order_approved_at") in flagged
    assert ("o4", "delivered_without_customer_date") in flagged
    assert res.accepted.loc[1, "order_approved_at"] is None     # empty string became NULL


def test_reviews_composite_key_allows_shared_review_id():
    raw = pd.DataFrame({
        "review_id": ["r1", "r1", "r2"], "order_id": ["o1", "o2", "o1"], "review_score": ["5", "4", "9"],
        "review_comment_title": ["", "", ""], "review_comment_message": ["", "", ""],
        "review_creation_date": ["2018-01-01", "2018-01-01", "2018-01-01"],
        "review_answer_timestamp": ["2018-01-02 00:00:00"] * 3,
    })
    res = validate(raw, TABLES_BY_NAME["reviews"], {"orders": {("o1",), ("o2",)}})
    assert len(res.accepted) == 2                                     # r1 twice is fine (different orders)
    assert res.rejects["reason"].tolist() == ["review_score not between 1 and 5"]
    assert (res.flags["rule"] == "review_id_shared_by_several_orders").sum() == 2
