-- BusinessLink Marketplace: PostgreSQL operational schema
-- Load CSVs after creating tables. All original transaction facts remain sourced from Olist.
CREATE TABLE buyer_organizations (
  buyer_org_id TEXT PRIMARY KEY, buyer_org_name TEXT NOT NULL, industry TEXT,
  organization_size TEXT, city TEXT, state CHAR(2), postal_code_prefix CHAR(5),
  latitude NUMERIC(10,7), longitude NUMERIC(10,7), source_customer_unique_id TEXT
);
CREATE TABLE suppliers (
  supplier_id TEXT PRIMARY KEY, supplier_name TEXT NOT NULL, supplier_segment TEXT,
  supplier_size TEXT, city TEXT, state CHAR(2), postal_code_prefix CHAR(5),
  latitude NUMERIC(10,7), longitude NUMERIC(10,7)
);
CREATE TABLE product_categories (
  category_id TEXT PRIMARY KEY, category_name_source TEXT, category_name_english TEXT
);
CREATE TABLE products (
  product_id TEXT PRIMARY KEY, category_id TEXT REFERENCES product_categories(category_id),
  source_name_length INTEGER, source_description_length INTEGER, photo_count INTEGER,
  weight_g NUMERIC, length_cm NUMERIC, height_cm NUMERIC, width_cm NUMERIC
);
CREATE TABLE supplier_product_catalog (
  catalog_id TEXT PRIMARY KEY, supplier_id TEXT NOT NULL REFERENCES suppliers(supplier_id),
  product_id TEXT NOT NULL REFERENCES products(product_id), list_price_brl NUMERIC(12,2),
  availability_status TEXT, quantity_available INTEGER, listing_status TEXT,
  historical_order_item_count INTEGER, currency CHAR(3), price_basis TEXT,
  UNIQUE(supplier_id, product_id)
);
CREATE TABLE orders (
  order_id TEXT PRIMARY KEY, buyer_org_id TEXT REFERENCES buyer_organizations(buyer_org_id),
  order_status TEXT, order_purchase_timestamp TIMESTAMP, order_approved_at TIMESTAMP,
  order_delivered_carrier_date TIMESTAMP, order_delivered_customer_date TIMESTAMP,
  order_estimated_delivery_date TIMESTAMP
);
CREATE TABLE order_items (
  order_line_id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(order_id),
  order_item_id INTEGER, catalog_id TEXT REFERENCES supplier_product_catalog(catalog_id),
  supplier_id TEXT REFERENCES suppliers(supplier_id), product_id TEXT REFERENCES products(product_id),
  shipping_limit_date TIMESTAMP, item_price_brl NUMERIC(12,2),
  freight_value_brl NUMERIC(12,2), currency CHAR(3)
);
CREATE TABLE payments (
  payment_id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(order_id),
  payment_sequential INTEGER, payment_type TEXT, payment_installments INTEGER,
  payment_amount_brl NUMERIC(12,2)
);
CREATE TABLE reviews (
  review_id TEXT PRIMARY KEY, order_id TEXT REFERENCES orders(order_id), review_score INTEGER,
  review_comment_title TEXT, review_comment_message TEXT,
  review_creation_date TIMESTAMP, review_answer_timestamp TIMESTAMP
);
CREATE TABLE order_deliveries (
  order_id TEXT PRIMARY KEY REFERENCES orders(order_id), order_status TEXT,
  order_delivered_carrier_date TIMESTAMP, order_delivered_customer_date TIMESTAMP,
  order_estimated_delivery_date TIMESTAMP, delivery_record_basis TEXT
);
CREATE TABLE postal_geolocation (
  postal_code_prefix CHAR(5) PRIMARY KEY, latitude NUMERIC(10,7), longitude NUMERIC(10,7),
  city TEXT, state CHAR(2)
);
CREATE INDEX idx_orders_buyer ON orders(buyer_org_id);
CREATE INDEX idx_orders_purchase_date ON orders(order_purchase_timestamp);
CREATE INDEX idx_order_items_order ON order_items(order_id);
CREATE INDEX idx_order_items_supplier ON order_items(supplier_id);
CREATE INDEX idx_order_items_product ON order_items(product_id);
CREATE INDEX idx_catalog_product ON supplier_product_catalog(product_id);
