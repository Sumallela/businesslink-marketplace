-- Suggested dimensional model for dashboard reporting.
-- Students can build ETL from the normalized operational tables.
CREATE TABLE dim_buyer (
  buyer_key BIGSERIAL PRIMARY KEY, buyer_org_id TEXT UNIQUE,
  buyer_org_name TEXT, industry TEXT, organization_size TEXT, city TEXT, state CHAR(2)
);
CREATE TABLE dim_supplier (
  supplier_key BIGSERIAL PRIMARY KEY, supplier_id TEXT UNIQUE,
  supplier_name TEXT, supplier_segment TEXT, supplier_size TEXT, city TEXT, state CHAR(2)
);
CREATE TABLE dim_product (
  product_key BIGSERIAL PRIMARY KEY, product_id TEXT UNIQUE,
  category_name_english TEXT, weight_g NUMERIC
);
CREATE TABLE dim_date (
  date_key INTEGER PRIMARY KEY, calendar_date DATE, year INTEGER, quarter INTEGER,
  month INTEGER, month_name TEXT, day_of_week INTEGER
);
CREATE TABLE fact_order_line (
  order_line_key BIGSERIAL PRIMARY KEY, source_order_line_id TEXT UNIQUE,
  order_id TEXT, buyer_key BIGINT REFERENCES dim_buyer(buyer_key),
  supplier_key BIGINT REFERENCES dim_supplier(supplier_key),
  product_key BIGINT REFERENCES dim_product(product_key),
  order_date_key INTEGER REFERENCES dim_date(date_key),
  quantity INTEGER, item_sales_brl NUMERIC(12,2), freight_brl NUMERIC(12,2)
);
-- Olist order_item_id is a line sequence, not a product quantity. Treat each row as one order line;
-- quantity should be interpreted as 1 unless the instructor explicitly introduces a synthetic quantity.
