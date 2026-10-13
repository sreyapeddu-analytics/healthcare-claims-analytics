"""Data-cleaning routines for the synthetic healthcare claims dataset.

Cleaning decisions (all documented, reproducible):
  * duplicate claim_id rows  -> keep first occurrence, report count
  * negative paid_amount     -> kept as claim adjustments in a separate flag
                                column (adjustments are legitimate in claims
                                data); excluded from "gross paid" KPIs and
                                included in "net paid"
  * orphan provider_id       -> quarantined into a rejects frame for the
                                provider-master remediation report, excluded
                                from spend analysis
"""

import pandas as pd

REQUIRED_CLAIM_COLS = [
    "claim_id", "member_id", "provider_id", "service_date",
    "claim_type", "diagnosis_group", "billed_amount", "paid_amount",
    "claim_status",
]


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def coerce_types(claims: pd.DataFrame) -> pd.DataFrame:
    claims = claims.copy()
    claims["service_date"] = pd.to_datetime(claims["service_date"], errors="coerce")
    for col in ("billed_amount", "paid_amount"):
        claims[col] = pd.to_numeric(claims[col], errors="coerce")
    for col in ("claim_id", "member_id", "provider_id", "claim_type",
                "diagnosis_group", "claim_status"):
        claims[col] = claims[col].astype(str).str.strip()
    return claims


def remove_duplicate_claims(claims: pd.DataFrame):
    """Drop exact duplicate claim_id rows, keeping the first occurrence."""
    dup_mask = claims.duplicated(subset="claim_id", keep="first")
    n_dupes = int(dup_mask.sum())
    return claims.loc[~dup_mask].reset_index(drop=True), n_dupes


def flag_adjustments(claims: pd.DataFrame) -> pd.DataFrame:
    claims = claims.copy()
    claims["is_adjustment"] = claims["paid_amount"] < 0
    return claims


def quarantine_orphan_providers(claims: pd.DataFrame, providers: pd.DataFrame):
    """Split off claims whose provider_id is missing from the provider master."""
    valid = set(providers["provider_id"].astype(str))
    orphan_mask = ~claims["provider_id"].isin(valid)
    rejects = claims.loc[orphan_mask].reset_index(drop=True)
    clean = claims.loc[~orphan_mask].reset_index(drop=True)
    return clean, rejects


def clean_claims(claims_raw: pd.DataFrame, providers: pd.DataFrame) -> dict:
    """Full cleaning pipeline. Returns clean frame, rejects and a DQ report."""
    claims = standardize_columns(claims_raw)
    missing = [c for c in REQUIRED_CLAIM_COLS if c not in claims.columns]
    if missing:
        raise ValueError(f"claims.csv is missing columns: {missing}")
    claims = coerce_types(claims)

    report = {"rows_raw": len(claims)}

    claims, n_dupes = remove_duplicate_claims(claims)
    report["duplicate_claim_rows_removed"] = n_dupes

    claims = flag_adjustments(claims)
    report["adjustment_rows_negative_paid"] = int(claims["is_adjustment"].sum())

    claims, rejects = quarantine_orphan_providers(claims, providers)
    report["orphan_provider_rows_quarantined"] = len(rejects)

    report["rows_null_service_date"] = int(claims["service_date"].isna().sum())
    report["rows_null_paid_amount"] = int(claims["paid_amount"].isna().sum())
    report["rows_clean"] = len(claims)
    return {"claims": claims, "rejects": rejects, "dq_report": report}
