# Dashboard — KPI definitions

The dashboard visuals in `../images/` (and the narrative in
`../notebooks/analysis.ipynb`) are built around the four KPIs below. Each KPI
is defined exactly as computed in `src/analysis.py`.

## KPIs

| KPI | Definition | Formula |
|---|---|---|
| **Total paid (net)** | Net medical spend over the period | `SUM(paid_amount)` on cleaned claims, adjustments included |
| **PMPM** | Per-member-per-month cost | `SUM(paid_amount) / SUM(member_months)` — the standard health-plan unit cost |
| **ER visits / 1,000** | Emergency utilization rate | `COUNT(ER claims) / (member_months / 12) * 1000` |
| **High-cost claimant share** | Spend concentration | Share of total paid driven by member-years with annual paid ≥ **$50,000** |
| **Top-10 provider concentration** | Network spend concentration | Share of total paid going to the 10 highest-paid providers |

## Supporting views

- **Monthly paid trend** — net paid per service month with a 3-month rolling
  average, to separate trend from seasonality/noise.
- **Cost by diagnosis group** — total paid and share of spend per diagnosis
  group (the cost-driver view).
- **Provider concentration** — top-10 providers by paid amount with each
  provider's share of total spend.

## Notes

- KPIs are computed on **cleaned** data: duplicate claim rows removed, orphan
  provider rows quarantined, and adjustment rows (negative paid) flagged and
  included only in net-spend figures.
- All data is synthetic (`../data/README.md`); the dashboard demonstrates
  layout and KPI logic, not real plan performance.
