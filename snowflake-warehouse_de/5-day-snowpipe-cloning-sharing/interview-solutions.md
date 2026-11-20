# Day 5 — Interview Solutions: Stages, COPY INTO, Snowpipe, and Zero-Copy Cloning

> Complete answers. Read after attempting on your own.
> All scenarios reference the Day 4 tables: ORDERS_RAW, STG_ORDERS, ORDERS_MART.

---

**Q1 — What is a Stage? Why do files need to go through one?**

A **Stage** is a Snowflake object that points to a file storage location. It acts as a landing zone — `COPY INTO` and Snowpipe can only read files from a stage, not from arbitrary file paths or your laptop.

Why files must go through a stage:
- Snowflake needs a **controlled access point** with defined file format settings (delimiter, header row, null handling).
- The stage enables **deduplication** — Snowflake records which files it has already loaded from each stage.
- It **decouples** the file source (internal storage, S3, ADLS) from the loading SQL — the COPY INTO statement stays the same regardless of where files come from.

---

**Q2 — Internal stage vs external stage. Which needs credentials?**

| | Internal Stage | External Stage |
|---|---|---|
| Storage | Snowflake-managed | Your own S3 / Azure ADLS / GCS |
| Credentials | None — Snowflake owns the storage | Requires Storage Integration or access keys |
| File upload | `PUT` command or Snowsight UI | Drop files directly in your cloud bucket |
| Data ownership | Snowflake | You |
| Best for | Testing, demos, pipelines without existing cloud storage | Production when files already land in your cloud |

**External stage** requires credentials because Snowflake needs permission to read from your cloud bucket.

---

**Q3 — Three internal stage sub-types. Which for production?**

| Sub-type | Reference | Shared? | Tied to one table? |
|---|---|---|---|
| User stage | `@~` | No — private to current user | No |
| Table stage | `@%ORDERS_RAW` | No — only feeds that one table | Yes |
| Named stage | `@ECOMM_DB.RAW_DATA.ORDERS_RAW_STAGE` | Yes | No |

**Use named stage in production.** Because:
- Multiple users and jobs can reference the same stage.
- File format is defined once on the stage, not repeated in every COPY INTO.
- Access is controlled by Snowflake RBAC — you can `GRANT USAGE ON STAGE` to specific roles.
- A table stage can only feed `ORDERS_RAW` — if you later need to load a different table from the same files, you are stuck.

---

**Q4 — What does COPY INTO do? Compute and billing?**

`COPY INTO` reads files from a stage and bulk-inserts them into a Snowflake table. It is a **manual, batch command**.

```sql
COPY INTO ECOMM_DB.RAW_DATA.ORDERS_RAW
    (order_id, customer_id, customer_name, product, quantity,
     unit_price, total_amount, status, order_date)
FROM @ECOMM_DB.RAW_DATA.ORDERS_RAW_STAGE
FILE_FORMAT = (TYPE = 'CSV' SKIP_HEADER = 1);
```

It runs on your **virtual warehouse** (XSMALL / SMALL / MEDIUM etc.) — you are billed warehouse credits for the duration of the COPY INTO run. The warehouse must be running when you execute it.

---

**Q5 — Stage has 2 already-loaded files and 1 new file. What happens to each?**

- **2 previously loaded files** → status `LOAD_SKIPPED`. COPY INTO has a 64-day deduplication window — it records each file's name, size, and last-modified timestamp after loading. On the next run it checks this metadata and skips any file already in the window.
- **1 new file** → status `LOADED`. It is not in the metadata, so it loads normally.

No duplicates in ORDERS_RAW. The Day 4 stream only captures the rows from the new file — the skipped files generate no stream records.

---

**Q6 — `FORCE = TRUE` on COPIES INTO ORDERS_RAW. Risk + impact on the Day 4 stream.**

`FORCE = TRUE` bypasses the deduplication metadata and loads the file regardless of whether it was previously loaded.

**Risk:** Every row in that file is inserted **again** into ORDERS_RAW — exact duplicate rows with the same `order_id`. Since `ORDERS_RAW` has a `PRIMARY KEY` on `order_id`, Snowflake will raise a constraint violation error (or silently allow duplicates if the PK is not enforced at DML level — Snowflake PKs are not enforced by default). You end up with duplicate order rows.

**Impact on the Day 4 stream:** The stream captures every INSERT including duplicates. The next time `RAW_TO_STG_TASK` fires, the MERGE into `STG_ORDERS` runs — but because MERGE matches on `order_id`, the duplicate INSERTs land in the `WHEN MATCHED` branch and simply overwrite the same row in staging with identical data. The mart numbers stay correct, but the stream was polluted with unnecessary work.

**When FORCE = TRUE is acceptable:** Only in testing — when you need to reload a file to re-test your pipeline. Never in production.

---

**Q7 — COPY INTO skipping `updated_at` and using DEFAULT.**

Name the target columns explicitly. Any column not listed uses its DEFAULT value:

```sql
COPY INTO ECOMM_DB.RAW_DATA.ORDERS_RAW
    (order_id, customer_id, customer_name, product, quantity,
     unit_price, total_amount, status, order_date)
    -- updated_at is NOT listed → Snowflake uses DEFAULT CURRENT_TIMESTAMP()
FROM @ECOMM_DB.RAW_DATA.ORDERS_RAW_STAGE
FILE_FORMAT = (TYPE = 'CSV' SKIP_HEADER = 1);
```

The CSV has 9 columns, the COPY INTO lists 9 columns, `updated_at` gets its default. This is cleaner than including `updated_at` in the CSV and trying to override it.

---

**Q8 — What is Snowpipe? How is it different from a 1-minute Task + COPY INTO?**

Snowpipe is Snowflake's **automatic, continuous file ingestion** service. You create a Pipe object with a COPY INTO statement. Snowpipe runs it automatically whenever new files arrive — no scheduler, no virtual warehouse to manage.

| | Task + COPY INTO | Snowpipe |
|---|---|---|
| Trigger | Fixed schedule (min 1 min) | File arrival or REST API call |
| Compute | Your virtual warehouse | Snowflake-managed (serverless) |
| Latency | Up to 1 min + warehouse startup | Seconds to ~1 minute |
| Idle cost | Warehouse may bill while idle | Zero — no files = no compute |
| Duplicate prevention | None built-in | Built-in (file metadata tracking) |
| Cost model | Warehouse credits | Per-second of serverless compute |

A Task polls every minute even when nothing changed. Snowpipe only runs when triggered and uses compute you never provision.

---

**Q9 — Snowpipe is "serverless." When would Task + COPY INTO be better?**

Snowflake maintains a shared pool of pre-warmed compute nodes. Snowpipe uses nodes from this pool — no warehouse to choose or start. You pay per second of actual compute used. Zero files = zero cost.

**When Task + COPY INTO beats Snowpipe:**
- **Very high throughput** — loading millions of rows per second. You can explicitly scale a virtual warehouse (LARGE, X-LARGE) to maximize parallel loading. Snowpipe's managed pool cannot be sized.
- **Transformation complexity** — if the COPY INTO needs joins or complex SELECT logic that benefits from large warehouse memory.
- **You already control the schedule** — if files always arrive at exactly 2 AM and your warehouse is already running for other jobs, a Task adds zero extra cost.

For typical file-by-file streaming (files every few seconds to minutes), Snowpipe is cheaper and simpler.

---

**Q10 — REFRESH called twice. Does Snowpipe load the files twice?**

**No.** Snowpipe maintains its own file metadata table (separate from COPY INTO's tracking). After loading a file, it records the file's name, size, and last-modified timestamp. When `REFRESH` is triggered again, Snowpipe scans the stage but skips any file already in its metadata.

This is the same deduplication mechanism as COPY INTO — it is built into Snowpipe at the pipe level. Each pipe tracks independently, which is why a file can be loaded by COPY INTO into `ORDERS_RAW` and also independently loaded by Snowpipe into `ORDERS_RAW_PIPE_LOAD` without conflict (they maintain separate metadata).

---

**Q11 — Pipe was PAUSED for 2 hours, 15 files arrived. How to make sure all load?**

```sql
-- Step 1: Resume the pipe
ALTER PIPE ECOMM_DB.RAW_DATA.ORDERS_RAW_PIPE SET PIPE_EXECUTION_PAUSED = FALSE;

-- Step 2: Force a scan of the stage to pick up all files that arrived while paused
ALTER PIPE ECOMM_DB.RAW_DATA.ORDERS_RAW_PIPE REFRESH;
-- Returns: filesScanned (shows all files in stage), filesQueued (shows new ones)

-- Step 3: Wait ~30 seconds for the serverless compute to process all 15 files

-- Step 4: Verify
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW;

SELECT file_name, row_count, status
FROM TABLE(INFORMATION_SCHEMA.COPY_HISTORY(
    TABLE_NAME  => 'ORDERS_RAW',
    START_TIME  => DATEADD('hours', -3, CURRENT_TIMESTAMP())
))
ORDER BY LAST_LOAD_TIME DESC;
-- All 15 files should show status = LOADED
```

**Why no data loss:** Files stay in the stage while the pipe is paused — they are not deleted. `REFRESH` re-scans the stage and queues anything not yet in the pipe's metadata.

---

**Q12 — What is zero-copy cloning? When does storage get consumed?**

Zero-copy cloning creates a new Snowflake object that **shares the same underlying micro-partitions** as the source. No bytes are physically copied at clone time. Snowflake just creates a new metadata pointer to the same blocks.

**"Zero-copy"** = zero bytes duplicated at clone time. Storage cost at the moment of cloning: zero.

**Copy-on-Write semantics:** Storage is consumed only when either the source OR the clone is **modified**. Snowflake rewrites only the micro-partitions that contain changed rows — the rest remain shared.

```
After CREATE TABLE ORDERS_RAW_BACKUP CLONE ORDERS_RAW:
  ORDERS_RAW        ──► [Block A] [Block B] [Block C]   ← same blocks
  ORDERS_RAW_BACKUP ──► [Block A] [Block B] [Block C]   ← zero extra storage

After deleting from ORDERS_RAW_BACKUP:
  ORDERS_RAW        ──► [Block A] [Block B] [Block C]   ← untouched
  ORDERS_RAW_BACKUP ──► [Block A*] [Block B] [Block C]  ← Block A* is new
```

---

**Q13 — Developer truncates ORDERS_RAW in ECOMM_DB_DEV clone. What happens to the original?**

**Nothing.** The original `ECOMM_DB.RAW_DATA.ORDERS_RAW` is completely unaffected.

After `CREATE DATABASE ECOMM_DB_DEV CLONE ECOMM_DB`, both databases share the same micro-partitions. When the developer runs `TRUNCATE TABLE ECOMM_DB_DEV.RAW_DATA.ORDERS_RAW`, Snowflake marks all partitions as deleted in `ECOMM_DB_DEV`'s metadata only. The original `ECOMM_DB`'s metadata still points to all the original blocks — they are not touched.

This isolation is the whole point of dev/test cloning: developers can destroy and reload data in the dev clone without any risk to production.

---

**Q14 — Clone ORDERS_RAW. What happens to the stream and tasks?**

**Stream (`ORDERS_RAW_STREAM`):** Not cloned. Streams are excluded from cloning. The original stream continues tracking changes to `ECOMM_DB.RAW_DATA.ORDERS_RAW` exactly as before. The cloned table has no stream.

**Tasks (`RAW_TO_STG_TASK`, `STG_TO_MART_TASK`):** Also not cloned. Tasks are excluded from table and schema clones. When cloning a full database (`CLONE ECOMM_DB`), tasks ARE included in the clone but are created in a **SUSPENDED** state — Snowflake does not auto-start them to avoid two task DAGs running against the same underlying data.

If you need a stream on the cloned table:
```sql
CREATE STREAM ECOMM_DB.RAW_DATA.ORDERS_RAW_BACKUP_STREAM
    ON TABLE ECOMM_DB.RAW_DATA.ORDERS_RAW_BACKUP;
```

---

**Q15 — Recover rows deleted by a bad ETL job. Keep stream and tasks intact.**

```sql
-- Step 1: Identify the bad DELETE query
SELECT query_id, query_text, start_time
FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(
    DATE_RANGE_START => DATEADD('hours', -12, CURRENT_TIMESTAMP())
))
WHERE query_text ILIKE '%DELETE%ORDERS_RAW%'
ORDER BY start_time DESC
LIMIT 1;
-- Copy the query_id, e.g. '01ab2c34-...'

-- Step 2: Clone ORDERS_RAW as it was BEFORE the bad delete
-- This does not affect the stream, tasks, or any other object
CREATE TABLE ECOMM_DB.RAW_DATA.ORDERS_RAW_RECOVERED
    CLONE ECOMM_DB.RAW_DATA.ORDERS_RAW
    BEFORE (STATEMENT => '01ab2c34-...');

-- Step 3: Verify the recovered table has the deleted rows
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW_RECOVERED;
-- Should be 6 rows higher than current ORDERS_RAW

-- Step 4: Re-insert ONLY the missing rows
-- Using NOT EXISTS prevents double-inserting rows that survived the bad delete
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

-- Step 5: Verify count is restored
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.ORDERS_RAW;

-- Step 6: The re-inserted rows now appear in the stream as INSERT records
-- Run the Day 4 task to propagate them to STAGING and MART
EXECUTE TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK;

SELECT COUNT(*) FROM ECOMM_DB.STAGING.STG_ORDERS;
SELECT * FROM ECOMM_DB.MARTS.ORDERS_MART ORDER BY order_date;

-- Step 7: Drop the recovery table
DROP TABLE ECOMM_DB.RAW_DATA.ORDERS_RAW_RECOVERED;
```

**Why stream and tasks are unaffected:** Cloning creates a new table object — it does not touch the stream's offset or the tasks' state. The stream keeps tracking `ORDERS_RAW` from where it left off. The re-inserted rows appear as new INSERT records in the stream, which is correct — the tasks will push them through to staging and mart normally.
