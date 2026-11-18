# BusinessLink Marketplace — B2B Capstone Dataset

## Scenario
BusinessLink Marketplace is a fictional B2B marketplace. Business buyers browse a product catalog, compare supplier listings, and place orders. Suppliers list products and fulfill orders. Students design and query a relational database and build a management dashboard.

## What this dataset is
This is a **synthetic B2B teaching adaptation of the public Olist Brazilian E-Commerce dataset**. Olist's source transactions are marketplace/e-commerce transactions and are not documented as B2B transactions. The transformation maps unique Olist customers to fictional buyer organizations, retains Olist sellers as suppliers, and adds clearly synthetic organization and catalog attributes. Do not describe the source transactions as actual B2B purchases.

## Files
- `buyer_organizations.csv` — one synthetic business buyer per Olist unique customer.
- `suppliers.csv` — Olist sellers represented as marketplace suppliers; supplier labels/segments/sizes are synthetic.
- `product_categories.csv` — source category names and English translations.
- `products.csv` — Olist product attributes.
- `supplier_product_catalog.csv` — observed supplier-product combinations, median historical item price, plus synthetic stock/listing fields.
- `orders.csv` — original order status/timestamps, mapped to buyer organizations.
- `order_items.csv` — original order lines, prices and freight, linked to supplier catalog listings.
- `payments.csv` — original payment records.
- `reviews.csv` — original order-level reviews.
- `order_deliveries.csv` — order-level delivery timestamps; this is not supplier-specific shipment tracking.
- `postal_geolocation.csv` — postal-prefix centroid reference.

## Critical interpretation notes
1. Currency is Brazilian real (BRL); no currency conversion has been applied.
2. The original data spans 2016–2018. It is historical, not current marketplace activity.
3. Synthetic buyer names, buyer industries/sizes, supplier names/segments/sizes, catalog availability, inventory quantities, and listing status were generated for teaching.
4. Catalog list price is the median observed transaction item price for a supplier-product pair. It is a historical proxy, not a current offer price.
5. Olist's `order_item_id` is a line sequence. The source does not provide a reliable quantity field; each row is an order line, not a quantity count.
6. Reviews are attached to orders, not individual suppliers or products. Do not interpret them as supplier ratings.
7. Delivery timestamps are order-level. An order may contain items from multiple suppliers, so these timestamps should not be treated as supplier-specific performance measures.
8. Postal geolocation is aggregated to one centroid per postal-code prefix.
9. Some source records may have missing timestamps, category values, or geolocation matches. Students should profile and document missingness rather than silently discard records.

## Suggested student tasks
1. Profile all tables and prepare a data-quality report.
2. Draw an ERD and explain primary/foreign keys and normalization choices.
3. Load the CSVs into PostgreSQL using `01_postgresql_schema.sql`.
4. Write SQL for buyer, supplier, product, order, payment, and delivery analysis.
5. Design a star schema using `02_star_schema_design.sql`.
6. Build a dashboard with marketplace, supplier, buyer, product/category, and order-delivery views.
7. Recommend operational improvements, while distinguishing source facts from synthetic assumptions.

## Suggested dashboard KPIs
- Total order value (sum of item prices; state clearly whether freight is excluded).
- Number of orders and order lines.
- Average order value.
- Monthly order value and order count.
- Sales by product category.
- Supplier sales, order-line count, and catalog breadth.
- Buyer organization spend and order frequency.
- Cancellation and delivery-on-time rates (define denominator and treatment of missing dates).
- Payment mix.
- Average review score at the order level.

## Suggested SQL questions
1. Monthly order count and item sales.
2. Top 10 suppliers by item sales.
3. Top 10 product categories by item sales.
4. Buyers ranked by total spend.
5. Average order value by buyer industry.
6. Supplier catalog breadth and observed sales.
7. Product price range across suppliers.
8. Payment method distribution.
9. Order status distribution.
10. Late-delivery rate by month.
11. Average days from purchase to delivery.
12. Repeat-buyer analysis.
13. Supplier share of marketplace sales.
14. Category sales using a window function for rank.
15. Month-over-month sales change using `LAG`.
16. Buyers whose spend exceeds the overall buyer average.
17. Products listed by multiple suppliers.
18. Orders containing products from more than one supplier.

## Source and attribution
Source: Olist Brazilian E-Commerce Public Dataset, distributed via Kaggle by Olist. The original dataset is commonly distributed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0) license. Verify the current source-page license and follow its attribution, noncommercial, and share-alike terms before redistributing. Suggested citation: “Olist, Brazilian E-Commerce Public Dataset, Kaggle.”
