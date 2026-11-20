# Day 6 — Time Travel, Semi-Structured Data, and Query Optimization

## What You Will Learn

1. **Time Travel** — Query, restore, and clone data at any point in the past. Undo accidental changes.
2. **Semi-Structured Data** — Load and query JSON using VARIANT, colon syntax, and LATERAL FLATTEN.
3. **Query Optimization** — Result cache, clustering keys, query profile. Make queries faster and cheaper.

All examples continue using the Day 4 tables: `ECOMM_DB.RAW_DATA.ORDERS_RAW`, `ECOMM_DB.STAGING.STG_ORDERS`, `ECOMM_DB.MARTS.ORDERS_MART`.

---

## Concept 1 — Time Travel

### What is Time Travel?

Snowflake stores a history of every change made to a table. **Time Travel** lets you query that table as it existed at any point in the past — without restoring anything.

The default retention window is **1 day (24 hours)**. Enterprise edition can extend it to **90 days**.

```
Now ◄────────────────────────── Past
     [current state]  [1 hour ago]  [yesterday]
              Time Travel Window (1–90 days)
```

### Three ways to specify a point in time

```sql
-- 1. OFFSET — seconds back from now
SELECT * FROM ORDERS_RAW AT (OFFSET => -3600);  -- 1 hour ago

-- 2. TIMESTAMP — exact point in time
SELECT * FROM ORDERS_RAW AT (TIMESTAMP => '2024-01-10 08:00:00'::TIMESTAMP_NTZ);

-- 3. STATEMENT — just before or after a specific query ran (use query ID)
SELECT * FROM ORDERS_RAW BEFORE (STATEMENT => '01ab2c34-...');
```

### Hands-On: Time Travel on ORDERS_RAW

#### Step 1: Note current state

```sql
USE ROLE SYSADMIN;
USE WAREHOUSE COMPUTE_WH;
USE SCHEMA ECOMM_DB.RAW_DATA;

SELECT COUNT(*) AS current_count FROM ORDERS_RAW;
SELECT * FROM ORDERS_RAW ORDER BY order_id;
```

#### Step 2: Make a change, then travel back before it

```sql
-- Update some statuses
UPDATE ORDERS_RAW
SET status = 'CANCELLED', updated_at = CURRENT_TIMESTAMP()
WHERE order_id IN (1001, 1002);

-- Confirm the change
SELECT order_id, status FROM ORDERS_RAW WHERE order_id IN (1001, 1002);
-- Both show CANCELLED

-- Find the query ID of the UPDATE
SELECT query_id, query_text, start_time
FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(
    DATE_RANGE_START => DATEADD('minutes', -5, CURRENT_TIMESTAMP())
))
WHERE query_text ILIKE '%UPDATE%ORDERS_RAW%'
ORDER BY start_time DESC
LIMIT 1;
-- Copy the query_id

-- Query the table as it was BEFORE the update
SELECT order_id, status
FROM ORDERS_RAW BEFORE (STATEMENT => '<your-query-id>')
WHERE order_id IN (1001, 1002);
-- Shows original statuses before the update
```

#### Step 3: Query with AT OFFSET

```sql
-- What did the table look like 5 minutes ago?
SELECT order_id, status, updated_at
FROM ORDERS_RAW AT (OFFSET => -300)
ORDER BY order_id;
```

#### Step 4: Restore data using Time Travel + INSERT

```sql
-- Restore the two rows to their previous state using BEFORE
INSERT OVERWRITE INTO ORDERS_RAW
SELECT * FROM ORDERS_RAW BEFORE (STATEMENT => '<your-query-id>')
WHERE order_id IN (1001, 1002);

-- Verify restored
SELECT order_id, status FROM ORDERS_RAW WHERE order_id IN (1001, 1002);
```

#### Step 5: UNDROP — recover a dropped table

```sql
-- Drop the table
DROP TABLE ECOMM_DB.RAW_DATA.ORDERS_RAW;

-- Oops — it's gone
-- SELECT * FROM ORDERS_RAW; -- would error

-- Recover it with UNDROP (works within Time Travel window)
UNDROP TABLE ECOMM_DB.RAW_DATA.ORDERS_RAW;

-- It's back
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW;
```

UNDROP also works for schemas and databases:
```sql
UNDROP SCHEMA ECOMM_DB.RAW_DATA;
UNDROP DATABASE ECOMM_DB;
```

#### Step 6: Check and change the Time Travel retention window

```sql
-- Check current retention (in days)
SHOW TABLES LIKE 'ORDERS_RAW' IN SCHEMA ECOMM_DB.RAW_DATA;
-- DATA_RETENTION_TIME_IN_DAYS column shows the current setting

-- Change to 7 days (requires Standard edition or higher)
ALTER TABLE ECOMM_DB.RAW_DATA.ORDERS_RAW
    SET DATA_RETENTION_TIME_IN_DAYS = 7;

-- Set to 0 to disable Time Travel (saves storage cost on transient/temp tables)
-- ALTER TABLE ... SET DATA_RETENTION_TIME_IN_DAYS = 0;
```

### Time Travel vs Fail-Safe

| | Time Travel | Fail-Safe |
|---|---|---|
| Duration | 0–90 days (you control) | 7 days (Snowflake-managed, after TT window) |
| Access | You query/restore yourself with SQL | Only Snowflake Support can recover |
| Use | Self-service recovery, historical queries | Disaster recovery of last resort |
| Cost | Storage for historical data | Included in Snowflake storage |

---

## Concept 2 — Semi-Structured Data (VARIANT, JSON, FLATTEN)

### What is VARIANT?

`VARIANT` is a Snowflake column type that stores **any semi-structured data** — JSON, Avro, Parquet, XML — as a single value. One VARIANT column can hold an entire JSON document.

```sql
-- A table with a VARIANT column
CREATE TABLE orders_json_raw (
    raw_order  VARIANT,
    loaded_at  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
```

### Loading JSON into VARIANT

```sql
USE SCHEMA ECOMM_DB.RAW_DATA;

CREATE OR REPLACE TABLE ORDERS_JSON (
    raw_order  VARIANT,
    loaded_at  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Insert JSON directly using PARSE_JSON
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
```

### Querying VARIANT with Colon Syntax

Use `:` to navigate into JSON keys. Use `::TYPE` to cast to a Snowflake type.

```sql
-- Top-level fields
SELECT
    raw_order:order_id::NUMBER       AS order_id,
    raw_order:status::VARCHAR        AS status,
    raw_order:order_date::DATE       AS order_date,
    raw_order:total::NUMBER(10,2)    AS total
FROM ECOMM_DB.RAW_DATA.ORDERS_JSON;

-- Nested fields (dot notation inside the JSON)
SELECT
    raw_order:order_id::NUMBER           AS order_id,
    raw_order:customer.name::VARCHAR     AS customer_name,
    raw_order:customer.city::VARCHAR     AS city,
    raw_order:customer.tier::VARCHAR     AS tier
FROM ECOMM_DB.RAW_DATA.ORDERS_JSON;

-- Array element by index (zero-based)
SELECT
    raw_order:order_id::NUMBER           AS order_id,
    raw_order:items[0].product::VARCHAR  AS first_item,
    raw_order:items[0].price::NUMBER     AS first_item_price
FROM ECOMM_DB.RAW_DATA.ORDERS_JSON;
```

### LATERAL FLATTEN — Explode Arrays into Rows

When a JSON field is an array, `LATERAL FLATTEN` turns each element into its own row — like `UNNEST` in other databases.

```sql
-- Each item in the items array becomes its own row
SELECT
    o.raw_order:order_id::NUMBER      AS order_id,
    o.raw_order:customer.name::VARCHAR AS customer_name,
    item.value:product::VARCHAR        AS product,
    item.value:qty::NUMBER             AS qty,
    item.value:price::NUMBER(10,2)     AS price
FROM ECOMM_DB.RAW_DATA.ORDERS_JSON o,
     LATERAL FLATTEN(input => o.raw_order:items) item;
-- Alice's order produces 2 rows (Headphones + Phone Case)
-- Bob's order produces 1 row (Running Shoes)
-- Priya's order produces 2 rows (Coffee Maker + Coffee Beans)
-- Total: 5 rows
```

### Flatten and load into ORDERS_RAW

After parsing the JSON, you can insert the structured data into the existing Day 4 table:

```sql
-- Flatten JSON and load into ORDERS_RAW
INSERT INTO ECOMM_DB.RAW_DATA.ORDERS_RAW
    (order_id, customer_id, customer_name, product, quantity,
     unit_price, total_amount, status, order_date)
SELECT
    j.raw_order:order_id::NUMBER                        AS order_id,
    -- customer_id not in JSON, derive or default
    ROW_NUMBER() OVER (ORDER BY j.raw_order:order_id)   AS customer_id,
    j.raw_order:customer.name::VARCHAR                  AS customer_name,
    item.value:product::VARCHAR                         AS product,
    item.value:qty::NUMBER                              AS quantity,
    item.value:price::NUMBER(10,2)                      AS unit_price,
    item.value:price::NUMBER(10,2) * item.value:qty::NUMBER AS total_amount,
    j.raw_order:status::VARCHAR                         AS status,
    j.raw_order:order_date::DATE                        AS order_date
FROM ECOMM_DB.RAW_DATA.ORDERS_JSON j,
     LATERAL FLATTEN(input => j.raw_order:items) item;

-- Verify
SELECT * FROM ECOMM_DB.RAW_DATA.ORDERS_RAW
WHERE order_id >= 3001
ORDER BY order_id;
```

### Other Useful Functions for Semi-Structured Data

```sql
-- Check the type of a VARIANT value
SELECT TYPEOF(raw_order:total) FROM ORDERS_JSON;
-- Returns: 'DECIMAL'

-- Check if a key exists
SELECT raw_order:customer.loyalty_points IS NOT NULL AS has_loyalty
FROM ORDERS_JSON;

-- GET / GET_PATH — alternative to colon syntax
SELECT GET(raw_order, 'order_id')::NUMBER FROM ORDERS_JSON;
SELECT GET_PATH(raw_order, 'customer.city')::VARCHAR FROM ORDERS_JSON;

-- FLATTEN with index and key
SELECT
    raw_order:order_id::NUMBER AS order_id,
    item.index                 AS item_position,
    item.key                   AS field_name,
    item.value                 AS field_value
FROM ORDERS_JSON,
     LATERAL FLATTEN(input => raw_order:items[0]) item;
-- Expands first item's key-value pairs into rows
```

---

## Concept 3 — Query Optimization

### 3a — Result Cache

Snowflake automatically caches the **exact result** of every query for 24 hours. If you run the identical query again (same SQL, same table data, same session parameters), Snowflake returns the cached result — **no warehouse compute used, instant response**.

```sql
-- First run: warehouse processes the query
SELECT order_date, SUM(total_amount) AS revenue
FROM ECOMM_DB.STAGING.STG_ORDERS
WHERE is_deleted = FALSE
GROUP BY order_date;

-- Second run (identical SQL, data unchanged): returns from cache instantly
-- Check in Snowsight Query History: "Results Reused From Cache" = true
SELECT order_date, SUM(total_amount) AS revenue
FROM ECOMM_DB.STAGING.STG_ORDERS
WHERE is_deleted = FALSE
GROUP BY order_date;
```

**Cache is invalidated when:**
- The underlying table data changes (INSERT, UPDATE, DELETE)
- 24 hours pass
- The SQL changes even by one character (including whitespace)
- Session parameters that affect the query change

### 3b — Clustering Keys

Snowflake stores data in **micro-partitions** — small compressed files (~50–500MB uncompressed). When you query with a filter like `WHERE order_date = '2024-01-10'`, Snowflake scans only the micro-partitions that contain that date — this is called **partition pruning**.

By default, micro-partitions are ordered by **insertion order** — data for many dates is mixed across all partitions. A **clustering key** tells Snowflake to reorganize the data so rows with the same `order_date` values land in the same micro-partitions.

```
Without clustering (insertion order):
  Partition 1: order_id 1,5,9,12 — dates: Jan10, Jan12, Jan10, Jan11 (mixed)
  Partition 2: order_id 2,6,10,3 — dates: Jan10, Jan13, Jan11, Jan12 (mixed)
  → WHERE order_date='Jan10' must scan ALL partitions

With clustering on order_date:
  Partition 1: all Jan10 rows
  Partition 2: all Jan11 rows
  → WHERE order_date='Jan10' scans only Partition 1
```

```sql
-- Add a clustering key to ORDERS_RAW on order_date
ALTER TABLE ECOMM_DB.RAW_DATA.ORDERS_RAW
    CLUSTER BY (order_date);

-- Check clustering info
SELECT SYSTEM$CLUSTERING_INFORMATION('ECOMM_DB.RAW_DATA.ORDERS_RAW', '(order_date)');
-- Returns: average_overlaps (lower = better clustering), average_depth

-- Check the clustering state of the table
SHOW TABLES LIKE 'ORDERS_RAW' IN SCHEMA ECOMM_DB.RAW_DATA;
-- CLUSTERING_KEY column shows the key

-- Remove clustering key (stops Snowflake from maintaining it)
ALTER TABLE ECOMM_DB.RAW_DATA.ORDERS_RAW DROP CLUSTERING KEY;
```

**When to use clustering keys:**
- Table is large (100GB+) and queries always filter on the same column(s)
- Common filter columns: `order_date`, `region`, `customer_id`
- Not worth it on small tables — Snowflake already scans them fast

**Clustering cost:** Snowflake automatically re-clusters the table in the background (called **Automatic Clustering**). This uses serverless compute — you pay per second of clustering work. Enable only when query performance gains justify the cost.

### 3c — Query Profile

The **Query Profile** in Snowsight shows you a visual breakdown of where a query spent its time — which operators ran, how long each took, and how many rows passed through each step.

**How to access:**
1. Run a query in Snowsight
2. Click the query in the Results pane → "Query Profile" tab
3. Or: Activity → Query History → click any query → Query Profile

**Key things to look at:**

| Node type | What it means |
|---|---|
| `TableScan` | Reading data from a table — check "Partitions scanned vs total" |
| `Aggregate` | GROUP BY / COUNT / SUM — expensive if millions of rows |
| `Join` | Joining tables — check "Build side rows" and "Probe side rows" |
| `Filter` | WHERE clause applied — check rows in vs rows out |
| `Sort` | ORDER BY — avoidable if you don't need sorted output |

**Partition pruning check:**

```sql
-- Run this query
SELECT * FROM ECOMM_DB.RAW_DATA.ORDERS_RAW
WHERE order_date = '2024-01-10';

-- In Query Profile → TableScan node:
-- "Partitions scanned: 1 out of 5" = good pruning
-- "Partitions scanned: 5 out of 5" = no pruning, full table scan
```

### 3d — Other Optimization Tips

```sql
-- 1. Avoid SELECT * in production — scan only columns you need
-- Bad
SELECT * FROM STG_ORDERS;
-- Good
SELECT order_id, status, total_amount FROM STG_ORDERS;

-- 2. Filter early — push WHERE clauses as close to the table as possible
-- Snowflake's optimizer handles this automatically in most cases

-- 3. Use LIMIT when exploring data — stops scanning after N rows
SELECT * FROM ORDERS_RAW LIMIT 10;

-- 4. Warehouse sizing — if a query is slow, try a larger warehouse
--    XS = 1 node, S = 2 nodes, M = 4 nodes, L = 8 nodes (doubles each time)
--    Good for: complex joins, large aggregations, heavy COPY INTO
ALTER WAREHOUSE COMPUTE_WH SET WAREHOUSE_SIZE = 'SMALL';
-- Scale back down after the heavy query
ALTER WAREHOUSE COMPUTE_WH SET WAREHOUSE_SIZE = 'X-SMALL';

-- 5. Auto-suspend — don't pay for idle time
ALTER WAREHOUSE COMPUTE_WH SET AUTO_SUSPEND = 60;  -- suspend after 60s idle
```

---

## Summary

| Concept | Key command | Use |
|---|---|---|
| Time Travel (query past) | `SELECT * FROM t AT (OFFSET => -3600)` | Query historical state |
| Time Travel (recover rows) | `INSERT ... SELECT * FROM t BEFORE (STATEMENT => 'id')` | Restore deleted/updated rows |
| UNDROP | `UNDROP TABLE t` | Recover a dropped table |
| VARIANT | `raw_order:field::TYPE` | Query JSON fields |
| LATERAL FLATTEN | `LATERAL FLATTEN(input => col:array)` | Explode JSON arrays into rows |
| Result cache | Automatic | Same query, no compute cost |
| Clustering key | `ALTER TABLE t CLUSTER BY (col)` | Speed up range scans on large tables |
| Query Profile | Snowsight → Query History | Find slow operators, check pruning |

**Day 7 topics remaining:** Dynamic Tables, Data Sharing (deep dive), Materialized Views, Stored Procedures, Snowpark (Python in Snowflake), Row Access Policies, Column Masking Policies.
