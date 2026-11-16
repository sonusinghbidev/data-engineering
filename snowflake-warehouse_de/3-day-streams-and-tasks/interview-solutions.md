# Day 3 — Interview Solutions: Streams and Tasks

> Complete answers to all 18 questions. Read these after attempting the questions yourself.

---

## Concept 1: Streams — Change Data Capture

**Q1 — What is a Snowflake Stream? What problem does it solve?**

A **Stream** is a Snowflake object that sits on top of a table and records every DML change (INSERT, UPDATE, DELETE) made to that table since the stream was last consumed.

**Problem it solves:** Without CDC, keeping a downstream table in sync requires either:
- **Full reload** — truncate and reload the entire target table every run. Gets expensive as the table grows.
- **Timestamp delta** — query rows where `updated_at > last_run_time`. Fragile — requires a reliable `updated_at` column on every table.

A Stream removes both problems. Snowflake automatically tracks what changed, and your pipeline only processes the delta — no timestamp column needed, no full scan.

---

**Q2 — Three stream metadata columns? Possible values for `METADATA$ACTION`?**

| Column | Possible values | Meaning |
|---|---|---|
| `METADATA$ACTION` | `'INSERT'` or `'DELETE'` | Type of change |
| `METADATA$ISUPDATE` | `TRUE` or `FALSE` | Was this row part of an UPDATE? |
| `METADATA$ROW_ID` | unique string | Identifies the specific row that changed |

`METADATA$ACTION` only ever has two values — `INSERT` and `DELETE`. There is no `UPDATE` value. See Q3 for how updates are represented.

---

**Q3 — How does a stream represent an UPDATE? How many rows?**

A single UPDATE produces **two rows** in the stream:

| Row | `METADATA$ACTION` | `METADATA$ISUPDATE` | Content |
|---|---|---|---|
| Row 1 | `DELETE` | `TRUE` | Old values (before the update) |
| Row 2 | `INSERT` | `TRUE` | New values (after the update) |

This is the **pre/post image** pattern. Snowflake stores the before and after state of the changed row.

```sql
-- Get only the new values of updated rows
SELECT * FROM my_stream
WHERE METADATA$ACTION = 'INSERT' AND METADATA$ISUPDATE = TRUE;

-- Get the old values (useful for auditing what changed)
SELECT * FROM my_stream
WHERE METADATA$ACTION = 'DELETE' AND METADATA$ISUPDATE = TRUE;
```

---

**Q4 — Standard stream vs APPEND ONLY stream. Real-world example for each.**

| Type | Tracks | Use when |
|---|---|---|
| Standard | INSERT, UPDATE, DELETE | Rows in the source table can be modified after insertion |
| Append-only | INSERT only (more efficient) | Rows are written once and never changed |

**Standard stream — real-world example:**
A `CUSTOMERS` table where customer records are updated when they change their email, city, or subscription status. You need the stream to capture both new customers and updates to existing ones.

**Append-only stream — real-world example:**
An `ORDER_EVENTS` table where each row is a single event (order placed, payment received, shipped). Events are never updated — only new events are appended. An append-only stream is more efficient here because Snowflake does not track update/delete offsets.

---

**Q5 — You SELECT from a stream. Does the offset advance?**

**No. A plain `SELECT` does not advance the offset.**

The offset only advances when the stream is consumed inside a **DML transaction** that commits successfully:
- `INSERT INTO ... SELECT FROM stream`
- `MERGE INTO ... USING stream`

You can query the stream as many times as you want to inspect changes — they remain visible until used in a DML. If the DML fails and rolls back, the stream offset rolls back too.

---

**Q6 — Write a MERGE that uses a stream to keep STG_CUSTOMERS in sync.**

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
    target.city       = src.city,
    target.updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
  INSERT (customer_id, full_name, email, city, updated_at)
  VALUES (src.customer_id, src.full_name, src.email, src.city, CURRENT_TIMESTAMP());
```

Filtering to `METADATA$ACTION = 'INSERT'` captures both genuinely new rows (`METADATA$ISUPDATE = FALSE`) and the new-value row of updates (`METADATA$ISUPDATE = TRUE`). Both should be applied to the target. The `DELETE` rows (old values of updates) are ignored — we only want the latest state.

---

**Q7 — Filtering to `METADATA$ACTION = 'INSERT'` in the MERGE — does it correctly handle updates?**

**Yes, it correctly handles updates.**

When a row is updated in the source table, the stream produces two rows:
- `DELETE` with `METADATA$ISUPDATE = TRUE` — old values
- `INSERT` with `METADATA$ISUPDATE = TRUE` — new values

By filtering to `METADATA$ACTION = 'INSERT'`, you get the new-value row. The MERGE then finds the existing row in the target (`WHEN MATCHED`) and overwrites it with the new values. This is exactly the correct behavior for SCD Type 1 (keep only the latest state).

The `DELETE` row is intentionally ignored — it only carries the old values, which you no longer need.

---

**Q8 — What does it mean for a stream to become "stale"? How to recover?**

A stream becomes **stale** when the changes it was tracking have aged out of the source table's Time Travel history.

Streams internally rely on Time Travel to store the before-image of changed rows. If the stream is not consumed within the source table's data retention period (default: 1 day on Standard edition), Snowflake can no longer reconstruct those change records.

```sql
SHOW STREAMS IN SCHEMA RAW_DATA;
-- If the "stale" column is TRUE, the stream is no longer usable
```

**Recovery — you cannot un-stale a stream:**
1. Drop the stale stream
2. Recreate it — the new stream starts tracking from now
3. Perform a full reload of the target table (since incremental changes were lost)

**Prevention:** Ensure your Tasks run frequently enough to consume the stream before data ages out. If your table has 1-day retention, the Task must run at least once per day.

---

**Q9 — ORDERS_RAW where rows are only ever inserted. What stream type?**

**Append-only stream.**

```sql
CREATE STREAM IF NOT EXISTS RAW_DATA.ORDERS_STREAM
  ON TABLE RAW_DATA.ORDERS_RAW
  APPEND ONLY = TRUE;
```

Since rows are only ever inserted (never updated or deleted), a standard stream would track offsets for UPDATE and DELETE operations that never happen — wasted overhead. Append-only streams are more efficient for insert-only tables because Snowflake skips that tracking entirely.

---

## Concept 2: Tasks — Scheduling and Automation

**Q10 — What is a Snowflake Task? Two scheduling approaches?**

A **Task** is a Snowflake object that runs a single SQL statement on a schedule. It is Snowflake's native job scheduler — no Airflow or cron jobs needed for Snowflake-internal pipelines.

**Two scheduling approaches:**

1. **Interval-based:**
```sql
SCHEDULE = '5 MINUTE'    -- every 5 minutes
SCHEDULE = '60 MINUTE'   -- every hour
```

2. **CRON-based:**
```sql
SCHEDULE = 'USING CRON 0 2 * * * UTC'    -- 2 AM every day
SCHEDULE = 'USING CRON */15 * * * * UTC' -- every 15 minutes
SCHEDULE = 'USING CRON 0 9 * * 1 UTC'   -- 9 AM every Monday
```

---

**Q11 — Command to activate a task? Command to pause it?**

```sql
-- Activate (start running on schedule)
ALTER TASK STAGING.PROCESS_CHANGES_TASK RESUME;

-- Pause without dropping
ALTER TASK STAGING.PROCESS_CHANGES_TASK SUSPEND;

-- Check current state
SHOW TASKS IN SCHEMA STAGING;
-- "state" column: "started" = active on schedule, "suspended" = paused
```

Tasks are created in SUSPENDED state by default to prevent accidental execution before the pipeline is fully configured and tested.

---

**Q12 — What does `WHEN SYSTEM$STREAM_HAS_DATA(...)` do? Why does it matter for cost?**

`SYSTEM$STREAM_HAS_DATA('schema.stream_name')` returns `TRUE` if the stream has unconsumed changes, `FALSE` if it is empty.

When used in a Task's `WHEN` clause, the task only executes its SQL if the condition is `TRUE`. If `FALSE`, the task skips — **no warehouse starts, no credits consumed**.

```sql
CREATE TASK process_task
  WAREHOUSE = COMPUTE_WH
  SCHEDULE  = '1 MINUTE'
  WHEN SYSTEM$STREAM_HAS_DATA('RAW_DATA.CUSTOMERS_STREAM')
AS
MERGE INTO STAGING.STG_CUSTOMERS ...;
```

**Why it matters for cost:** A task running every minute would wake up and spin the warehouse 60 times per hour whether or not any data arrived. With `WHEN SYSTEM$STREAM_HAS_DATA(...)`, if no changes exist, the task skips every single time — zero warehouse cost for those skips. For a pipeline where data arrives once per hour, this avoids 59 unnecessary warehouse starts per hour.

---

**Q13 — Write a Task that checks every 5 minutes and runs a MERGE, with WHEN condition.**

```sql
CREATE TASK IF NOT EXISTS STAGING.PROCESS_CUSTOMER_CHANGES_TASK
  WAREHOUSE = COMPUTE_WH
  SCHEDULE  = '5 MINUTE'
  WHEN SYSTEM$STREAM_HAS_DATA('RAW_DATA.CUSTOMERS_STREAM')
AS
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

-- Always resume after creating
ALTER TASK STAGING.PROCESS_CUSTOMER_CHANGES_TASK RESUME;
```

---

**Q14 — What is `EXECUTE TASK`? Two situations to use it in production.**

```sql
EXECUTE TASK STAGING.PROCESS_CUSTOMER_CHANGES_TASK;
```

`EXECUTE TASK` triggers a task immediately without waiting for the next scheduled run. It respects the same `WHEN` condition as the scheduled run — if the stream is empty, it still skips.

**Two production situations:**

1. **Testing after creation** — After creating a new task, verify it works immediately instead of waiting up to N minutes for the first scheduled fire.

2. **Manual recovery after failure** — If a task failed (warehouse down, SQL error), fix the issue and use `EXECUTE TASK` to reprocess the backlog right away rather than waiting for the next scheduled run.

---

**Q15 — Explain Task chaining. Root task vs child task. Can a child have its own schedule?**

Task chaining builds a **DAG (directed acyclic graph)** using the `AFTER` keyword:

```sql
-- Root: has a schedule
CREATE TASK root_task WAREHOUSE=WH SCHEDULE='USING CRON 0 2 * * * UTC' AS <sql>;

-- Child: fires when root completes successfully
CREATE TASK child_task WAREHOUSE=WH AFTER root_task AS <sql>;
```

| | Root task | Child task |
|---|---|---|
| Schedule | Yes — has `SCHEDULE` | No — has `AFTER <parent>` |
| What triggers it | The clock (CRON or interval) | Parent task completing successfully |
| Can it have its own schedule? | Yes | **No** — a task cannot have both `SCHEDULE` and `AFTER` |

If the root task fails, child tasks do not run. If a child fails, its downstream children also do not run.

---

**Q16 — Three tasks: LOAD_TASK → TRANSFORM_TASK → MART_TASK. Resume order?**

```sql
ALTER TASK MART_TASK RESUME;       -- grandchild first
ALTER TASK TRANSFORM_TASK RESUME;  -- child second
ALTER TASK LOAD_TASK RESUME;       -- root last
```

**Why children first:** When you resume the root task, Snowflake validates the entire DAG. If any child task is still suspended, the root resume fails. Resuming children first ensures the whole chain is ready before the root is activated and the schedule starts firing.

---

**Q17 — Task failed, warehouse auto-suspended, stream has 18 hours of changes. How to recover?**

**Step 1: Check if the stream is still valid (not stale)**
```sql
SHOW STREAMS IN SCHEMA RAW_DATA;
-- If "stale" = TRUE: stream is lost, need a full reload of the target table
-- If "stale" = FALSE: changes are still there, proceed
```

**Step 2: Check how many changes are pending**
```sql
SELECT COUNT(*) FROM RAW_DATA.CUSTOMERS_STREAM;
```

**Step 3: Resume the warehouse and manually trigger the task**
```sql
ALTER WAREHOUSE COMPUTE_WH RESUME;
EXECUTE TASK STAGING.PROCESS_CUSTOMER_CHANGES_TASK;
```

**Step 4: Verify the task succeeded and stream is consumed**
```sql
SELECT name, state, error_message
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
    SCHEDULED_TIME_RANGE_START => DATEADD('minutes', -10, CURRENT_TIMESTAMP()),
    TASK_NAME => 'PROCESS_CUSTOMER_CHANGES_TASK'
));
-- state should be SUCCEEDED

SELECT COUNT(*) FROM RAW_DATA.CUSTOMERS_STREAM;
-- Should be 0 after successful consumption
```

**Step 5: Investigate root cause** — Why did the warehouse auto-suspend during task execution? Add a Task failure alert (Snowflake Alerts or external monitoring) so the team is notified before the stream goes stale next time.

---

**Q18 (System design) — Fully Snowflake-native CDC pipeline for retail SALES_RAW.**

```sql
-- ── STREAM on the raw table ───────────────────────────────────────────────
CREATE STREAM IF NOT EXISTS RAW_DATA.SALES_STREAM
  ON TABLE RAW_DATA.SALES_RAW;
-- Standard stream (not append-only) because existing sales records can be updated

-- ── STAGING TABLE ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS STAGING.STG_SALES (
    sale_id       NUMBER       PRIMARY KEY,
    customer_id   NUMBER,
    product_id    NUMBER,
    amount        NUMBER(12,2),
    sale_date     DATE,
    status        VARCHAR,
    updated_at    TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- ── MART TABLE ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS MARTS.SALES_MART (
    sale_date     DATE,
    total_sales   NUMBER,
    total_revenue NUMBER(14,2)
);

-- ── ROOT TASK: sync stream changes into staging ───────────────────────────
CREATE TASK IF NOT EXISTS PIPELINE.SYNC_SALES_TASK
  WAREHOUSE = COMPUTE_WH
  SCHEDULE  = '5 MINUTE'
  WHEN SYSTEM$STREAM_HAS_DATA('RAW_DATA.SALES_STREAM')
AS
MERGE INTO STAGING.STG_SALES AS target
USING (
  SELECT * FROM RAW_DATA.SALES_STREAM
  WHERE METADATA$ACTION = 'INSERT'
) AS src
ON target.sale_id = src.sale_id
WHEN MATCHED THEN
  UPDATE SET
    target.amount     = src.amount,
    target.status     = src.status,
    target.updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
  INSERT (sale_id, customer_id, product_id, amount, sale_date, status, updated_at)
  VALUES (src.sale_id, src.customer_id, src.product_id, src.amount, src.sale_date, src.status, CURRENT_TIMESTAMP());

-- ── CHILD TASK: refresh mart after staging sync ───────────────────────────
CREATE TASK IF NOT EXISTS PIPELINE.REFRESH_SALES_MART_TASK
  WAREHOUSE = COMPUTE_WH
  AFTER PIPELINE.SYNC_SALES_TASK
AS
INSERT INTO MARTS.SALES_MART (sale_date, total_sales, total_revenue)
SELECT sale_date, COUNT(*), SUM(amount)
FROM STAGING.STG_SALES
GROUP BY sale_date;

-- ── RESUME: children first, root last ─────────────────────────────────────
ALTER TASK PIPELINE.REFRESH_SALES_MART_TASK RESUME;
ALTER TASK PIPELINE.SYNC_SALES_TASK RESUME;
```

**Design decisions:**
- Standard stream (not append-only) because sales records can be updated (e.g., status changes from PENDING to DELIVERED)
- `WHEN SYSTEM$STREAM_HAS_DATA(...)` on the root task — no warehouse startup if no changes arrived
- Child task has no `WHEN` condition — it always runs after the root succeeds (the mart refresh is fast regardless)
- Root fires every 5 minutes — frequent enough to stay well within the 1-day stream retention window
