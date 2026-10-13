# Data

> **All files in this folder are fully SYNTHETIC.** They were generated with
> `src/generate_data.py` (seeded, `random_state=42`) and contain **no real
> patient information**. No real payer, provider, or member is represented.

| File | Rows | Description |
|---|---|---|
| `members.csv` | ~4,000 | One row per member: `member_id`, `age`, `gender`, `state`, `plan_type`, `enrollment_start`, `enrollment_end`, `member_months`, `high_utilizer` |
| `providers.csv` | ~120 | Provider master: `provider_id`, `provider_name`, `provider_type` (Hospital / Clinic / Pharmacy / Lab / Specialty Practice), `specialty`, `city`, `state` |
| `claims.csv` | ~15,000 | One row per claim: `claim_id`, `member_id`, `provider_id`, `service_date` (2023-2024), `claim_type` (inpatient / outpatient / ER / pharmacy), `diagnosis_group`, `billed_amount`, `paid_amount`, `claim_status` (paid / denied / adjusted) |

## Design notes

- **Realistic skew:** paid amounts are lognormal per claim type, and ~1–2% of
  claims are catastrophic (5–15× typical) — a small share of members drives a
  large share of spend, as in real claims data.
- **Denied claims** carry `paid_amount = 0` and still count toward utilization.
- **Intentional data-quality issues** (a small, documented set) exercise the
  cleaning pipeline in `src/data_cleaning.py`:
  - 10 exact duplicate `claim_id` rows,
  - 8 adjustment rows with **negative** `paid_amount`,
  - 5 claims with an orphan `provider_id` (`P999`, absent from the provider master).

## Regenerate

```bash
python src/generate_data.py
```

Total CSV size is under 2 MB.
