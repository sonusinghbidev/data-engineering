# Day 6 — Interview Solutions: Time Travel, Semi-Structured Data, Query Optimization

> Complete answers. Read after attempting on your own.

---

**Q1 — What is Time Travel? Default and maximum retention window?**

Time Travel is Snowflake's ability to query, restore, or clone a table as it existed at any point within a retention window — without taking manual snapshots or backups. Snowflake automatically keeps historical versions of every micro-partition as data changes.

- **Default retention:** 1 day (24 hours) — applies to all editions
- **Maximum retention:** 90 days — available on Enterprise edition and above
- Setting `DATA_RETENTION_TIME_IN_DAYS = 0` disables Time Travel for a specific table

---

**Q2 — Three ways to specify a Time Travel point. Example each.**

```sql
-- 1. OFFSET — seconds back from now (negative number)
SELECT * FROM ORDERS_RAW AT (OFFSET => -3600);
-- Queries the table as it was exactly 1 hour ago

-- 2. TIMESTAMP — exact datetime
SELECT * FROM ORDERS_RAW AT (TIMESTAMP => '2024-01-10 06:00:00'::TIMESTAMP_NTZ);
-- Queries as it was at 6 AM on Jan 10

-- 3. STATEMENT — just before or after a specific query (use query ID from history)
SELECT * FROM ORDERS_RAW BEFORE (STATEMENT => '01ab2c34-...');
-- Queries as it was just before that query executed
-- AT (STATEMENT => ...) gives the state just AFTER the query completed
```

`AT` means "as of that moment or after" — `BEFORE` means "just before that statement ran."

---

**Q3 — Restore status values overwritten at 2 AM. SQL to fix it.**

```sql
-- Step 1: Find the bad UPDATE query ID
SELECT query_id, query_text, start_time
FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(
    DATE_RANGE_START => DATEADD('hours', -12, CURRENT_TIMESTAMP())
))
WHERE query_text ILIKE '%UPDATE%ORDERS_RAW%status%CANCELLED%'
ORDER BY start_time DESC
LIMIT 1;
-- Copy the query_id

-- Step 2: See what values looked like before the bad update
SELECT order_id, status
FROM ECOMM_DB.RAW_DATA.ORDERS_RAW BEFORE (STATEMENT => '<query_id>')
WHERE order_id < 1010;

-- Step 3: Restore just the affected rows
-- Use a MERGE to update only the rows that were changed
MERGE INTO ECOMM_DB.RAW_DATA.ORDERS_RAW AS target
USING (
    SELECT order_id, status
    FROM ECOMM_DB.RAW_DATA.ORDERS_RAW BEFORE (STATEMENT => '<query_id>')
    WHERE order_id < 1010
) AS src
ON target.order_id = src.order_id
WHEN MATCHED THEN
    UPDATE SET target.status = src.status,
               target.updated_at = CURRENT_TIMESTAMP();

-- Verify
SELECT order_id, status FROM ECOMM_DB.RAW_DATA.ORDERS_RAW
WHERE order_id < 1010 ORDER BY order_id;
```

---

**Q4 — Time Travel vs Fail-Safe. Can you query Fail-Safe yourself?**

| | Time Travel | Fail-Safe |
|---|---|---|
| Duration | 0–90 days (you set it) | 7 days after TT window expires |
| Access | Full SQL access — `AT`, `BEFORE`, `UNDROP` | No — only Snowflake Support |
| Use case | Self-service recovery, historical queries, cloning | Last-resort disaster recovery |
| Cost | Storage for historical micro-partitions | Included in Snowflake storage pricing |

**You cannot query Fail-Safe data yourself.** Fail-Safe is an emergency backstop — if your Time Travel window expired and you still need data, you open a Snowflake support ticket and they may be able to recover it. It is not a SQL feature you can access directly.

The practical takeaway: set your retention window (Time Travel) generously for important tables. Rely on Fail-Safe only as a last resort, not as a planned recovery strategy.

---

**Q5 — Why set `DATA_RETENTION_TIME_IN_DAYS = 0`? The trade-off.**

Setting retention to 0 disables Time Travel for that table — you can no longer query historical states or use `UNDROP`.

**Why you'd want it:**
- **Storage cost** — Time Travel keeps copies of all changed micro-partitions. On large tables with heavy write activity (millions of updates/deletes per day), the historical data can grow to 2–5x the table's current size. Setting retention to 0 stops this.
- **Transient and temporary tables** — these tables are designed for intermediate pipeline steps. They are truncated and reloaded frequently, have no long-term value, and do not need recovery. `CREATE TRANSIENT TABLE` automatically sets retention to 0 or 1.

**The trade-off:** You permanently give up the ability to recover from accidental changes on that table. Use `= 0` only on tables where data loss is acceptable (staging tables that are fully rebuilt from source, temp intermediate tables).

---

**Q6 — What is VARIANT? What can it store?**

`VARIANT` is a Snowflake column type that can store **any semi-structured data** as a single value. It is schema-on-read — you define no columns up front; the structure is embedded in the data itself.

It can store:
- **JSON** — most common
- **Avro**
- **Parquet**
- **ORC**
- **XML** (via XMLGET)
- Scalar values: strings, numbers, booleans, nulls, arrays, objects — all in one column

The column stores the entire document. You query into it using colon (`:`) syntax or `GET`/`GET_PATH` functions, casting with `::TYPE` to extract typed values.

---

**Q7 — Get product name and price of the second item using colon syntax.**

Arrays in VARIANT are zero-indexed. The second item is index `[1]`:

```sql
SELECT
    raw_order:order_id::NUMBER           AS order_id,
    raw_order:items[1].product::VARCHAR  AS second_product,
    raw_order:items[1].price::NUMBER     AS second_price
FROM ECOMM_DB.RAW_DATA.ORDERS_JSON
WHERE raw_order:items[1] IS NOT NULL;  -- only orders with at least 2 items
```

If an order has only one item, `raw_order:items[1]` returns NULL — the `IS NOT NULL` filter excludes those rows.

---

**Q8 — What does LATERAL FLATTEN do? Why needed for arrays?**

A VARIANT array lives inside a single row — you cannot filter, aggregate, or join on its elements without first exploding it into separate rows. `LATERAL FLATTEN` does that explosion:

```sql
SELECT
    o.raw_order:order_id::NUMBER       AS order_id,
    item.value:product::VARCHAR        AS product,
    item.value:price::NUMBER           AS price
FROM ECOMM_DB.RAW_DATA.ORDERS_JSON o,
     LATERAL FLATTEN(input => o.raw_order:items) item;
```

`LATERAL FLATTEN` takes the array `raw_order:items`, outputs one row per element, and makes the element accessible as `item.value`. `LATERAL` means it can reference columns from the same FROM clause (the `o` alias) — without it, you cannot reference `o.raw_order` inside the FLATTEN.

**Why you need it:** Without FLATTEN, `raw_order:items[0]`, `[1]`, `[2]` etc. must be listed manually — you do not know how many items each order has. FLATTEN handles variable-length arrays automatically.

---

**Q9 — Extract city from nested JSON: `{"customer": {"address": {"city": "NY"}}}`.**

Navigate through nested objects with dots inside the colon syntax:

```sql
SELECT
    raw_order:order_id::NUMBER                        AS order_id,
    raw_order:customer.name::VARCHAR                  AS customer_name,
    raw_order:customer.address.city::VARCHAR          AS city,
    raw_order:customer.address.zip::VARCHAR           AS zip
FROM ECOMM_DB.RAW_DATA.ORDERS_JSON;
```

Each `.` goes one level deeper into the nested JSON object. Alternatively using `GET_PATH`:

```sql
SELECT GET_PATH(raw_order, 'customer.address.city')::VARCHAR AS city
FROM ECOMM_DB.RAW_DATA.ORDERS_JSON;
```

---

**Q10 — `raw_order:customer.phone` returns NULL. Does it mean the field doesn't exist?**

Not necessarily. There are two possible reasons for NULL:

1. **The key does not exist** in the JSON document — Snowflake returns NULL for any path that is not present in the VARIANT value.
2. **The key exists but its value is JSON null** — `{"customer": {"phone": null}}` — the key is present but the value is null.

You cannot distinguish between them with `:` syntax alone. To check whether a key actually exists:

```sql
-- Check if the key path exists (non-null value)
SELECT
    raw_order:customer.phone IS NOT NULL  AS phone_exists_with_value,
    -- This is TRUE only if the key exists AND has a non-null value

    -- To check key existence regardless of value, use CHECK_JSON or TYPEOF
    TYPEOF(raw_order:customer.phone)      AS value_type
    -- 'NULL_VALUE' means key exists but value is null
    -- NULL (SQL null) means the key does not exist
FROM ECOMM_DB.RAW_DATA.ORDERS_JSON;
```

---

**Q11 — What is the result cache? When used and when invalidated?**

Snowflake caches the **exact result set** of every query for 24 hours. If you run the identical query again — same SQL text, same underlying table data, same session parameters — Snowflake returns the cached result instantly with **zero warehouse compute**.

**When it is used:**
- SQL text is byte-for-byte identical (even a space difference bypasses cache)
- The underlying tables have not changed since the last run
- The same user role and session parameters are in effect

**When it is invalidated:**
- Any DML on the underlying table (INSERT, UPDATE, DELETE, MERGE)
- 24 hours pass
- SQL changes at all (even changing `SELECT *` to `SELECT a, b`)
- Session-level parameters that affect query results change

**Practical use:** Result cache is automatic — you do not configure it. BI dashboard queries that run on unchanged data hit the cache on every refresh after the first run. This makes dashboards feel instant and costs nothing beyond the first execution.

---

**Q12 — What is a clustering key? Problem it solves and cost.**

Snowflake stores table data in micro-partitions (small compressed files). By default, micro-partitions are written in insertion order — data for all dates, regions, etc. is mixed across all partitions.

**Problem:** If you query `WHERE order_date = '2024-01-10'` on a table with 3 years of data, Snowflake must scan every micro-partition to find Jan 10 rows — even though they may represent 0.1% of the data. This is called a full table scan.

**Clustering key solution:** `ALTER TABLE t CLUSTER BY (order_date)` tells Snowflake to reorganize data so rows with the same `order_date` values land in the same micro-partitions. The query now scans only the partitions containing Jan 10 data — this is partition pruning.

```sql
ALTER TABLE ECOMM_DB.RAW_DATA.ORDERS_RAW CLUSTER BY (order_date);
```

**Cost:** Snowflake runs **Automatic Clustering** in the background — a serverless process that continuously re-clusters new data as it arrives. You pay per second of this background compute. For small or infrequently queried tables this cost exceeds the benefit. Use clustering only on large (100GB+) tables with consistent, repeated filter patterns.

---

**Q13 — 500M row table, `WHERE order_date BETWEEN` runs 50 times/day. How to optimize?**

Two-step approach:

**Step 1 — Add a clustering key on `order_date`** (the filter column):
```sql
ALTER TABLE ECOMM_DB.RAW_DATA.ORDERS_RAW CLUSTER BY (order_date);
```
This ensures Snowflake reads only the micro-partitions for Jan 2024 instead of scanning all 3 years. With 3 years of daily data, you go from scanning 100% of partitions to roughly 3% — a ~33x reduction in data scanned.

**Step 2 — Remove SELECT * — select only the columns you need:**
```sql
-- Instead of SELECT *
SELECT order_id, customer_name, status, total_amount
FROM ORDERS_RAW
WHERE order_date BETWEEN '2024-01-01' AND '2024-01-31';
```
Snowflake is columnar — scanning fewer columns reduces I/O significantly.

**Bonus — result cache:** Since this same query runs 50 times per day and the data likely does not change between runs, the result cache will serve most of these 50 queries for free after the first execution.

---

**Q14 — Query Profile shows `Partitions scanned 500 out of 500`. Two fixes.**

This means Snowflake scanned **every single micro-partition** — no partition pruning happened. This is a full table scan.

**Cause:** The query's WHERE clause filter column is not aligned with how the data is physically organized — rows matching the filter are spread across all partitions.

**Fix 1 — Add a clustering key on the filter column:**
```sql
ALTER TABLE ORDERS_RAW CLUSTER BY (order_date);
-- After re-clustering, the same query will scan only the relevant partitions
```

**Fix 2 — Rewrite the query to filter on a column that IS already clustered:**
If the table is clustered by `order_date` but your query filters on `customer_id`, you still get a full scan. Either add `order_date` to your filter or change the clustering key:
```sql
-- If clustered by order_date, add order_date to the filter
SELECT * FROM ORDERS_RAW
WHERE customer_id = 42 AND order_date >= '2024-01-01';
-- Now Snowflake prunes by order_date, reducing the scan footprint
```

---

**Q15 — 45-second JOIN query on XS warehouse. Fastest fix and trade-off.**

**Fastest fix: scale up the warehouse.**

```sql
ALTER WAREHOUSE COMPUTE_WH SET WAREHOUSE_SIZE = 'LARGE';
-- Run the query
-- Scale back down
ALTER WAREHOUSE COMPUTE_WH SET WAREHOUSE_SIZE = 'X-SMALL';
```

A LARGE warehouse has 8x the compute nodes of XS. Each node processes a slice of the data in parallel. A 45-second query on XS may drop to 5–10 seconds on LARGE.

**Trade-off:** A LARGE warehouse costs 8x the credits per second. If you use it for one 10-second query, the cost is 8x higher than a 45-second query on XS — it may actually cost more. Scale up only when:
- The query runs frequently (hourly batch, real-time dashboard)
- The time saving matters (SLA, user experience)
- You scale back down immediately after

**Better long-term fix:** Use Query Profile to find the actual bottleneck. If the scan is reading too many partitions → add a clustering key. If it is an inefficient JOIN → rewrite the query. Scaling up the warehouse masks the problem without fixing it.
