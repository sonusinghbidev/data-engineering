# Day 6 — Practice Exercises: Time Travel, Semi-Structured Data, Query Optimization

> All exercises use the Day 4 tables: ORDERS_RAW, STG_ORDERS, ORDERS_MART.
> Run everything in Snowsight in order.
> Estimated total time: 60–75 minutes.

---

## Pre-Check

```sql
USE ROLE SYSADMIN;
USE WAREHOUSE COMPUTE_WH;

SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW;
SELECT COUNT(*) FROM ECOMM_DB.STAGING.STG_ORDERS;
SELECT COUNT(*) FROM ECOMM_DB.MARTS.ORDERS_MART;
```

> If tables are empty, run Day 4 Steps 1–6 to populate them before continuing.

---

## Exercise 1 — Time Travel: Query the Past

**What we are testing:** AT OFFSET, BEFORE STATEMENT, historical comparison.

### Step 1: Record current state

```sql
USE SCHEMA ECOMM_DB.RAW_DATA;

SELECT order_id, customer_name, status, total_amount
FROM ORDERS_RAW
ORDER BY order_id;
-- Note the current statuses
```

### Step 2: Make a change

```sql
-- Update 3 orders' statuses
UPDATE ORDERS_RAW
SET status     = 'CANCELLED',
    updated_at = CURRENT_TIMESTAMP()
WHERE order_id IN (1001, 1002, 1003);

-- Confirm the change
SELECT order_id, status FROM ORDERS_RAW WHERE order_id IN (1001, 1002, 1003);
-- All 3 show CANCELLED
```

### Step 3: Use AT OFFSET to query before the change

```sql
-- Query as it was 2 minutes ago (120 seconds)
SELECT order_id, status
FROM ORDERS_RAW AT (OFFSET => -120)
WHERE order_id IN (1001, 1002, 1003);
-- Should show original statuses (not CANCELLED)
-- If 2 min is not enough, try -300 (5 min)
```

### Step 4: Use BEFORE STATEMENT to query just before the UPDATE

```sql
-- Find the UPDATE query ID
SELECT query_id, query_text, start_time
FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(
    DATE_RANGE_START => DATEADD('minutes', -10, CURRENT_TIMESTAMP())
))
WHERE query_text ILIKE '%UPDATE%ORDERS_RAW%CANCELLED%'
ORDER BY start_time DESC
LIMIT 1;
-- Copy the query_id

-- Query the exact state just before the UPDATE ran
SELECT order_id, status
FROM ORDERS_RAW BEFORE (STATEMENT => '<your-query-id>')
WHERE order_id IN (1001, 1002, 1003);
-- Shows original statuses
```

### Step 5: Restore using MERGE + Time Travel

```sql
-- Restore the 3 rows to their pre-update statuses
MERGE INTO ECOMM_DB.RAW_DATA.ORDERS_RAW AS tgt
USING (
    SELECT order_id, status
    FROM ECOMM_DB.RAW_DATA.ORDERS_RAW BEFORE (STATEMENT => '<your-query-id>')
    WHERE order_id IN (1001, 1002, 1003)
) AS src
ON tgt.order_id = src.order_id
WHEN MATCHED THEN
    UPDATE SET tgt.status = src.status, tgt.updated_at = CURRENT_TIMESTAMP();

-- Verify restored
SELECT order_id, status FROM ORDERS_RAW WHERE order_id IN (1001, 1002, 1003);
-- Should show original values again
```

---

## Exercise 2 — Time Travel: UNDROP

**What we are testing:** Recovering a dropped table.

### Step 1: Drop the ORDERS_MART table

```sql
USE SCHEMA ECOMM_DB.MARTS;

-- Check current state
SELECT COUNT(*) FROM ORDERS_MART;

-- Drop it
DROP TABLE ECOMM_DB.MARTS.ORDERS_MART;

-- Confirm it is gone
SHOW TABLES IN SCHEMA ECOMM_DB.MARTS;
```

### Step 2: Recover it with UNDROP

```sql
UNDROP TABLE ECOMM_DB.MARTS.ORDERS_MART;

-- Confirm it is back
SELECT COUNT(*) FROM ECOMM_DB.MARTS.ORDERS_MART;
-- Same row count as before the drop
SHOW TABLES IN SCHEMA ECOMM_DB.MARTS;
```

### Step 3: Check and set the retention window

```sql
-- Check retention for ORDERS_RAW
SHOW TABLES LIKE 'ORDERS_RAW' IN SCHEMA ECOMM_DB.RAW_DATA;
-- DATA_RETENTION_TIME_IN_DAYS column

-- Increase retention to 3 days
ALTER TABLE ECOMM_DB.RAW_DATA.ORDERS_RAW
    SET DATA_RETENTION_TIME_IN_DAYS = 3;

-- Confirm
SHOW TABLES LIKE 'ORDERS_RAW' IN SCHEMA ECOMM_DB.RAW_DATA;

-- Reset to 1 day
ALTER TABLE ECOMM_DB.RAW_DATA.ORDERS_RAW
    SET DATA_RETENTION_TIME_IN_DAYS = 1;
```

---

## Exercise 3 — Semi-Structured Data: VARIANT and JSON

**What we are testing:** PARSE_JSON, colon syntax, nested access, TYPEOF.

### Step 1: Create the ORDERS_JSON table and insert data

```sql
USE SCHEMA ECOMM_DB.RAW_DATA;

CREATE OR REPLACE TABLE ORDERS_JSON (
    raw_order  VARIANT,
    loaded_at  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

INSERT INTO ORDERS_JSON (raw_order) SELECT PARSE_JSON('{
    "order_id": 3001,
    "customer": {"name": "Alice Johnson", "city": "New York", "tier": "VIP"},
    "items": [
        {"product": "Wireless Headphones", "qty": 1, "price": 149.99},
        {"product": "Phone Case",          "qty": 2, "price": 15.99}
    ],
    "status": "CONFIRMED",
    "order_date": "2024-03-01",
    "total": 181.97
}');

INSERT INTO ORDERS_JSON (raw_order) SELECT PARSE_JSON('{
    "order_id": 3002,
    "customer": {"name": "Bob Smith", "city": "Chicago", "tier": "STANDARD"},
    "items": [
        {"product": "Running Shoes", "qty": 1, "price": 89.99}
    ],
    "status": "SHIPPED",
    "order_date": "2024-03-01",
    "total": 89.99
}');

INSERT INTO ORDERS_JSON (raw_order) SELECT PARSE_JSON('{
    "order_id": 3003,
    "customer": {"name": "Priya Sharma", "city": "Austin", "tier": "VIP"},
    "items": [
        {"product": "Coffee Maker", "qty": 1, "price": 129.99},
        {"product": "Coffee Beans", "qty": 3, "price": 19.99}
    ],
    "status": "DELIVERED",
    "order_date": "2024-03-02",
    "total": 189.96
}');

-- See the raw VARIANT data
SELECT raw_order FROM ORDERS_JSON;
```

### Step 2: Extract top-level fields with colon syntax

```sql
SELECT
    raw_order:order_id::NUMBER       AS order_id,
    raw_order:status::VARCHAR        AS status,
    raw_order:order_date::DATE       AS order_date,
    raw_order:total::NUMBER(10,2)    AS total
FROM ORDERS_JSON;
```

### Step 3: Extract nested fields

```sql
SELECT
    raw_order:order_id::NUMBER           AS order_id,
    raw_order:customer.name::VARCHAR     AS customer_name,
    raw_order:customer.city::VARCHAR     AS city,
    raw_order:customer.tier::VARCHAR     AS tier
FROM ORDERS_JSON;
```

### Step 4: Access array elements by index

```sql
-- First item (index 0)
SELECT
    raw_order:order_id::NUMBER           AS order_id,
    raw_order:items[0].product::VARCHAR  AS first_product,
    raw_order:items[0].price::NUMBER     AS first_price
FROM ORDERS_JSON;

-- Second item (index 1) — NULL for Bob who has only 1 item
SELECT
    raw_order:order_id::NUMBER           AS order_id,
    raw_order:items[1].product::VARCHAR  AS second_product,
    raw_order:items[1].price::NUMBER     AS second_price
FROM ORDERS_JSON;
-- order_id 3002 (Bob): NULL — only 1 item

-- Only orders with 2+ items
SELECT
    raw_order:order_id::NUMBER           AS order_id,
    raw_order:items[1].product::VARCHAR  AS second_product
FROM ORDERS_JSON
WHERE raw_order:items[1] IS NOT NULL;
```

### Step 5: Check TYPEOF

```sql
-- See what type Snowflake infers for each JSON field
SELECT
    TYPEOF(raw_order:order_id)   AS order_id_type,   -- INTEGER
    TYPEOF(raw_order:total)      AS total_type,       -- DECIMAL
    TYPEOF(raw_order:status)     AS status_type,      -- VARCHAR
    TYPEOF(raw_order:items)      AS items_type,       -- ARRAY
    TYPEOF(raw_order:customer)   AS customer_type     -- OBJECT
FROM ORDERS_JSON
LIMIT 1;
```

---

## Exercise 4 — LATERAL FLATTEN

**What we are testing:** Exploding JSON arrays into rows, joining with flat columns.

### Step 1: Flatten the items array

```sql
-- Each item in the array becomes its own row
SELECT
    o.raw_order:order_id::NUMBER       AS order_id,
    o.raw_order:customer.name::VARCHAR AS customer_name,
    item.value:product::VARCHAR        AS product,
    item.value:qty::NUMBER             AS qty,
    item.value:price::NUMBER(10,2)     AS unit_price,
    item.value:qty::NUMBER * item.value:price::NUMBER AS line_total
FROM ECOMM_DB.RAW_DATA.ORDERS_JSON o,
     LATERAL FLATTEN(input => o.raw_order:items) item;
-- Expected: 5 rows total (Alice=2, Bob=1, Priya=2)
```

### Step 2: Aggregate after flattening

```sql
-- Total items and revenue per order
SELECT
    o.raw_order:order_id::NUMBER       AS order_id,
    o.raw_order:customer.name::VARCHAR AS customer_name,
    COUNT(item.value)                  AS item_count,
    SUM(item.value:qty::NUMBER * item.value:price::NUMBER) AS total_revenue
FROM ECOMM_DB.RAW_DATA.ORDERS_JSON o,
     LATERAL FLATTEN(input => o.raw_order:items) item
GROUP BY 1, 2
ORDER BY 1;
```

### Step 3: Filter on a flattened field

```sql
-- Only items priced over $50
SELECT
    o.raw_order:order_id::NUMBER       AS order_id,
    item.value:product::VARCHAR        AS product,
    item.value:price::NUMBER           AS price
FROM ECOMM_DB.RAW_DATA.ORDERS_JSON o,
     LATERAL FLATTEN(input => o.raw_order:items) item
WHERE item.value:price::NUMBER > 50
ORDER BY price DESC;
```

### Step 4: Load flattened JSON into ORDERS_RAW

```sql
-- Parse the JSON and insert structured rows into ORDERS_RAW
INSERT INTO ECOMM_DB.RAW_DATA.ORDERS_RAW
    (order_id, customer_id, customer_name, product, quantity,
     unit_price, total_amount, status, order_date)
SELECT
    j.raw_order:order_id::NUMBER                                           AS order_id,
    ROW_NUMBER() OVER (ORDER BY j.raw_order:order_id, item.index)         AS customer_id,
    j.raw_order:customer.name::VARCHAR                                     AS customer_name,
    item.value:product::VARCHAR                                            AS product,
    item.value:qty::NUMBER                                                 AS quantity,
    item.value:price::NUMBER(10,2)                                         AS unit_price,
    item.value:qty::NUMBER * item.value:price::NUMBER(10,2)               AS total_amount,
    j.raw_order:status::VARCHAR                                            AS status,
    j.raw_order:order_date::DATE                                           AS order_date
FROM ECOMM_DB.RAW_DATA.ORDERS_JSON j,
     LATERAL FLATTEN(input => j.raw_order:items) item;

-- Verify the new rows in ORDERS_RAW
SELECT * FROM ECOMM_DB.RAW_DATA.ORDERS_RAW
WHERE order_id >= 3001 ORDER BY order_id;

-- Trigger Day 4 tasks to push to STG and MART
EXECUTE TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK;
SELECT * FROM ECOMM_DB.MARTS.ORDERS_MART ORDER BY order_date;
-- March 01 and March 02 should appear
```

---

## Exercise 5 — Query Optimization

**What we are testing:** Result cache, clustering key, Query Profile.

### Step 1: Observe the result cache

```sql
-- Run this query
SELECT order_date, COUNT(*) AS orders, SUM(total_amount) AS revenue
FROM ECOMM_DB.STAGING.STG_ORDERS
WHERE is_deleted = FALSE
GROUP BY order_date
ORDER BY order_date;

-- Run the identical query again immediately
SELECT order_date, COUNT(*) AS orders, SUM(total_amount) AS revenue
FROM ECOMM_DB.STAGING.STG_ORDERS
WHERE is_deleted = FALSE
GROUP BY order_date
ORDER BY order_date;

-- Check Activity → Query History in Snowsight
-- Second run should show "Results reused from cache" = true, duration ~0ms
```

### Step 2: Invalidate the cache with a DML change

```sql
-- Make any change to the underlying table
UPDATE ECOMM_DB.STAGING.STG_ORDERS
SET stg_updated_at = CURRENT_TIMESTAMP()
WHERE order_id = 1001;

-- Run the same query again — cache is now invalidated, warehouse runs it fresh
SELECT order_date, COUNT(*) AS orders, SUM(total_amount) AS revenue
FROM ECOMM_DB.STAGING.STG_ORDERS
WHERE is_deleted = FALSE
GROUP BY order_date
ORDER BY order_date;
-- This run takes normal time (no cache hit)
```

### Step 3: Add a clustering key to ORDERS_RAW

```sql
USE SCHEMA ECOMM_DB.RAW_DATA;

-- Check current clustering state
SELECT SYSTEM$CLUSTERING_INFORMATION('ECOMM_DB.RAW_DATA.ORDERS_RAW', '(order_date)');
-- average_overlaps: how many partitions each value appears in (lower = better)

-- Add clustering key on order_date (most common filter column)
ALTER TABLE ECOMM_DB.RAW_DATA.ORDERS_RAW
    CLUSTER BY (order_date);

-- Confirm
SHOW TABLES LIKE 'ORDERS_RAW' IN SCHEMA ECOMM_DB.RAW_DATA;
-- CLUSTERING_KEY column shows: LINEAR(ORDER_DATE)
```

### Step 4: Check Query Profile for partition pruning

```sql
-- Run a filtered query
SELECT order_id, customer_name, product, total_amount
FROM ECOMM_DB.RAW_DATA.ORDERS_RAW
WHERE order_date = '2024-01-10';

-- In Snowsight:
-- 1. Click the query in results → "Query Profile" tab
-- 2. Click the TableScan node
-- 3. Look at "Partitions scanned" vs "Partitions total"
-- With a small table, all partitions fit in a few micro-partitions — scan may be 1 of 1
-- On a large table, good clustering = 1 or 2 partitions scanned out of hundreds
```

### Step 5: Remove the clustering key

```sql
-- Remove clustering (stops Automatic Clustering charges)
ALTER TABLE ECOMM_DB.RAW_DATA.ORDERS_RAW DROP CLUSTERING KEY;

-- Confirm removed
SHOW TABLES LIKE 'ORDERS_RAW' IN SCHEMA ECOMM_DB.RAW_DATA;
-- CLUSTERING_KEY column is now empty
```

### Step 6: Warehouse sizing — observe the effect

```sql
-- Check current warehouse size
SHOW WAREHOUSES LIKE 'COMPUTE_WH';

-- Scale up for a heavy query
ALTER WAREHOUSE COMPUTE_WH SET WAREHOUSE_SIZE = 'SMALL';

-- Run a large aggregation
SELECT
    status,
    order_date,
    COUNT(*)          AS order_count,
    SUM(total_amount) AS revenue,
    AVG(total_amount) AS avg_order
FROM ECOMM_DB.STAGING.STG_ORDERS
WHERE is_deleted = FALSE
GROUP BY status, order_date
ORDER BY order_date, status;

-- Scale back down immediately after
ALTER WAREHOUSE COMPUTE_WH SET WAREHOUSE_SIZE = 'X-SMALL';

-- Confirm
SHOW WAREHOUSES LIKE 'COMPUTE_WH';
```

---

## Final Consistency Check

```sql
-- Verify all three layers are in sync after all exercises
SELECT
    (SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW)                        AS raw_count,
    (SELECT COUNT(*) FROM ECOMM_DB.STAGING.STG_ORDERS WHERE is_deleted = FALSE) AS stg_active,
    (SELECT SUM(total_amount)  FROM ECOMM_DB.RAW_DATA.ORDERS_RAW)               AS raw_revenue,
    (SELECT SUM(total_revenue) FROM ECOMM_DB.MARTS.ORDERS_MART)                 AS mart_revenue;
-- raw_count = stg_active, raw_revenue = mart_revenue
```

---

## Teardown

```sql
USE ROLE SYSADMIN;

-- Suspend tasks
ALTER TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK  SUSPEND;
ALTER TASK ECOMM_DB.RAW_DATA.STG_TO_MART_TASK SUSPEND;

-- Drop the JSON table created today
DROP TABLE ECOMM_DB.RAW_DATA.ORDERS_JSON;

-- Reset table retention to default
ALTER TABLE ECOMM_DB.RAW_DATA.ORDERS_RAW SET DATA_RETENTION_TIME_IN_DAYS = 1;
```

---

## Summary

| Exercise | What you verified |
|---|---|
| 1 | AT OFFSET, BEFORE STATEMENT, MERGE restore from Time Travel |
| 2 | UNDROP table, check and set retention window |
| 3 | VARIANT, PARSE_JSON, colon syntax, nested access, TYPEOF |
| 4 | LATERAL FLATTEN, aggregate on flattened rows, load JSON into ORDERS_RAW |
| 5 | Result cache hit/invalidation, clustering key add/remove, Query Profile, warehouse sizing |

**Day 7 topics remaining:** Dynamic Tables, Data Sharing (deep dive), Materialized Views, Stored Procedures & UDFs, Snowpark (Python in Snowflake), Row Access Policies, Column Masking Policies.
