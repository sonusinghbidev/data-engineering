# Day 5 — Practice Exercises: Snowpipe, Cloning & Data Sharing

> Run everything in Snowsight in order. Each exercise builds on the previous.
> Estimated total time: 60–90 minutes.

---

## Setup — Run This Once

```sql
USE ROLE SYSADMIN;
USE WAREHOUSE COMPUTE_WH;
USE DATABASE ECOMM_DB;
USE SCHEMA RAW_DATA;
```

---

## Exercise 1 — Snowpipe: Create a Pipe and Load Files Manually

**What we are testing:** Pipe creation, stage upload, `ALTER PIPE REFRESH`, load history.

### Step 1: Create the target table and internal stage

```sql
USE SCHEMA ECOMM_DB.RAW_DATA;

CREATE OR REPLACE TABLE ORDERS_INGEST (
    order_id      NUMBER,
    customer_name VARCHAR(200),
    product       VARCHAR(200),
    quantity      NUMBER,
    total_amount  NUMBER(10,2),
    status        VARCHAR(50),
    order_date    DATE
);

CREATE OR REPLACE STAGE ORDERS_STAGE
    FILE_FORMAT = (
        TYPE                         = 'CSV'
        SKIP_HEADER                  = 1
        FIELD_OPTIONALLY_ENCLOSED_BY = '"'
        NULL_IF                      = ('NULL', 'null', '')
    );
```

### Step 2: Create the pipe

```sql
CREATE OR REPLACE PIPE ECOMM_DB.RAW_DATA.ORDERS_PIPE
    AUTO_INGEST = FALSE
    COMMENT     = 'Loads CSV order files from ORDERS_STAGE'
AS
COPY INTO ECOMM_DB.RAW_DATA.ORDERS_INGEST
FROM @ECOMM_DB.RAW_DATA.ORDERS_STAGE
FILE_FORMAT = (
    TYPE                         = 'CSV'
    SKIP_HEADER                  = 1
    FIELD_OPTIONALLY_ENCLOSED_BY = '"'
);
```

### Step 3: Verify the pipe was created

```sql
SHOW PIPES IN DATABASE ECOMM_DB;
-- Should see ORDERS_PIPE with definition status = RUNNING

-- Check pipe status
SELECT SYSTEM$PIPE_STATUS('ECOMM_DB.RAW_DATA.ORDERS_PIPE');
-- Look for: "executionState": "RUNNING"
```

### Step 4: Create a CSV file and upload it to the stage

Snowsight does not support `PUT` — use SnowSQL CLI or the Snowsight stage file browser.

**Option A — SnowSQL CLI (if installed):**
1. Create a local file `orders_batch1.csv` with this content:
```
order_id,customer_name,product,quantity,total_amount,status,order_date
1001,Alice Johnson,Wireless Headphones,1,149.99,CONFIRMED,2024-01-10
1002,Bob Smith,Running Shoes,2,179.98,CONFIRMED,2024-01-10
1003,Priya Sharma,Coffee Maker,1,129.99,SHIPPED,2024-01-11
1004,Carlos Mendez,Python Book,3,149.97,PENDING,2024-01-11
1005,Yuki Tanaka,Yoga Mat,2,79.98,DELIVERED,2024-01-12
```
2. Run from terminal: `PUT file:///path/to/orders_batch1.csv @ECOMM_DB.RAW_DATA.ORDERS_STAGE;`

**Option B — Snowsight stage browser:**
1. Go to Data → Databases → ECOMM_DB → RAW_DATA → Stages → ORDERS_STAGE
2. Click the upload icon and upload the CSV file

### Step 5: Confirm the file is in the stage

```sql
LIST @ECOMM_DB.RAW_DATA.ORDERS_STAGE;
-- Should show orders_batch1.csv.gz (Snowflake auto-compresses)
```

### Step 6: Trigger Snowpipe to load the file

```sql
-- Scan the stage and queue new files for loading
ALTER PIPE ECOMM_DB.RAW_DATA.ORDERS_PIPE REFRESH;
-- Returns: number of files queued

-- Wait 10-20 seconds for the serverless compute to process
-- Then check load history
SELECT *
FROM TABLE(INFORMATION_SCHEMA.COPY_HISTORY(
    TABLE_NAME  => 'ORDERS_INGEST',
    START_TIME  => DATEADD('minutes', -5, CURRENT_TIMESTAMP())
))
ORDER BY LAST_LOAD_TIME DESC;
```

### Step 7: Verify the data loaded

```sql
SELECT * FROM ECOMM_DB.RAW_DATA.ORDERS_INGEST ORDER BY order_id;
-- Expected: 5 rows

SELECT COUNT(*) AS row_count FROM ECOMM_DB.RAW_DATA.ORDERS_INGEST;
-- Expected: 5
```

### Step 8: Upload a second batch and trigger again

Create `orders_batch2.csv`:
```
order_id,customer_name,product,quantity,total_amount,status,order_date
1006,Sophie Dubois,Standing Desk,1,499.99,CONFIRMED,2024-01-12
1007,Marco Rossi,Mechanical Keyboard,1,189.99,CONFIRMED,2024-01-13
1008,Aisha Patel,Smart Watch,1,299.99,PENDING,2024-01-13
```

Upload it to the stage and trigger refresh:
```sql
ALTER PIPE ECOMM_DB.RAW_DATA.ORDERS_PIPE REFRESH;

-- Wait ~20 seconds
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_INGEST;
-- Expected: 8 (5 from batch1 + 3 from batch2)

-- Load history should now show 2 files
SELECT file_name, row_count, status
FROM TABLE(INFORMATION_SCHEMA.COPY_HISTORY(
    TABLE_NAME  => 'ORDERS_INGEST',
    START_TIME  => DATEADD('minutes', -15, CURRENT_TIMESTAMP())
))
ORDER BY LAST_LOAD_TIME DESC;
```

### Step 9: Test idempotency — try to load batch1 again

```sql
-- Trigger refresh — batch1 is already loaded
ALTER PIPE ECOMM_DB.RAW_DATA.ORDERS_PIPE REFRESH;

-- Wait 20 seconds
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_INGEST;
-- Still 8 — batch1 was NOT loaded again (Snowpipe's dedup protection)

-- Load history shows batch1 as LOAD_IN_PROGRESS or not at all
SELECT file_name, row_count, status
FROM TABLE(INFORMATION_SCHEMA.COPY_HISTORY(
    TABLE_NAME  => 'ORDERS_INGEST',
    START_TIME  => DATEADD('minutes', -15, CURRENT_TIMESTAMP())
))
ORDER BY LAST_LOAD_TIME DESC;
```

**Question to answer:** Why did Snowpipe skip batch1 on the second refresh attempt?

---

## Exercise 2 — Snowpipe: Pause, Resume, and Inspect

**What we are testing:** Pipe lifecycle management.

### Step 1: Pause the pipe

```sql
ALTER PIPE ECOMM_DB.RAW_DATA.ORDERS_PIPE SET PIPE_EXECUTION_PAUSED = TRUE;

-- Confirm it's paused
SELECT SYSTEM$PIPE_STATUS('ECOMM_DB.RAW_DATA.ORDERS_PIPE');
-- "executionState" should be "PAUSED"
```

### Step 2: Try to load while paused

Create `orders_batch3.csv`:
```
order_id,customer_name,product,quantity,total_amount,status,order_date
1009,Lena Müller,Noise Cancelling Mic,1,79.99,CONFIRMED,2024-01-13
```

Upload to stage, then run refresh:
```sql
ALTER PIPE ECOMM_DB.RAW_DATA.ORDERS_PIPE REFRESH;

-- Check the count — should still be 8 (pipe is paused)
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_INGEST;
```

### Step 3: Resume and reload

```sql
ALTER PIPE ECOMM_DB.RAW_DATA.ORDERS_PIPE SET PIPE_EXECUTION_PAUSED = FALSE;

-- Trigger refresh again to pick up batch3
ALTER PIPE ECOMM_DB.RAW_DATA.ORDERS_PIPE REFRESH;

-- Wait ~20 seconds
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_INGEST;
-- Expected: 9
```

### Step 4: Check pipe usage history (compute cost)

```sql
SELECT *
FROM TABLE(INFORMATION_SCHEMA.PIPE_USAGE_HISTORY(
    DATE_RANGE_START => DATEADD('hours', -1, CURRENT_TIMESTAMP())
));
-- Shows credits consumed by Snowpipe's serverless compute
```

---

## Exercise 3 — Zero-Copy Cloning

**What we are testing:** Instant cloning, storage behavior, clone isolation, Time Travel clone.

### Step 1: Clone the RAW_DATA schema

```sql
-- Clone the entire schema — creates a snapshot of ORDERS_RAW, ORDERS_INGEST, all objects
CREATE SCHEMA ECOMM_DB.RAW_DATA_BACKUP CLONE ECOMM_DB.RAW_DATA;

-- Verify: clone should have all tables
SHOW TABLES IN SCHEMA ECOMM_DB.RAW_DATA_BACKUP;
```

### Step 2: Confirm the clone has the same data

```sql
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_INGEST;        -- source
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA_BACKUP.ORDERS_INGEST; -- clone
-- Both should return the same count
```

### Step 3: Modify the source, verify clone is isolated

```sql
-- Insert a new row into the SOURCE
INSERT INTO ECOMM_DB.RAW_DATA.ORDERS_INGEST
VALUES (9999, 'Test User', 'Test Product', 1, 50.00, 'PENDING', '2024-01-14');

-- Source has the new row
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_INGEST;        -- +1
-- Clone does NOT have it
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA_BACKUP.ORDERS_INGEST; -- same as before
```

**Key point:** The clone is an independent snapshot. Changes to the source after cloning do not appear in the clone.

### Step 4: Modify the clone, verify source is isolated

```sql
-- Delete from the CLONE
DELETE FROM ECOMM_DB.RAW_DATA_BACKUP.ORDERS_INGEST
WHERE order_id <= 1003;

-- Clone: fewer rows
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA_BACKUP.ORDERS_INGEST;

-- Source: unchanged
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_INGEST;
```

### Step 5: Clone a table at a point in time (Time Travel clone)

```sql
-- Check current row count
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_INGEST;

-- Simulate an accidental bad delete
DELETE FROM ECOMM_DB.RAW_DATA.ORDERS_INGEST WHERE order_id > 1005;

SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_INGEST;
-- Fewer rows now — disaster!

-- Find the query ID of the bad DELETE
SELECT query_id, query_text, start_time
FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(
    DATE_RANGE_START => DATEADD('minutes', -5, CURRENT_TIMESTAMP())
))
WHERE query_text ILIKE '%DELETE%ORDERS_INGEST%'
ORDER BY start_time DESC
LIMIT 1;
-- Copy the query_id

-- Clone the table as it was BEFORE the bad delete
CREATE TABLE ECOMM_DB.RAW_DATA.ORDERS_INGEST_RECOVERED
    CLONE ECOMM_DB.RAW_DATA.ORDERS_INGEST
    BEFORE (STATEMENT => '<paste-query-id-here>');

-- Verify: recovered table has all rows
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_INGEST_RECOVERED;

-- Restore: insert back the missing rows
INSERT INTO ECOMM_DB.RAW_DATA.ORDERS_INGEST
SELECT * FROM ECOMM_DB.RAW_DATA.ORDERS_INGEST_RECOVERED r
WHERE NOT EXISTS (
    SELECT 1 FROM ECOMM_DB.RAW_DATA.ORDERS_INGEST s
    WHERE s.order_id = r.order_id
);

SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_INGEST;
-- Back to full count
```

### Step 6: Clean up clones

```sql
DROP SCHEMA ECOMM_DB.RAW_DATA_BACKUP;
DROP TABLE ECOMM_DB.RAW_DATA.ORDERS_INGEST_RECOVERED;
```

---

## Exercise 4 — Data Sharing (Provider Side)

> **Note:** This exercise sets up the provider side. If you have a second Snowflake account (free trial), complete Exercise 5 from that account. Otherwise, complete steps 1–4 to practice the provider setup.

### Step 1: Create the mart summary table (if not from Day 4)

```sql
USE SCHEMA ECOMM_DB.MARTS;

CREATE TABLE IF NOT EXISTS ORDERS_MART (
    order_date        DATE PRIMARY KEY,
    total_orders      NUMBER,
    confirmed_orders  NUMBER,
    shipped_orders    NUMBER,
    delivered_orders  NUMBER,
    cancelled_orders  NUMBER,
    total_revenue     NUMBER(14,2),
    avg_order_value   NUMBER(10,2),
    mart_updated_at   TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Seed some data if the mart is empty
INSERT INTO ORDERS_MART
SELECT
    order_date,
    COUNT(*)                                                AS total_orders,
    SUM(CASE WHEN status = 'CONFIRMED'  THEN 1 ELSE 0 END) AS confirmed_orders,
    SUM(CASE WHEN status = 'SHIPPED'    THEN 1 ELSE 0 END) AS shipped_orders,
    SUM(CASE WHEN status = 'DELIVERED'  THEN 1 ELSE 0 END) AS delivered_orders,
    SUM(CASE WHEN status = 'CANCELLED'  THEN 1 ELSE 0 END) AS cancelled_orders,
    SUM(total_amount)                                       AS total_revenue,
    AVG(total_amount)                                       AS avg_order_value,
    CURRENT_TIMESTAMP()
FROM ECOMM_DB.RAW_DATA.ORDERS_INGEST
GROUP BY order_date;

SELECT * FROM ORDERS_MART ORDER BY order_date;
```

### Step 2: Create a Secure View (hide any sensitive columns from sharing)

```sql
USE SCHEMA ECOMM_DB.MARTS;

CREATE OR REPLACE SECURE VIEW ORDERS_PUBLIC_SUMMARY AS
SELECT
    order_date,
    total_orders,
    confirmed_orders,
    shipped_orders,
    delivered_orders,
    cancelled_orders,
    total_revenue,
    avg_order_value
FROM ORDERS_MART;

-- A SECURE view hides its SQL definition from consumers
-- A regular view shows the definition — consumers can reverse-engineer your logic
-- Use SECURE whenever sharing externally
```

### Step 3: Create the Share

```sql
USE ROLE ACCOUNTADMIN;  -- Data Sharing requires ACCOUNTADMIN

CREATE SHARE ORDERS_SUMMARY_SHARE
    COMMENT = 'Daily orders summary for BI partner — no PII';

-- Grant the minimum necessary permissions
GRANT USAGE  ON DATABASE ECOMM_DB                       TO SHARE ORDERS_SUMMARY_SHARE;
GRANT USAGE  ON SCHEMA ECOMM_DB.MARTS                   TO SHARE ORDERS_SUMMARY_SHARE;
GRANT SELECT ON VIEW ECOMM_DB.MARTS.ORDERS_PUBLIC_SUMMARY TO SHARE ORDERS_SUMMARY_SHARE;
```

### Step 4: Inspect the share

```sql
-- What is in the share?
DESC SHARE ORDERS_SUMMARY_SHARE;

-- All shares in your account
SHOW SHARES;
-- OUTBOUND shares are ones you created; INBOUND are ones shared to you
```

### Step 5: Add a consumer account (if you have one)

```sql
-- Get your own account identifier (to give to the consumer)
SELECT CURRENT_ORGANIZATION_NAME() || '.' || CURRENT_ACCOUNT_NAME();

-- Add the consumer account
ALTER SHARE ORDERS_SUMMARY_SHARE
    ADD ACCOUNTS = '<consumer_org_name>.<consumer_account_name>';

-- Verify
SHOW GRANTS TO SHARE ORDERS_SUMMARY_SHARE;
```

---

## Exercise 5 — Data Sharing (Consumer Side)

> Run this from the **consumer Snowflake account**. Skip if you only have one account.

```sql
USE ROLE ACCOUNTADMIN;

-- See available inbound shares
SHOW SHARES;
-- Find ORDERS_SUMMARY_SHARE from the provider account

-- Create a local database FROM the share (no data is copied)
CREATE DATABASE PARTNER_ORDERS
    FROM SHARE <provider_org>.<provider_account>.ORDERS_SUMMARY_SHARE;

-- Grant access to analysts in this account
GRANT IMPORTED PRIVILEGES ON DATABASE PARTNER_ORDERS TO ROLE SYSADMIN;

-- Query the live shared data using your own warehouse
USE ROLE SYSADMIN;
USE WAREHOUSE COMPUTE_WH;

SELECT * FROM PARTNER_ORDERS.MARTS.ORDERS_PUBLIC_SUMMARY ORDER BY order_date;

-- Now have the provider insert a new row in their account, then re-run this:
-- The new data should appear immediately — it is live, not a snapshot
```

---

## Exercise 6 — Full Consistency Check

Run this after all exercises to verify everything is in order.

```sql
USE ROLE SYSADMIN;

-- Pipe: still running?
SELECT SYSTEM$PIPE_STATUS('ECOMM_DB.RAW_DATA.ORDERS_PIPE');

-- Data loaded via pipe
SELECT COUNT(*) AS pipe_loaded FROM ECOMM_DB.RAW_DATA.ORDERS_INGEST;

-- Load history summary
SELECT
    file_name,
    row_count,
    status,
    LAST_LOAD_TIME
FROM TABLE(INFORMATION_SCHEMA.COPY_HISTORY(
    TABLE_NAME  => 'ORDERS_INGEST',
    START_TIME  => DATEADD('hours', -2, CURRENT_TIMESTAMP())
))
ORDER BY LAST_LOAD_TIME DESC;

-- Mart populated from ingest data
SELECT * FROM ECOMM_DB.MARTS.ORDERS_MART ORDER BY order_date;

-- Share still active
USE ROLE ACCOUNTADMIN;
SHOW SHARES;
DESC SHARE ORDERS_SUMMARY_SHARE;
```

---

## Teardown — Clean Up After Practice

```sql
USE ROLE ACCOUNTADMIN;

-- Remove consumer from the share (if added)
-- ALTER SHARE ORDERS_SUMMARY_SHARE REMOVE ACCOUNTS = '<consumer>';

-- Drop the share
DROP SHARE ORDERS_SUMMARY_SHARE;

USE ROLE SYSADMIN;

-- Drop the pipe
DROP PIPE ECOMM_DB.RAW_DATA.ORDERS_PIPE;

-- Drop the stage and ingest table
DROP STAGE ECOMM_DB.RAW_DATA.ORDERS_STAGE;
DROP TABLE ECOMM_DB.RAW_DATA.ORDERS_INGEST;

-- Confirm cleanup
SHOW PIPES    IN DATABASE ECOMM_DB;
SHOW STAGES   IN DATABASE ECOMM_DB;
SHOW SHARES;
```

---

## Summary of What You Practiced

| Exercise | Concept verified |
|---|---|
| 1 | Pipe creation, stage upload, REFRESH trigger, deduplication |
| 2 | Pause/resume pipe, observe blocked loading during pause |
| 3 | Clone schema, clone isolation, Time Travel recovery with BEFORE(STATEMENT) |
| 4 | Create Share, Secure View, grant privileges, inspect share |
| 5 | Consume a share from consumer account, live data visibility |
| 6 | End-to-end consistency check |

**Next:** Day 6 — Time Travel, Fail-Safe, and Query Optimization (clustering keys, result cache, query profile).
