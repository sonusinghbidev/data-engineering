# Day 4 — Interview Solutions: RAW → STAGING → MART Pipeline

> Complete answers to all 15 questions. Read these after attempting the questions yourself.
> Test data (INSERT / UPDATE / DELETE batches) is in `notes.md` Step 6 — run those first before attempting scenario questions.

---

**Q1 — Purpose of each layer. Why not load directly into the mart?**

| Layer | Purpose |
|---|---|
| **RAW** | Exact copy of source data — no transformations, no deletions. Audit trail and reprocessing source. |
| **STAGING** | Cleaned, deduplicated, latest-state view. Business logic applied (soft deletes, type casts, column renaming). |
| **MART** | Aggregated, business-ready. Answers specific business questions (daily revenue, order counts). Optimized for reads. |

**Why not skip straight to the mart:**
- If the mart breaks or has bad data, you need RAW to replay from scratch. Without it, the source data is gone.
- Staging decouples source changes from mart logic. If the mart query changes, you re-aggregate from staging — you do not re-ingest from the source.
- Multiple marts can be built from the same staging layer without each one re-applying transformation logic independently.

---

**Q2 — What is a soft delete? Why use it in STAGING?**

A **soft delete** marks a row as deleted without physically removing it — by flipping a flag like `is_deleted = TRUE` — rather than running a `DELETE` statement.

**Why soft delete in STAGING instead of hard delete:**

1. **History preservation** — The mart and downstream reports may need to know that an order existed and was cancelled. A hard delete erases that fact.
2. **Replayability** — If the mart is rebuilt from staging, soft-deleted rows are excluded by the `WHERE is_deleted = FALSE` filter. No data is lost.
3. **Audit trail** — You can answer "how many orders were placed and later removed?" — impossible if rows are hard-deleted.
4. **Safety** — Accidental deletes in RAW do not destroy staging data permanently. You can flip `is_deleted = FALSE` to restore.

---

**Q3 — Why does filtering to `METADATA$ACTION = 'INSERT'` correctly handle updates?**

When a row is updated in RAW, the stream produces **two rows**:
- `DELETE` with `METADATA$ISUPDATE = TRUE` — carries the **old values**
- `INSERT` with `METADATA$ISUPDATE = TRUE` — carries the **new values**

Filtering to `METADATA$ACTION = 'INSERT'` captures the new-value row. The MERGE then finds the existing row in staging (`WHEN MATCHED`) and overwrites it with the new values.

The `DELETE` row (old values) is intentionally ignored — you only need the latest state. This is exactly correct behavior for SCD Type 1 (overwrite with current values).

---

**Q4 — Three MERGE branches: what does each handle?**

```sql
-- Branch 1
WHEN MATCHED AND src.METADATA$ACTION = 'INSERT'
```
Row already exists in staging **and** this is the new-value row of an update (or the same row being re-inserted). Overwrites all columns with fresh values, sets `is_deleted = FALSE`.

```sql
-- Branch 2
WHEN MATCHED AND src.METADATA$ACTION = 'DELETE' AND src.METADATA$ISUPDATE = FALSE
```
Row already exists in staging **and** this is a genuine hard delete from RAW (not the before-image of an update). Sets `is_deleted = TRUE` — soft delete.

```sql
-- Branch 3
WHEN NOT MATCHED AND src.METADATA$ACTION = 'INSERT'
```
Row does not exist in staging yet — this is a brand new order. Inserts the full row with `is_deleted = FALSE`.

**What is NOT handled:** `WHEN NOT MATCHED AND METADATA$ACTION = 'DELETE'` — a delete for a row that never existed in staging. This can happen if RAW data was deleted before the stream was ever consumed. The MERGE silently ignores it, which is correct.

---

**Q5 — The DELETE row from an UPDATE has `METADATA$ISUPDATE = TRUE`. Does it cause a problem?**

No. Here is exactly what happens to it in the MERGE:

The DELETE row with `METADATA$ISUPDATE = TRUE` matches `WHEN MATCHED AND src.METADATA$ACTION = 'DELETE' AND src.METADATA$ISUPDATE = FALSE` — but `METADATA$ISUPDATE = TRUE` does NOT satisfy `= FALSE`, so this branch is skipped.

It also does not match Branch 1 (`ACTION = 'INSERT'`) or Branch 3 (`NOT MATCHED`).

**Result:** The DELETE row from an update matches zero branches in the MERGE and is silently ignored. This is the correct behavior — you never want to soft-delete a row just because it was updated.

---

**Q6 — Order inserted Jan 10 as PENDING, updated Jan 12 to DELIVERED. What does the mart show?**

The mart groups by `order_date` — the date the order was placed — not the date it was updated. The order was placed on January 10, so it always lives in the **January 10 mart row** regardless of when its status changed.

**Before the status update:**
- Jan 10 mart row: `pending_orders += 1` (or whichever status column tracks PENDING)

**After the status update (Task runs):**
- Staging row for order_id 1004: `status = 'DELIVERED'`
- Mart MERGE re-aggregates Jan 10 from the full staging table
- Jan 10 mart row: `delivered_orders += 1`, pending count drops

**Jan 12 mart row:** Not affected at all. The order's `order_date` is still Jan 10 — the update does not change which mart row it belongs to.

---

**Q7 — Task 2 has no `WHEN SYSTEM$STREAM_HAS_DATA(...)`. Is it safe?**

Yes, and here is why: Task 1 already has the `WHEN` condition. If Task 1's stream is empty, Task 1 **skips entirely** — it never runs its SQL, and Task 2 never fires because it only runs `AFTER` Task 1 completes.

If Task 1's stream has data, Task 1 runs and completes, then Task 2 fires. At that point it is guaranteed something changed in staging, so running the mart MERGE is correct and necessary.

Adding `WHEN SYSTEM$STREAM_HAS_DATA(...)` on Task 2 as well would actually require a second stream on STG_ORDERS — which is extra overhead. The `AFTER` dependency already provides the right guard.

---

**Q8 — Task 1 succeeded, Task 2 failed mid-MERGE. What state is the pipeline in? How to recover?**

**State of the pipeline:**
- RAW stream: consumed (empty) — Task 1 successfully merged all changes into staging
- STAGING: fully up to date — Task 1 completed successfully
- MART: partially updated or unchanged — Task 2's MERGE failed and rolled back (Snowflake MERGE is atomic — either all rows update or none do)
- No data is lost. The mart is just stale.

**Recovery:**
```sql
-- Step 1: Check task history to confirm Task 1 succeeded and Task 2 failed
SELECT name, state, error_message
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
    SCHEDULED_TIME_RANGE_START => DATEADD('hours', -1, CURRENT_TIMESTAMP())
))
ORDER BY scheduled_time DESC;

-- Step 2: Fix the root cause (e.g., resume the warehouse)
ALTER WAREHOUSE COMPUTE_WH RESUME;

-- Step 3: Manually run just Task 2 — no need to reprocess Task 1
EXECUTE TASK ECOMM_DB.RAW_DATA.STG_TO_MART_TASK;

-- Step 4: Verify mart is now correct
SELECT * FROM ECOMM_DB.MARTS.ORDERS_MART ORDER BY order_date;
```

You do NOT need to rerun Task 1 — staging is already correct. Task 2 reads from the full staging table (not a stream), so it can be re-executed any number of times safely.

---

**Q9 — An order on Jan 10 is soft-deleted. What happens to the Jan 10 mart row? Walk through the SQL.**

**Step 1:** The DELETE from RAW generates a stream record with `METADATA$ACTION = 'DELETE', METADATA$ISUPDATE = FALSE`.

**Step 2:** Task 1's MERGE matches `WHEN MATCHED AND ACTION = 'DELETE' AND ISUPDATE = FALSE` → sets `is_deleted = TRUE` on that staging row.

**Step 3:** Task 2 fires. The mart MERGE re-aggregates from staging with `WHERE is_deleted = FALSE`. The soft-deleted order is now excluded from the COUNT and SUM.

**Step 4:** The mart MERGE finds the existing Jan 10 row (`WHEN MATCHED`) and updates the counts and revenue to reflect one fewer order.

**Result:** The Jan 10 mart row now has `total_orders - 1` and reduced `total_revenue`. The soft-deleted staging row still exists for audit purposes but does not affect the mart numbers.

---

**Q10 — MERGE SQL run twice manually. Stream consumed on first run. What does the second run process?**

**After the first run:** The stream is consumed — the offset advanced, change records are cleared. The stream is now empty.

**Second run:** The MERGE executes with an empty stream as its source. The `USING (SELECT * FROM stream)` returns zero rows. No `WHEN MATCHED` or `WHEN NOT MATCHED` conditions fire. Zero rows updated, zero rows inserted. The staging table is unchanged.

**No duplicates.** MERGE with an empty source is a no-op. This is one of the key safety properties of the stream + MERGE pattern.

---

**Q11 — Rebuild STAGING and MART from RAW from scratch. Stream is empty. How?**

The stream is empty so there is nothing to replay through it. You need to do a full reload directly from RAW:

```sql
-- Step 1: Suspend tasks to prevent interference during rebuild
ALTER TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK  SUSPEND;
ALTER TASK ECOMM_DB.RAW_DATA.STG_TO_MART_TASK SUSPEND;

-- Step 2: Wipe staging and mart
TRUNCATE TABLE ECOMM_DB.STAGING.STG_ORDERS;
TRUNCATE TABLE ECOMM_DB.MARTS.ORDERS_MART;

-- Step 3: Full load from RAW into STAGING (bypassing the stream)
INSERT INTO ECOMM_DB.STAGING.STG_ORDERS
    (order_id, customer_id, customer_name, product, quantity,
     unit_price, total_amount, status, order_date, is_deleted, stg_updated_at)
SELECT
    order_id, customer_id, customer_name, product, quantity,
    unit_price, total_amount, status, order_date, FALSE, CURRENT_TIMESTAMP()
FROM ECOMM_DB.RAW_DATA.ORDERS_RAW;

-- Step 4: Rebuild mart from staging
MERGE INTO ECOMM_DB.MARTS.ORDERS_MART AS tgt
USING (
    SELECT order_date, COUNT(*) AS total_orders,
           SUM(CASE WHEN status = 'CONFIRMED'  THEN 1 ELSE 0 END) AS confirmed_orders,
           SUM(CASE WHEN status = 'SHIPPED'    THEN 1 ELSE 0 END) AS shipped_orders,
           SUM(CASE WHEN status = 'DELIVERED'  THEN 1 ELSE 0 END) AS delivered_orders,
           SUM(CASE WHEN status = 'CANCELLED'  THEN 1 ELSE 0 END) AS cancelled_orders,
           SUM(total_amount) AS total_revenue, AVG(total_amount) AS avg_order_value
    FROM ECOMM_DB.STAGING.STG_ORDERS WHERE is_deleted = FALSE GROUP BY order_date
) AS src
ON tgt.order_date = src.order_date
WHEN NOT MATCHED THEN
    INSERT (order_date, total_orders, confirmed_orders, shipped_orders,
            delivered_orders, cancelled_orders, total_revenue, avg_order_value)
    VALUES (src.order_date, src.total_orders, src.confirmed_orders, src.shipped_orders,
            src.delivered_orders, src.cancelled_orders, src.total_revenue, src.avg_order_value);

-- Step 5: Resume tasks (child first, root last)
ALTER TASK ECOMM_DB.RAW_DATA.STG_TO_MART_TASK RESUME;
ALTER TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK  RESUME;
```

---

**Q12 — 1-minute window, no new data in RAW. What happens step by step?**

1. The 1-minute schedule fires — Snowflake evaluates the `WHEN` condition before starting the warehouse.
2. `SYSTEM$STREAM_HAS_DATA('ECOMM_DB.RAW_DATA.ORDERS_RAW_STREAM')` returns `FALSE` — the stream is empty.
3. Task 1 is marked as **SKIPPED** in task history. No warehouse is started. No credits consumed.
4. Because Task 1 skipped (did not complete), Task 2 does not fire.
5. Both tasks remain idle until the next minute tick.

This repeats every minute for as long as no data arrives. The pipeline costs nothing during idle periods.

---

**Q13 — New column `region VARCHAR(50)` added to ORDERS_RAW. What else needs to change?**

Four things:

```sql
-- 1. Add the column to STAGING
ALTER TABLE ECOMM_DB.STAGING.STG_ORDERS ADD COLUMN region VARCHAR(50);

-- 2. Update Task 1's MERGE to include the new column in all three branches
--    WHEN MATCHED AND ACTION = 'INSERT': add  tgt.region = src.region
--    WHEN NOT MATCHED AND ACTION = 'INSERT': add region to INSERT column list and VALUES

-- 3. Drop and recreate Task 1 with the updated MERGE SQL
--    (Tasks cannot be ALTER-ed to change their SQL — must DROP and CREATE)
ALTER TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK  SUSPEND;
DROP TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK;
-- CREATE OR REPLACE TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK ... with updated MERGE SQL including region
ALTER TASK ECOMM_DB.RAW_DATA.STG_TO_MART_TASK RESUME;
ALTER TASK ECOMM_DB.RAW_DATA.RAW_TO_STG_TASK  RESUME;

-- 4. If the mart needs region-level breakdowns, update ORDERS_MART and Task 2 similarly
--    If the mart aggregates don't need region, no change to Task 2 is required
```

**Important:** The stream on ORDERS_RAW automatically picks up the new column — streams reflect the current table schema. No need to recreate the stream.

---

**Q14 — Three source tables, three streams, one joined mart. Design the full Task DAG.**

```
CUSTOMERS_RAW ──[stream]──► STG_CUSTOMERS ──┐
PRODUCTS_RAW  ──[stream]──► STG_PRODUCTS  ──┼──► JOINED_MART
ORDERS_RAW    ──[stream]──► STG_ORDERS    ──┘
```

**Task design:**

```sql
-- Three parallel root tasks — each syncs one stream into one staging table
-- All three share the same schedule so they fire together

CREATE TASK SYNC_CUSTOMERS_TASK  WAREHOUSE=WH SCHEDULE='5 MINUTE'
  WHEN SYSTEM$STREAM_HAS_DATA('RAW_DATA.CUSTOMERS_STREAM')
  AS MERGE INTO STAGING.STG_CUSTOMERS ...;

CREATE TASK SYNC_PRODUCTS_TASK   WAREHOUSE=WH SCHEDULE='5 MINUTE'
  WHEN SYSTEM$STREAM_HAS_DATA('RAW_DATA.PRODUCTS_STREAM')
  AS MERGE INTO STAGING.STG_PRODUCTS ...;

CREATE TASK SYNC_ORDERS_TASK     WAREHOUSE=WH SCHEDULE='5 MINUTE'
  WHEN SYSTEM$STREAM_HAS_DATA('RAW_DATA.ORDERS_STREAM')
  AS MERGE INTO STAGING.STG_ORDERS ...;

-- One child task per staging table (runs after its own root)
CREATE TASK REFRESH_MART_TASK  WAREHOUSE=WH
  AFTER SYNC_ORDERS_TASK       -- mart depends on orders; fires when orders sync completes
  AS MERGE INTO MARTS.JOINED_MART ...;
```

**Why three separate root tasks instead of one:**
Each source table changes independently. If only orders changed today, the customers and products syncs skip (stream empty → WHEN = FALSE). One combined root task would need to run even if only one table changed, and cannot skip selectively.

**Resume order:**
```sql
ALTER TASK REFRESH_MART_TASK  RESUME;
ALTER TASK SYNC_ORDERS_TASK   RESUME;
ALTER TASK SYNC_PRODUCTS_TASK RESUME;
ALTER TASK SYNC_CUSTOMERS_TASK RESUME;
```

---

**Q15 — Mart must refresh within 5 seconds of a RAW change. Tasks won't work. What instead?**

**Snowflake Dynamic Tables.**

A Dynamic Table is a continuously maintained materialized result — you define the query, and Snowflake automatically refreshes it whenever the underlying data changes, with a configurable target lag (minimum a few seconds).

```sql
CREATE OR REPLACE DYNAMIC TABLE MARTS.ORDERS_MART
    TARGET_LAG = '5 seconds'
    WAREHOUSE  = COMPUTE_WH
AS
SELECT
    order_date,
    COUNT(*)                                              AS total_orders,
    SUM(CASE WHEN status = 'CONFIRMED'  THEN 1 ELSE 0 END) AS confirmed_orders,
    SUM(CASE WHEN status = 'DELIVERED'  THEN 1 ELSE 0 END) AS delivered_orders,
    SUM(total_amount)                                     AS total_revenue
FROM ECOMM_DB.STAGING.STG_ORDERS
WHERE is_deleted = FALSE
GROUP BY order_date;
```

**Why Tasks cannot achieve 5 seconds:** The minimum Task interval is 1 minute. Even with `EXECUTE TASK`, there is warehouse startup latency. Dynamic Tables are purpose-built for near-real-time derived results and handle the refresh scheduling internally without you writing any MERGE logic.
