# Day 4 — Streams and Tasks: Hands-On Pipeline

## What You Will Build

A fully automated RAW → STAGING → MART pipeline for an e-commerce orders dataset.

You will insert, update, and delete data in the RAW layer, watch Streams capture every change, and see Tasks automatically propagate those changes through Staging into the Mart — without you running anything manually after the initial setup.

**The pipeline:**
```
ORDERS_RAW  ──[stream]──►  STG_ORDERS  ──────────►  ORDERS_MART
     │                          │                        │
  INSERT                    MERGE (upsert)           MERGE (upsert)
  UPDATE                                                 │
  DELETE                                                 │
                                                         │
              RAW_TO_STG_TASK (root, 1 min)              │
              STG_TO_MART_TASK (child, after root) ──────┘
              Both tasks in ECOMM_DB.RAW_DATA schema
```

> **Important:** Both tasks must be in the **same schema** for `AFTER` chaining to work. We keep both in `ECOMM_DB.RAW_DATA`.

---

## Step 1 — Set Up the Schema and Tables

```sql
USE ROLE SYSADMIN;
USE WAREHOUSE COMPUTE_WH;

CREATE DATABASE IF NOT EXISTS ECOMM_DB;
CREATE SCHEMA  IF NOT EXISTS ECOMM_DB.RAW_DATA;
CREATE SCHEMA  IF NOT EXISTS ECOMM_DB.STAGING;
CREATE SCHEMA  IF NOT EXISTS ECOMM_DB.MARTS;
```

### RAW table

```sql
USE SCHEMA ECOMM_DB.RAW_DATA;

CREATE OR REPLACE TABLE ORDERS_RAW (
    order_id       NUMBER         PRIMARY KEY,
    customer_id    NUMBER         NOT NULL,
    customer_name  VARCHAR(200),
    product        VARCHAR(200),
    quantity       NUMBER         DEFAULT 1,
    unit_price     NUMBER(10,2),
    total_amount   NUMBER(12,2),
    status         VARCHAR(50),   -- PENDING, CONFIRMED, SHIPPED, DELIVERED, CANCELLED
    order_date     DATE,
    updated_at     TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP()
);
```

### STAGING table

```sql
USE SCHEMA ECOMM_DB.STAGING;

CREATE OR REPLACE TABLE STG_ORDERS (
    order_id       NUMBER         PRIMARY KEY,
    customer_id    NUMBER,
    customer_name  VARCHAR(200),
    product        VARCHAR(200),
    quantity       NUMBER,
    unit_price     NUMBER(10,2),
    total_amount   NUMBER(12,2),
    status         VARCHAR(50),
    order_date     DATE,
    is_deleted     BOOLEAN        DEFAULT FALSE,
    stg_updated_at TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP()
);
```

### MART table

```sql
USE SCHEMA ECOMM_DB.MARTS;

CREATE TABLE IF NOT EXISTS ORDERS_MART (
    order_date        DATE           PRIMARY KEY,
    total_orders      NUMBER,
    confirmed_orders  NUMBER,
    shipped_orders    NUMBER,
    delivered_orders  NUMBER,
    cancelled_orders  NUMBER,
    total_revenue     NUMBER(14,2),
    avg_order_value   NUMBER(10,2),
    mart_updated_at   TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP()
);
```

> `ORDERS_MART` uses `CREATE TABLE IF NOT EXISTS` — not `CREATE OR REPLACE` — so existing mart data is not wiped when you re-run setup.

---

## Step 2 — Create Streams

```sql
-- Stream on RAW: captures INSERT / UPDATE / DELETE on ORDERS_RAW
CREATE OR REPLACE STREAM ECOMM_DB.RAW_DATA.ORDERS_RAW_STREAM
  ON TABLE ECOMM_DB.RAW_DATA.ORDERS_RAW
  COMMENT = 'Captures all DML changes on ORDERS_RAW';

-- Verify
SHOW STREAMS IN DATABASE ECOMM_DB;
```

> Re-creating tables (Step 1) drops their streams. Always re-run Step 2 after re-running Step 1.

---

## Step 3 — The MERGE Logic (understand before creating tasks)

### MERGE 1: RAW → STAGING

Handles all three change types from the stream in one statement:

```sql
MERGE INTO ECOMM_DB.STAGING.STG_ORDERS AS tgt
USING (
    SELECT * FROM ECOMM_DB.RAW_DATA.ORDERS_RAW_STREAM
) AS src
ON tgt.order_id = src.order_id

-- New insert OR the new-value row of an update (both have ACTION = 'INSERT')
WHEN MATCHED AND src.METADATA$ACTION = 'INSERT' THEN
    UPDATE SET
        tgt.customer_id    = src.customer_id,
        tgt.customer_name  = src.customer_name,
        tgt.product        = src.product,
        tgt.quantity       = src.quantity,
        tgt.unit_price     = src.unit_price,
        tgt.total_amount   = src.total_amount,
        tgt.status         = src.status,
        tgt.order_date     = src.order_date,
        tgt.is_deleted     = FALSE,
        tgt.stg_updated_at = CURRENT_TIMESTAMP()

-- Hard delete from RAW → soft delete in STAGING
WHEN MATCHED AND src.METADATA$ACTION = 'DELETE' AND src.METADATA$ISUPDATE = FALSE THEN
    UPDATE SET
        tgt.is_deleted     = TRUE,
        tgt.stg_updated_at = CURRENT_TIMESTAMP()

-- Brand new row not yet in STAGING
WHEN NOT MATCHED AND src.METADATA$ACTION = 'INSERT' THEN
    INSERT (order_id, customer_id, customer_name, product, quantity,
            unit_price, total_amount, status, order_date, is_deleted, stg_updated_at)
    VALUES (src.order_id, src.customer_id, src.customer_name, src.product, src.quantity,
            src.unit_price, src.total_amount, src.status, src.order_date, FALSE, CURRENT_TIMESTAMP());
```

### MERGE 2: STAGING → MART

Re-aggregates the daily summary from staging, excluding soft-deleted rows:

```sql
MERGE INTO ECOMM_DB.MARTS.ORDERS_MART AS tgt
USING (
    SELECT
        order_date,
        COUNT(*)                                                AS total_orders,
        SUM(CASE WHEN status = 'CONFIRMED'  THEN 1 ELSE 0 END) AS confirmed_orders,
        SUM(CASE WHEN status = 'SHIPPED'    THEN 1 ELSE 0 END) AS shipped_orders,
        SUM(CASE WHEN status = 'DELIVERED'  THEN 1 ELSE 0 END) AS delivered_orders,
        SUM(CASE WHEN status = 'CANCELLED'  THEN 1 ELSE 0 END) AS cancelled_orders,
        SUM(total_amount)                                       AS total_revenue,
        AVG(total_amount)                                       AS avg_order_value
    FROM ECOMM_DB.STAGING.STG_ORDERS
    WHERE is_deleted = FALSE
    GROUP BY order_date
) AS src
ON tgt.order_date = src.order_date
WHEN MATCHED THEN
    UPDATE SET
        tgt.total_orders     = src.total_orders,
        tgt.confirmed_orders = src.confirmed_orders,
        tgt.shipped_orders   = src.shipped_orders,
        tgt.delivered_orders = src.delivered_orders,
        tgt.cancelled_orders = src.cancelled_orders,
        tgt.total_revenue    = src.total_revenue,
        tgt.avg_order_value  = src.avg_order_value,
        tgt.mart_updated_at  = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
    INSERT (order_date, total_orders, confirmed_orders, shipped_orders,
            delivered_orders, cancelled_orders, total_revenue, avg_order_value, mart_updated_at)
    VALUES (src.order_date, src.total_orders, src.confirmed_orders, src.shipped_orders,
            src.delivered_orders, src.cancelled_orders, src.total_revenue, src.avg_order_value,
            CURRENT_TIMESTAMP());
```

---

## Step 4 — Create the Task Chain

Both tasks live in `ECOMM_DB.RAW_DATA` — Snowflake requires tasks in the same schema for `AFTER` chaining.

```sql
-- Task 1 (ROOT): RAW → STAGING
-- Runs every minute; skips if stream is empty
CREATE OR REPLACE TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK
    WAREHOUSE = COMPUTE_WH
    SCHEDULE  = '1 MINUTE'
    WHEN SYSTEM$STREAM_HAS_DATA('ECOMM_DB.RAW_DATA.ORDERS_RAW_STREAM')
AS
MERGE INTO ECOMM_DB.STAGING.STG_ORDERS AS tgt
USING (SELECT * FROM ECOMM_DB.RAW_DATA.ORDERS_RAW_STREAM) AS src
ON tgt.order_id = src.order_id
WHEN MATCHED AND src.METADATA$ACTION = 'INSERT' THEN
    UPDATE SET
        tgt.customer_id = src.customer_id, tgt.customer_name = src.customer_name,
        tgt.product = src.product, tgt.quantity = src.quantity,
        tgt.unit_price = src.unit_price, tgt.total_amount = src.total_amount,
        tgt.status = src.status, tgt.order_date = src.order_date,
        tgt.is_deleted = FALSE, tgt.stg_updated_at = CURRENT_TIMESTAMP()
WHEN MATCHED AND src.METADATA$ACTION = 'DELETE' AND src.METADATA$ISUPDATE = FALSE THEN
    UPDATE SET tgt.is_deleted = TRUE, tgt.stg_updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED AND src.METADATA$ACTION = 'INSERT' THEN
    INSERT (order_id, customer_id, customer_name, product, quantity,
            unit_price, total_amount, status, order_date, is_deleted, stg_updated_at)
    VALUES (src.order_id, src.customer_id, src.customer_name, src.product, src.quantity,
            src.unit_price, src.total_amount, src.status, src.order_date, FALSE, CURRENT_TIMESTAMP());


-- Task 2 (CHILD): STAGING → MART
-- Same schema as Task 1 — required for AFTER chaining
CREATE OR REPLACE TASK ECOMM_DB.RAW_DATA.STG_TO_MART_TASK
    WAREHOUSE = COMPUTE_WH
    AFTER     ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK
AS
MERGE INTO ECOMM_DB.MARTS.ORDERS_MART AS tgt
USING (
    SELECT
        order_date,
        COUNT(*)                                                AS total_orders,
        SUM(CASE WHEN status = 'CONFIRMED'  THEN 1 ELSE 0 END) AS confirmed_orders,
        SUM(CASE WHEN status = 'SHIPPED'    THEN 1 ELSE 0 END) AS shipped_orders,
        SUM(CASE WHEN status = 'DELIVERED'  THEN 1 ELSE 0 END) AS delivered_orders,
        SUM(CASE WHEN status = 'CANCELLED'  THEN 1 ELSE 0 END) AS cancelled_orders,
        SUM(total_amount)                                       AS total_revenue,
        AVG(total_amount)                                       AS avg_order_value
    FROM ECOMM_DB.STAGING.STG_ORDERS
    WHERE is_deleted = FALSE
    GROUP BY order_date
) AS src
ON tgt.order_date = src.order_date
WHEN MATCHED THEN
    UPDATE SET
        tgt.total_orders = src.total_orders, tgt.confirmed_orders = src.confirmed_orders,
        tgt.shipped_orders = src.shipped_orders, tgt.delivered_orders = src.delivered_orders,
        tgt.cancelled_orders = src.cancelled_orders, tgt.total_revenue = src.total_revenue,
        tgt.avg_order_value = src.avg_order_value, tgt.mart_updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
    INSERT (order_date, total_orders, confirmed_orders, shipped_orders,
            delivered_orders, cancelled_orders, total_revenue, avg_order_value, mart_updated_at)
    VALUES (src.order_date, src.total_orders, src.confirmed_orders, src.shipped_orders,
            src.delivered_orders, src.cancelled_orders, src.total_revenue, src.avg_order_value,
            CURRENT_TIMESTAMP());


-- Resume: child first, root last
ALTER TASK ECOMM_DB.RAW_DATA.STG_TO_MART_TASK RESUME;
ALTER TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK  RESUME;
```

---

## Step 5 — Verification Queries

Run these after every batch to confirm all three layers are in sync.

```sql
-- RAW layer
SELECT order_id, customer_name, product, status, total_amount, updated_at
FROM ECOMM_DB.RAW_DATA.ORDERS_RAW
ORDER BY order_id;

-- STAGING layer (soft deletes visible)
SELECT order_id, customer_name, product, status, total_amount, is_deleted, stg_updated_at
FROM ECOMM_DB.STAGING.STG_ORDERS
ORDER BY order_id;

-- MART layer
SELECT * FROM ECOMM_DB.MARTS.ORDERS_MART ORDER BY order_date;

-- Stream: should be FALSE after task runs
SELECT SYSTEM$STREAM_HAS_DATA('ECOMM_DB.RAW_DATA.ORDERS_RAW_STREAM') AS raw_stream_has_data;

-- Task run history
SELECT name, state, scheduled_time, completed_time, error_message
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
    SCHEDULED_TIME_RANGE_START => DATEADD('minutes', -10, CURRENT_TIMESTAMP())
))
ORDER BY scheduled_time DESC;
```

---

## Step 6 — Test Data: Insert, Update, and Delete

Run each batch in order. After each one, check the stream, trigger the task, and verify all three layers.

```sql
USE ROLE SYSADMIN;
USE WAREHOUSE COMPUTE_WH;
USE SCHEMA ECOMM_DB.RAW_DATA;
```

### Batch 1 — Initial inserts (6 orders across 3 dates)

```sql
INSERT INTO ORDERS_RAW
    (order_id, customer_id, customer_name, product, quantity, unit_price, total_amount, status, order_date)
VALUES
    (1001, 1, 'Alice Johnson',  'Wireless Headphones', 1, 149.99, 149.99, 'CONFIRMED', '2024-01-10'),
    (1002, 2, 'Bob Smith',      'Running Shoes',       2,  89.99, 179.98, 'CONFIRMED', '2024-01-10'),
    (1003, 3, 'Priya Sharma',   'Coffee Maker',        1, 129.99, 129.99, 'SHIPPED',   '2024-01-11'),
    (1004, 4, 'Carlos Mendez',  'Python Book',         3,  49.99, 149.97, 'PENDING',   '2024-01-11'),
    (1005, 5, 'Yuki Tanaka',    'Yoga Mat',            2,  39.99,  79.98, 'DELIVERED', '2024-01-12'),
    (1006, 6, 'Sophie Dubois',  'Standing Desk',       1, 499.99, 499.99, 'CONFIRMED', '2024-01-12');
```

Check stream — all 6 rows as `INSERT`, `METADATA$ISUPDATE = FALSE`:
```sql
SELECT order_id, customer_name, status, METADATA$ACTION, METADATA$ISUPDATE
FROM ECOMM_DB.RAW_DATA.ORDERS_RAW_STREAM;
```

Trigger and verify:
```sql
EXECUTE TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK;

SELECT order_id, customer_name, status, total_amount FROM ECOMM_DB.RAW_DATA.ORDERS_RAW ORDER BY order_id;
SELECT order_id, customer_name, status, is_deleted   FROM ECOMM_DB.STAGING.STG_ORDERS  ORDER BY order_id;
SELECT * FROM ECOMM_DB.MARTS.ORDERS_MART ORDER BY order_date;
```

**Expected mart:**

| order_date | total_orders | confirmed | shipped | delivered | total_revenue |
|---|---|---|---|---|---|
| 2024-01-10 | 2 | 2 | 0 | 0 | 329.97 |
| 2024-01-11 | 2 | 0 | 1 | 0 | 279.96 |
| 2024-01-12 | 2 | 1 | 0 | 1 | 579.97 |

---

### Batch 2 — Status updates (3 orders change status)

```sql
-- Bob's shoes shipped
UPDATE ORDERS_RAW SET status = 'SHIPPED',   updated_at = CURRENT_TIMESTAMP() WHERE order_id = 1002;
-- Priya's maker delivered
UPDATE ORDERS_RAW SET status = 'DELIVERED', updated_at = CURRENT_TIMESTAMP() WHERE order_id = 1003;
-- Carlos cancelled his order
UPDATE ORDERS_RAW SET status = 'CANCELLED', updated_at = CURRENT_TIMESTAMP() WHERE order_id = 1004;
```

Check stream — each UPDATE = 2 rows (pre/post image):
```sql
SELECT order_id, customer_name, status, METADATA$ACTION, METADATA$ISUPDATE
FROM ECOMM_DB.RAW_DATA.ORDERS_RAW_STREAM
ORDER BY order_id, METADATA$ACTION DESC;
-- 6 rows: DELETE+INSERT for each of 1002, 1003, 1004
```

Trigger and verify:
```sql
EXECUTE TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK;

SELECT order_id, customer_name, status, is_deleted FROM ECOMM_DB.STAGING.STG_ORDERS ORDER BY order_id;
SELECT * FROM ECOMM_DB.MARTS.ORDERS_MART ORDER BY order_date;
```

**Expected mart changes:**

| order_date | confirmed | shipped | delivered | cancelled |
|---|---|---|---|---|
| 2024-01-10 | 1 | 1 | 0 | 0 | ← Bob moved to SHIPPED |
| 2024-01-11 | 0 | 0 | 1 | 1 | ← Priya DELIVERED, Carlos CANCELLED |

---

### Batch 3 — Hard delete (remove Carlos from RAW)

```sql
DELETE FROM ORDERS_RAW WHERE order_id = 1004;
```

Check stream — 1 row, `ACTION = 'DELETE'`, `ISUPDATE = FALSE`:
```sql
SELECT order_id, customer_name, status, METADATA$ACTION, METADATA$ISUPDATE
FROM ECOMM_DB.RAW_DATA.ORDERS_RAW_STREAM;
```

Trigger and verify:
```sql
EXECUTE TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK;

SELECT COUNT(*) AS raw_count FROM ECOMM_DB.RAW_DATA.ORDERS_RAW;           -- 5
SELECT COUNT(*) AS stg_count FROM ECOMM_DB.STAGING.STG_ORDERS;            -- still 6

-- Carlos: is_deleted = TRUE in staging (soft delete, row preserved)
SELECT order_id, customer_name, status, is_deleted FROM ECOMM_DB.STAGING.STG_ORDERS ORDER BY order_id;

-- Jan 11: drops to 1 order (Carlos excluded)
SELECT * FROM ECOMM_DB.MARTS.ORDERS_MART ORDER BY order_date;
```

---

### Batch 4 — Mixed: new inserts + updates in one task run

```sql
-- New orders on Jan 13
INSERT INTO ORDERS_RAW
    (order_id, customer_id, customer_name, product, quantity, unit_price, total_amount, status, order_date)
VALUES
    (1007, 7, 'Marco Rossi', 'Mechanical Keyboard',  1, 189.99, 189.99, 'CONFIRMED', '2024-01-13'),
    (1008, 8, 'Aisha Patel', 'Smart Watch',          1, 299.99, 299.99, 'PENDING',   '2024-01-13'),
    (1009, 9, 'Lena Müller', 'Noise Cancelling Mic', 1,  79.99,  79.99, 'CONFIRMED', '2024-01-13');

-- Alice's headphones shipped
UPDATE ORDERS_RAW SET status = 'SHIPPED',   updated_at = CURRENT_TIMESTAMP() WHERE order_id = 1001;
-- Sophie's desk delivered
UPDATE ORDERS_RAW SET status = 'DELIVERED', updated_at = CURRENT_TIMESTAMP() WHERE order_id = 1006;
```

Check stream — 7 rows (3 inserts + 2×2 for the two updates):
```sql
SELECT order_id, customer_name, status, METADATA$ACTION, METADATA$ISUPDATE
FROM ECOMM_DB.RAW_DATA.ORDERS_RAW_STREAM
ORDER BY order_id, METADATA$ACTION DESC;
```

Trigger and verify:
```sql
EXECUTE TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK;

-- 9 rows in staging (6 original + 3 new); Carlos still soft-deleted
SELECT order_id, customer_name, status, is_deleted FROM ECOMM_DB.STAGING.STG_ORDERS ORDER BY order_id;

-- Jan 13 appears as a new mart row
SELECT * FROM ECOMM_DB.MARTS.ORDERS_MART ORDER BY order_date;
```

---

### Batch 5 — Quantity and price correction

```sql
-- Lena ordered 2 mics, not 1
UPDATE ORDERS_RAW
SET quantity = 2, total_amount = 159.98, updated_at = CURRENT_TIMESTAMP()
WHERE order_id = 1009;

-- Aisha's watch confirmed
UPDATE ORDERS_RAW SET status = 'CONFIRMED', updated_at = CURRENT_TIMESTAMP() WHERE order_id = 1008;
```

Trigger and verify:
```sql
EXECUTE TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK;

-- Lena: quantity=2, total_amount=159.98  |  Aisha: status=CONFIRMED
SELECT order_id, customer_name, quantity, total_amount, status
FROM ECOMM_DB.STAGING.STG_ORDERS WHERE order_id IN (1008, 1009);

-- Jan 13: revenue increases, confirmed_orders = 3
SELECT * FROM ECOMM_DB.MARTS.ORDERS_MART WHERE order_date = '2024-01-13';
```

---

### Full consistency check (run after any batch)

```sql
-- Row counts: RAW must equal active STAGING rows
SELECT
    (SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW)                         AS raw_count,
    (SELECT COUNT(*) FROM ECOMM_DB.STAGING.STG_ORDERS WHERE is_deleted = FALSE)  AS stg_active,
    (SELECT COUNT(*) FROM ECOMM_DB.STAGING.STG_ORDERS WHERE is_deleted = TRUE)   AS stg_deleted;

-- Revenue: active STAGING must equal MART total
SELECT
    (SELECT SUM(total_amount)  FROM ECOMM_DB.STAGING.STG_ORDERS WHERE is_deleted = FALSE) AS stg_revenue,
    (SELECT SUM(total_revenue) FROM ECOMM_DB.MARTS.ORDERS_MART)                            AS mart_revenue;

-- Task history
SELECT name, state, scheduled_time, completed_time, error_message
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
    SCHEDULED_TIME_RANGE_START => DATEADD('hours', -2, CURRENT_TIMESTAMP())
))
ORDER BY scheduled_time DESC;
```

---

### Teardown — suspend tasks when done

```sql
ALTER TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK  SUSPEND;
ALTER TASK ECOMM_DB.RAW_DATA.STG_TO_MART_TASK SUSPEND;
```

---

## Summary

| Layer | Table | How it gets data |
|---|---|---|
| RAW | `ORDERS_RAW` | Direct INSERT / UPDATE / DELETE |
| STAGING | `STG_ORDERS` | MERGE from stream on RAW (RAW_TO_STG_TASK) |
| MART | `ORDERS_MART` | MERGE from full STG_ORDERS scan (STG_TO_MART_TASK) |

**Next:** Day 5 covers semi-structured data — VARIANT, loading JSON, colon syntax, and LATERAL FLATTEN.
