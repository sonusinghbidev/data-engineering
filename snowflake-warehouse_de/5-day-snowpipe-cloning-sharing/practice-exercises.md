# Day 5 — Practice Exercises: Stages, COPY INTO, Snowpipe, and Zero-Copy Cloning

> All exercises use the Day 4 tables — ORDERS_RAW, STG_ORDERS, ORDERS_MART — no new schemas.
> Run everything in Snowsight in order. Each exercise builds on the previous.
> Estimated total time: 60–75 minutes.

---

## Pre-Check — Confirm Day 4 Setup Exists

```sql
USE ROLE SYSADMIN;
USE WAREHOUSE COMPUTE_WH;

-- Confirm all Day 4 tables exist and have data
SELECT COUNT(*) AS raw_count FROM ECOMM_DB.RAW_DATA.ORDERS_RAW;
SELECT COUNT(*) AS stg_count FROM ECOMM_DB.STAGING.STG_ORDERS;
SELECT COUNT(*) AS mart_count FROM ECOMM_DB.MARTS.ORDERS_MART;

-- Confirm stream exists
SHOW STREAMS IN SCHEMA ECOMM_DB.RAW_DATA;

-- Confirm tasks exist
SHOW TASKS IN DATABASE ECOMM_DB;
```

> If any table is empty or missing, run Day 4 Steps 1–6 first to set up the pipeline and load initial data.

---

## Exercise 1 — Create a Named Internal Stage

**What we are testing:** Stage creation, file format definition, inspection.

```sql
USE SCHEMA ECOMM_DB.RAW_DATA;

-- Create a named internal stage matching ORDERS_RAW's structure
CREATE OR REPLACE STAGE ECOMM_DB.RAW_DATA.ORDERS_RAW_STAGE
    FILE_FORMAT = (
        TYPE                         = 'CSV'
        SKIP_HEADER                  = 1
        FIELD_OPTIONALLY_ENCLOSED_BY = '"'
        NULL_IF                      = ('NULL', 'null', '')
    )
    COMMENT = 'Internal stage for loading order CSV files into ORDERS_RAW';

-- Verify it was created
SHOW STAGES IN SCHEMA ECOMM_DB.RAW_DATA;

-- See its definition
DESC STAGE ECOMM_DB.RAW_DATA.ORDERS_RAW_STAGE;

-- Confirm it is empty
LIST @ECOMM_DB.RAW_DATA.ORDERS_RAW_STAGE;
-- Expected: 0 rows
```

**Question:** What is the difference between this named stage and a table stage (`@%ORDERS_RAW`)?

---

## Exercise 2 — COPY INTO ORDERS_RAW

**What we are testing:** File upload, COPY INTO, deduplication, loading into the existing Day 4 pipeline.

### Step 1: Prepare the CSV file

Create a local file `orders_batch1.csv` with this content (copy into a text editor and save):

```
order_id,customer_id,customer_name,product,quantity,unit_price,total_amount,status,order_date
2001,11,Nina Reyes,Bluetooth Speaker,1,89.99,89.99,CONFIRMED,2024-02-01
2002,12,Tom Baker,Gaming Mouse,2,49.99,99.98,CONFIRMED,2024-02-01
2003,13,Sara Kim,Desk Lamp,1,39.99,39.99,SHIPPED,2024-02-02
2004,14,Wei Zhang,Laptop Stand,1,79.99,79.99,PENDING,2024-02-02
2005,15,Ravi Patel,Webcam HD,1,119.99,119.99,DELIVERED,2024-02-03
```

> We start from order_id 2001 to avoid conflicts with any Day 4 data already in ORDERS_RAW.

### Step 2: Upload to the stage

**Snowsight UI:** Data → Databases → ECOMM_DB → RAW_DATA → Stages → ORDERS_RAW_STAGE → Upload button

**SnowSQL CLI:** `PUT file:///path/to/orders_batch1.csv @ECOMM_DB.RAW_DATA.ORDERS_RAW_STAGE;`

Confirm the file is there:
```sql
LIST @ECOMM_DB.RAW_DATA.ORDERS_RAW_STAGE;
-- Expected: orders_batch1.csv.gz
```

### Step 3: Load into ORDERS_RAW with COPY INTO

```sql
COPY INTO ECOMM_DB.RAW_DATA.ORDERS_RAW
    (order_id, customer_id, customer_name, product, quantity,
     unit_price, total_amount, status, order_date)
FROM @ECOMM_DB.RAW_DATA.ORDERS_RAW_STAGE
FILE_FORMAT = (
    TYPE                         = 'CSV'
    SKIP_HEADER                  = 1
    FIELD_OPTIONALLY_ENCLOSED_BY = '"'
);
-- Output: status = LOADED, rows_loaded = 5
```

> `updated_at` is not listed — it uses `DEFAULT CURRENT_TIMESTAMP()` automatically.

### Step 4: Verify ORDERS_RAW has the new rows

```sql
SELECT order_id, customer_name, product, status, order_date
FROM ECOMM_DB.RAW_DATA.ORDERS_RAW
WHERE order_id >= 2001
ORDER BY order_id;
-- Expected: 5 new rows
```

### Step 5: Confirm the Day 4 stream captured the inserts

```sql
SELECT order_id, customer_name, METADATA$ACTION, METADATA$ISUPDATE
FROM ECOMM_DB.RAW_DATA.ORDERS_RAW_STREAM;
-- 5 rows, all ACTION = 'INSERT', ISUPDATE = FALSE
```

### Step 6: Trigger the Day 4 task to push through STAGING and MART

```sql
EXECUTE TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK;

-- Wait ~10 seconds
SELECT COUNT(*) FROM ECOMM_DB.STAGING.STG_ORDERS;
-- Should include the 5 new rows

SELECT * FROM ECOMM_DB.MARTS.ORDERS_MART ORDER BY order_date;
-- Feb 01, Feb 02, Feb 03 should appear as new mart rows
```

### Step 7: Try loading the same file again — observe deduplication

```sql
COPY INTO ECOMM_DB.RAW_DATA.ORDERS_RAW
    (order_id, customer_id, customer_name, product, quantity,
     unit_price, total_amount, status, order_date)
FROM @ECOMM_DB.RAW_DATA.ORDERS_RAW_STAGE
FILE_FORMAT = (TYPE = 'CSV' SKIP_HEADER = 1);
-- Status: LOAD_SKIPPED — file already in dedup metadata

SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW;
-- Count unchanged — no duplicates
```

### Step 8: Load a second batch

Create `orders_batch2.csv`:
```
order_id,customer_id,customer_name,product,quantity,unit_price,total_amount,status,order_date
2006,16,Diana Prince,Ergonomic Chair,1,349.99,349.99,CONFIRMED,2024-02-03
2007,17,Ivan Drago,Protein Powder,3,29.99,89.97,PENDING,2024-02-04
2008,18,Maria Santos,Running Watch,1,249.99,249.99,SHIPPED,2024-02-04
```

Upload to `ORDERS_RAW_STAGE`, then:

```sql
COPY INTO ECOMM_DB.RAW_DATA.ORDERS_RAW
    (order_id, customer_id, customer_name, product, quantity,
     unit_price, total_amount, status, order_date)
FROM @ECOMM_DB.RAW_DATA.ORDERS_RAW_STAGE
FILE_FORMAT = (TYPE = 'CSV' SKIP_HEADER = 1);
-- batch1: LOAD_SKIPPED  |  batch2: LOADED (3 rows)

SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW;

-- Push through the pipeline
EXECUTE TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK;
SELECT * FROM ECOMM_DB.MARTS.ORDERS_MART ORDER BY order_date;
```

### Step 9: Check full load history

```sql
SELECT file_name, row_count, status, last_load_time
FROM TABLE(INFORMATION_SCHEMA.COPY_HISTORY(
    TABLE_NAME  => 'ORDERS_RAW',
    START_TIME  => DATEADD('hours', -1, CURRENT_TIMESTAMP())
))
ORDER BY LAST_LOAD_TIME DESC;
```

---

## Exercise 3 — Snowpipe into ORDERS_RAW

**What we are testing:** Pipe creation, REFRESH trigger, deduplication via pipe, pause/resume.

### Step 1: Create the pipe pointing to ORDERS_RAW

```sql
USE SCHEMA ECOMM_DB.RAW_DATA;

CREATE OR REPLACE PIPE ECOMM_DB.RAW_DATA.ORDERS_RAW_PIPE
    AUTO_INGEST = FALSE
    COMMENT     = 'Loads CSV files from ORDERS_RAW_STAGE into ORDERS_RAW'
AS
COPY INTO ECOMM_DB.RAW_DATA.ORDERS_RAW
    (order_id, customer_id, customer_name, product, quantity,
     unit_price, total_amount, status, order_date)
FROM @ECOMM_DB.RAW_DATA.ORDERS_RAW_STAGE
FILE_FORMAT = (
    TYPE                         = 'CSV'
    SKIP_HEADER                  = 1
    FIELD_OPTIONALLY_ENCLOSED_BY = '"'
);
```

### Step 2: Verify the pipe is running

```sql
SHOW PIPES IN DATABASE ECOMM_DB;

SELECT SYSTEM$PIPE_STATUS('ECOMM_DB.RAW_DATA.ORDERS_RAW_PIPE');
-- Look for: "executionState": "RUNNING"
```

### Step 3: Upload a new batch file

Create `orders_batch3.csv`:
```
order_id,customer_id,customer_name,product,quantity,unit_price,total_amount,status,order_date
2009,19,Fatima Al-Hassan,Smart Bulb Pack,2,24.99,49.98,CONFIRMED,2024-02-05
2010,20,Chen Wei,Tablet Stand,1,44.99,44.99,PENDING,2024-02-05
```

Upload to `ORDERS_RAW_STAGE`.

### Step 4: Trigger Snowpipe

```sql
-- The pipe has its own metadata — batch1 and batch2 were loaded by COPY INTO,
-- NOT by this pipe, so the pipe will load them too unless they are already in the stage.
-- batch3 is brand new for everyone — it will definitely load.
ALTER PIPE ECOMM_DB.RAW_DATA.ORDERS_RAW_PIPE REFRESH;
-- Returns: filesScanned, filesQueued

-- Wait 15–20 seconds
```

### Step 5: Verify data reached ORDERS_RAW

```sql
SELECT order_id, customer_name, product, status
FROM ECOMM_DB.RAW_DATA.ORDERS_RAW
WHERE order_id >= 2009
ORDER BY order_id;
-- Expected: 2009 and 2010 rows from batch3

-- Trigger tasks to push through the pipeline
EXECUTE TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK;
SELECT * FROM ECOMM_DB.MARTS.ORDERS_MART ORDER BY order_date;
-- Feb 05 should now appear
```

### Step 6: Trigger REFRESH again — test deduplication

```sql
ALTER PIPE ECOMM_DB.RAW_DATA.ORDERS_RAW_PIPE REFRESH;

-- Wait 20 seconds
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW;
-- Count unchanged — Snowpipe skips already-loaded files
```

### Step 7: Pause the pipe and test

```sql
ALTER PIPE ECOMM_DB.RAW_DATA.ORDERS_RAW_PIPE SET PIPE_EXECUTION_PAUSED = TRUE;

SELECT SYSTEM$PIPE_STATUS('ECOMM_DB.RAW_DATA.ORDERS_RAW_PIPE');
-- "executionState": "PAUSED"
```

Upload `orders_batch4.csv`:
```
order_id,customer_id,customer_name,product,quantity,unit_price,total_amount,status,order_date
2011,21,Oscar Nkosi,Coffee Grinder,1,69.99,69.99,CONFIRMED,2024-02-06
```

```sql
-- Trigger while paused — nothing should load
ALTER PIPE ECOMM_DB.RAW_DATA.ORDERS_RAW_PIPE REFRESH;

SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW;
-- Still same count — pipe is paused
```

### Step 8: Resume and recover the missed file

```sql
ALTER PIPE ECOMM_DB.RAW_DATA.ORDERS_RAW_PIPE SET PIPE_EXECUTION_PAUSED = FALSE;

ALTER PIPE ECOMM_DB.RAW_DATA.ORDERS_RAW_PIPE REFRESH;

-- Wait 20 seconds
SELECT order_id, customer_name FROM ECOMM_DB.RAW_DATA.ORDERS_RAW WHERE order_id = 2011;
-- Oscar's order should appear now

EXECUTE TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK;
SELECT * FROM ECOMM_DB.MARTS.ORDERS_MART ORDER BY order_date;
```

---

## Exercise 4 — Zero-Copy Cloning

**What we are testing:** Clone ORDERS_RAW, isolation, database clone, Time Travel recovery.

### Step 1: Clone ORDERS_RAW

```sql
USE SCHEMA ECOMM_DB.RAW_DATA;

SELECT COUNT(*) FROM ORDERS_RAW;  -- note the count

-- Clone instantly — zero extra storage
CREATE TABLE ECOMM_DB.RAW_DATA.ORDERS_RAW_BACKUP
    CLONE ECOMM_DB.RAW_DATA.ORDERS_RAW;

-- Both have the same count
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW;
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW_BACKUP;
```

### Step 2: Source changes do not affect the clone

```sql
-- Insert a row into the LIVE table
INSERT INTO ECOMM_DB.RAW_DATA.ORDERS_RAW
    (order_id, customer_id, customer_name, product, quantity,
     unit_price, total_amount, status, order_date)
VALUES (9999, 99, 'Test User', 'Test Product', 1, 50.00, 50.00, 'PENDING', '2024-02-07');

SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW;        -- +1
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW_BACKUP; -- unchanged
```

### Step 3: Clone changes do not affect the source

```sql
-- Delete from the BACKUP clone
DELETE FROM ECOMM_DB.RAW_DATA.ORDERS_RAW_BACKUP
WHERE order_id >= 2008;

SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW_BACKUP; -- fewer rows
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW;        -- unchanged
```

### Step 4: Clone the entire ECOMM_DB database

```sql
-- Clones all three schemas: RAW_DATA, STAGING, MARTS — instantly
CREATE DATABASE ECOMM_DB_DEV CLONE ECOMM_DB;

SHOW SCHEMAS IN DATABASE ECOMM_DB_DEV;

SELECT COUNT(*) FROM ECOMM_DB_DEV.RAW_DATA.ORDERS_RAW;
SELECT COUNT(*) FROM ECOMM_DB_DEV.STAGING.STG_ORDERS;
SELECT COUNT(*) FROM ECOMM_DB_DEV.MARTS.ORDERS_MART;
-- All match ECOMM_DB counts at clone time

-- Tasks in the dev clone are SUSPENDED — Snowflake auto-suspends to avoid conflicts
SHOW TASKS IN DATABASE ECOMM_DB_DEV;
-- state = "suspended" for all tasks
```

### Step 5: Time Travel recovery — restore accidentally deleted rows

```sql
USE SCHEMA ECOMM_DB.RAW_DATA;

-- Note count before
SELECT COUNT(*) FROM ORDERS_RAW;

-- Simulate accidental delete
DELETE FROM ORDERS_RAW WHERE order_date >= '2024-02-05';
SELECT COUNT(*) FROM ORDERS_RAW;
-- Rows gone!

-- Find the bad query
SELECT query_id, query_text, start_time
FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(
    DATE_RANGE_START => DATEADD('minutes', -5, CURRENT_TIMESTAMP())
))
WHERE query_text ILIKE '%DELETE%ORDERS_RAW%'
ORDER BY start_time DESC
LIMIT 1;
-- Copy the query_id

-- Clone ORDERS_RAW as it was BEFORE the bad delete
CREATE TABLE ECOMM_DB.RAW_DATA.ORDERS_RAW_RECOVERED
    CLONE ECOMM_DB.RAW_DATA.ORDERS_RAW
    BEFORE (STATEMENT => '<paste-query-id-here>');

-- Verify recovered table has the deleted rows
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW_RECOVERED;

-- Re-insert the missing rows
INSERT INTO ECOMM_DB.RAW_DATA.ORDERS_RAW
    (order_id, customer_id, customer_name, product, quantity,
     unit_price, total_amount, status, order_date, updated_at)
SELECT order_id, customer_id, customer_name, product, quantity,
       unit_price, total_amount, status, order_date, updated_at
FROM ECOMM_DB.RAW_DATA.ORDERS_RAW_RECOVERED r
WHERE NOT EXISTS (
    SELECT 1 FROM ECOMM_DB.RAW_DATA.ORDERS_RAW s
    WHERE s.order_id = r.order_id
);

-- Confirm full count is back
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW;

-- The stream captured the re-inserts — push them through the pipeline
EXECUTE TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK;
SELECT * FROM ECOMM_DB.MARTS.ORDERS_MART ORDER BY order_date;

-- Clean up recovery table
DROP TABLE ECOMM_DB.RAW_DATA.ORDERS_RAW_RECOVERED;
```

---

## Final Consistency Check

```sql
-- RAW count must equal active STAGING rows
SELECT
    (SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW)                         AS raw_count,
    (SELECT COUNT(*) FROM ECOMM_DB.STAGING.STG_ORDERS WHERE is_deleted = FALSE)  AS stg_active,
    (SELECT COUNT(*) FROM ECOMM_DB.STAGING.STG_ORDERS WHERE is_deleted = TRUE)   AS stg_deleted;

-- Revenue must match across layers
SELECT
    (SELECT SUM(total_amount)  FROM ECOMM_DB.RAW_DATA.ORDERS_RAW)                        AS raw_revenue,
    (SELECT SUM(total_amount)  FROM ECOMM_DB.STAGING.STG_ORDERS WHERE is_deleted = FALSE) AS stg_revenue,
    (SELECT SUM(total_revenue) FROM ECOMM_DB.MARTS.ORDERS_MART)                           AS mart_revenue;
-- All three should match
```

---

## Teardown

```sql
USE ROLE SYSADMIN;

-- Suspend tasks
ALTER TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK  SUSPEND;
ALTER TASK ECOMM_DB.RAW_DATA.STG_TO_MART_TASK SUSPEND;

-- Drop pipe
DROP PIPE ECOMM_DB.RAW_DATA.ORDERS_RAW_PIPE;

-- Drop backup/dev objects
DROP TABLE    ECOMM_DB.RAW_DATA.ORDERS_RAW_BACKUP;
DROP DATABASE ECOMM_DB_DEV;

-- Confirm
SHOW PIPES IN DATABASE ECOMM_DB;
```

---

## Summary

| Exercise | What you verified |
|---|---|
| 1 | Named internal stage creation, file format, inspection |
| 2 | COPY INTO into ORDERS_RAW, stream captures inserts, task propagates to STG + MART, dedup |
| 3 | Snowpipe into ORDERS_RAW, REFRESH trigger, dedup, pause → missed files → resume + REFRESH |
| 4 | Clone isolation, database clone, Time Travel BEFORE(STATEMENT) recovery + pipeline re-sync |

**Next:** Day 6 — Time Travel, Fail-Safe, and Query Optimization.
