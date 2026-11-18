# Data-quality report (ETL output)

Generated 2026-11-18 03:51 by `python -m etl.reconcile`.

**Rejected** rows are not loaded (see `rejects/`). **Flagged** rows are loaded, and the note sits in `etl_dq_flags` so the app and SQL can show or exclude them.

## Flags by rule (rows loaded, needs attention)

| table | rule | rows flagged |
|---|---|---|
| buyer_organizations | missing_coordinates | 268 |
| order_items | zero_freight_value_brl | 383 |
| orders | order_delivered_carrier_date_before_order_approved_at | 1359 |
| orders | order_delivered_carrier_date_before_order_purchase_timestamp | 166 |
| orders | order_delivered_customer_date_before_order_approved_at | 61 |
| orders | order_delivered_customer_date_before_order_delivered_carrier_date | 23 |
| orders | delivered_without_customer_date | 8 |
| payments | zero_payment_amount_brl | 9 |
| payments | payment_type_not_defined | 3 |
| payments | zero_payment_installments | 2 |
| products | missing_name_description_photo | 610 |
| products | zero_weight_g | 4 |
| products | missing_weight_or_dimensions | 2 |
| reviews | review_id_shared_by_several_orders | 1603 |
| suppliers | missing_coordinates | 7 |

## Post-load consistency checks

| check | meaning | count |
|---|---|---|
| orders_without_items | Orders with no order line (often canceled/unavailable orders in the source). | 775 |
| orders_without_payments | Orders with no payment record. | 1 |
| orders_without_delivery_record | Orders missing their 1:1 order_deliveries row. | 0 |
| payment_total_differs_from_items_plus_freight | Orders whose payments differ from item price + freight by more than R$1.00 (installment interest/vouchers can explain this; do NOT add payments to item sales). | 249 |
| delivery_record_differs_from_order | order_deliveries status/dates not equal to the same order's values. | 0 |
| order_line_listing_mismatch | Order lines whose supplier/product differ from their catalog listing (enforced by the composite foreign key, so must be 0). | 0 |
| buyer_postal_prefix_not_in_geolocation | Buyers whose postal prefix has no centroid (logical link, not an FK). | 268 |
| supplier_postal_prefix_not_in_geolocation | Suppliers whose postal prefix has no centroid. | 7 |
| orders_with_more_than_one_review | Orders carrying more than one review record. | 547 |
| products_listed_by_multiple_suppliers | Informational: products offered by 2+ suppliers. | 1225 |
