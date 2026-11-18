import pandas as pd

from etl.clean import cast_decimal, cast_int, cast_postal, cast_timestamp, clean_text, standardize_columns


def test_standardize_columns():
    df = pd.DataFrame(columns=[" Order ID ", "item-price (BRL)"])
    assert list(standardize_columns(df).columns) == ["order_id", "item_price_brl"]


def test_clean_text_trims_and_blanks_to_none():
    assert clean_text(pd.Series(["  a ", "", "   ", None])).tolist() == ["a", None, None, None]


def test_cast_int_accepts_float_text_and_flags_garbage():
    cleaned, bad = cast_int(pd.Series(["40.0", "7", "", "4.5", "abc"]))
    assert cleaned.tolist() == ["40", "7", None, None, None]
    assert bad.tolist() == [False, False, False, True, True]


def test_cast_decimal_keeps_original_text():
    cleaned, bad = cast_decimal(pd.Series(["-23.499062689784743", "58.9", "", "x", "inf"]))
    assert cleaned.tolist() == ["-23.499062689784743", "58.9", None, None, None]
    assert bad.tolist() == [False, False, False, True, True]


def test_cast_timestamp_normalises_and_flags_bad_dates():
    cleaned, bad = cast_timestamp(pd.Series(["2017-10-02 10:56:33", "2018-01-18", "", "2018-13-45 00:00:00"]))
    assert cleaned.tolist() == ["2017-10-02 10:56:33", "2018-01-18 00:00:00", None, None]
    assert bad.tolist() == [False, False, False, True]


def test_cast_postal_restores_leading_zero():
    cleaned, bad, padded = cast_postal(pd.Series(["01001", "6273", "", "12-34"]))
    assert cleaned.tolist() == ["01001", "06273", None, None]
    assert bad.tolist() == [False, False, False, True]
    assert padded.tolist() == [False, True, False, False]
