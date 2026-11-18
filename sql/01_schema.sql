-- BusinessLink Marketplace: MySQL 8.4 operational schema
-- Column types follow the team ERD (MySQL Workbench) and the EDA; tables, keys and relationships follow the
-- instructor's 01_postgresql_schema.sql (docs/source/). Team changes (each one in docs/DECISIONS.md):
--   * reviews: primary key is (review_id, order_id) because review_id repeats in the source (EDA)
--   * NOT NULL / CHECK constraints where the data dictionary says a value is always present / valid
--   * order_items -> catalog is a composite FK so a line's supplier/product must match its listing
--   * postal_code_prefix -> postal_geolocation stays a logical link (data dictionary: "not enforced")
--   * etl_load_log and etl_dq_flags hold the ETL run log and the data-quality flags
-- Runs automatically the first time the Docker database starts (docker-entrypoint-initdb.d), in DB_NAME.

SET NAMES utf8mb4;

-- ---------------------------------------------------------------- reference data
CREATE TABLE product_categories (
  category_id            VARCHAR(100) PRIMARY KEY,
  category_name_source   VARCHAR(255),
  category_name_english  VARCHAR(255)
);

CREATE TABLE postal_geolocation (
  postal_code_prefix  CHAR(5) PRIMARY KEY,
  latitude            DECIMAL(10,7),
  longitude           DECIMAL(10,7),
  city                VARCHAR(100),
  state               CHAR(2),
  CONSTRAINT chk_geo_postal CHECK (postal_code_prefix REGEXP '^[0-9]{5}$'),
  CONSTRAINT chk_geo_lat    CHECK (latitude  BETWEEN -90  AND 90),
  CONSTRAINT chk_geo_long   CHECK (longitude BETWEEN -180 AND 180)
);

-- ---------------------------------------------------------------- parties
CREATE TABLE buyer_organizations (
  buyer_org_id               VARCHAR(100) PRIMARY KEY,
  buyer_org_name             VARCHAR(255) NOT NULL,
  industry                   VARCHAR(100),
  organization_size          VARCHAR(50),
  city                       VARCHAR(100),
  state                      CHAR(2),
  postal_code_prefix         CHAR(5),
  latitude                   DECIMAL(10,7),
  longitude                  DECIMAL(10,7),
  source_customer_unique_id  VARCHAR(100),
  CONSTRAINT chk_buyer_size   CHECK (organization_size IN ('Micro','Small','Medium','Large')),
  CONSTRAINT chk_buyer_postal CHECK (postal_code_prefix REGEXP '^[0-9]{5}$'),
  CONSTRAINT chk_buyer_lat    CHECK (latitude  BETWEEN -90  AND 90),
  CONSTRAINT chk_buyer_long   CHECK (longitude BETWEEN -180 AND 180)
);

CREATE TABLE suppliers (
  supplier_id         VARCHAR(100) PRIMARY KEY,
  supplier_name       VARCHAR(255) NOT NULL,
  supplier_segment    VARCHAR(100),
  supplier_size       VARCHAR(50),
  city                VARCHAR(100),
  state               CHAR(2),
  postal_code_prefix  CHAR(5),
  latitude            DECIMAL(10,7),
  longitude           DECIMAL(10,7),
  CONSTRAINT chk_supplier_size   CHECK (supplier_size IN ('Small','Medium','Large')),
  CONSTRAINT chk_supplier_postal CHECK (postal_code_prefix REGEXP '^[0-9]{5}$'),
  CONSTRAINT chk_supplier_lat    CHECK (latitude  BETWEEN -90  AND 90),
  CONSTRAINT chk_supplier_long   CHECK (longitude BETWEEN -180 AND 180)
);

-- ---------------------------------------------------------------- product catalog
CREATE TABLE products (
  product_id                 VARCHAR(100) PRIMARY KEY,
  category_id                VARCHAR(100),
  source_name_length         INT,
  source_description_length  INT,
  photo_count                INT,
  weight_g                   DECIMAL(10,2),
  length_cm                  DECIMAL(10,2),
  height_cm                  DECIMAL(10,2),
  width_cm                   DECIMAL(10,2),
  CONSTRAINT fk_products_category FOREIGN KEY (category_id) REFERENCES product_categories(category_id),
  CONSTRAINT chk_products_nonneg CHECK (source_name_length >= 0 AND source_description_length >= 0
    AND photo_count >= 0 AND weight_g >= 0 AND length_cm >= 0 AND height_cm >= 0 AND width_cm >= 0)
);

CREATE TABLE supplier_product_catalog (
  catalog_id                   VARCHAR(100) PRIMARY KEY,
  supplier_id                  VARCHAR(100) NOT NULL,
  product_id                   VARCHAR(100) NOT NULL,
  list_price_brl               DECIMAL(12,2),
  availability_status          VARCHAR(50),
  quantity_available           INT,
  listing_status               VARCHAR(50),
  historical_order_item_count  INT,
  currency                     CHAR(3) NOT NULL DEFAULT 'BRL',
  price_basis                  VARCHAR(255),
  CONSTRAINT uq_catalog_supplier_product UNIQUE (supplier_id, product_id),
  CONSTRAINT uq_catalog_listing UNIQUE (catalog_id, supplier_id, product_id),  -- target of order_items FK
  CONSTRAINT fk_catalog_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
  CONSTRAINT fk_catalog_product  FOREIGN KEY (product_id)  REFERENCES products(product_id),
  CONSTRAINT chk_catalog_nonneg   CHECK (list_price_brl >= 0 AND quantity_available >= 0
    AND historical_order_item_count >= 0),
  CONSTRAINT chk_catalog_currency CHECK (currency = 'BRL')
);

-- ---------------------------------------------------------------- transactions
CREATE TABLE orders (
  order_id                       VARCHAR(100) PRIMARY KEY,
  buyer_org_id                   VARCHAR(100) NOT NULL,
  order_status                   VARCHAR(50) NOT NULL,
  order_purchase_timestamp       DATETIME NOT NULL,
  order_approved_at              DATETIME,
  order_delivered_carrier_date   DATETIME,
  order_delivered_customer_date  DATETIME,
  order_estimated_delivery_date  DATETIME,
  CONSTRAINT fk_orders_buyer FOREIGN KEY (buyer_org_id) REFERENCES buyer_organizations(buyer_org_id),
  INDEX idx_orders_purchase_date (order_purchase_timestamp)
);

CREATE TABLE order_items (
  order_line_id        VARCHAR(100) PRIMARY KEY,
  order_id             VARCHAR(100) NOT NULL,
  order_item_id        INT NOT NULL,                -- line sequence, NOT a quantity
  catalog_id           VARCHAR(100) NOT NULL,
  supplier_id          VARCHAR(100) NOT NULL,
  product_id           VARCHAR(100) NOT NULL,
  shipping_limit_date  DATETIME,
  item_price_brl       DECIMAL(12,2) NOT NULL,
  freight_value_brl    DECIMAL(12,2) NOT NULL,
  currency             CHAR(3) NOT NULL DEFAULT 'BRL',
  CONSTRAINT uq_order_items_line UNIQUE (order_id, order_item_id),
  CONSTRAINT fk_items_order    FOREIGN KEY (order_id)    REFERENCES orders(order_id),
  CONSTRAINT fk_items_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
  CONSTRAINT fk_items_product  FOREIGN KEY (product_id)  REFERENCES products(product_id),
  CONSTRAINT fk_items_listing  FOREIGN KEY (catalog_id, supplier_id, product_id)
    REFERENCES supplier_product_catalog (catalog_id, supplier_id, product_id),
  CONSTRAINT chk_items_seq      CHECK (order_item_id >= 1),
  CONSTRAINT chk_items_nonneg   CHECK (item_price_brl >= 0 AND freight_value_brl >= 0),
  CONSTRAINT chk_items_currency CHECK (currency = 'BRL')
);

CREATE TABLE payments (
  payment_id            VARCHAR(100) PRIMARY KEY,
  order_id              VARCHAR(100) NOT NULL,
  payment_sequential    INT NOT NULL,
  payment_type          VARCHAR(50) NOT NULL,
  payment_installments  INT,
  payment_amount_brl    DECIMAL(12,2) NOT NULL,
  CONSTRAINT uq_payments_seq UNIQUE (order_id, payment_sequential),
  CONSTRAINT fk_payments_order FOREIGN KEY (order_id) REFERENCES orders(order_id),
  CONSTRAINT chk_payments_seq    CHECK (payment_sequential >= 1),
  CONSTRAINT chk_payments_nonneg CHECK (payment_installments >= 0 AND payment_amount_brl >= 0)
);

-- ---------------------------------------------------------------- fulfilment + feedback
CREATE TABLE reviews (
  review_id                VARCHAR(100) NOT NULL,
  order_id                 VARCHAR(100) NOT NULL,
  review_score             INT NOT NULL,
  review_comment_title     TEXT,
  review_comment_message   TEXT,
  review_creation_date     DATETIME,
  review_answer_timestamp  DATETIME,
  PRIMARY KEY (review_id, order_id),               -- review_id alone repeats in the source (EDA)
  CONSTRAINT fk_reviews_order FOREIGN KEY (order_id) REFERENCES orders(order_id),
  CONSTRAINT chk_reviews_score CHECK (review_score BETWEEN 1 AND 5)
);

CREATE TABLE order_deliveries (
  order_id                       VARCHAR(100) PRIMARY KEY,
  order_status                   VARCHAR(50) NOT NULL,
  order_delivered_carrier_date   DATETIME,
  order_delivered_customer_date  DATETIME,
  order_estimated_delivery_date  DATETIME,
  delivery_record_basis          VARCHAR(255),
  CONSTRAINT fk_deliveries_order FOREIGN KEY (order_id) REFERENCES orders(order_id)
);
-- InnoDB creates an index for every foreign key automatically (buyer, order, supplier, product, catalog, ...).

-- ---------------------------------------------------------------- ETL audit (run log + data-quality flags)
CREATE TABLE etl_load_log (
  run_id        VARCHAR(20) NOT NULL,
  table_name    VARCHAR(64) NOT NULL,
  source_file   VARCHAR(255),
  rows_read     INT,
  rows_loaded   INT,
  rows_rejected INT,
  rows_flagged  INT,
  status        VARCHAR(10) NOT NULL,          -- ok | failed
  message       TEXT,
  started_at    DATETIME NOT NULL,
  finished_at   DATETIME,
  PRIMARY KEY (run_id, table_name)
);

-- A flag marks a row that WAS loaded but needs a human to look at it
-- (e.g. carrier hand-off before approval, zero freight). Rejected rows go to rejects/*.csv instead.
CREATE TABLE etl_dq_flags (
  run_id      VARCHAR(20) NOT NULL,
  table_name  VARCHAR(64) NOT NULL,
  record_key  VARCHAR(255) NOT NULL,
  rule        VARCHAR(100) NOT NULL,
  detail      VARCHAR(255),
  INDEX idx_dq_flags_rule (table_name, rule)
);
