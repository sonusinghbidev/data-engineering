# Day 5 — Stages, COPY INTO, Snowpipe, and Zero-Copy Cloning

## Context — Continuing from Day 4

Day 4 built this pipeline:
```
ORDERS_RAW  ──[stream]──►  STG_ORDERS  ──────────►  ORDERS_MART
              RAW_TO_STG_TASK (root, 1 min)
              STG_TO_MART_TASK (child, after root)
```

Day 5 adds the **ingestion layer** in front of that pipeline. Instead of inserting rows manually with `INSERT INTO`, we load data from CSV files using a Stage + COPY INTO + Snowpipe. The Day 4 stream and tasks take over from there — nothing in Day 4 changes.

```
CSV files  ──►  Internal Stage  ──►  COPY INTO / Snowpipe  ──►  ORDERS_RAW
                                                                      │
                                                              [Day 4 takes over]
                                                                      │
                                                                STG_ORDERS
                                                                      │
                                                                ORDERS_MART
```

**Tables used throughout Day 5 — all from Day 4, no new schemas:**

| Table | Schema |
|---|---|
| `ORDERS_RAW` | `ECOMM_DB.RAW_DATA` |
| `STG_ORDERS` | `ECOMM_DB.STAGING` |
| `ORDERS_MART` | `ECOMM_DB.MARTS` |

---

## Concept 1 — Stages

### What is a Stage?

A **Stage** is a Snowflake object that points to a file storage location. Files must land in a stage before Snowflake can load them into a table.

Think of it as a **landing zone** — your CSV / JSON / Parquet files arrive here first, then `COPY INTO` or Snowpipe moves the data into a table.

```
Your CSV files  ──►  Stage (landing zone)  ──►  ORDERS_RAW table
```

### Two Types of Stage

#### Internal Stage (Snowflake-managed storage)

Snowflake hosts the storage for you. No cloud bucket, no credentials to manage. Three sub-types:

| Sub-type | Reference | Auto-created? | Use |
|---|---|---|---|
| User stage | `@~` | Yes | Private to current user |
| Table stage | `@%table_name` | Yes | Tied to one specific table |
| Named stage | `@schema.stage_name` | No — you create it | Shared, reusable — use this in real pipelines |

**Named stage** is what you create and control. It is the right choice for any pipeline that multiple people or processes need to use.

#### External Stage (your cloud storage)

Snowflake reads from your own S3 bucket, Azure ADLS, or GCS container. You provide the URL and credentials. Files stay in your cloud storage — Snowflake never copies them in.

```sql
-- External stage — definition only, requires cloud credentials
CREATE STAGE my_s3_stage
    URL                 = 's3://my-bucket/orders/'
    STORAGE_INTEGRATION = my_s3_integration;
```

> External stages need a **Storage Integration** (OAuth trust between Snowflake and your cloud). We use **internal named stages** for today — no cloud credentials needed.

---

### Hands-On: Create a Named Internal Stage on ORDERS_RAW

```sql
USE ROLE SYSADMIN;
USE WAREHOUSE COMPUTE_WH;
USE SCHEMA ECOMM_DB.RAW_DATA;

-- Create a named internal stage matching the ORDERS_RAW column structure
CREATE OR REPLACE STAGE ORDERS_RAW_STAGE
    FILE_FORMAT = (
        TYPE                         = 'CSV'
        SKIP_HEADER                  = 1
        FIELD_OPTIONALLY_ENCLOSED_BY = '"'
        NULL_IF                      = ('NULL', 'null', '')
    )
    COMMENT = 'Internal stage for loading order CSV files into ORDERS_RAW';
```

Inspect it:

```sql
SHOW STAGES IN SCHEMA ECOMM_DB.RAW_DATA;

-- See the full definition
DESC STAGE ECOMM_DB.RAW_DATA.ORDERS_RAW_STAGE;

-- Confirm it is currently empty
LIST @ECOMM_DB.RAW_DATA.ORDERS_RAW_STAGE;
```

---

## Concept 2 — COPY INTO

### What is COPY INTO?

`COPY INTO` reads files from a stage and bulk-loads them into a Snowflake table. It is a **manual, batch command** — you run it when you want to load. It uses your virtual warehouse.

```
Stage  ──►  COPY INTO  ──►  ORDERS_RAW
```

### Key behaviors

- **Deduplication built-in** — tracks loaded files by name + size + last-modified. Re-running COPY INTO on the same file does NOT insert duplicate rows.
- **Atomic per file** — if a file fails halfway, zero rows from that file are inserted.
- **Transformation at load time** — cast, rename, or reorder columns inline using a SELECT.

---

### Hands-On: COPY INTO ORDERS_RAW

#### Step 1: Prepare your CSV file

Create a local file called `orders_batch1.csv` with this content:

```
order_id,customer_id,customer_name,product,quantity,unit_price,total_amount,status,order_date
1001,1,Alice Johnson,Wireless Headphones,1,149.99,149.99,CONFIRMED,2024-01-10
1002,2,Bob Smith,Running Shoes,2,89.99,179.98,CONFIRMED,2024-01-10
1003,3,Priya Sharma,Coffee Maker,1,129.99,129.99,SHIPPED,2024-01-11
1004,4,Carlos Mendez,Python Book,3,49.99,149.97,PENDING,2024-01-11
1005,5,Yuki Tanaka,Yoga Mat,2,39.99,79.98,DELIVERED,2024-01-12
```

#### Step 2: Upload the file to the stage

**Snowsight UI:** Data → Databases → ECOMM_DB → RAW_DATA → Stages → ORDERS_RAW_STAGE → Upload button

**SnowSQL CLI:** `PUT file:///path/to/orders_batch1.csv @ECOMM_DB.RAW_DATA.ORDERS_RAW_STAGE;`

Confirm it landed:

```sql
LIST @ECOMM_DB.RAW_DATA.ORDERS_RAW_STAGE;
-- Should show: orders_batch1.csv.gz  (Snowflake auto-compresses on upload)
```

#### Step 3: Run COPY INTO to load into ORDERS_RAW

```sql
USE SCHEMA ECOMM_DB.RAW_DATA;

COPY INTO ECOMM_DB.RAW_DATA.ORDERS_RAW
    (order_id, customer_id, customer_name, product, quantity,
     unit_price, total_amount, status, order_date)
FROM @ECOMM_DB.RAW_DATA.ORDERS_RAW_STAGE
FILE_FORMAT = (
    TYPE                         = 'CSV'
    SKIP_HEADER                  = 1
    FIELD_OPTIONALLY_ENCLOSED_BY = '"'
);
-- Output: status = LOADED, rows_loaded = 5, errors_seen = 0
```

> We explicitly name the target columns and skip `updated_at` — it uses `DEFAULT CURRENT_TIMESTAMP()` automatically.

#### Step 4: Verify ORDERS_RAW has the data

```sql
SELECT * FROM ECOMM_DB.RAW_DATA.ORDERS_RAW ORDER BY order_id;
-- 5 rows

SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW;
```

#### Step 5: The Day 4 stream captured these inserts automatically

```sql
-- Check the stream — should have 5 INSERT rows
SELECT order_id, customer_name, status, METADATA$ACTION, METADATA$ISUPDATE
FROM ECOMM_DB.RAW_DATA.ORDERS_RAW_STREAM;
-- All 5 rows show ACTION = 'INSERT', ISUPDATE = FALSE
```

#### Step 6: Trigger the Day 4 task to propagate to STAGING and MART

```sql
EXECUTE TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK;

-- Wait ~10 seconds, then verify all three layers
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW;      -- 5
SELECT COUNT(*) FROM ECOMM_DB.STAGING.STG_ORDERS;        -- 5
SELECT * FROM ECOMM_DB.MARTS.ORDERS_MART ORDER BY order_date;
-- 3 mart rows: Jan 10, Jan 11, Jan 12
```

#### Step 7: Run COPY INTO again on the same file — observe deduplication

```sql
COPY INTO ECOMM_DB.RAW_DATA.ORDERS_RAW
    (order_id, customer_id, customer_name, product, quantity,
     unit_price, total_amount, status, order_date)
FROM @ECOMM_DB.RAW_DATA.ORDERS_RAW_STAGE
FILE_FORMAT = (TYPE = 'CSV' SKIP_HEADER = 1);
-- Status: LOAD_SKIPPED — file already loaded, no duplicate rows inserted

SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW;
-- Still 5
```

#### Step 8: Load a second batch

Create `orders_batch2.csv`:

```
order_id,customer_id,customer_name,product,quantity,unit_price,total_amount,status,order_date
1006,6,Sophie Dubois,Standing Desk,1,499.99,499.99,CONFIRMED,2024-01-12
1007,7,Marco Rossi,Mechanical Keyboard,1,189.99,189.99,CONFIRMED,2024-01-13
1008,8,Aisha Patel,Smart Watch,1,299.99,299.99,PENDING,2024-01-13
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
-- 8 rows

-- Trigger tasks to push new rows through to STAGING and MART
EXECUTE TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK;

-- Verify
SELECT COUNT(*) FROM ECOMM_DB.STAGING.STG_ORDERS;
SELECT * FROM ECOMM_DB.MARTS.ORDERS_MART ORDER BY order_date;
```

#### Step 9: Check load history

```sql
SELECT file_name, row_count, status, last_load_time
FROM TABLE(INFORMATION_SCHEMA.COPY_HISTORY(
    TABLE_NAME  => 'ORDERS_RAW',
    START_TIME  => DATEADD('hours', -1, CURRENT_TIMESTAMP())
))
ORDER BY LAST_LOAD_TIME DESC;
```

---

## Key Properties — COPY INTO vs Task + COPY INTO vs Snowpipe

| Property | COPY INTO (manual) | Task + COPY INTO | Snowpipe |
|---|---|---|---|
| **Trigger** | You run it manually | Fixed schedule (min 1 min) | File arrival or REST API call |
| **Compute** | Your virtual warehouse | Your virtual warehouse | Snowflake-managed (serverless) |
| **Latency** | On demand | Up to 1 minute + startup | Seconds to ~1 minute |
| **Idle cost** | Zero | Warehouse may bill while idle | Zero — no files = no compute |
| **Duplicate prevention** | Built-in (64-day window) | You must handle it | Built-in (file metadata tracking) |
| **Cost model** | Warehouse credits | Warehouse credits | Per-second of serverless compute |
| **Best for** | One-time / ad-hoc loads | Scheduled micro-batches | Continuous file streaming |

---

## Concept 3 — Snowpipe

### What is Snowpipe?

Snowpipe is Snowflake's **automatic, continuous file ingestion** service. You create a **Pipe** object — which stage to watch and what COPY INTO to run — and Snowpipe runs it automatically whenever new files arrive.

```
File lands in stage  ──►  Snowpipe detects it  ──►  COPY INTO ORDERS_RAW  ──►  [Day 4 stream + tasks kick in]
```

**Two trigger modes:**

| Mode | How it works |
|---|---|
| **REST API / REFRESH** | You call the Snowpipe REST endpoint or run `ALTER PIPE ... REFRESH` to trigger a scan |
| **Auto-Ingest** | Cloud storage fires an event (S3 SNS / Azure Event Grid / GCS Pub/Sub) → Snowpipe picks it up automatically |

We use the `REFRESH` mode — works in Snowsight, no cloud event setup needed.

---

### Hands-On: Snowpipe into ORDERS_RAW

#### Step 1: Create the pipe

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

#### Step 2: Check pipe status

```sql
SHOW PIPES IN DATABASE ECOMM_DB;

SELECT SYSTEM$PIPE_STATUS('ECOMM_DB.RAW_DATA.ORDERS_RAW_PIPE');
-- Look for: "executionState": "RUNNING"
```

#### Step 3: Upload a new batch file

Create `orders_batch3.csv`:

```
order_id,customer_id,customer_name,product,quantity,unit_price,total_amount,status,order_date
1009,9,Lena Müller,Noise Cancelling Mic,1,79.99,79.99,CONFIRMED,2024-01-13
1010,10,James Lee,USB-C Hub,2,34.99,69.98,SHIPPED,2024-01-14
```

Upload to `ORDERS_RAW_STAGE`.

#### Step 4: Trigger Snowpipe to scan and load

```sql
-- Scan the stage — queues new files for loading by this pipe
ALTER PIPE ECOMM_DB.RAW_DATA.ORDERS_RAW_PIPE REFRESH;
-- Returns: filesScanned, filesQueued

-- Wait 15–20 seconds (serverless compute loads the file)
```

#### Step 5: Verify data reached ORDERS_RAW

```sql
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW;
-- Should show 10 (8 from earlier + 2 from batch3)

SELECT order_id, customer_name, product, status
FROM ECOMM_DB.RAW_DATA.ORDERS_RAW
WHERE order_id IN (1009, 1010);
```

#### Step 6: Trigger the Day 4 task to push through the pipeline

```sql
EXECUTE TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK;

SELECT COUNT(*) FROM ECOMM_DB.STAGING.STG_ORDERS;
-- 10 rows

SELECT * FROM ECOMM_DB.MARTS.ORDERS_MART ORDER BY order_date;
-- Jan 13 and Jan 14 now appear
```

#### Step 7: Test Snowpipe deduplication

```sql
-- Trigger REFRESH again — same files are already loaded
ALTER PIPE ECOMM_DB.RAW_DATA.ORDERS_RAW_PIPE REFRESH;

-- Wait 20 seconds
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW;
-- Still 10 — Snowpipe does not reload already-loaded files
```

#### Step 8: Pause and resume the pipe

```sql
ALTER PIPE ECOMM_DB.RAW_DATA.ORDERS_RAW_PIPE SET PIPE_EXECUTION_PAUSED = TRUE;

SELECT SYSTEM$PIPE_STATUS('ECOMM_DB.RAW_DATA.ORDERS_RAW_PIPE');
-- "executionState": "PAUSED"

-- Resume
ALTER PIPE ECOMM_DB.RAW_DATA.ORDERS_RAW_PIPE SET PIPE_EXECUTION_PAUSED = FALSE;

SELECT SYSTEM$PIPE_STATUS('ECOMM_DB.RAW_DATA.ORDERS_RAW_PIPE');
-- "executionState": "RUNNING"
```

#### Step 9: Check load history

```sql
SELECT file_name, row_count, status, last_load_time
FROM TABLE(INFORMATION_SCHEMA.COPY_HISTORY(
    TABLE_NAME  => 'ORDERS_RAW',
    START_TIME  => DATEADD('hours', -1, CURRENT_TIMESTAMP())
))
ORDER BY LAST_LOAD_TIME DESC;
```

---

## Concept 4 — Zero-Copy Cloning

### What is Zero-Copy Cloning?

Cloning creates an **instant copy** of a table, schema, or database that **costs zero extra storage** at clone time. The clone and the source share the same underlying data blocks — no bytes are duplicated.

```sql
CREATE DATABASE ECOMM_DB_DEV CLONE ECOMM_DB;
-- Runs in milliseconds regardless of size.
-- Storage cost at clone time: ZERO
```

This uses **Copy-on-Write (CoW)**: both the original and clone point to the same physical blocks. New storage is only allocated when either side is **modified** — and only for the changed blocks.

```
After cloning:
  ORDERS_RAW        ──► [Block A] [Block B] [Block C]
  ORDERS_RAW_BACKUP ──► [Block A] [Block B] [Block C]   ← same blocks, zero extra storage

After deleting rows from ORDERS_RAW_BACKUP:
  ORDERS_RAW        ──► [Block A] [Block B] [Block C]   ← untouched
  ORDERS_RAW_BACKUP ──► [Block A*] [Block B] [Block C]  ← only the changed partition is new
```

### What can be cloned?

| Object | Example |
|---|---|
| Table | `CREATE TABLE t2 CLONE t1` |
| Schema | `CREATE SCHEMA s2 CLONE s1` |
| Database | `CREATE DATABASE db2 CLONE db1` |
| Streams / Tasks | Cannot be cloned |

### Real-world use cases

| Scenario | Why |
|---|---|
| Dev/test environment | Clone prod DB → real data, zero storage cost |
| Pre-migration backup | Clone before a risky `ALTER TABLE` or bulk `UPDATE` |
| Disaster recovery | Accidentally deleted rows? Clone at a past point in time |
| Data science sandbox | Each analyst gets their own clone — modify freely, no prod impact |

---

### Hands-On: Zero-Copy Cloning on Day 4 Tables

#### Step 1: Clone ORDERS_RAW

```sql
USE SCHEMA ECOMM_DB.RAW_DATA;

-- Confirm source has data
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW;

-- Clone it instantly
CREATE TABLE ECOMM_DB.RAW_DATA.ORDERS_RAW_BACKUP
    CLONE ECOMM_DB.RAW_DATA.ORDERS_RAW;

-- Both have the same count — zero extra storage right now
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW;
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW_BACKUP;
```

#### Step 2: Verify isolation — source changes do not affect clone

```sql
-- Insert a new row into ORDERS_RAW
INSERT INTO ECOMM_DB.RAW_DATA.ORDERS_RAW
    (order_id, customer_id, customer_name, product, quantity, unit_price, total_amount, status, order_date)
VALUES (9999, 99, 'Test User', 'Test Product', 1, 50.00, 50.00, 'PENDING', '2024-01-15');

-- Source: has the new row
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW;        -- +1

-- Clone: does NOT have it
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW_BACKUP; -- unchanged
```

#### Step 3: Verify isolation — clone changes do not affect source

```sql
-- Delete some rows from the CLONE
DELETE FROM ECOMM_DB.RAW_DATA.ORDERS_RAW_BACKUP
WHERE order_id <= 1003;

-- Clone: fewer rows
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW_BACKUP;

-- Source: completely unaffected
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW;
```

#### Step 4: Clone the entire database (all schemas + tables at once)

```sql
-- Clone ECOMM_DB — creates ECOMM_DB_DEV with all schemas:
-- RAW_DATA, STAGING, MARTS — all tables cloned, all data accessible instantly
CREATE DATABASE ECOMM_DB_DEV CLONE ECOMM_DB;

-- Verify all schemas exist in the clone
SHOW SCHEMAS IN DATABASE ECOMM_DB_DEV;

-- Verify data is there
SELECT COUNT(*) FROM ECOMM_DB_DEV.RAW_DATA.ORDERS_RAW;
SELECT COUNT(*) FROM ECOMM_DB_DEV.STAGING.STG_ORDERS;
SELECT COUNT(*) FROM ECOMM_DB_DEV.MARTS.ORDERS_MART;
-- All match the source counts at clone time
```

#### Step 5: Time Travel clone — disaster recovery on ORDERS_RAW

```sql
USE SCHEMA ECOMM_DB.RAW_DATA;

-- Step 1: Note current row count
SELECT COUNT(*) FROM ORDERS_RAW;

-- Step 2: Accidental delete
DELETE FROM ORDERS_RAW WHERE order_id > 1005;
SELECT COUNT(*) FROM ORDERS_RAW;
-- Rows are gone!

-- Step 3: Find the bad query ID from history
SELECT query_id, query_text, start_time
FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(
    DATE_RANGE_START => DATEADD('minutes', -5, CURRENT_TIMESTAMP())
))
WHERE query_text ILIKE '%DELETE%ORDERS_RAW%'
ORDER BY start_time DESC
LIMIT 1;
-- Copy the query_id

-- Step 4: Clone ORDERS_RAW as it was BEFORE that query
CREATE TABLE ECOMM_DB.RAW_DATA.ORDERS_RAW_RECOVERED
    CLONE ECOMM_DB.RAW_DATA.ORDERS_RAW
    BEFORE (STATEMENT => '<paste-query-id-here>');

-- Step 5: Verify recovered data
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW_RECOVERED;
-- Full count before the accidental delete

-- Step 6: Restore the missing rows
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

-- Step 7: Verify full count is back
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW;

-- Step 8: Drop the recovery table
DROP TABLE ECOMM_DB.RAW_DATA.ORDERS_RAW_RECOVERED;
```

---

## Teardown

```sql
USE ROLE SYSADMIN;

-- Suspend tasks before dropping anything
ALTER TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK  SUSPEND;
ALTER TASK ECOMM_DB.RAW_DATA.STG_TO_MART_TASK SUSPEND;

-- Drop the pipe
DROP PIPE ECOMM_DB.RAW_DATA.ORDERS_RAW_PIPE;

-- Drop backup/dev objects
DROP TABLE    ECOMM_DB.RAW_DATA.ORDERS_RAW_BACKUP;
DROP DATABASE ECOMM_DB_DEV;

-- Confirm
SHOW PIPES IN DATABASE ECOMM_DB;
```

---

## Summary

| Concept | What it does | Key command |
|---|---|---|
| Internal Stage | File landing zone inside Snowflake | `CREATE STAGE ORDERS_RAW_STAGE FILE_FORMAT = (...)` |
| External Stage | Points to your S3 / ADLS / GCS | `CREATE STAGE ... URL='s3://...'` (definition only) |
| COPY INTO | Manual bulk load from stage → table | `COPY INTO ORDERS_RAW FROM @ORDERS_RAW_STAGE` |
| Snowpipe | Auto-load on file arrival, serverless | `CREATE PIPE ... AS COPY INTO ...` |
| Zero-Copy Clone | Instant copy, zero storage cost | `CREATE TABLE t2 CLONE t1` |
| Time Travel Clone | Recover from accidental deletes | `CLONE ... BEFORE (STATEMENT => 'query_id')` |

**Next:** Day 6 — Time Travel, Fail-Safe, and Query Optimization.
