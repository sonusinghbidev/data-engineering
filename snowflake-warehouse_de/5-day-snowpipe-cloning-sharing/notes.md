# Day 5 — Snowpipe, ADLS Auto-Ingest, and Zero-Copy Cloning & Sharing

## What You Will Learn

Three concepts that complete the data-loading and data-distribution picture in Snowflake:

1. **Snowpipe** — Continuous, micro-batch file ingestion. Files land in a stage → Snowpipe loads them automatically, within minutes, without you scheduling anything.
2. **Snowpipe with ADLS Auto-Ingest (Azure Event Grid)** — Event-driven ingestion. A file arrives in Azure Data Lake Storage → Azure fires an event → Snowpipe picks it up immediately. Zero polling, zero scheduling.
3. **Zero-Copy Cloning & Data Sharing** — Clone a full database/schema/table instantly with no data duplication. Share live data with another Snowflake account with no data movement.

---

## Concept 1 — Snowpipe: Continuous File Ingestion

### The Problem Snowpipe Solves

Day 3 showed you COPY INTO — it loads files from a stage into a table. But COPY INTO is a **manual, batch command**. Someone (or a scheduler) must run it. If you want files loaded within seconds/minutes of them arriving, you need Snowpipe.

```
Without Snowpipe:              With Snowpipe:
File lands in S3/ADLS/GCS     File lands in S3/ADLS/GCS
        │                               │
  wait for scheduler            Snowpipe detects it
        │                               │
  run COPY INTO                  loads it in minutes
        │                               │
  data available                 data available
  (minutes to hours)             (seconds to minutes)
```

### What is Snowpipe?

Snowpipe is a **serverless, continuous data ingestion service** built into Snowflake. You define a pipe object — which stage to watch and what COPY INTO to run — and Snowpipe takes care of the rest.

Key properties:
- **Serverless** — No virtual warehouse needed. Snowpipe uses Snowflake-managed compute. You pay per second of compute used, not per warehouse size.
- **Micro-batch** — Loads files as they arrive, not in large hourly batches. Latency is typically under 1 minute.
- **Idempotent** — Tracks which files have already been loaded (via a metadata table). Re-sending the same file does not create duplicates.
- **Two trigger modes** — REST API (you push a notification) or Auto-Ingest (cloud storage fires an event automatically).

### Architecture

```
Cloud Storage (S3 / ADLS / GCS)
        │
        │  file arrives
        ▼
    External Stage
        │
        │  Snowpipe monitors (REST) or receives event (auto-ingest)
        ▼
    Pipe Object  ──► COPY INTO your_table
        │
        ▼
    Target Table
```

### Step 1 — Create a Stage and Target Table

```sql
USE ROLE SYSADMIN;
USE WAREHOUSE COMPUTE_WH;
USE DATABASE ECOMM_DB;
USE SCHEMA RAW_DATA;

-- Target table: orders arriving as CSV files
CREATE OR REPLACE TABLE ORDERS_INGEST (
    order_id      NUMBER,
    customer_name VARCHAR(200),
    product       VARCHAR(200),
    quantity      NUMBER,
    total_amount  NUMBER(10,2),
    status        VARCHAR(50),
    order_date    DATE
);

-- Internal named stage (Snowflake-managed storage, no cloud creds needed)
-- Use this for demos and testing; production uses external stages (S3/ADLS/GCS)
CREATE OR REPLACE STAGE ORDERS_STAGE
    FILE_FORMAT = (
        TYPE            = 'CSV'
        SKIP_HEADER     = 1
        FIELD_OPTIONALLY_ENCLOSED_BY = '"'
        NULL_IF         = ('NULL', 'null', '')
    )
    COMMENT = 'Internal stage for order CSV files';
```

### Step 2 — Create the Pipe

```sql
CREATE OR REPLACE PIPE ECOMM_DB.RAW_DATA.ORDERS_PIPE
    AUTO_INGEST = FALSE   -- manual REST trigger; set TRUE for event-driven
    COMMENT     = 'Loads CSV files from ORDERS_STAGE into ORDERS_INGEST'
AS
COPY INTO ECOMM_DB.RAW_DATA.ORDERS_INGEST
FROM @ECOMM_DB.RAW_DATA.ORDERS_STAGE
FILE_FORMAT = (
    TYPE        = 'CSV'
    SKIP_HEADER = 1
    FIELD_OPTIONALLY_ENCLOSED_BY = '"'
);
```

The `AS` clause is a standard COPY INTO statement. Snowpipe runs this automatically every time it detects new files.

### Step 3 — Upload a File and Notify Snowpipe (REST mode)

For the internal stage demo, use `PUT` to upload a file from your local machine, then call `SYSTEM$PIPE_FORCE_RESUME` to trigger loading.

```sql
-- From SnowSQL CLI (not Snowsight) — uploads local CSV to the stage
-- PUT file:///tmp/orders_jan.csv @ECOMM_DB.RAW_DATA.ORDERS_STAGE;

-- In Snowsight: use the stage UI upload button, or use the REST API

-- Check what files are in the stage
LIST @ECOMM_DB.RAW_DATA.ORDERS_STAGE;

-- Manually trigger Snowpipe to scan the stage and load new files
-- (This calls the Snowpipe REST API internally)
ALTER PIPE ECOMM_DB.RAW_DATA.ORDERS_PIPE REFRESH;
```

> `ALTER PIPE ... REFRESH` is the Snowsight-friendly way to trigger a one-time re-scan. In production, your application calls the Snowpipe REST API: `POST /v1/data/pipes/<pipe_name>/insertFiles`.

### Step 4 — Monitor the Pipe

```sql
-- Current pipe status (paused, running, stale)
SELECT SYSTEM$PIPE_STATUS('ECOMM_DB.RAW_DATA.ORDERS_PIPE');

-- Load history: which files loaded, how many rows, any errors
SELECT *
FROM TABLE(INFORMATION_SCHEMA.COPY_HISTORY(
    TABLE_NAME  => 'ORDERS_INGEST',
    START_TIME  => DATEADD('hours', -1, CURRENT_TIMESTAMP())
));

-- Pipe-specific load history
SELECT *
FROM TABLE(INFORMATION_SCHEMA.PIPE_USAGE_HISTORY(
    DATE_RANGE_START => DATEADD('hours', -1, CURRENT_TIMESTAMP()),
    PIPE_NAME        => 'ECOMM_DB.RAW_DATA.ORDERS_PIPE'
));

-- Check the data landed
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_INGEST;
```

### Step 5 — Important Pipe Operations

```sql
-- Pause a pipe (stops loading new files; already-queued files may still load)
ALTER PIPE ECOMM_DB.RAW_DATA.ORDERS_PIPE SET PIPE_EXECUTION_PAUSED = TRUE;

-- Resume a pipe
ALTER PIPE ECOMM_DB.RAW_DATA.ORDERS_PIPE SET PIPE_EXECUTION_PAUSED = FALSE;

-- Force resume (use after a pipe goes stale)
SELECT SYSTEM$PIPE_FORCE_RESUME('ECOMM_DB.RAW_DATA.ORDERS_PIPE');

-- Show all pipes in the database
SHOW PIPES IN DATABASE ECOMM_DB;

-- Drop a pipe
DROP PIPE ECOMM_DB.RAW_DATA.ORDERS_PIPE;
```

### Key Properties — Snowpipe vs COPY INTO vs Tasks

| Property | COPY INTO | Task + COPY INTO | Snowpipe |
|---|---|---|---|
| Trigger | Manual | Scheduled (min 1 min) | File arrival / REST call |
| Compute | Virtual warehouse | Virtual warehouse | Serverless (managed) |
| Latency | On demand | Up to 1 minute | Seconds to 1 minute |
| Duplicate prevention | Manual tracking | Manual tracking | Built-in (file metadata) |
| Cost model | Warehouse credits | Warehouse credits | Per-second of serverless compute |
| Best for | One-time loads | Scheduled micro-batches | Continuous streaming files |

---

## Concept 2 — Snowpipe with ADLS Auto-Ingest (Azure Event Grid)

### The Problem

In Concept 1, your application calls the Snowpipe REST API to say "new files have arrived." That still requires your application to know about files and make an HTTP call. 

**What if you want zero application code?** A file lands in ADLS → Snowpipe loads it → Done. No REST calls, no polling, no task scheduler. That's what **Auto-Ingest** with **Azure Event Grid** delivers.

### How It Works

```
Your pipeline / ETL / IoT device
        │
        │  writes file
        ▼
Azure Data Lake Storage Gen2 (ADLS)
        │
        │  Azure Event Grid fires storage event (BlobCreated)
        ▼
Azure Storage Queue (SAS URL)
        │
        │  Snowpipe polls the queue (every few seconds)
        ▼
    Pipe Object (AUTO_INGEST = TRUE)
        │
        │  runs COPY INTO
        ▼
    Snowflake Table
```

Snowflake does not connect directly to ADLS. Instead, Azure Event Grid writes notifications to a **Storage Queue** that Snowflake has permission to read. This decouples the two systems.

### Full Setup Walkthrough

#### Part A — Azure Setup (done once per storage account)

```
1. In Azure Portal:
   - Open your Storage Account → Events
   - Create an Event Subscription:
       Name:            snowflake-ingest-sub
       Event types:     Microsoft.Storage.BlobCreated
       Endpoint type:   Storage Queue
       Queue:           (create a new queue, e.g. "snowpipe-queue")
       Filter prefix:   /blobServices/default/containers/orders-raw/blobs/
         (optional: only fire for files in a specific container/folder)
```

This means: whenever a blob is created under `orders-raw/`, write a message to `snowpipe-queue`.

#### Part B — Snowflake: Create the External Stage pointing to ADLS

```sql
USE ROLE ACCOUNTADMIN;  -- needs ACCOUNTADMIN to create integrations

-- Step 1: Create a Storage Integration (OAuth trust between Snowflake and Azure)
CREATE OR REPLACE STORAGE INTEGRATION AZURE_ORDERS_INT
    TYPE                      = EXTERNAL_STAGE
    STORAGE_PROVIDER          = 'AZURE'
    ENABLED                   = TRUE
    AZURE_TENANT_ID           = '<your-azure-tenant-id>'
    STORAGE_ALLOWED_LOCATIONS = ('azure://<storage-account>.blob.core.windows.net/orders-raw/');

-- Step 2: Retrieve the consent URL and service principal — give Azure permission
DESC INTEGRATION AZURE_ORDERS_INT;
-- Copy AZURE_CONSENT_URL → open in browser → grant consent
-- Copy AZURE_MULTI_TENANT_APP_NAME → in Azure, assign Storage Blob Data Reader role to this service principal

-- Step 3: Create a Notification Integration (lets Snowflake read the Event Grid queue)
CREATE OR REPLACE NOTIFICATION INTEGRATION AZURE_ORDERS_QUEUE_INT
    TYPE          = QUEUE
    NOTIFICATION_PROVIDER = AZURE_STORAGE_QUEUE
    ENABLED       = TRUE
    AZURE_STORAGE_QUEUE_PRIMARY_URI = 'https://<storage-account>.queue.core.windows.net/snowpipe-queue'
    AZURE_TENANT_ID = '<your-azure-tenant-id>';

-- Retrieve the queue service principal
DESC INTEGRATION AZURE_ORDERS_QUEUE_INT;
-- Assign "Storage Queue Data Contributor" role to the service principal shown in AZURE_MULTI_TENANT_APP_NAME

-- Step 4: Create the external stage pointing to the ADLS container
CREATE OR REPLACE STAGE ECOMM_DB.RAW_DATA.ADLS_ORDERS_STAGE
    URL                 = 'azure://<storage-account>.blob.core.windows.net/orders-raw/'
    STORAGE_INTEGRATION = AZURE_ORDERS_INT
    FILE_FORMAT         = (
        TYPE            = 'CSV'
        SKIP_HEADER     = 1
        FIELD_OPTIONALLY_ENCLOSED_BY = '"'
    );

-- Verify: list files in the ADLS container from Snowflake
LIST @ECOMM_DB.RAW_DATA.ADLS_ORDERS_STAGE;
```

#### Part C — Create the Auto-Ingest Pipe

```sql
USE ROLE SYSADMIN;

CREATE OR REPLACE PIPE ECOMM_DB.RAW_DATA.ADLS_ORDERS_PIPE
    AUTO_INGEST           = TRUE
    INTEGRATION           = 'AZURE_ORDERS_QUEUE_INT'   -- the notification integration
    COMMENT               = 'Auto-ingest from ADLS orders-raw container'
AS
COPY INTO ECOMM_DB.RAW_DATA.ORDERS_INGEST
FROM @ECOMM_DB.RAW_DATA.ADLS_ORDERS_STAGE
FILE_FORMAT = (
    TYPE        = 'CSV'
    SKIP_HEADER = 1
    FIELD_OPTIONALLY_ENCLOSED_BY = '"'
);
```

The pipe is now live. Drop an `orders_*.csv` file into the `orders-raw` ADLS container and Snowflake will load it within seconds — no REST call, no task.

#### Part D — Verify and Monitor

```sql
-- Is the pipe running and reading the queue?
SELECT SYSTEM$PIPE_STATUS('ECOMM_DB.RAW_DATA.ADLS_ORDERS_PIPE');
-- pendingFileCount: how many files are queued but not yet loaded
-- executionState:  RUNNING / PAUSED / STALE

-- Load history
SELECT *
FROM TABLE(INFORMATION_SCHEMA.COPY_HISTORY(
    TABLE_NAME  => 'ORDERS_INGEST',
    START_TIME  => DATEADD('hours', -1, CURRENT_TIMESTAMP())
))
ORDER BY LAST_LOAD_TIME DESC;

-- How many rows loaded?
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_INGEST;
```

### Troubleshooting Auto-Ingest

| Symptom | Likely cause | Fix |
|---|---|---|
| `executionState: STALE` | Pipe has not received queue messages in a long time | `SELECT SYSTEM$PIPE_FORCE_RESUME(...)` |
| Files in stage but `pendingFileCount = 0` | Event Grid subscription not set up, or wrong queue URL | Verify Event Grid → Queue subscription in Azure Portal |
| Files loaded but rows wrong | FILE_FORMAT mismatch (delimiter, header) | `SHOW FILE FORMATS` and compare |
| Permission denied on stage | Storage Integration service principal missing RBAC | Re-check Azure IAM — Storage Blob Data Reader |
| Queue SAS expired | Notification integration SAS token expired | Recreate the notification integration |

### Auto-Ingest vs REST trigger — When to use which

| Scenario | Use |
|---|---|
| Azure pipeline drops files in ADLS | Auto-Ingest (Event Grid) |
| AWS Lambda / GCP Cloud Function uploads files | Auto-Ingest (SNS / GCS Pub/Sub) |
| Your application directly calls Snowflake | REST trigger |
| On-premise ETL tool writes to an internal stage | REST trigger + `ALTER PIPE ... REFRESH` |
| Testing / demo | `ALTER PIPE ... REFRESH` |

---

## Concept 3 — Zero-Copy Cloning and Data Sharing

### Zero-Copy Cloning

#### What is it?

Cloning creates an **instant, zero-storage-cost copy** of a table, schema, or database. The clone shares the same underlying micro-partitions as the source — no data is physically copied. New storage is only allocated when the clone (or the source) is modified.

```
CREATE DATABASE ECOMM_DB_CLONE CLONE ECOMM_DB;
-- Runs in milliseconds, regardless of how big ECOMM_DB is.
-- Storage cost: zero (until writes happen to either copy)
```

This is called **Copy-on-Write (CoW)**: both copies point to the same data blocks; a new block is created only when a write diverges.

#### What can be cloned?

| Object | Syntax |
|---|---|
| Table | `CREATE TABLE t2 CLONE t1` |
| Schema | `CREATE SCHEMA s2 CLONE s1` |
| Database | `CREATE DATABASE db2 CLONE db1` |
| Stage | `CREATE STAGE stg2 CLONE stg1` |
| Stream | Cannot clone a stream directly |
| Task | Cannot clone a task directly |

```sql
-- Clone the entire ECOMM_DB (all schemas, tables, views, stages)
CREATE DATABASE ECOMM_DB_DEV CLONE ECOMM_DB;

-- Clone just the STAGING schema
CREATE SCHEMA ECOMM_DB.STAGING_BACKUP CLONE ECOMM_DB.STAGING;

-- Clone a single table
CREATE TABLE ECOMM_DB.RAW_DATA.ORDERS_RAW_BACKUP
    CLONE ECOMM_DB.RAW_DATA.ORDERS_RAW;

-- Clone at a point in time (Time Travel clone)
CREATE TABLE ECOMM_DB.RAW_DATA.ORDERS_RAW_YESTERDAY
    CLONE ECOMM_DB.RAW_DATA.ORDERS_RAW
    AT (OFFSET => -86400);  -- 24 hours ago
```

#### Real-world use cases

| Use case | How cloning helps |
|---|---|
| Dev/test environment | Clone prod database → developers test against realistic data, zero storage cost |
| Pre-migration backup | Clone before a risky ALTER TABLE or bulk UPDATE |
| Data science sandbox | Each analyst gets a cloned schema — they can modify freely without affecting others |
| Disaster recovery | Clone + Time Travel gives you point-in-time snapshots |
| A/B testing pipelines | Clone staging, run the new pipeline on the clone, compare results |

#### Clone + Time Travel

You can clone a table (or database) **at any point within its Time Travel window** (default 1 day, up to 90 days on Enterprise):

```sql
-- Clone as it was 2 hours ago
CREATE TABLE ORDERS_RAW_2H_AGO
    CLONE ECOMM_DB.RAW_DATA.ORDERS_RAW
    AT (OFFSET => -7200);

-- Clone as it was at a specific timestamp
CREATE TABLE ORDERS_RAW_BEFORE_LOAD
    CLONE ECOMM_DB.RAW_DATA.ORDERS_RAW
    AT (TIMESTAMP => '2024-01-10 08:00:00'::TIMESTAMP_NTZ);

-- Clone as it was just before a query ran
-- (use query ID from query history)
CREATE TABLE ORDERS_RAW_BEFORE_BAD_DELETE
    CLONE ECOMM_DB.RAW_DATA.ORDERS_RAW
    BEFORE (STATEMENT => '<query_id>');
```

#### Monitoring clones

```sql
-- List all clones of a table
SELECT table_name, table_catalog, table_schema, clone_group_id, bytes
FROM INFORMATION_SCHEMA.TABLES
WHERE clone_group_id IS NOT NULL;

-- Storage consumed by clone vs original (once writes diverge)
SELECT table_name, bytes / 1024 / 1024 AS size_mb
FROM INFORMATION_SCHEMA.TABLES
WHERE table_schema = 'RAW_DATA'
ORDER BY bytes DESC;
```

---

### Data Sharing

#### What is it?

Data Sharing lets you give **another Snowflake account live, read-only access to your data** — with no data movement, no ETL, no copies. The consumer queries your data directly from your storage using their own compute.

```
Provider Account (you)          Consumer Account (partner/customer)
  ECOMM_DB.MARTS.ORDERS_MART  ──────────────────────────────► SELECT * FROM ...
        │                                                           │
        └── data lives here                   consumer uses their own warehouse
                                              zero data transfer costs
```

This is built on the same micro-partition architecture as cloning — both accounts point to the same physical blocks.

#### Create and Use a Share (Provider side)

```sql
USE ROLE ACCOUNTADMIN;  -- Data Sharing requires ACCOUNTADMIN

-- Step 1: Create a share object
CREATE SHARE ORDERS_MART_SHARE
    COMMENT = 'Daily orders mart — shared with partner BI team';

-- Step 2: Grant database usage to the share
GRANT USAGE ON DATABASE ECOMM_DB TO SHARE ORDERS_MART_SHARE;
GRANT USAGE ON SCHEMA ECOMM_DB.MARTS TO SHARE ORDERS_MART_SHARE;

-- Step 3: Grant SELECT on specific tables/views
GRANT SELECT ON TABLE ECOMM_DB.MARTS.ORDERS_MART TO SHARE ORDERS_MART_SHARE;

-- Share a secure view instead of raw table (hides sensitive columns)
CREATE OR REPLACE SECURE VIEW ECOMM_DB.MARTS.ORDERS_MART_PUBLIC AS
SELECT order_date, total_orders, total_revenue, avg_order_value
FROM ECOMM_DB.MARTS.ORDERS_MART;

GRANT SELECT ON VIEW ECOMM_DB.MARTS.ORDERS_MART_PUBLIC TO SHARE ORDERS_MART_SHARE;

-- Step 4: Add the consumer's Snowflake account to the share
ALTER SHARE ORDERS_MART_SHARE ADD ACCOUNTS = '<consumer_account_identifier>';
-- Account identifier format: <org_name>.<account_name>  (e.g. MYORG.PARTNER_PROD)

-- View current share details
SHOW SHARES;
DESC SHARE ORDERS_MART_SHARE;
```

#### Consume a Share (Consumer side)

```sql
-- Consumer runs this in their own Snowflake account
USE ROLE ACCOUNTADMIN;

-- Create a database FROM the share (read-only, live data)
CREATE DATABASE PARTNER_ORDERS
    FROM SHARE <provider_account_identifier>.ORDERS_MART_SHARE;

-- Grant usage to other roles in the consumer account
GRANT IMPORTED PRIVILEGES ON DATABASE PARTNER_ORDERS TO ROLE ANALYST;

-- Now query as normal — but you're reading the provider's data, live
USE ROLE ANALYST;
SELECT * FROM PARTNER_ORDERS.MARTS.ORDERS_MART ORDER BY order_date;
```

#### Share vs Clone vs COPY INTO — decision table

| Feature | Share | Clone | COPY INTO |
|---|---|---|---|
| Data movement | None (zero-copy) | None (zero-copy) | Full copy |
| Writable by consumer | No (read-only) | Yes | Yes |
| Cross-account | Yes | No | Yes |
| Real-time | Yes (live) | Snapshot at clone time | Batch |
| Storage cost | None | None until writes | Full copy cost |
| Best for | Sharing live data externally | Dev/test, backups, sandboxes | Loading external files |

#### Secure Views in Sharing

When you share a table directly, the consumer can see all columns including PII. Best practice: share a **Secure View** instead:

```sql
-- A regular view exposes its definition (consumers can see your SQL logic)
-- A SECURE view hides the definition — consumers only see the result

CREATE OR REPLACE SECURE VIEW ECOMM_DB.MARTS.ORDERS_SUMMARY AS
SELECT
    order_date,
    COUNT(*)          AS total_orders,
    SUM(total_amount) AS total_revenue
FROM ECOMM_DB.STAGING.STG_ORDERS
WHERE is_deleted = FALSE
GROUP BY order_date;

GRANT SELECT ON VIEW ECOMM_DB.MARTS.ORDERS_SUMMARY TO SHARE ORDERS_MART_SHARE;
```

#### Snowflake Marketplace

The Snowflake Data Marketplace is a catalog of data products shared publicly — weather data, financial data, geolocation enrichment, etc. Consuming Marketplace data works exactly like consuming a private share: you create a database FROM the share and query it. No files, no ETL, no credentials.

```sql
-- After getting a Marketplace dataset (e.g. weather data):
CREATE DATABASE WEATHER_DATA
    FROM SHARE <marketplace_provider_account>.WEATHER_SHARE;

SELECT * FROM WEATHER_DATA.PUBLIC.DAILY_WEATHER
WHERE date = '2024-01-10';
```

---

## Summary

| Concept | What it does | Key command |
|---|---|---|
| Snowpipe (REST) | Loads files on demand via REST API | `CREATE PIPE ... AUTO_INGEST = FALSE` |
| Snowpipe (Auto-Ingest) | Loads files automatically when they arrive in ADLS/S3/GCS | `CREATE PIPE ... AUTO_INGEST = TRUE` |
| Zero-Copy Cloning | Instant zero-storage-cost copy of table/schema/database | `CREATE DATABASE dev CLONE prod` |
| Data Sharing | Live read-only access to your data for another Snowflake account | `CREATE SHARE ... → ADD ACCOUNTS` |

**Next:** Day 6 — Time Travel, Fail-Safe, and Query Optimization (clustering keys, result cache, query profile).
