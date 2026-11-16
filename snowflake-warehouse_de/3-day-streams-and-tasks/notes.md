# Day 3 — Streams and Tasks

## What You Will Learn

By the end of Day 3 you will understand how Snowflake tracks row-level changes automatically (Streams / CDC) and how to schedule SQL to run on a timer without any external tools (Tasks).

**Overview — 2 concepts, 4 steps:**
1. Create a Stream on a table to start tracking changes
2. Query the Stream to see INSERT / UPDATE / DELETE metadata
3. Create a Task with a schedule to process those changes automatically
4. Chain Tasks together to build a simple automated pipeline

---

## Concept 1 — Streams: Change Data Capture (CDC)

### The problem Streams solve

Imagine your `CUSTOMERS_RAW` table receives hundreds of inserts and updates every hour. You have a staging table `STG_CUSTOMERS` that needs to stay in sync.

**Without CDC, your options are:**
- Full reload — truncate and reload the entire staging table every run. Works but gets expensive as the table grows to millions of rows.
- Timestamp delta — query rows where `updated_at > last_run_time`. Fragile — requires every table to have a reliable `updated_at` column that is always correctly maintained.

**With a Stream**, Snowflake automatically records exactly what changed and when. Your pipeline only processes the delta — no timestamp column needed, no full table scan.

### What is a Stream?

A **Stream** is a Snowflake object that sits on top of a table and records every DML change (INSERT, UPDATE, DELETE) made to that table since the stream was last consumed.

```
Source table ──► [Stream] ──► Your query / MERGE / Task
```

The stream does not store a copy of the data — it stores **change records**: what row changed, what the new value is, and what type of change occurred.

### Creating a Stream

```sql
-- Standard stream: captures INSERT, UPDATE, DELETE
CREATE STREAM IF NOT EXISTS RAW_DATA.CUSTOMERS_STREAM
  ON TABLE RAW_DATA.CUSTOMERS_RAW;

-- Append-only stream: captures only INSERTs (more efficient)
CREATE STREAM IF NOT EXISTS RAW_DATA.ORDERS_STREAM
  ON TABLE RAW_DATA.ORDERS_RAW
  APPEND ONLY = TRUE;
```

Use `APPEND ONLY = TRUE` for tables where rows are only ever inserted — event logs, raw ingest tables, audit trails. It is more efficient because Snowflake does not need to track UPDATE and DELETE offsets.

### Stream metadata columns

Every row returned from a stream includes three extra columns:

| Column | Type | Values | Meaning |
|---|---|---|---|
| `METADATA$ACTION` | VARCHAR | `INSERT` or `DELETE` | Type of change |
| `METADATA$ISUPDATE` | BOOLEAN | `TRUE` or `FALSE` | Was this row part of an UPDATE? |
| `METADATA$ROW_ID` | VARCHAR | unique ID | Identifies the specific row that changed |

### How UPDATE is represented in a Stream

An UPDATE produces **two rows** in the stream — not one:

| Row | `METADATA$ACTION` | `METADATA$ISUPDATE` | Content |
|---|---|---|---|
| Row 1 | `DELETE` | `TRUE` | Old values (before the update) |
| Row 2 | `INSERT` | `TRUE` | New values (after the update) |

This is called the **pre/post image** pattern. Snowflake stores the before and after state of the row.

To get only new inserts:
```sql
SELECT * FROM my_stream
WHERE METADATA$ACTION = 'INSERT' AND METADATA$ISUPDATE = FALSE;
```

To get only updates (new value):
```sql
SELECT * FROM my_stream
WHERE METADATA$ACTION = 'INSERT' AND METADATA$ISUPDATE = TRUE;
```

To get only deletes:
```sql
SELECT * FROM my_stream
WHERE METADATA$ACTION = 'DELETE' AND METADATA$ISUPDATE = FALSE;
```

### How the stream offset works

The stream has an internal **offset** (a timestamp pointer). It advances only when you consume the stream inside a DML transaction:

```
Make changes → query stream → see changes → consume in MERGE/INSERT → stream clears
```

A plain `SELECT` from the stream does **not** advance the offset. Changes stay visible until you use them in a DML that commits successfully. If the DML rolls back, the stream offset rolls back too.

### Consuming the stream with MERGE

The most common pattern — use the stream to keep a staging table in sync:

```sql
MERGE INTO STAGING.STG_CUSTOMERS AS target
USING (
  SELECT * FROM RAW_DATA.CUSTOMERS_STREAM
  WHERE METADATA$ACTION = 'INSERT'
) AS src
ON target.customer_id = src.customer_id
WHEN MATCHED THEN
  UPDATE SET
    target.full_name  = src.full_name,
    target.email      = src.email,
    target.updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
  INSERT (customer_id, full_name, email, updated_at)
  VALUES (src.customer_id, src.full_name, src.email, CURRENT_TIMESTAMP());
```

This is **SCD Type 1** — overwrite with the latest values.

### Stream staleness

A stream becomes **stale** if changes are not consumed within the source table's data retention period (default: 1 day on Standard edition).

```sql
SHOW STREAMS IN SCHEMA RAW_DATA;
-- Check the "stale" column — TRUE means the stream can no longer be used
```

If a stream goes stale: drop it, recreate it, and do a full reload of the target table. Prevention: ensure your pipeline runs frequently enough to consume the stream before data ages out.

---

## Concept 2 — Tasks: Scheduling and Automation

### What is a Task?

A **Task** is a Snowflake object that runs a single SQL statement on a schedule. It is Snowflake's native job scheduler — no Airflow, cron, or external tools needed for simple Snowflake-internal pipelines.

### Creating a Task

```sql
-- Run every 5 minutes
CREATE TASK IF NOT EXISTS STAGING.PROCESS_CHANGES_TASK
  WAREHOUSE = COMPUTE_WH
  SCHEDULE  = '5 MINUTE'
AS
MERGE INTO STAGING.STG_CUSTOMERS AS target
USING (SELECT * FROM RAW_DATA.CUSTOMERS_STREAM WHERE METADATA$ACTION = 'INSERT') AS src
ON target.customer_id = src.customer_id
WHEN MATCHED THEN
  UPDATE SET target.full_name = src.full_name, target.email = src.email
WHEN NOT MATCHED THEN
  INSERT (customer_id, full_name, email) VALUES (src.customer_id, src.full_name, src.email);
```

```sql
-- Run at 2 AM UTC every day using CRON
CREATE TASK IF NOT EXISTS STAGING.DAILY_SYNC_TASK
  WAREHOUSE = COMPUTE_WH
  SCHEDULE  = 'USING CRON 0 2 * * * UTC'
AS
<your SQL here>;
```

### CRON syntax

```
USING CRON <min> <hour> <day-of-month> <month> <day-of-week> <timezone>

0 2 * * *      → 2 AM every day
0 */6 * * *    → every 6 hours
*/5 * * * *    → every 5 minutes
0 9 * * 1      → 9 AM every Monday
```

### Tasks start SUSPENDED — you must resume them

```sql
-- Activate the task
ALTER TASK STAGING.PROCESS_CHANGES_TASK RESUME;

-- Pause without dropping
ALTER TASK STAGING.PROCESS_CHANGES_TASK SUSPEND;

-- Check status
SHOW TASKS IN SCHEMA STAGING;
-- "state" column: "started" = active, "suspended" = paused
```

### WHEN condition — skip execution if no data

```sql
CREATE TASK IF NOT EXISTS STAGING.PROCESS_CHANGES_TASK
  WAREHOUSE = COMPUTE_WH
  SCHEDULE  = '1 MINUTE'
  WHEN SYSTEM$STREAM_HAS_DATA('RAW_DATA.CUSTOMERS_STREAM')
AS
MERGE INTO STAGING.STG_CUSTOMERS ...;
```

`SYSTEM$STREAM_HAS_DATA()` returns `TRUE` only when the stream has unconsumed changes. When it returns `FALSE`, the task skips execution — no warehouse starts, no credits consumed. This is essential when the task runs frequently but data only arrives occasionally.

### Manually trigger a task

```sql
EXECUTE TASK STAGING.PROCESS_CHANGES_TASK;
```

Useful for testing immediately after creation without waiting for the next scheduled run.

### Check task run history

```sql
SELECT
    name,
    state,
    scheduled_time,
    completed_time,
    error_message,
    DATEDIFF('seconds', scheduled_time, completed_time) AS duration_sec
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
    SCHEDULED_TIME_RANGE_START => DATEADD('hours', -1, CURRENT_TIMESTAMP()),
    TASK_NAME => 'PROCESS_CHANGES_TASK'
))
ORDER BY scheduled_time DESC;
```

### Chaining Tasks — building a pipeline DAG

Tasks can depend on other tasks using `AFTER`. This creates a **directed acyclic graph (DAG)**:

```sql
-- Root task: has a schedule, starts the chain
CREATE TASK PIPELINE.ROOT_TASK
  WAREHOUSE = COMPUTE_WH
  SCHEDULE  = 'USING CRON 0 3 * * * UTC'
AS <step 1 SQL>;

-- Child task: runs after ROOT_TASK finishes
CREATE TASK PIPELINE.CHILD_TASK
  WAREHOUSE = COMPUTE_WH
  AFTER PIPELINE.ROOT_TASK
AS <step 2 SQL>;

-- Grandchild task: runs after CHILD_TASK finishes
CREATE TASK PIPELINE.GRANDCHILD_TASK
  WAREHOUSE = COMPUTE_WH
  AFTER PIPELINE.CHILD_TASK
AS <step 3 SQL>;
```

Only the root task has a `SCHEDULE`. Child tasks have no schedule — they fire when their parent completes successfully. If the parent fails, the child does not run.

**Resume order — children first, root last:**

```sql
ALTER TASK PIPELINE.GRANDCHILD_TASK RESUME;
ALTER TASK PIPELINE.CHILD_TASK RESUME;
ALTER TASK PIPELINE.ROOT_TASK RESUME;   -- activates the schedule for the whole chain
```

---

## Summary

| Concept | Key object | What it does |
|---|---|---|
| Streams | `CREATE STREAM ON TABLE` | Tracks row-level changes (INSERT / UPDATE / DELETE) automatically |
| Tasks | `CREATE TASK ... SCHEDULE` | Runs SQL on a timer without external schedulers |

**The standard pattern together:**

```
Source table changes
       │
       ▼
   [Stream] ← captures the delta
       │
       ▼
  Task (every N min) + WHEN SYSTEM$STREAM_HAS_DATA(...)
       │
       ▼
  MERGE INTO staging table
```

**Next:** Day 4 covers semi-structured data — VARIANT, loading JSON, colon syntax, and LATERAL FLATTEN.
