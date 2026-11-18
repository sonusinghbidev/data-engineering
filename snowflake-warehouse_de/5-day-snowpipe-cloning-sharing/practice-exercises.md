# Day 3 — Practice Exercises: Streams and Tasks

> All exercises run entirely in Snowsight SQL worksheets — no local tools needed.
> Complete them in order — each builds on the previous one.
> Estimated total time: 50–70 minutes.

---

## Exercise 1 — Create a Stream and Observe CDC

**Concept:** Stream creation, INSERT / UPDATE / DELETE metadata

**1a. Set up your session and create a table to track**
```sql
USE ROLE SYSADMIN;
USE WAREHOUSE COMPUTE_WH;
USE DATABASE ECOMM_DB;
USE SCHEMA RAW_DATA;

CREATE TABLE IF NOT EXISTS CUSTOMERS_RAW (
    customer_id   NUMBER       PRIMARY KEY,
    full_name     VARCHAR(200),
    email         VARCHAR(200),
    city          VARCHAR(100),
    status        VARCHAR(50)  DEFAULT 'ACTIVE'
);
```

**1b. Create a stream on the table**
```sql
CREATE STREAM IF NOT EXISTS CUSTOMERS_STREAM
  ON TABLE ECOMM_DB.RAW_DATA.CUSTOMERS_RAW
  COMMENT = 'CDC stream — tracks all changes to CUSTOMERS_RAW';

-- Verify it was created
SHOW STREAMS IN SCHEMA ECOMM_DB.RAW_DATA;
```

**1c. Insert initial rows**
```sql
INSERT INTO CUSTOMERS_RAW (customer_id, full_name, email, city) VALUES
  (1, 'Alice Johnson',  'alice@example.com',  'New York'),
  (2, 'Bob Smith',      'bob@example.com',    'Chicago'),
  (3, 'Priya Sharma',   'priya@example.com',  'Austin'),
  (4, 'Carlos Mendez',  'carlos@example.com', 'Miami'),
  (5, 'Yuki Tanaka',    'yuki@example.com',   'Seattle');
```

**1d. See what the stream captured**
```sql
SELECT
    customer_id,
    full_name,
    city,
    METADATA$ACTION,
    METADATA$ISUPDATE
FROM ECOMM_DB.RAW_DATA.CUSTOMERS_STREAM
ORDER BY customer_id;
```

Questions:
- How many rows? What is `METADATA$ACTION` for all of them?
- What is `METADATA$ISUPDATE` for all of them?

**1e. Make changes — update, delete, and insert**
```sql
-- Update Bob's city
UPDATE CUSTOMERS_RAW SET city = 'Los Angeles' WHERE customer_id = 2;

-- Delete Carlos
DELETE FROM CUSTOMERS_RAW WHERE customer_id = 4;

-- Insert a new customer
INSERT INTO CUSTOMERS_RAW VALUES (6, 'Sophie Dubois', 'sophie@example.com', 'Denver', 'ACTIVE');
```

**1f. Query the stream again — observe how each change type looks**
```sql
SELECT
    customer_id,
    full_name,
    city,
    METADATA$ACTION,
    METADATA$ISUPDATE
FROM ECOMM_DB.RAW_DATA.CUSTOMERS_STREAM
ORDER BY customer_id, METADATA$ACTION;
```

Questions to answer:
- The UPDATE to Bob (customer_id=2) — how many rows in the stream? What are their METADATA$ACTION values?
- The DELETE of Carlos (customer_id=4) — what does the stream show?
- The INSERT of Sophie (customer_id=6) — what does the stream show?

**1g. Filter stream by change type**
```sql
-- New inserts only
SELECT customer_id, full_name, city, 'NEW' AS change_type
FROM ECOMM_DB.RAW_DATA.CUSTOMERS_STREAM
WHERE METADATA$ACTION = 'INSERT' AND METADATA$ISUPDATE = FALSE;

-- Updates — new value rows
SELECT customer_id, full_name, city, 'UPDATED' AS change_type
FROM ECOMM_DB.RAW_DATA.CUSTOMERS_STREAM
WHERE METADATA$ACTION = 'INSERT' AND METADATA$ISUPDATE = TRUE;

-- Deletes
SELECT customer_id, full_name, city, 'DELETED' AS change_type
FROM ECOMM_DB.RAW_DATA.CUSTOMERS_STREAM
WHERE METADATA$ACTION = 'DELETE' AND METADATA$ISUPDATE = FALSE;
```

**Expected outcome:** You can see all three types of changes clearly separated. Bob's update appears as 2 rows, Carlos's delete as 1 row, Sophie's insert as 1 row.

---

## Exercise 2 — Consume the Stream with MERGE

**Concept:** Stream offset, MERGE from stream, staging sync

**2a. Create the staging table**
```sql
USE SCHEMA ECOMM_DB.STAGING;

CREATE TABLE IF NOT EXISTS STG_CUSTOMERS (
    customer_id   NUMBER       PRIMARY KEY,
    full_name     VARCHAR(200),
    email         VARCHAR(200),
    city          VARCHAR(100),
    status        VARCHAR(50),
    updated_at    TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
```

**2b. Run a MERGE to apply stream changes to staging**
```sql
MERGE INTO ECOMM_DB.STAGING.STG_CUSTOMERS AS target
USING (
  SELECT * FROM ECOMM_DB.RAW_DATA.CUSTOMERS_STREAM
  WHERE METADATA$ACTION = 'INSERT'
) AS src
ON target.customer_id = src.customer_id
WHEN MATCHED THEN
  UPDATE SET
    target.full_name  = src.full_name,
    target.email      = src.email,
    target.city       = src.city,
    target.status     = src.status,
    target.updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
  INSERT (customer_id, full_name, email, city, status, updated_at)
  VALUES (src.customer_id, src.full_name, src.email, src.city, src.status, CURRENT_TIMESTAMP());
```

**2c. Check the staging table**
```sql
SELECT * FROM ECOMM_DB.STAGING.STG_CUSTOMERS ORDER BY customer_id;
```

Questions:
- Is Bob's city `Los Angeles` (the new value) or `Chicago` (the old value)?
- Is Carlos in the staging table? Why or why not?
- Is Sophie there?

**2d. Check the stream after consuming**
```sql
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.CUSTOMERS_STREAM;
-- Should be 0 — the MERGE consumed the stream, offset advanced
```

**2e. Make more changes and verify the stream captures them**
```sql
-- Go back to RAW_DATA schema to make changes
USE SCHEMA ECOMM_DB.RAW_DATA;

INSERT INTO CUSTOMERS_RAW VALUES (7, 'Marco Rossi', 'marco@example.com', 'Boston', 'ACTIVE');
UPDATE CUSTOMERS_RAW SET status = 'VIP' WHERE customer_id = 1;

-- Stream should show 3 rows (1 insert + 2 for the update)
SELECT customer_id, full_name, status, METADATA$ACTION, METADATA$ISUPDATE
FROM ECOMM_DB.RAW_DATA.CUSTOMERS_STREAM
ORDER BY customer_id, METADATA$ACTION;
```

**2f. Run the MERGE again to sync the new changes**
```sql
MERGE INTO ECOMM_DB.STAGING.STG_CUSTOMERS AS target
USING (
  SELECT * FROM ECOMM_DB.RAW_DATA.CUSTOMERS_STREAM
  WHERE METADATA$ACTION = 'INSERT'
) AS src
ON target.customer_id = src.customer_id
WHEN MATCHED THEN
  UPDATE SET
    target.full_name  = src.full_name,
    target.email      = src.email,
    target.city       = src.city,
    target.status     = src.status,
    target.updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
  INSERT (customer_id, full_name, email, city, status, updated_at)
  VALUES (src.customer_id, src.full_name, src.email, src.city, src.status, CURRENT_TIMESTAMP());

-- Verify: Alice should be VIP, Marco should appear
SELECT * FROM ECOMM_DB.STAGING.STG_CUSTOMERS ORDER BY customer_id;
```

**Expected outcome:** Staging table stays in sync with only the changes — no full reload needed. Stream is empty after each MERGE.

---

## Exercise 3 — Automate with a Task

**Concept:** Task creation, WHEN condition, EXECUTE TASK, task history

**3a. Create a task that runs the MERGE automatically**
```sql
USE ROLE SYSADMIN;
USE DATABASE ECOMM_DB;
USE SCHEMA STAGING;

CREATE TASK IF NOT EXISTS ECOMM_DB.STAGING.SYNC_CUSTOMERS_TASK
  WAREHOUSE = COMPUTE_WH
  SCHEDULE  = '1 MINUTE'
  WHEN SYSTEM$STREAM_HAS_DATA('ECOMM_DB.RAW_DATA.CUSTOMERS_STREAM')
AS
MERGE INTO ECOMM_DB.STAGING.STG_CUSTOMERS AS target
USING (
  SELECT * FROM ECOMM_DB.RAW_DATA.CUSTOMERS_STREAM
  WHERE METADATA$ACTION = 'INSERT'
) AS src
ON target.customer_id = src.customer_id
WHEN MATCHED THEN
  UPDATE SET
    target.full_name  = src.full_name,
    target.email      = src.email,
    target.city       = src.city,
    target.status     = src.status,
    target.updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
  INSERT (customer_id, full_name, email, city, status, updated_at)
  VALUES (src.customer_id, src.full_name, src.email, src.city, src.status, CURRENT_TIMESTAMP());
```

**3b. Add new data to generate stream changes**
```sql
USE SCHEMA ECOMM_DB.RAW_DATA;

INSERT INTO CUSTOMERS_RAW VALUES
  (8, 'Aisha Patel', 'aisha@example.com', 'Phoenix', 'ACTIVE'),
  (9, 'Lena Müller', 'lena@example.com',  'Berlin',  'ACTIVE');

UPDATE CUSTOMERS_RAW SET city = 'San Francisco' WHERE customer_id = 3;

-- Confirm stream has data
SELECT COUNT(*) FROM ECOMM_DB.RAW_DATA.CUSTOMERS_STREAM;
```

**3c. Test the task manually — do not wait for the schedule**
```sql
EXECUTE TASK ECOMM_DB.STAGING.SYNC_CUSTOMERS_TASK;
```

**3d. Check task run history**
```sql
SELECT
    name,
    state,
    scheduled_time,
    completed_time,
    error_message
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
    SCHEDULED_TIME_RANGE_START => DATEADD('minutes', -5, CURRENT_TIMESTAMP()),
    TASK_NAME => 'SYNC_CUSTOMERS_TASK'
))
ORDER BY scheduled_time DESC;
-- state should be SUCCEEDED
```

**3e. Verify staging was updated**
```sql
SELECT * FROM ECOMM_DB.STAGING.STG_CUSTOMERS ORDER BY customer_id;
-- Aisha and Lena should appear
-- Priya should show city = 'San Francisco'
```

**3f. Activate the schedule and test the WHEN condition**
```sql
-- Resume the task (activates the schedule)
ALTER TASK ECOMM_DB.STAGING.SYNC_CUSTOMERS_TASK RESUME;

SHOW TASKS IN SCHEMA ECOMM_DB.STAGING;
-- state should say "started"

-- Stream is now empty — WHEN condition should prevent execution
-- Wait 1–2 minutes, then check task history
SELECT name, state, scheduled_time, query_start_time
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
    SCHEDULED_TIME_RANGE_START => DATEADD('minutes', -5, CURRENT_TIMESTAMP()),
    TASK_NAME => 'SYNC_CUSTOMERS_TASK'
))
ORDER BY scheduled_time DESC;
-- You should see "SKIPPED" status for runs where the stream had no data
```

**3g. Add data and watch the task pick it up automatically**
```sql
-- Insert one more customer
INSERT INTO ECOMM_DB.RAW_DATA.CUSTOMERS_RAW
VALUES (10, 'James Lee', 'james@example.com', 'Atlanta', 'ACTIVE');

-- Wait about 1 minute, then check staging
SELECT * FROM ECOMM_DB.STAGING.STG_CUSTOMERS WHERE customer_id = 10;
-- James should appear without you running anything manually
```

**3h. Suspend the task when done**
```sql
ALTER TASK ECOMM_DB.STAGING.SYNC_CUSTOMERS_TASK SUSPEND;
-- Always suspend tasks after exercises to stop credit usage
```

**Expected outcome:** The task runs automatically, picks up new data from the stream, applies it to staging, and skips when there is nothing to process.

---

## Bonus — Chain Two Tasks

**Concept:** Task DAG, root + child task, resume order

Extend the pipeline: after syncing staging, automatically refresh a summary mart.

```sql
-- Create a mart table
CREATE TABLE IF NOT EXISTS ECOMM_DB.MARTS.CUSTOMER_CITY_SUMMARY (
    city           VARCHAR(100),
    customer_count NUMBER,
    vip_count      NUMBER,
    updated_at     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Recreate the sync task as a root task (needs to be dropped and recreated without SCHEDULE removed)
-- Drop existing task first
ALTER TASK ECOMM_DB.STAGING.SYNC_CUSTOMERS_TASK SUSPEND;
DROP TASK ECOMM_DB.STAGING.SYNC_CUSTOMERS_TASK;

-- Root task: same MERGE as before
CREATE TASK ECOMM_DB.STAGING.SYNC_CUSTOMERS_TASK
  WAREHOUSE = COMPUTE_WH
  SCHEDULE  = '1 MINUTE'
  WHEN SYSTEM$STREAM_HAS_DATA('ECOMM_DB.RAW_DATA.CUSTOMERS_STREAM')
AS
MERGE INTO ECOMM_DB.STAGING.STG_CUSTOMERS AS target
USING (
  SELECT * FROM ECOMM_DB.RAW_DATA.CUSTOMERS_STREAM
  WHERE METADATA$ACTION = 'INSERT'
) AS src
ON target.customer_id = src.customer_id
WHEN MATCHED THEN
  UPDATE SET target.full_name = src.full_name, target.city = src.city,
             target.status = src.status, target.updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
  INSERT (customer_id, full_name, email, city, status, updated_at)
  VALUES (src.customer_id, src.full_name, src.email, src.city, src.status, CURRENT_TIMESTAMP());

-- Child task: refresh the mart after staging sync
CREATE TASK ECOMM_DB.MARTS.REFRESH_CITY_SUMMARY_TASK
  WAREHOUSE = COMPUTE_WH
  AFTER ECOMM_DB.STAGING.SYNC_CUSTOMERS_TASK
AS
INSERT INTO ECOMM_DB.MARTS.CUSTOMER_CITY_SUMMARY (city, customer_count, vip_count, updated_at)
SELECT
    city,
    COUNT(*)                                              AS customer_count,
    SUM(CASE WHEN status = 'VIP' THEN 1 ELSE 0 END)      AS vip_count,
    CURRENT_TIMESTAMP()
FROM ECOMM_DB.STAGING.STG_CUSTOMERS
GROUP BY city;

-- Resume: child first, root last
ALTER TASK ECOMM_DB.MARTS.REFRESH_CITY_SUMMARY_TASK RESUME;
ALTER TASK ECOMM_DB.STAGING.SYNC_CUSTOMERS_TASK RESUME;

-- Trigger the chain manually
INSERT INTO ECOMM_DB.RAW_DATA.CUSTOMERS_RAW
VALUES (11, 'Nina Reyes', 'nina@example.com', 'Austin', 'VIP');

EXECUTE TASK ECOMM_DB.STAGING.SYNC_CUSTOMERS_TASK;

-- After it completes, check both tables
SELECT * FROM ECOMM_DB.STAGING.STG_CUSTOMERS ORDER BY customer_id;
SELECT * FROM ECOMM_DB.MARTS.CUSTOMER_CITY_SUMMARY ORDER BY customer_count DESC;

-- Check both tasks ran in sequence
SELECT name, state, scheduled_time, completed_time
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
    SCHEDULED_TIME_RANGE_START => DATEADD('minutes', -5, CURRENT_TIMESTAMP())
))
ORDER BY scheduled_time DESC;

-- Suspend both when done
ALTER TASK ECOMM_DB.STAGING.SYNC_CUSTOMERS_TASK SUSPEND;
ALTER TASK ECOMM_DB.MARTS.REFRESH_CITY_SUMMARY_TASK SUSPEND;
```

**Discussion:** The mart refresh uses `INSERT INTO` every run — over time this adds duplicate city rows. What would you use instead to always have one row per city with the latest counts?
