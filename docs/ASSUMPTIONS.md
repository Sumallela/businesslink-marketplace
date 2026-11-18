# Assumptions

1. **product_categories has 74 rows**, the package summary (`04_transformation_summary.json`) says 71. All 74 rows are
   loaded (the team EDA also counted 74); the difference is assumed to be categories added as a "classroom supplement"
   (the data dictionary mentions supplemented English names). Confirm with the instructor.
2. **No sample ETL script was supplied**; the ETL was written from scratch from the instructions, data dictionary and EDA.
3. The data is a **synthetic B2B adaptation of historical B2C Olist data (2016–2018)**, amounts in BRL. Buyer/supplier
   names, industries, sizes, segments and catalog stock/listing fields are synthetic.
4. `order_item_id` is a line sequence, **not a quantity** — each order_items row is one order line.
5. Reviews and delivery timestamps are **order-level**; they are not supplier or product ratings/tracking.
6. Timestamps have no time zone in the source and are stored as `TIMESTAMP` (no time zone), assumed Brazil local time.
7. The 249 orders whose payments differ from items + freight by more than R$1 are left as-is (installment interest or
   vouchers are likely causes); they are listed in DATA_QUALITY.md.
8. 775 orders have no order lines and 1 order has no payment; these match the original Olist data and are kept.
