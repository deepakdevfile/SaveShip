import numpy as np 
import pandas as pd

from .clean import city_tier
from .llm_checks import assess

def add_checks(df):
    res = [assess(r.customer_name, r.address, r.city, r.state, r.pincode) for r in df.itertuples()]
    df = df.copy()
    df["address_quality"] = [r["address_quality"] for r in res]
    df["name_fake"] = [bool(r["name_fake"]) for r in res]
    df["check_source"] = [r["source"] for r in res]
    return df

FEATURES = ["tier_tier2", "tier_tier3", "addr_partial", "addr_unusable", "name_fake", "phone_invalid",
            "prior_rto_1", "prior_rto_2plus", "repeat_clean", "high_value", "meta_first"]

def build_X(df):
    X = pd.DataFrame(index=df.index)
    t = df["city"].map(city_tier)
    X["tier_tier2"] = (t == "tier2").astype(float)
    X["tier_tier3"] = (t == "tier3").astype(float)
    X["addr_partial"] = (df["address_quality"] == "partial").astype(float)
    X["addr_unusable"] = (df["address_quality"] == "unusable").astype(float)
    X["name_fake"] = df["name_fake"].astype(float)
    X["phone_invalid"] = (~df["phone_valid"]).astype(float)
    X["prior_rto_1"] = (df["customer_prior_rto"] == 1).astype(float)
    X["prior_rto_2plus"] = (df["customer_prior_rto"] >= 2).astype(float)
    X["repeat_clean"] = ((df["customer_prior_orders"] > 0) & (df["customer_prior_rto"] == 0)).astype(float)
    X["high_value"] = (df["order_value"] > 1500).astype(float)
    X["meta_first"] = ((df["utm_source"] == "meta_ads") & df["first_order"]).astype(float)
    return X[FEATURES]