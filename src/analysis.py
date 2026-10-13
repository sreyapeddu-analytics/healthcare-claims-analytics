"""Analytical functions for the healthcare claims project.

All KPIs are computed on the CLEANED claims frame produced by
``src/data_cleaning.py``. Denied claims (paid_amount = 0) contribute to
utilization counts; adjustment rows (negative paid) are reported separately
and included only in net-spend figures.
"""

import os
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

HIGH_COST_THRESHOLD = 50_000  # annual paid per member: standard high-cost flag


def load_data(data_dir: str = DATA_DIR) -> dict:
    members = pd.read_csv(os.path.join(data_dir, "members.csv"),
                          parse_dates=["enrollment_start", "enrollment_end"])
    providers = pd.read_csv(os.path.join(data_dir, "providers.csv"))
    claims = pd.read_csv(os.path.join(data_dir, "claims.csv"),
                         parse_dates=["service_date"])
    return {"members": members, "providers": providers, "claims": claims}


def total_member_months(members: pd.DataFrame) -> int:
    return int(members["member_months"].sum())


def pmpm(claims: pd.DataFrame, members: pd.DataFrame, net: bool = True) -> float:
    """Per-member-per-month paid: total paid / total member-months."""
    paid = claims["paid_amount"] if net else claims.loc[~claims["is_adjustment"], "paid_amount"]
    return float(paid.sum() / total_member_months(members))


def monthly_paid_trend(claims: pd.DataFrame) -> pd.DataFrame:
    df = claims.copy()
    df["month"] = df["service_date"].dt.to_period("M").dt.to_timestamp()
    trend = (
        df.groupby("month")
        .agg(total_paid=("paid_amount", "sum"),
             claim_count=("claim_id", "count"),
             members_with_claims=("member_id", "nunique"))
        .reset_index()
    )
    return trend


def top_providers(claims: pd.DataFrame, providers: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    spend = (
        claims[~claims["is_adjustment"]]
        .groupby("provider_id")
        .agg(total_paid=("paid_amount", "sum"),
             claim_count=("claim_id", "count"))
        .reset_index()
        .merge(providers, on="provider_id", how="left")
        .sort_values("total_paid", ascending=False)
        .head(n)
        .reset_index(drop=True)
    )
    total = claims.loc[~claims["is_adjustment"], "paid_amount"].sum()
    spend["share_of_spend"] = spend["total_paid"] / total
    return spend


def er_rate_per_1k(claims: pd.DataFrame, members: pd.DataFrame) -> float:
    """ER visits per 1,000 member-years."""
    er_visits = int((claims["claim_type"] == "ER").sum())
    member_years = total_member_months(members) / 12
    return er_visits / member_years * 1000


def cost_by_diagnosis(claims: pd.DataFrame) -> pd.DataFrame:
    df = claims[~claims["is_adjustment"]]
    out = (
        df.groupby("diagnosis_group")
        .agg(total_paid=("paid_amount", "sum"),
             claim_count=("claim_id", "count"),
             avg_paid=("paid_amount", "mean"))
        .reset_index()
        .sort_values("total_paid", ascending=False)
        .reset_index(drop=True)
    )
    out["share_of_spend"] = out["total_paid"] / out["total_paid"].sum()
    return out


def cost_by_claim_type(claims: pd.DataFrame) -> pd.DataFrame:
    df = claims[~claims["is_adjustment"]]
    return (
        df.groupby("claim_type")
        .agg(total_paid=("paid_amount", "sum"),
             claim_count=("claim_id", "count"),
             avg_paid=("paid_amount", "mean"),
             median_paid=("paid_amount", "median"))
        .reset_index()
        .sort_values("total_paid", ascending=False)
        .reset_index(drop=True)
    )


def high_cost_claimant_share(claims: pd.DataFrame,
                             threshold: float = HIGH_COST_THRESHOLD) -> dict:
    """Share of total spend driven by members above the annual paid threshold."""
    df = claims[~claims["is_adjustment"]].copy()
    df["year"] = df["service_date"].dt.year
    member_year = df.groupby(["member_id", "year"])["paid_amount"].sum().reset_index()
    high = member_year[member_year["paid_amount"] >= threshold]
    total = df["paid_amount"].sum()
    return {
        "threshold": threshold,
        "high_cost_member_years": int(len(high)),
        "pct_of_member_years": float(len(high) / len(member_year) * 100),
        "spend_by_high_cost": float(high["paid_amount"].sum()),
        "share_of_spend": float(high["paid_amount"].sum() / total * 100),
    }


def data_quality_checks(claims_raw: pd.DataFrame,
                        providers: pd.DataFrame,
                        members: pd.DataFrame) -> pd.DataFrame:
    """Row-level DQ checks mirroring the queries in sql/analysis_queries.sql."""
    checks = [
        ("duplicate_claim_id",
         int(claims_raw.duplicated(subset="claim_id", keep=False).sum())),
        ("negative_paid_amount",
         int((pd.to_numeric(claims_raw["paid_amount"], errors="coerce") < 0).sum())),
        ("orphan_provider_id",
         int((~claims_raw["provider_id"].astype(str).isin(
             set(providers["provider_id"].astype(str)))).sum())),
        ("orphan_member_id",
         int((~claims_raw["member_id"].astype(str).isin(
             set(members["member_id"].astype(str)))).sum())),
        ("null_service_date",
         int(pd.to_datetime(claims_raw["service_date"], errors="coerce").isna().sum())),
        ("future_service_date",
         int((pd.to_datetime(claims_raw["service_date"], errors="coerce")
              > pd.Timestamp("2024-12-31")).sum())),
        ("paid_exceeds_billed_x2",
         int((pd.to_numeric(claims_raw["paid_amount"], errors="coerce")
              > 2 * pd.to_numeric(claims_raw["billed_amount"], errors="coerce")).sum())),
    ]
    return pd.DataFrame(checks, columns=["check", "violation_rows"])
