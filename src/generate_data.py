"""Generate SYNTHETIC healthcare claims data for the portfolio project.

All data is randomly generated (seeded with random_state=42). It contains no
real patient information and is not affiliated with any payer or provider.

Outputs (written to ../data/):
    members.csv    ~4,000 members enrolled 2023-2024
    providers.csv  ~120 providers (hospitals, clinics, pharmacies, labs, specialty)
    claims.csv     ~15,000 claims + a small number of intentional data-quality
                   issues (duplicate claim rows, adjustment/negative amounts,
                   orphan provider keys) to exercise the cleaning workflow.
"""

import os
import numpy as np
import pandas as pd

SEED = 42
N_MEMBERS = 4000
N_PROVIDERS = 120
N_CLAIMS = 15000
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

rng = np.random.default_rng(SEED)

PERIOD_START = pd.Timestamp("2023-01-01")
PERIOD_END = pd.Timestamp("2024-12-31")

# ---------------------------------------------------------------- members ---
def make_members(n: int) -> pd.DataFrame:
    member_id = [f"M{i:04d}" for i in range(1, n + 1)]

    is_child = rng.random(n) < 0.12
    age = np.where(
        is_child,
        rng.integers(0, 18, n),
        np.clip(rng.normal(47, 19, n), 18, 89).astype(int),
    )

    gender = rng.choice(["F", "M"], n, p=[0.52, 0.48])

    states = ["TX", "CA", "FL", "NY", "IL", "GA", "AZ", "OH", "NC", "PA", "CO"]
    state_p = [0.40, 0.10, 0.08, 0.07, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05]
    state = rng.choice(states, n, p=state_p)

    plan_type = rng.choice(["PPO", "HMO", "HDHP"], n, p=[0.45, 0.30, 0.25])

    # enrollment windows (most members enrolled for the full 24-month period)
    start = np.full(n, PERIOD_START)
    late_join = rng.random(n) < 0.15
    start[late_join] = PERIOD_START + pd.to_timedelta(
        rng.integers(1, 18, late_join.sum()), unit="D"
    ) + pd.to_timedelta(rng.integers(0, 12, late_join.sum()), unit="D") * 30

    end = np.full(n, PERIOD_END)
    churned = rng.random(n) < 0.10
    end[churned] = PERIOD_START + pd.to_timedelta(
        rng.integers(6, 23, churned.sum()), unit="D"
    ) + pd.to_timedelta(rng.integers(0, 12, churned.sum()), unit="D") * 30
    end = np.maximum(end, start + pd.to_timedelta(30, unit="D"))

    members = pd.DataFrame(
        {
            "member_id": member_id,
            "age": age,
            "gender": gender,
            "state": state,
            "plan_type": plan_type,
            "enrollment_start": pd.to_datetime(start),
            "enrollment_end": pd.to_datetime(end),
        }
    )
    # member-months over the analysis period
    eff_start = members["enrollment_start"].clip(lower=PERIOD_START)
    eff_end = members["enrollment_end"].clip(upper=PERIOD_END)
    months = (
        (eff_end.dt.year - eff_start.dt.year) * 12
        + (eff_end.dt.month - eff_start.dt.month)
        + 1
    ).clip(lower=1)
    members["member_months"] = months.astype(int)
    # high-utilizer flag: ~3% of members drive a disproportionate share of claims
    members["high_utilizer"] = rng.random(n) < 0.03
    return members


# --------------------------------------------------------------- providers ---
def make_providers(n: int) -> pd.DataFrame:
    provider_id = [f"P{i:03d}" for i in range(1, n + 1)]

    type_plan = (
        ["Hospital"] * 15
        + ["Clinic"] * 45
        + ["Pharmacy"] * 30
        + ["Lab"] * 15
        + ["Specialty Practice"] * 15
    )
    rng.shuffle(type_plan)
    provider_type = type_plan[:n]

    prefixes = [
        "Sunrise", "Lakeside", "Metro", "Cedar", "Summit",
        "Riverbend", "Clearview", "Northgate", "Harmony", "Brightpath",
    ]
    kind_by_type = {
        "Hospital": "Medical Center",
        "Clinic": "Clinic",
        "Pharmacy": "Pharmacy",
        "Lab": "Diagnostics Lab",
        "Specialty Practice": "Specialty Center",
    }
    names, counters = [], {}
    for i, ptype in enumerate(provider_type):
        counters[ptype] = counters.get(ptype, 0) + 1
        names.append(
            f"{prefixes[i % len(prefixes)]} "
            f"{kind_by_type[ptype]} {counters[ptype]:02d}"
        )

    specialty = np.where(
        np.array(provider_type) == "Specialty Practice",
        rng.choice(
            ["Cardiology", "Orthopedics", "Oncology", "Endocrinology", "Neurology"], n
        ),
        "General",
    )

    cities = ["Dallas", "Houston", "Austin", "Phoenix", "Atlanta", "Chicago", "Denver", "Miami"]
    city = rng.choice(cities, n)
    state = rng.choice(
        ["TX", "CA", "FL", "NY", "IL", "GA", "AZ", "OH", "NC", "PA", "CO"],
        n,
        p=[0.40, 0.10, 0.08, 0.07, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05],
    )

    return pd.DataFrame(
        {
            "provider_id": provider_id,
            "provider_name": names,
            "provider_type": provider_type,
            "specialty": specialty,
            "city": city,
            "state": state,
        }
    )


# ------------------------------------------------------------------ claims ---
CLAIM_TYPE_P = {"outpatient": 0.55, "pharmacy": 0.28, "ER": 0.09, "inpatient": 0.08}

DIAGNOSIS_BY_TYPE = {
    "inpatient": (
        ["Cardiovascular", "Musculoskeletal", "Oncology", "Respiratory", "Pregnancy"],
        [0.28, 0.24, 0.18, 0.16, 0.14],
    ),
    "ER": (
        ["Cardiovascular", "Musculoskeletal", "Respiratory", "Mental Health", "Other"],
        [0.24, 0.26, 0.20, 0.12, 0.18],
    ),
    "outpatient": (
        ["Diabetes", "Musculoskeletal", "Mental Health", "Preventive", "Respiratory", "Cardiovascular"],
        [0.18, 0.24, 0.14, 0.16, 0.12, 0.16],
    ),
    "pharmacy": (
        ["Diabetes", "Cardiovascular", "Mental Health", "Respiratory", "Other"],
        [0.26, 0.28, 0.16, 0.12, 0.18],
    ),
}

# (median paid, sigma) per claim type -> realistic right-skewed spend
PAID_PARAMS = {
    "inpatient": (12000, 1.1),
    "ER": (1400, 0.9),
    "outpatient": (220, 0.9),
    "pharmacy": (85, 0.8),
}

PROVIDER_TYPE_BY_CLAIM = {
    "inpatient": ["Hospital"],
    "ER": ["Hospital"],
    "outpatient": ["Clinic", "Specialty Practice", "Lab"],
    "pharmacy": ["Pharmacy"],
}
PROVIDER_TYPE_W = {
    "outpatient": [0.60, 0.25, 0.15],
}


def make_claims(n: int, members: pd.DataFrame, providers: pd.DataFrame) -> pd.DataFrame:
    member_idx = np.arange(len(members))
    # sampling weight: older members + high utilizers generate more claims
    w = (members["age"].to_numpy() / 45).clip(0.4, 2.5)
    w = np.where(members["high_utilizer"].to_numpy(), w * 8.0, w)
    w = w / w.sum()
    chosen_members = rng.choice(member_idx, n, p=w)

    claim_types = rng.choice(
        list(CLAIM_TYPE_P.keys()), n, p=list(CLAIM_TYPE_P.values())
    )

    provider_ids = []
    for ct in claim_types:
        allowed = PROVIDER_TYPE_BY_CLAIM[ct]
        pool = providers[providers["provider_type"].isin(allowed)]
        if ct == "outpatient":
            sub = [
                pool[pool["provider_type"] == t]
                for t in ["Clinic", "Specialty Practice", "Lab"]
            ]
            pick_from = rng.choice([0, 1, 2], p=PROVIDER_TYPE_W["outpatient"])
            pool = sub[pick_from]
        provider_ids.append(rng.choice(pool["provider_id"].to_numpy()))
    provider_ids = np.array(provider_ids)

    diag_groups = []
    for ct in claim_types:
        groups, p = DIAGNOSIS_BY_TYPE[ct]
        diag_groups.append(rng.choice(groups, p=p))

    paid = np.empty(n)
    for i, ct in enumerate(claim_types):
        median, sigma = PAID_PARAMS[ct]
        paid[i] = rng.lognormal(np.log(median), sigma)
    # catastrophic claims: a small share become very expensive (the classic skew)
    cata_p = np.where(claim_types == "inpatient", 0.015, 0.004)
    catastrophic = rng.random(n) < cata_p
    paid[catastrophic] *= rng.uniform(6, 14, catastrophic.sum())
    paid = np.round(paid, 2)

    contract_rate = rng.uniform(0.35, 0.75, n)
    billed = np.round(paid / contract_rate, 2)

    status = rng.choice(["paid", "denied", "adjusted"], n, p=[0.93, 0.05, 0.02])
    paid = np.where(status == "denied", 0.0, paid)

    # service dates inside the member's enrollment window
    start = members["enrollment_start"].to_numpy()[chosen_members]
    end = members["enrollment_end"].to_numpy()[chosen_members]
    span_days = ((end - start) / np.timedelta64(1, "D")).astype(int).clip(min=1)
    service_date = start + (rng.random(n) * span_days).astype(int) * np.timedelta64(1, "D")

    claims = pd.DataFrame(
        {
            "claim_id": [f"C{i:06d}" for i in range(1, n + 1)],
            "member_id": members["member_id"].to_numpy()[chosen_members],
            "provider_id": provider_ids,
            "service_date": pd.to_datetime(service_date),
            "claim_type": claim_types,
            "diagnosis_group": diag_groups,
            "billed_amount": billed,
            "paid_amount": np.round(paid, 2),
            "claim_status": status,
        }
    )

    # ---- intentional data-quality issues (documented in data/README.md) ----
    dq_rows = []
    # 10 exact duplicate claim rows
    dq_rows.append(claims.sample(10, random_state=7))
    # 8 adjustment rows with negative paid amounts
    adj = claims.sample(8, random_state=11).copy()
    adj["claim_id"] = [f"C9{i:05d}" for i in range(1, 9)]
    adj["paid_amount"] = -np.round(rng.uniform(200, 3000, 8), 2)
    adj["billed_amount"] = -adj["paid_amount"]
    adj["claim_status"] = "adjusted"
    dq_rows.append(adj)
    # 5 claims referencing a provider that does not exist (orphan keys)
    orph = claims.sample(5, random_state=23).copy()
    orph["claim_id"] = [f"C8{i:05d}" for i in range(1, 6)]
    orph["provider_id"] = "P999"
    dq_rows.append(orph)

    claims = pd.concat([claims] + dq_rows, ignore_index=True)
    claims = claims.sample(frac=1.0, random_state=SEED).reset_index(drop=True)  # shuffle
    return claims


def main() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    members = make_members(N_MEMBERS)
    providers = make_providers(N_PROVIDERS)
    claims = make_claims(N_CLAIMS, members, providers)

    members.to_csv(os.path.join(DATA_DIR, "members.csv"), index=False)
    providers.to_csv(os.path.join(DATA_DIR, "providers.csv"), index=False)
    claims.to_csv(os.path.join(DATA_DIR, "claims.csv"), index=False)

    total_mb = sum(
        os.path.getsize(os.path.join(DATA_DIR, f))
        for f in ("members.csv", "providers.csv", "claims.csv")
    ) / 1e6
    print(f"members:   {len(members):>6,} rows")
    print(f"providers: {len(providers):>6,} rows")
    print(f"claims:    {len(claims):>6,} rows")
    print(f"total CSV size: {total_mb:.2f} MB")


if __name__ == "__main__":
    main()
