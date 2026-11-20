# Day 5 — Interview Questions: Stages, COPY INTO, Snowpipe, and Zero-Copy Cloning

> 15 questions. Difficulty tags: (Warm-up) → (Conceptual) → (Scenario) → (Tricky)
> All scenarios use the Day 4 tables: ORDERS_RAW, STG_ORDERS, ORDERS_MART.

---

**Q1 (Warm-up)** — What is a Stage in Snowflake? Why do files need to go through a stage before they can be loaded into a table?

**Q2 (Warm-up)** — What is the difference between an internal stage and an external stage? Which one requires cloud credentials?

**Q3 (Conceptual)** — Snowflake internal stages have three sub-types: user, table, and named. What is the difference? Which should you use for a shared production pipeline and why?

**Q4 (Warm-up)** — What does `COPY INTO` do? What compute resource runs it and how is it billed?

**Q5 (Conceptual)** — You run `COPY INTO ORDERS_RAW` on a stage that already has two previously loaded files and one new file. What happens to each file? Why?

**Q6 (Tricky)** — A developer uses `FORCE = TRUE` in a `COPY INTO` command targeting `ORDERS_RAW`. What is the risk? What problem does this create for the Day 4 stream?

**Q7 (Scenario)** — Your CSV has 9 columns matching ORDERS_RAW exactly, but you want to skip the `updated_at` column and let it use its `DEFAULT CURRENT_TIMESTAMP()`. How do you write the COPY INTO?

**Q8 (Warm-up)** — What is Snowpipe? How is it different from a 1-minute scheduled Task that runs COPY INTO?

**Q9 (Conceptual)** — Snowpipe is "serverless." What does that mean for compute and billing? When would a Task + COPY INTO actually be better than Snowpipe?

**Q10 (Tricky)** — You call `ALTER PIPE ORDERS_RAW_PIPE REFRESH` twice in a row. The same files are in the stage. Does Snowpipe load the files twice? Why or why not?

**Q11 (Scenario)** — Your Snowpipe has been PAUSED for 2 hours. During that time, 15 new CSV files arrived in the stage. You resume the pipe. How do you make sure all 15 files get loaded?

**Q12 (Warm-up)** — What is zero-copy cloning? What does "zero-copy" mean technically, and when does storage actually get consumed?

**Q13 (Conceptual)** — You run `CREATE DATABASE ECOMM_DB_DEV CLONE ECOMM_DB`. A developer then truncates `ORDERS_RAW` in `ECOMM_DB_DEV`. What happens to `ECOMM_DB.RAW_DATA.ORDERS_RAW` in the original database?

**Q14 (Tricky)** — You clone `ORDERS_RAW`. The original table has an active stream `ORDERS_RAW_STREAM`. What happens to the stream after cloning? What about the Day 4 tasks?

**Q15 (Scenario)** — At 3 AM, a bad ETL job ran `DELETE FROM ECOMM_DB.RAW_DATA.ORDERS_RAW WHERE order_date < '2024-01-12'` and wiped 6 rows. The table has a 1-day Time Travel window. Write the exact SQL to identify the bad query and restore the deleted rows without affecting the stream or tasks.
