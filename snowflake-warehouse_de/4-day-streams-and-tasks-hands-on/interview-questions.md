# Day 4 — Interview Questions: RAW → STAGING → MART Pipeline

> 15 questions focused on real pipeline design — the kind asked in data engineer interviews.
> Difficulty tags: (Warm-up) → (Conceptual) → (Scenario) → (Tricky) → (System design)

---

**Q1 (Warm-up)** — In a RAW → STAGING → MART pipeline, what is the purpose of each layer? Why keep all three instead of loading directly into the mart?

**Q2 (Warm-up)** — What is a soft delete? Why do you soft delete in STAGING instead of hard deleting when a row is removed from RAW?

**Q3 (Conceptual)** — Your MERGE from the stream uses `WHERE METADATA$ACTION = 'INSERT'` to handle both new inserts and updates. Explain why this works for updates — specifically, which stream row carries the new values after an UPDATE?

**Q4 (Conceptual)** — The RAW → STAGING MERGE has three branches: `WHEN MATCHED AND ACTION = 'INSERT'`, `WHEN MATCHED AND ACTION = 'DELETE' AND ISUPDATE = FALSE`, and `WHEN NOT MATCHED AND ACTION = 'INSERT'`. What scenario does each branch handle?

**Q5 (Tricky)** — A row is updated in RAW. The stream shows two rows for that order — a DELETE and an INSERT, both with `METADATA$ISUPDATE = TRUE`. Your MERGE filters to `METADATA$ACTION = 'INSERT'`. What happens to the DELETE row? Does it cause any problem?

**Q6 (Scenario)** — An order is inserted into RAW on January 10 with status `PENDING`. On January 12 the status changes to `DELIVERED`. What does the mart row for January 10 show before and after the status update? Does the mart row for January 12 get affected?

**Q7 (Tricky)** — The Task 2 (STAGING → MART) has no `WHEN SYSTEM$STREAM_HAS_DATA(...)` condition, even though Task 1 does. Why is it safe to run the mart MERGE every time Task 1 runs, even if Task 1 processed no new data because the stream was empty?

**Q8 (Scenario)** — It is 2 AM. Task 1 fires, processes 500 changes from RAW into STAGING successfully. Then Task 2 fails mid-way through the mart MERGE because the warehouse ran out of credits. What state is the pipeline in? Is data lost? How do you recover?

**Q9 (Conceptual)** — Your ORDERS_MART groups by `order_date` using a MERGE. What happens to the mart row for January 10 if an existing order on that date is soft-deleted? Walk through the exact SQL path.

**Q10 (Tricky)** — A developer accidentally runs the MERGE SQL for RAW → STAGING twice manually — back to back. The stream was consumed on the first run. What does the second run process? Can it cause duplicates?

**Q11 (Scenario)** — You need to replay all historical data through the pipeline — wipe STAGING and MART and rebuild from RAW from scratch. The stream is currently empty. How do you do it without touching the RAW table?

**Q12 (Deep dive)** — The pipeline uses `EXECUTE TASK` during testing. In production, the task runs on a 1-minute schedule with `WHEN SYSTEM$STREAM_HAS_DATA(...)`. Describe exactly what happens during a 1-minute window where no new data arrives in RAW — step by step.

**Q13 (Scenario)** — You add a new column `region VARCHAR(50)` to ORDERS_RAW. What else do you need to change to make the new column flow through to STAGING and the MART?

**Q14 (System design)** — You have three source tables: `CUSTOMERS_RAW`, `PRODUCTS_RAW`, and `ORDERS_RAW`. Each needs its own stream and staging table. The mart is a joined view across all three. Design the full Task DAG — how many tasks, what order, what schedule, and what WHEN conditions?

**Q15 (System design)** — Your pipeline currently runs on a 1-minute schedule. The business now says the mart must be refreshed within 5 seconds of any change to RAW. What Snowflake feature would you use instead of a Task with a fixed schedule, and why?
