-- =====================================================================
-- Healthcare Claims Analytics — SQL
-- SQLite-compatible. Models the synthetic CSVs as a star schema, then
-- runs the core cost / utilization / data-quality analyses.
-- =====================================================================

-- ---------------------------------------------------------------------
-- STAR SCHEMA DDL
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dim_member (
    member_id        TEXT PRIMARY KEY,
    age              INTEGER,
    gender           TEXT,
    state            TEXT,
    plan_type        TEXT,
    enrollment_start DATE,
    enrollment_end   DATE,
    member_months    INTEGER,
    high_utilizer    INTEGER          -- 1/0 flag
);

CREATE TABLE IF NOT EXISTS dim_provider (
    provider_id   TEXT PRIMARY KEY,
    provider_name TEXT,
    provider_type TEXT,               -- Hospital | Clinic | Pharmacy | Lab | Specialty Practice
    specialty     TEXT,
    city          TEXT,
    state         TEXT
);

CREATE TABLE IF NOT EXISTS dim_date (
    date_key   DATE PRIMARY KEY,      -- calendar date
    year       INTEGER,
    month      INTEGER,               -- 1-12
    month_key  TEXT,                  -- 'YYYY-MM'
    quarter    TEXT                   -- 'YYYY-Qn'
);

CREATE TABLE IF NOT EXISTS fact_claims (
    claim_id        TEXT PRIMARY KEY,
    member_id       TEXT NOT NULL REFERENCES dim_member (member_id),
    provider_id     TEXT NOT NULL REFERENCES dim_provider (provider_id),
    service_date    DATE NOT NULL,
    claim_type      TEXT NOT NULL,    -- inpatient | outpatient | ER | pharmacy
    diagnosis_group TEXT,
    billed_amount   REAL,
    paid_amount     REAL,
    claim_status    TEXT,             -- paid | denied | adjusted
    is_adjustment   INTEGER DEFAULT 0 -- 1 when paid_amount < 0 (claim adjustment)
);

CREATE INDEX IF NOT EXISTS ix_fact_service_date ON fact_claims (service_date);
CREATE INDEX IF NOT EXISTS ix_fact_member      ON fact_claims (member_id);
CREATE INDEX IF NOT EXISTS ix_fact_provider    ON fact_claims (provider_id);
CREATE INDEX IF NOT EXISTS ix_fact_claim_type  ON fact_claims (claim_type);

-- ---------------------------------------------------------------------
-- 1. Monthly PMPM trend (net paid per member-month by service month)
-- ---------------------------------------------------------------------
WITH monthly AS (
    SELECT substr(service_date, 1, 7) AS month_key,
           SUM(paid_amount)           AS total_paid
    FROM fact_claims
    GROUP BY 1
),
mm AS (
    SELECT SUM(member_months) / 24.0 AS avg_member_months_per_month
    FROM dim_member
)
SELECT m.month_key,
       ROUND(m.total_paid, 2)                                   AS total_paid,
       ROUND(m.total_paid / mm.avg_member_months_per_month, 2)  AS pmpm
FROM monthly m CROSS JOIN mm
ORDER BY m.month_key;

-- ---------------------------------------------------------------------
-- 2. Top 10 providers by paid amount (with share of total spend)
-- ---------------------------------------------------------------------
WITH provider_spend AS (
    SELECT p.provider_id,
           p.provider_name,
           p.provider_type,
           SUM(f.paid_amount) AS total_paid,
           COUNT(*)           AS claim_count
    FROM fact_claims f
    JOIN dim_provider p ON p.provider_id = f.provider_id
    WHERE f.is_adjustment = 0
    GROUP BY 1, 2, 3
),
total AS (
    SELECT SUM(paid_amount) AS grand_total
    FROM fact_claims
    WHERE is_adjustment = 0
)
SELECT provider_id,
       provider_name,
       provider_type,
       ROUND(total_paid, 2)                        AS total_paid,
       claim_count,
       ROUND(total_paid / (SELECT grand_total FROM total) * 100, 2)
                                                   AS pct_of_spend
FROM provider_spend
ORDER BY total_paid DESC
LIMIT 10;

-- ---------------------------------------------------------------------
-- 3. ER visits per 1,000 member-years
-- ---------------------------------------------------------------------
SELECT ROUND(
         COUNT(*) * 1000.0
         / ((SELECT SUM(member_months) FROM dim_member) / 12.0),
         1
       ) AS er_visits_per_1000_member_years
FROM fact_claims
WHERE claim_type = 'ER';

-- ---------------------------------------------------------------------
-- 4. Average paid by diagnosis group (cost-driver view)
-- ---------------------------------------------------------------------
SELECT diagnosis_group,
       COUNT(*)                        AS claim_count,
       ROUND(SUM(paid_amount), 2)       AS total_paid,
       ROUND(AVG(paid_amount), 2)       AS avg_paid,
       ROUND(SUM(paid_amount) * 100.0
             / SUM(SUM(paid_amount)) OVER (), 2) AS pct_of_spend
FROM fact_claims
WHERE is_adjustment = 0
GROUP BY diagnosis_group
ORDER BY total_paid DESC;

-- ---------------------------------------------------------------------
-- 5. Spend skew: inpatient share of claims vs. share of spend
-- ---------------------------------------------------------------------
SELECT claim_type,
       COUNT(*) AS claim_count,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1)      AS pct_of_claims,
       ROUND(SUM(paid_amount), 2)                             AS total_paid,
       ROUND(SUM(paid_amount) * 100.0
             / SUM(SUM(paid_amount)) OVER (), 1)               AS pct_of_spend
FROM fact_claims
WHERE is_adjustment = 0
GROUP BY claim_type
ORDER BY total_paid DESC;

-- ---------------------------------------------------------------------
-- 6. DATA-QUALITY CHECKS
-- ---------------------------------------------------------------------

-- 6a. Duplicate claim_id rows
SELECT claim_id, COUNT(*) AS occurrences
FROM fact_claims
GROUP BY claim_id
HAVING COUNT(*) > 1;

-- 6b. Negative paid amounts (expected only on flagged adjustments)
SELECT COUNT(*) AS negative_paid_rows,
       SUM(CASE WHEN is_adjustment = 0 THEN 1 ELSE 0 END) AS unflagged_negatives
FROM fact_claims
WHERE paid_amount < 0;

-- 6c. Orphan provider keys (claims with no provider-master match)
SELECT COUNT(*) AS orphan_provider_rows
FROM fact_claims f
LEFT JOIN dim_provider p ON p.provider_id = f.provider_id
WHERE p.provider_id IS NULL;

-- 6d. Orphan member keys
SELECT COUNT(*) AS orphan_member_rows
FROM fact_claims f
LEFT JOIN dim_member m ON m.member_id = f.member_id
WHERE m.member_id IS NULL;

-- 6e. Paid amounts that look implausible vs. billed (paid > 2x billed)
SELECT COUNT(*) AS paid_gt_2x_billed
FROM fact_claims
WHERE paid_amount > 2 * billed_amount;

-- 6f. Service dates outside the 2023-2024 analysis window
SELECT COUNT(*) AS out_of_window_dates
FROM fact_claims
WHERE service_date < '2023-01-01' OR service_date > '2024-12-31';
