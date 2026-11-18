# Day 5 — Interview Solutions: Snowpipe, ADLS Auto-Ingest, Cloning & Sharing

> Complete answers to all 15 questions. Read after attempting on your own.

---

**Q1 — What is Snowpipe and how does it differ from a Task + COPY INTO?**

Snowpipe is a **serverless, continuous ingestion service** — you define a Pipe object with a COPY INTO statement, and Snowpipe runs that statement automatically whenever new files arrive in the associated stage.

| | Task + COPY INTO | Snowpipe |
|---|---|---|
| Trigger | Time-based schedule (minimum 1 minute) | File arrival (auto-ingest) or REST API call |
| Compute | Your virtual warehouse (you pay warehouse credits) | Snowflake-managed serverless compute (per-second billing) |
| Latency | Up to 1 minute + warehouse startup | Seconds to 1 minute |
| Idle cost | Warehouse may auto-suspend, but task checks run | Zero — no files = no compute |
| Duplicate prevention | None built-in — you must deduplicate | Built-in — tracks loaded files by name + size + last-modified |

**Key difference:** A Task polls on a schedule regardless of whether files exist. Snowpipe only runs when triggered, and uses managed compute — no warehouse size to choose.

---

**Q2 — What does `AUTO_INGEST = TRUE` mean? What infrastructure component enables it on Azure?**

`AUTO_INGEST = TRUE` tells the pipe to **listen for event notifications** from cloud storage rather than waiting for a REST API call. When a file lands in the stage's underlying cloud storage, an event is automatically fired and the pipe loads the file.

On **Azure**, the enabling component is **Azure Event Grid** paired with an **Azure Storage Queue**:

1. Azure Event Grid subscription watches the ADLS container for `BlobCreated` events.
2. When a blob arrives, Event Grid writes a message to an Azure Storage Queue.
3. Snowflake's Snowpipe service polls that queue every few seconds.
4. When a message appears, the pipe runs its COPY INTO statement for that file.

Snowflake never connects directly to ADLS for the notification — the queue decouples the two systems. The Snowflake `NOTIFICATION INTEGRATION` object stores the credentials to read from that queue.

---

**Q3 — What does "serverless" mean for Snowpipe? How is it billed?**

Snowflake maintains a pool of pre-warmed compute nodes internally. When Snowpipe loads files, it uses nodes from this shared pool — you do not spin up a virtual warehouse (no XSMALL/SMALL/MEDIUM to choose). Snowflake allocates just enough compute to handle the current ingestion volume, then reclaims it.

**Billing:** You are charged **Snowpipe credits** (a separate unit from warehouse credits) based on the actual seconds of compute used to load files. If no files arrive for 8 hours, you pay zero. This makes Snowpipe far cheaper than keeping a 1-minute scheduled Task running a warehouse all night for zero rows.

**Practical implication:** You cannot tune the warehouse size for Snowpipe. If you need very high throughput loading (millions of rows per second), a dedicated warehouse + COPY INTO may actually be faster because you can scale the warehouse explicitly.

---

**Q4 — Same filename uploaded twice. Does Snowpipe load it twice?**

**No**, Snowpipe does **not** load it the second time by default.

Snowpipe tracks loaded files in an internal metadata table using a combination of **file name, file size, and last-modified timestamp**. When a file notification arrives, Snowpipe checks this metadata before running COPY INTO.

- Same filename + same size + same timestamp → already loaded → **skipped**
- Same filename + different size OR different timestamp → treated as a **new file** → loaded again

**Implications:**
- Overwriting a file with the same name and same content → Snowpipe will not reload it. If you need to reload, you must delete the metadata (using `ALTER PIPE ... REFRESH` with explicit file list, or by recreating the pipe).
- Renaming and re-uploading → loaded because the filename is different.
- This behavior is the same as the native `COPY INTO` deduplication window (64 days).

---

**Q5 — Pipe shows `executionState = STALE`. What does it mean and what do you do?**

**What STALE means:** The pipe has not received any event queue messages from Azure Storage Queue for an extended period (Snowflake considers this a signal that the notification pipeline may be broken — not just empty). It could mean:
- The Event Grid subscription was deleted or misconfigured
- The Storage Queue was deleted or its SAS/credentials expired
- The Notification Integration lost access to the queue
- The pipe has been paused for a very long time

**What to do:**
```sql
-- Step 1: Check detailed pipe status
SELECT SYSTEM$PIPE_STATUS('ECOMM_DB.RAW_DATA.ADLS_ORDERS_PIPE');

-- Step 2: Verify the queue still exists in Azure Portal and Event Grid subscription is active

-- Step 3: Force resume — resets the stale state and reconnects to the queue
SELECT SYSTEM$PIPE_FORCE_RESUME('ECOMM_DB.RAW_DATA.ADLS_ORDERS_PIPE');

-- Step 4: If files arrived while the pipe was stale, manually refresh
-- (auto-ingest only captures events going forward — files missed during STALE need manual refresh)
ALTER PIPE ECOMM_DB.RAW_DATA.ADLS_ORDERS_PIPE REFRESH;
```

> **Important:** Files that arrived while the pipe was STALE are **not automatically backfilled**. The Event Grid messages that fired during the stale window may have already expired from the queue. Use `REFRESH` to re-scan the stage and load any missed files.

---

**Q6 — 50 files not loaded, pipe shows PAUSED. Two most likely causes and recovery.**

**Cause 1 — Pipe was explicitly paused** (someone ran `ALTER PIPE ... SET PIPE_EXECUTION_PAUSED = TRUE`)
```sql
-- Check pipe status
SELECT SYSTEM$PIPE_STATUS('ECOMM_DB.RAW_DATA.ORDERS_PIPE');

-- Resume
ALTER PIPE ECOMM_DB.RAW_DATA.ORDERS_PIPE SET PIPE_EXECUTION_PAUSED = FALSE;

-- Then force a scan to pick up the files that arrived while paused
ALTER PIPE ECOMM_DB.RAW_DATA.ORDERS_PIPE REFRESH;
```

**Cause 2 — The pipe's underlying stage or integration credentials expired/were rotated**
Snowpipe pauses itself when it encounters repeated auth errors. Check the `COPY_HISTORY` for error messages:
```sql
SELECT *
FROM TABLE(INFORMATION_SCHEMA.COPY_HISTORY(
    TABLE_NAME  => 'ORDERS_INGEST',
    START_TIME  => DATEADD('hours', -24, CURRENT_TIMESTAMP())
))
WHERE STATUS = 'LOAD_FAILED'
ORDER BY LAST_LOAD_TIME DESC;
```
If you see `Access Denied` or `Auth error`: update the Storage Integration credentials in Azure (re-assign RBAC roles if the service principal changed), then resume the pipe.

---

**Q7 — Loading JSON files into a VARIANT column via Snowpipe. Key differences.**

Target table needs a VARIANT column:
```sql
CREATE OR REPLACE TABLE ORDERS_JSON_RAW (
    raw_order  VARIANT,
    loaded_at  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
```

Stage FILE_FORMAT must be JSON, not CSV:
```sql
CREATE OR REPLACE STAGE ADLS_JSON_STAGE
    URL                 = 'azure://<account>.blob.core.windows.net/orders-json/'
    STORAGE_INTEGRATION = AZURE_ORDERS_INT
    FILE_FORMAT         = (TYPE = 'JSON' STRIP_OUTER_ARRAY = TRUE);
-- STRIP_OUTER_ARRAY: if the file is a JSON array [{"a":1},{"a":2}]
-- each element becomes its own row. Without it, the whole array is one VARIANT row.
```

Pipe definition:
```sql
CREATE OR REPLACE PIPE ECOMM_DB.RAW_DATA.ADLS_JSON_PIPE
    AUTO_INGEST = TRUE
    INTEGRATION = 'AZURE_ORDERS_QUEUE_INT'
AS
COPY INTO ECOMM_DB.RAW_DATA.ORDERS_JSON_RAW (raw_order)
FROM (SELECT $1 FROM @ECOMM_DB.RAW_DATA.ADLS_JSON_STAGE)
FILE_FORMAT = (TYPE = 'JSON' STRIP_OUTER_ARRAY = TRUE);
```

After loading, query the JSON using colon syntax:
```sql
SELECT
    raw_order:order_id::NUMBER       AS order_id,
    raw_order:customer_name::VARCHAR AS customer_name,
    raw_order:status::VARCHAR        AS status
FROM ECOMM_DB.RAW_DATA.ORDERS_JSON_RAW;
```

**Key differences from CSV:**
- FILE_FORMAT TYPE = JSON (not CSV), no SKIP_HEADER, add STRIP_OUTER_ARRAY if needed
- Target column is VARIANT, not individual typed columns
- COPY INTO uses `SELECT $1` to put the whole document into the VARIANT column
- Parsing happens after load with colon (`:`) syntax

---

**Q8 — Why are STORAGE INTEGRATION and NOTIFICATION INTEGRATION both needed for ADLS auto-ingest?**

They serve completely different purposes:

**STORAGE INTEGRATION** — authenticates Snowflake to **read file data** from ADLS.
- Uses Azure AD OAuth (service principal with Storage Blob Data Reader role).
- Required for the external Stage to access the actual file bytes.
- Used by: Stage, COPY INTO, Snowpipe when reading the file.

**NOTIFICATION INTEGRATION** — authenticates Snowflake to **read event messages** from the Azure Storage Queue.
- Uses a separate service principal with Storage Queue Data Contributor role on the queue.
- Required for auto-ingest: Snowflake polls this queue to find out which files to load.
- Used by: the Pipe object's `INTEGRATION` parameter.

You need both because:
- Without Storage Integration → Snowflake can hear the notification but cannot read the file from ADLS.
- Without Notification Integration → Snowflake never knows a file arrived (pipe cannot poll the queue).

They are separate objects because the two operations (file read vs. queue read) require different Azure RBAC roles on different Azure resources. Separating them follows the principle of least privilege.

---

**Q9 — What is zero-copy cloning? Is there no data when you first clone?**

Zero-copy cloning creates a new Snowflake object that **shares the same underlying micro-partitions** as the source. No bytes are copied to new storage. The clone is a new metadata entry that points to the same physical blocks.

**"Zero-copy" means zero byte duplication at clone time** — both objects share the same blocks.

**Copy-on-Write semantics:** When either the source OR the clone is modified (INSERT, UPDATE, DELETE), Snowflake creates new micro-partitions only for the changed data. The unmodified partitions continue to be shared.

```
Immediately after:  CREATE DATABASE DEV CLONE PROD
  PROD ──► [Block A] [Block B] [Block C]
  DEV  ──► [Block A] [Block B] [Block C]   ← same blocks, no copy, zero extra storage

After:  DELETE FROM DEV.orders WHERE year = 2020
  PROD ──► [Block A] [Block B] [Block C]   ← unchanged
  DEV  ──► [Block A*] [Block B] [Block C]  ← Block A* is new (modified partition)
                                             Only Block A* is new storage cost
```

---

**Q10 — Developer deletes old rows in a 10 TB clone. How much new storage is consumed?**

Only the micro-partitions that contain the deleted rows are rewritten. Snowflake does not rewrite the entire table.

For the `DELETE FROM orders WHERE order_date < '2023-01-01'` scenario:
- Micro-partitions that contain only pre-2023 rows → these partitions are marked deleted in the clone's metadata. No new storage consumed for the deleted data itself.
- Micro-partitions that contain a mix of pre-2023 and post-2023 rows → these are rewritten. The new partition contains only the post-2023 rows. **New storage = size of the rewritten mixed partitions**.
- Micro-partitions that contain only post-2023 rows → still shared with PROD. Zero new storage.

**In practice:** If the data is well-ordered by date (Snowflake's natural micro-partition clustering), old data likely lives in its own partitions. The delete may touch zero or very few mixed partitions — storage impact is minimal. If the data is randomly ordered, more mixed partitions exist → more storage consumed.

**The original PROD database is completely unaffected** — it still points to all the original blocks.

---

**Q11 — Can you clone a table that has an active Stream? What happens to the stream in the clone?**

Yes, you can clone a table that has an active stream. The table itself is cloned normally.

**What happens to the stream:**
- The stream is **not cloned**. Streams are not part of the cloned object set even when cloning a schema or database.
- The clone does not have any stream on it after cloning.
- The original stream on the source table continues working normally — the clone operation does not consume or affect the stream's offset.

If you need a stream on the cloned table, you must create one manually:
```sql
-- After cloning
CREATE STREAM ECOMM_DB.STAGING_BACKUP.STG_ORDERS_STREAM
    ON TABLE ECOMM_DB.STAGING_BACKUP.STG_ORDERS;
```

**Why streams are not cloned:** A stream tracks changes from its current offset forward. If a stream were automatically cloned, its behavior would be ambiguous — should the cloned stream replay changes from the same offset, or start fresh? Snowflake avoids this ambiguity by not cloning streams.

---

**Q12 — Recover 2 million accidentally deleted rows using cloning + Time Travel.**

```sql
-- Step 1: Find the query ID of the bad DELETE (from query history)
SELECT query_id, query_text, start_time
FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(
    DATE_RANGE_START => DATEADD('hours', -12, CURRENT_TIMESTAMP())
))
WHERE query_text ILIKE '%DELETE%STG_ORDERS%'
ORDER BY start_time DESC;
-- Copy the query_id of the bad DELETE, e.g. '01ab2c34-...'

-- Step 2: Clone the staging table as it was BEFORE that query ran
CREATE TABLE ECOMM_DB.STAGING.STG_ORDERS_RECOVERED
    CLONE ECOMM_DB.STAGING.STG_ORDERS
    BEFORE (STATEMENT => '01ab2c34-...');
-- This creates a full snapshot of the table in the state just before the DELETE

-- Step 3: Verify the recovered rows are there
SELECT COUNT(*) FROM ECOMM_DB.STAGING.STG_ORDERS_RECOVERED;
-- Should be 2 million rows higher than the current STG_ORDERS

-- Step 4: Re-insert the missing rows into the live table
INSERT INTO ECOMM_DB.STAGING.STG_ORDERS
SELECT * FROM ECOMM_DB.STAGING.STG_ORDERS_RECOVERED r
WHERE NOT EXISTS (
    SELECT 1 FROM ECOMM_DB.STAGING.STG_ORDERS s
    WHERE s.order_id = r.order_id
);

-- Step 5: Verify count is restored, then drop the recovery clone
SELECT COUNT(*) FROM ECOMM_DB.STAGING.STG_ORDERS;
DROP TABLE ECOMM_DB.STAGING.STG_ORDERS_RECOVERED;
```

**Alternative if you want a full table swap:**
```sql
-- Swap the recovered table into the live position
ALTER TABLE ECOMM_DB.STAGING.STG_ORDERS RENAME TO STG_ORDERS_BAD;
ALTER TABLE ECOMM_DB.STAGING.STG_ORDERS_RECOVERED RENAME TO STG_ORDERS;
DROP TABLE ECOMM_DB.STAGING.STG_ORDERS_BAD;
```

---

**Q13 — What is Snowflake Data Sharing? Does the consumer need to copy data first?**

Snowflake Data Sharing is a feature that allows a **provider account** to give one or more **consumer accounts** read-only access to live data — with **no data movement, no ETL, and no data copy**.

The consumer creates a database FROM the share using `CREATE DATABASE ... FROM SHARE ...`. After that, they query the data exactly like any other database — using their own virtual warehouse. The data physically stays in the provider's cloud storage. The consumer's warehouse reads directly from the provider's micro-partitions.

**Key properties:**
- **No copy** — the consumer database is a metadata pointer to the provider's data, not a physical copy.
- **Live** — changes the provider makes (new rows, updates) are immediately visible to the consumer.
- **Read-only** — consumers cannot write to shared data.
- **Cross-account but same cloud/region** (by default) — for cross-region or cross-cloud sharing, Snowflake replicates the data, which does incur storage cost.
- **Consumer uses their own compute** — the provider is not charged for the consumer's queries.

---

**Q14 — Partner can see PII. How to share aggregated data while hiding raw PII.**

Share a **Secure View** instead of the raw table:

```sql
USE ROLE ACCOUNTADMIN;

-- Step 1: Create a secure view that exposes only non-PII aggregated data
CREATE OR REPLACE SECURE VIEW ECOMM_DB.MARTS.ORDERS_PUBLIC_SUMMARY AS
SELECT
    order_date,
    COUNT(*)          AS total_orders,
    SUM(total_amount) AS total_revenue,
    AVG(total_amount) AS avg_order_value
FROM ECOMM_DB.STAGING.STG_ORDERS
WHERE is_deleted = FALSE
GROUP BY order_date;
-- customer_name, customer_id, email etc. are NOT exposed

-- Step 2: Revoke the direct table grant if it exists
REVOKE SELECT ON TABLE ECOMM_DB.STAGING.STG_ORDERS FROM SHARE ORDERS_MART_SHARE;

-- Step 3: Grant SELECT on the secure view instead
GRANT USAGE  ON DATABASE ECOMM_DB                    TO SHARE ORDERS_MART_SHARE;
GRANT USAGE  ON SCHEMA ECOMM_DB.MARTS                TO SHARE ORDERS_MART_SHARE;
GRANT SELECT ON VIEW ECOMM_DB.MARTS.ORDERS_PUBLIC_SUMMARY TO SHARE ORDERS_MART_SHARE;
```

**Why SECURE view, not regular view:**
A regular view in a share exposes its **SQL definition** to the consumer — they can see your column names, table names, filters, and business logic. A SECURE view hides the definition completely. The consumer only sees the view name and the columns in its result.

---

**Q15 — System design: real-time JSON orders from ADLS → live summary for a partner.**

```
Microservice A ──┐
Microservice B ──┼──► ADLS Container: orders-json/   (JSON files, every few seconds)
Microservice C ──┘          │
                             │  Azure Event Grid (BlobCreated)
                             ▼
                    Azure Storage Queue
                             │
                             │  Snowpipe polls (AUTO_INGEST = TRUE)
                             ▼
                ECOMM_DB.RAW_DATA.ORDERS_JSON_RAW     (VARIANT column)
                             │
                             │  Snowflake Task or Dynamic Table (1 min)
                             ▼
                ECOMM_DB.STAGING.STG_ORDERS            (typed, flattened)
                             │
                             │  Dynamic Table (5-second lag) OR Task
                             ▼
                ECOMM_DB.MARTS.ORDERS_DAILY_SUMMARY    (aggregated, no PII)
                             │
                             │  Data Share → partner Snowflake account
                             ▼
                PARTNER_ACCOUNT: CREATE DATABASE FROM SHARE
                             │
                             │  partner queries live summary
                             ▼
                     BI Tool (Tableau / Power BI)
```

**Component-by-component design:**

```sql
-- 1. Ingestion: ADLS auto-ingest pipe (from notes.md Concept 2)
CREATE OR REPLACE PIPE ECOMM_DB.RAW_DATA.ORDERS_JSON_PIPE
    AUTO_INGEST = TRUE
    INTEGRATION = 'AZURE_ORDERS_QUEUE_INT'
AS COPY INTO ECOMM_DB.RAW_DATA.ORDERS_JSON_RAW (raw_order)
FROM (SELECT $1 FROM @ECOMM_DB.RAW_DATA.ADLS_JSON_STAGE)
FILE_FORMAT = (TYPE = 'JSON' STRIP_OUTER_ARRAY = TRUE);

-- 2. Flatten JSON → typed staging (Dynamic Table for near-real-time)
CREATE OR REPLACE DYNAMIC TABLE ECOMM_DB.STAGING.STG_ORDERS
    TARGET_LAG = '1 minute'
    WAREHOUSE  = COMPUTE_WH
AS
SELECT
    raw_order:order_id::NUMBER       AS order_id,
    raw_order:customer_id::NUMBER    AS customer_id,
    raw_order:product::VARCHAR       AS product,
    raw_order:total_amount::NUMBER   AS total_amount,
    raw_order:status::VARCHAR        AS status,
    raw_order:order_date::DATE       AS order_date
FROM ECOMM_DB.RAW_DATA.ORDERS_JSON_RAW;

-- 3. Daily summary mart — no PII (Dynamic Table)
CREATE OR REPLACE DYNAMIC TABLE ECOMM_DB.MARTS.ORDERS_DAILY_SUMMARY
    TARGET_LAG = '5 minutes'
    WAREHOUSE  = COMPUTE_WH
AS
SELECT
    order_date,
    COUNT(*)          AS total_orders,
    SUM(total_amount) AS total_revenue,
    AVG(total_amount) AS avg_order_value
FROM ECOMM_DB.STAGING.STG_ORDERS
GROUP BY order_date;

-- 4. Share the summary mart securely (no raw data)
CREATE SECURE VIEW ECOMM_DB.MARTS.ORDERS_SUMMARY_PUBLIC
AS SELECT * FROM ECOMM_DB.MARTS.ORDERS_DAILY_SUMMARY;

CREATE SHARE PARTNER_ORDERS_SHARE;
GRANT USAGE  ON DATABASE ECOMM_DB TO SHARE PARTNER_ORDERS_SHARE;
GRANT USAGE  ON SCHEMA ECOMM_DB.MARTS TO SHARE PARTNER_ORDERS_SHARE;
GRANT SELECT ON VIEW ECOMM_DB.MARTS.ORDERS_SUMMARY_PUBLIC TO SHARE PARTNER_ORDERS_SHARE;
ALTER SHARE PARTNER_ORDERS_SHARE ADD ACCOUNTS = '<partner_account>';
```

**Why each choice:**
- **Snowpipe + auto-ingest**: files trigger load automatically, no task scheduler needed, serverless billing
- **Dynamic Tables** (instead of Tasks): declarative, no MERGE logic to write, Snowflake manages refresh scheduling
- **Secure View for sharing**: hides SQL definition and all PII columns from the partner
- **Data Share** (not Marketplace): private share to a specific partner account, not public
