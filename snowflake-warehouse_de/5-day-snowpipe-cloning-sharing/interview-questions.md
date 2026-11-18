# Day 5 — Interview Questions: Snowpipe, ADLS Auto-Ingest, Cloning & Sharing

> 15 questions covering all three concepts. Difficulty tags: (Warm-up) → (Conceptual) → (Scenario) → (Tricky) → (System design)

---

**Q1 (Warm-up)** — What is Snowpipe and how does it differ from a Task that runs `COPY INTO` on a 1-minute schedule?

**Q2 (Warm-up)** — What does `AUTO_INGEST = TRUE` on a Pipe object mean? What infrastructure component enables it on Azure?

**Q3 (Conceptual)** — Snowpipe is described as "serverless." What exactly does that mean in this context — what compute does it use and how is it billed?

**Q4 (Conceptual)** — A file is uploaded to the stage twice — once at 10:00 AM and again at 10:05 AM with the same filename but different content. Does Snowpipe load it twice? Why or why not?

**Q5 (Tricky)** — You set up auto-ingest with Azure Event Grid. Files land in ADLS but `SYSTEM$PIPE_STATUS` shows `executionState = STALE`. What does STALE mean and what do you do?

**Q6 (Scenario)** — Your Snowpipe loaded 10,000 files successfully over the past month. This morning, 50 files arrived but were not loaded — the pipe shows `PAUSED`. What are the two most likely causes and how do you recover?

**Q7 (Scenario)** — You need to load JSON files (not CSV) from an ADLS container into a VARIANT column using Snowpipe. Walk through the key differences in your Pipe definition compared to loading CSV.

**Q8 (Tricky)** — What is the difference between the `STORAGE INTEGRATION` and the `NOTIFICATION INTEGRATION` required for ADLS auto-ingest? Why are two separate integrations needed?

**Q9 (Warm-up)** — What is zero-copy cloning? What does "zero-copy" mean technically — is there no data at all when you first clone?

**Q10 (Conceptual)** — You clone a 10 TB production database to create a dev environment. A developer then runs `DELETE FROM orders WHERE order_date < '2023-01-01'` in the clone. How much additional storage is consumed, and where does it come from?

**Q11 (Tricky)** — Can you clone a table that has an active Stream on it? What happens to the stream in the clone?

**Q12 (Scenario)** — A developer accidentally deleted 2 million rows from the STAGING table at 3 AM. You need to recover the data. The table has a 1-day Time Travel window. Write the exact SQL to restore the rows using cloning.

**Q13 (Conceptual)** — What is Snowflake Data Sharing? How does the consumer access shared data — do they need to copy it into their account first?

**Q14 (Tricky)** — You share a table directly with a partner. The table contains customer PII (email, phone). The partner complains they can see the PII. What is the correct Snowflake pattern to share aggregated data while hiding raw PII? Write the SQL.

**Q15 (System design)** — Design a real-time order analytics system: orders arrive as JSON files in an ADLS container every few seconds from multiple microservices. The BI team in a partner company needs to query a live daily summary. No data should be shared raw. Walk through the full architecture — storage, ingestion, pipeline, and sharing.
