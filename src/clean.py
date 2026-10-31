"""Data cleaning"""
import re
import pandas as pd
import numpy as np

def normalise_phone(p):
    d = re.sub(r"\D", "", str(p))
    if len(d) == 12 and d.startswith("91"): d = d[2:]
    return d

def load_orders(path="data/orders_sample.csv", labelled=True):
    df = pd.read_csv(path, dtype={"phone": str})
    n0 = len(df)
    df = df.drop_duplicates().copy()                         # 30 exact duplicate rows
    df["phone"] = df["phone"].map(normalise_phone)           # '+91 61348 94572' -> '6134894572'
    df["phone_valid"] = df["phone"].str.fullmatch(r"[6-9]\d{9}").fillna(False)
    df["order_datetime"] = pd.to_datetime(df["order_datetime"])
    df["pincode"] = df["pincode"].astype("Int64")

    # city missing for 4 rows: fall back to most common city for that state
    mode_city = df.dropna(subset=["city"]).groupby("state")["city"].agg(lambda s: s.mode().iat[0])
    df["city"] = df["city"].fillna(df["state"].map(mode_city))

    # order_value == 0 (3 rows): rebuild from num_items x median price of the item
    df["order_value"] = df["order_value"].astype(float)
    bad = df["order_value"] <= 0
    df.loc[bad, "order_value"] = df.loc[bad, "num_items"] * 449.0
    df["first_order"] = df["customer_prior_orders"] == 0

    if labelled:
        s = df["final_status"].str.strip().str.upper()
        df = df[s.isin(["DELIVERED", "RTO"])].copy()         # drops 1 IN_TRANSIT (no outcome yet)
        df["rto"] = (s[df.index] == "RTO").astype(int)

    df.attrs["rows_dropped_duplicates"] = n0 - len(df)
    return df.reset_index(drop=True)

METRO = ["Delhi", "Mumbai", "Bengaluru", "Hyderabad", "Pune", "Chennai", "Kolkata"]
TIER2 = ["Jaipur", "Lucknow", "Indore", "Patna", "Guwahati"]
def city_tier(c):
    return "metro" if c in METRO else ("tier2" if c in TIER2 else "tier3")