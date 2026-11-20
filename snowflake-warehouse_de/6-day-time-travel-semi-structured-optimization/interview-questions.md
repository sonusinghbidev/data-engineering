# Day 6 — Interview Questions: Time Travel, Semi-Structured Data, Query Optimization

> 15 questions. Difficulty: (Warm-up) → (Conceptual) → (Scenario) → (Tricky)
> All scenarios use the Day 4 tables: ORDERS_RAW, STG_ORDERS, ORDERS_MART.

---

**Q1 (Warm-up)** — What is Snowflake Time Travel? What is the default retention window and what determines the maximum?

**Q2 (Warm-up)** — What are the three ways to specify a point in time in a Time Travel query? Give an example of each.

**Q3 (Scenario)** — A developer ran `UPDATE ORDERS_RAW SET status = 'CANCELLED' WHERE order_id < 1010` at 2 AM. No one noticed until 9 AM. The table has a 1-day Time Travel window. Write the SQL to restore the original status values for those rows.

**Q4 (Tricky)** — What is the difference between Time Travel and Fail-Safe? Can you query data in Fail-Safe yourself?

**Q5 (Conceptual)** — Setting `DATA_RETENTION_TIME_IN_DAYS = 0` on a table disables Time Travel. What is the trade-off — why would you ever want to do this?

**Q6 (Warm-up)** — What is a VARIANT column in Snowflake? What types of data can it store?

**Q7 (Conceptual)** — You have a JSON field `raw_order:items` which is an array. Write the SQL to get the product name and price of the **second item** in each order using colon syntax.

**Q8 (Conceptual)** — What does `LATERAL FLATTEN` do? Why do you need it when dealing with JSON arrays?

**Q9 (Scenario)** — Your JSON payload has this structure: `{"order_id": 1, "customer": {"name": "Alice", "address": {"city": "NY", "zip": "10001"}}}`. Write the SQL to extract the city using colon syntax.

**Q10 (Tricky)** — You query `ORDERS_JSON` and get `NULL` for `raw_order:customer.phone`. Does that mean the phone field definitely does not exist in the JSON? What else could it mean?

**Q11 (Warm-up)** — What is the Snowflake result cache? When is it used and when is it invalidated?

**Q12 (Conceptual)** — What is a clustering key? What problem does it solve and what is the cost of enabling it?

**Q13 (Scenario)** — Your team runs this query 50 times per day: `SELECT * FROM ORDERS_RAW WHERE order_date BETWEEN '2024-01-01' AND '2024-01-31'`. The table has 500 million rows spread across 3 years of data. What would you do to optimize this query and why?

**Q14 (Tricky)** — In Query Profile you see `TableScan: Partitions scanned 500 out of 500`. What does this tell you and what are two ways to fix it?

**Q15 (Scenario)** — A query that JOINs `ORDERS_RAW` and `STG_ORDERS` takes 45 seconds on an XS warehouse. Your manager asks what the fastest fix is. What do you say, and what is the trade-off?
