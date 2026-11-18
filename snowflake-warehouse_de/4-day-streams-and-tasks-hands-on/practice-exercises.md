# Day 4 — Practice Exercises: RAW → STAGING → MART Pipeline

> Run everything in Snowsight, in order. Each round builds on the previous one.
> After every round: check all three layers to confirm the pipeline behaved correctly.
> Estimated total time: 60–90 minutes.

---

## Setup — Run This Once

If you completed Day 3 exercises, your database already exists. If starting fresh, run the full setup from `notes.md` Step 1 through Step 4 first, then come back here.

```sql
-- Quick check: confirm all objects exist before starting
SHOW TABLES    IN DATABASE ECOMM_DB;
SHOW STREAMS   IN DATABASE ECOMM_DB;
SHOW TASKS     IN DATABASE ECOMM_DB;
```

You should see:
- Tables: `ORDERS_RAW`, `STG_ORDERS`, `ORDERS_MART`
- Streams: `ORDERS_RAW_STREAM`, `STG_ORDERS_STREAM`
- Tasks: `RAW_TO_STG_TASK` (started), `STG_TO_MART_TASK` (started)

---

## Round 1 — First Batch: Pure Inserts

**What we are testing:** New orders flow from RAW → STAGING → MART correctly.

### Step 1: Insert 6 orders into RAW

```sql
USE ROLE SYSADMIN;
USE WAREHOUSE COMPUTE_WH;
USE SCHEMA ECOMM_DB.RAW_DATA;

INSERT INTO ORDERS_RAW
    (order_id, customer_id, customer_name, product, quantity, unit_price, total_amount, status, order_date)
VALUES
    (1001, 1, 'Alice Johnson',  'Wireless Headphones', 1, 149.99, 149.99, 'CONFIRMED',  '2024-01-10'),
    (1002, 2, 'Bob Smith',      'Running Shoes',       2,  89.99, 179.98, 'CONFIRMED',  '2024-01-10'),
    (1003, 3, 'Priya Sharma',   'Coffee Maker',        1, 129.99, 129.99, 'SHIPPED',    '2024-01-11'),
    (1004, 4, 'Carlos Mendez',  'Python Book',         3,  49.99, 149.97, 'PENDING',    '2024-01-11'),
    (1005, 5, 'Yuki Tanaka',    'Yoga Mat',            2,  39.99,  79.98, 'DELIVERED',  '2024-01-12'),
    (1006, 6, 'Sophie Dubois',  'Standing Desk',       1, 499.99, 499.99, 'CONFIRMED',  '2024-01-12');
```

### Step 2: Check the stream captured all 6 rows

```sql
SELECT order_id, customer_name, product, status, METADATA$ACTION, METADATA$ISUPDATE
FROM ECOMM_DB.RAW_DATA.ORDERS_RAW_STREAM
ORDER BY order_id;
-- Expected: 6 rows, all METADATA$ACTION = 'INSERT', METADATA$ISUPDATE = FALSE
```

### Step 3: Trigger the task manually

```sql
EXECUTE TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK;
```

### Step 4: Wait ~10 seconds, then verify all three layers

```sql
-- RAW: 6 rows
SELECT COUNT(*) AS raw_count FROM ECOMM_DB.RAW_DATA.ORDERS_RAW;

-- STAGING: 6 rows, all is_deleted = FALSE
SELECT order_id, customer_name, product, status, total_amount, is_deleted
FROM ECOMM_DB.STAGING.STG_ORDERS
ORDER BY order_id;

-- MART: 3 rows (one per date: Jan 10, 11, 12)
SELECT * FROM ECOMM_DB.MARTS.ORDERS_MART ORDER BY order_date;

-- Stream: should be empty now
SELECT SYSTEM$STREAM_HAS_DATA('ECOMM_DB.RAW_DATA.ORDERS_RAW_STREAM') AS has_data;
-- Expected: FALSE
```

### Expected mart output

| order_date | total_orders | confirmed | shipped | delivered | cancelled | total_revenue | avg_order_value |
|---|---|---|---|---|---|---|---|
| 2024-01-10 | 2 | 2 | 0 | 0 | 0 | 329.97 | 164.99 |
| 2024-01-11 | 2 | 0 | 1 | 0 | 0 | 279.96 | 139.98 |
| 2024-01-12 | 2 | 1 | 0 | 1 | 0 | 579.97 | 289.99 |

---

## Round 2 — Status Updates: Orders Progress

**What we are testing:** UPDATEs flow correctly. Stream shows pre/post image. Mart reflects new status counts.

### Step 1: Update order statuses

```sql
USE SCHEMA ECOMM_DB.RAW_DATA;

-- Bob's order shipped
UPDATE ORDERS_RAW
SET status = 'SHIPPED', updated_at = CURRENT_TIMESTAMP()
WHERE order_id = 1002;

-- Priya's order delivered
UPDATE ORDERS_RAW
SET status = 'DELIVERED', updated_at = CURRENT_TIMESTAMP()
WHERE order_id = 1003;

-- Carlos cancelled his order
UPDATE ORDERS_RAW
SET status = 'CANCELLED', updated_at = CURRENT_TIMESTAMP()
WHERE order_id = 1004;
```

### Step 2: Inspect the stream — observe the pre/post image

```sql
SELECT order_id, customer_name, status, METADATA$ACTION, METADATA$ISUPDATE
FROM ECOMM_DB.RAW_DATA.ORDERS_RAW_STREAM
ORDER BY order_id, METADATA$ACTION DESC;
```

**What you should see for each updated order — 2 rows:**

| order_id | status | METADATA$ACTION | METADATA$ISUPDATE |
|---|---|---|---|
| 1002 | CONFIRMED | DELETE | TRUE  |  ← old value (before update)
| 1002 | SHIPPED   | INSERT | TRUE  |  ← new value (after update)
| 1003 | SHIPPED   | DELETE | TRUE  |  ← old value
| 1003 | DELIVERED | INSERT | TRUE  |  ← new value
| 1004 | PENDING   | DELETE | TRUE  |  ← old value
| 1004 | CANCELLED | INSERT | TRUE  |  ← new value

**Key observation:** Every UPDATE = 2 rows in the stream. The MERGE uses `METADATA$ACTION = 'INSERT'` to get the new value and `WHEN MATCHED` to overwrite the existing staging row.

### Step 3: Trigger the task

```sql
EXECUTE TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK;
```

### Step 4: Verify all three layers

```sql
-- STAGING: check the 3 orders have new statuses
SELECT order_id, customer_name, status, is_deleted, stg_updated_at
FROM ECOMM_DB.STAGING.STG_ORDERS
WHERE order_id IN (1002, 1003, 1004)
ORDER BY order_id;
-- 1002 → SHIPPED, 1003 → DELIVERED, 1004 → CANCELLED

-- MART: Jan 10 and Jan 11 totals should change
SELECT * FROM ECOMM_DB.MARTS.ORDERS_MART ORDER BY order_date;
```

**Expected mart changes:**

| order_date | confirmed | shipped | delivered | cancelled |
|---|---|---|---|---|
| 2024-01-10 | 1 | 1 | 0 | 0 | ← Bob moved from confirmed to shipped |
| 2024-01-11 | 0 | 0 | 1 | 1 | ← Priya delivered, Carlos cancelled |
| 2024-01-12 | 1 | 0 | 1 | 0 | ← unchanged |

---

## Round 3 — Hard Deletes: Cancelled Orders Removed from RAW

**What we are testing:** DELETE from RAW becomes a soft delete in STAGING (`is_deleted = TRUE`). Mart excludes soft-deleted rows.

### Step 1: Delete the cancelled order from RAW

```sql
USE SCHEMA ECOMM_DB.RAW_DATA;

-- Remove Carlos's cancelled order entirely from RAW
DELETE FROM ORDERS_RAW WHERE order_id = 1004;
```

### Step 2: Check the stream

```sql
SELECT order_id, customer_name, status, METADATA$ACTION, METADATA$ISUPDATE
FROM ECOMM_DB.RAW_DATA.ORDERS_RAW_STREAM;
-- Expected: 1 row, order_id=1004, METADATA$ACTION='DELETE', METADATA$ISUPDATE=FALSE
```

This is a **hard delete** (not an update) — `METADATA$ISUPDATE = FALSE` confirms it.

### Step 3: Trigger the task

```sql
EXECUTE TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK;
```

### Step 4: Verify

```sql
-- RAW: Carlos is gone
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW;
-- Expected: 5

-- STAGING: Carlos still exists but is_deleted = TRUE
SELECT order_id, customer_name, status, is_deleted, stg_updated_at
FROM ECOMM_DB.STAGING.STG_ORDERS
WHERE order_id = 1004;
-- Expected: 1 row, is_deleted = TRUE

-- STAGING: total row count is still 6 (soft delete preserves the row)
SELECT COUNT(*) FROM ECOMM_DB.STAGING.STG_ORDERS;
-- Expected: 6

-- MART: Jan 11 should now show 1 total order (Carlos excluded)
SELECT * FROM ECOMM_DB.MARTS.ORDERS_MART ORDER BY order_date;
```

**Expected Jan 11 in mart:**

| order_date | total_orders | delivered | cancelled | total_revenue |
|---|---|---|---|---|
| 2024-01-11 | 1 | 1 | 0 | 129.99 | ← only Priya, Carlos excluded |

---

## Round 4 — New Orders + Partial Updates Together

**What we are testing:** Mixed batch — new orders and updates arriving at the same time. Everything processes in one task run.

### Step 1: Insert new orders AND update existing ones simultaneously

```sql
USE SCHEMA ECOMM_DB.RAW_DATA;

-- New orders (Jan 13)
INSERT INTO ORDERS_RAW
    (order_id, customer_id, customer_name, product, quantity, unit_price, total_amount, status, order_date)
VALUES
    (1007, 7, 'Marco Rossi',  'Mechanical Keyboard', 1, 189.99, 189.99, 'CONFIRMED', '2024-01-13'),
    (1008, 8, 'Aisha Patel',  'Smart Watch',         1, 299.99, 299.99, 'PENDING',   '2024-01-13'),
    (1009, 9, 'Lena Müller',  'Noise Cancelling Mic',1,  79.99,  79.99, 'CONFIRMED', '2024-01-13');

-- Alice's headphones shipped
UPDATE ORDERS_RAW
SET status = 'SHIPPED', updated_at = CURRENT_TIMESTAMP()
WHERE order_id = 1001;

-- Sophie's desk delivered
UPDATE ORDERS_RAW
SET status = 'DELIVERED', updated_at = CURRENT_TIMESTAMP()
WHERE order_id = 1006;
```

### Step 2: Check stream — should have 3 inserts + 4 update rows (2 per update)

```sql
SELECT order_id, customer_name, status, METADATA$ACTION, METADATA$ISUPDATE
FROM ECOMM_DB.RAW_DATA.ORDERS_RAW_STREAM
ORDER BY order_id, METADATA$ACTION DESC;
-- Expected: 7 rows total
--   1001: DELETE(TRUE) + INSERT(TRUE)  — Alice update
--   1006: DELETE(TRUE) + INSERT(TRUE)  — Sophie update
--   1007: INSERT(FALSE)               — Marco new
--   1008: INSERT(FALSE)               — Aisha new
--   1009: INSERT(FALSE)               — Lena new
```

### Step 3: Trigger the task

```sql
EXECUTE TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK;
```

### Step 4: Verify all three layers

```sql
-- STAGING: 9 rows total (6 original + 3 new, Carlos still soft-deleted)
SELECT order_id, customer_name, product, status, is_deleted
FROM ECOMM_DB.STAGING.STG_ORDERS
ORDER BY order_id;

-- Alice and Sophie should have new statuses
SELECT order_id, customer_name, status FROM ECOMM_DB.STAGING.STG_ORDERS
WHERE order_id IN (1001, 1006);
-- 1001 → SHIPPED, 1006 → DELIVERED

-- MART: Jan 13 should appear as a new row
SELECT * FROM ECOMM_DB.MARTS.ORDERS_MART ORDER BY order_date;
```

**Expected mart after Round 4:**

| order_date | total_orders | confirmed | shipped | delivered | total_revenue |
|---|---|---|---|---|---|
| 2024-01-10 | 2 | 0 | 2 | 0 | 329.97 |
| 2024-01-11 | 1 | 0 | 0 | 1 | 129.99 |
| 2024-01-12 | 2 | 0 | 0 | 2 | 579.97 |
| 2024-01-13 | 3 | 2 | 0 | 0 | 569.97 |

---

## Round 5 — Quantity and Price Correction

**What we are testing:** Non-status updates (business data changes) also flow correctly.

### Step 1: Correct a quantity and recalculate the total

```sql
USE SCHEMA ECOMM_DB.RAW_DATA;

-- Lena ordered 2 mics, not 1 — correct the quantity and total
UPDATE ORDERS_RAW
SET quantity     = 2,
    total_amount = 159.98,
    updated_at   = CURRENT_TIMESTAMP()
WHERE order_id = 1009;

-- Aisha's watch moved to confirmed
UPDATE ORDERS_RAW
SET status     = 'CONFIRMED',
    updated_at = CURRENT_TIMESTAMP()
WHERE order_id = 1008;
```

### Step 2: Trigger and verify

```sql
EXECUTE TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK;

-- Check Lena's correction in staging
SELECT order_id, customer_name, quantity, total_amount, status
FROM ECOMM_DB.STAGING.STG_ORDERS
WHERE order_id IN (1008, 1009);
-- 1009: quantity=2, total_amount=159.98
-- 1008: status=CONFIRMED

-- Jan 13 mart row should update: revenue increases (79.99 → 159.98)
SELECT order_date, total_orders, confirmed_orders, total_revenue
FROM ECOMM_DB.MARTS.ORDERS_MART
WHERE order_date = '2024-01-13';
-- confirmed_orders: 3 (Marco, Aisha, Lena)
-- total_revenue: 649.96 (189.99 + 299.99 + 159.98)
```

---

## Round 6 — Full Consistency Check

**What we are testing:** All three layers match and nothing has been lost or duplicated.

```sql
-- 1. Count check: RAW vs STAGING (active rows only)
SELECT
    (SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW)                        AS raw_count,
    (SELECT COUNT(*) FROM ECOMM_DB.STAGING.STG_ORDERS WHERE is_deleted = FALSE) AS stg_active_count,
    (SELECT COUNT(*) FROM ECOMM_DB.STAGING.STG_ORDERS WHERE is_deleted = TRUE)  AS stg_deleted_count;
-- raw_count = stg_active_count. Deleted count = how many soft deletes exist.

-- 2. Revenue check: RAW vs STAGING (active rows only)
SELECT
    (SELECT SUM(total_amount) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW)                        AS raw_revenue,
    (SELECT SUM(total_amount) FROM ECOMM_DB.STAGING.STG_ORDERS WHERE is_deleted = FALSE) AS stg_revenue;
-- Should match exactly.

-- 3. Revenue check: STAGING vs MART
SELECT
    (SELECT SUM(total_amount) FROM ECOMM_DB.STAGING.STG_ORDERS WHERE is_deleted = FALSE) AS stg_revenue,
    (SELECT SUM(total_revenue) FROM ECOMM_DB.MARTS.ORDERS_MART)                           AS mart_revenue;
-- Should match exactly.

-- 4. Status distribution check: STAGING vs MART
SELECT status, COUNT(*) AS stg_count
FROM ECOMM_DB.STAGING.STG_ORDERS
WHERE is_deleted = FALSE
GROUP BY status
ORDER BY status;
-- Compare with mart columns (confirmed_orders, shipped_orders, etc.)

-- 5. Soft delete audit
SELECT order_id, customer_name, product, status, stg_updated_at
FROM ECOMM_DB.STAGING.STG_ORDERS
WHERE is_deleted = TRUE;
-- Should show only Carlos (order_id = 1004)

-- 6. Task run history — confirm both tasks succeeded every round
SELECT name, state, scheduled_time, completed_time, error_message
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
    SCHEDULED_TIME_RANGE_START => DATEADD('hours', -2, CURRENT_TIMESTAMP())
))
ORDER BY scheduled_time DESC;
-- All states should be SUCCEEDED (not FAILED or SKIPPED unexpectedly)
```

---

## Teardown — Suspend Tasks When Done

```sql
ALTER TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK  SUSPEND;
ALTER TASK ECOMM_DB.RAW_DATA.STG_TO_MART_TASK SUSPEND;

-- Confirm suspended
SHOW TASKS IN DATABASE ECOMM_DB;
-- Both should show state = "suspended"
```

Always suspend tasks after a practice session. Active tasks consume warehouse credits on every scheduled run.
