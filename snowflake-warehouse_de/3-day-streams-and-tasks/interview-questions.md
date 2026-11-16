# Day 3 — Interview Questions: Streams and Tasks

> 18 questions across both concepts. Attempt your own answer first, then check the solutions file.
> Difficulty tags: (Warm-up) → (Conceptual) → (Scenario) → (Tricky) → (Deep dive) → (System design)

---

## Concept 1: Streams — Change Data Capture

**Q1 (Warm-up)** — What is a Snowflake Stream? What problem does it solve compared to doing a full table reload every pipeline run?

**Q2 (Warm-up)** — What are the three metadata columns every Stream adds to its rows? What are the possible values for `METADATA$ACTION`?

**Q3 (Conceptual)** — How does a Snowflake Stream represent an UPDATE? How many rows appear in the stream for a single UPDATE, and what are their `METADATA$ACTION` and `METADATA$ISUPDATE` values?

**Q4 (Conceptual)** — What is the difference between a standard stream and an `APPEND ONLY` stream? Give a real-world example of when you would use each.

**Q5 (Tricky)** — You query a stream with `SELECT *` and see 200 change records. Does the stream offset advance? What action actually clears the stream?

**Q6 (Scenario)** — You have a `CUSTOMERS_RAW` table that receives inserts and updates throughout the day. Write the MERGE statement that uses a stream on this table to keep `STG_CUSTOMERS` in sync — handling both new inserts and updates.

**Q7 (Tricky)** — A stream on a table shows an UPDATE as two rows — a DELETE and an INSERT. In your MERGE, you filter to `METADATA$ACTION = 'INSERT'` only. Does this correctly handle updates? Why or why not?

**Q8 (Deep dive)** — What does it mean for a stream to become "stale"? What causes it, and what do you have to do to recover?

**Q9 (Scenario)** — You have an `ORDERS_RAW` table where rows are only ever inserted — never updated or deleted. What type of stream should you create and why?

---

## Concept 2: Tasks — Scheduling and Automation

**Q10 (Warm-up)** — What is a Snowflake Task? What two scheduling approaches does it support?

**Q11 (Warm-up)** — Tasks are created in SUSPENDED state by default. What command do you run to activate a task? What command pauses it without dropping it?

**Q12 (Conceptual)** — What does `WHEN SYSTEM$STREAM_HAS_DATA('schema.stream_name')` do in a Task definition? Why does this matter for cost?

**Q13 (Scenario)** — Write a Task that checks for new customer changes every 5 minutes and runs a MERGE to sync a staging table. Include the WHEN condition so the warehouse only starts when there is actual data.

**Q14 (Tricky)** — What is `EXECUTE TASK`? How is it different from waiting for the scheduled run? Give two situations where you would use it in production.

**Q15 (Conceptual)** — Explain Task chaining. What is the difference between a root task and a child task? Can a child task have its own schedule?

**Q16 (Scenario)** — You have three tasks: `LOAD_TASK` → `TRANSFORM_TASK` → `MART_TASK`. In what order do you resume them and why?

**Q17 (Deep dive)** — Your Task fails because the warehouse was auto-suspended. The stream has been accumulating changes for 18 hours. Walk through the steps you take to recover without losing data.

**Q18 (System design)** — Design a fully Snowflake-native CDC pipeline for a retail company. The `SALES_RAW` table receives new and updated rows throughout the day. You need to: keep `STG_SALES` in sync using a stream and MERGE, then refresh `SALES_MART` after each sync. Use chained tasks with a schedule and WHEN condition. Describe the full setup.
