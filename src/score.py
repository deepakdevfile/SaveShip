"""Score ONE new COD order.
  python -m src.score '{"order_id":"KT999","customer_name":"Asha Verma","phone":"9876543210","address":"near station","city":"Patna","state":"Bihar","pincode":800001,"order_value":799,"items":"Hair Oil 100ml","num_items":1,"customer_prior_orders":0,"customer_prior_rto":0,"utm_source":"meta_ads"}'
Also exposed as POST /api/decide in app.py."""
import sys, json, datetime as dt, pandas as pd
from .clean import normalise_phone
from .features import add_checks
from . import model as M
from .engine import Engine, feature_rates, ACTION_LABEL
import pathlib, json as _json

_ENGINE = None
def engine():
    global _ENGINE
    if _ENGINE is None:
        root = pathlib.Path(__file__).resolve().parent.parent / "output"
        if not (root / "model.joblib").exists():
            from .run_batch import run; run()
        _ENGINE = Engine(M.load(), _json.load(open(root / "feature_rates.json")))
    return _ENGINE

def score_new_order(o):
    o = dict(o)
    o.setdefault("order_datetime", dt.datetime.now()); o.setdefault("courier", "NA")
    df = pd.DataFrame([o])
    df["phone"] = df["phone"].map(normalise_phone)
    df["phone_valid"] = df["phone"].str.fullmatch(r"[6-9]\d{9}")
    df["first_order"] = df["customer_prior_orders"] == 0
    df["order_value"] = df["order_value"].astype(float)
    df = add_checks(df)
    eng = engine(); p = float(M.predict(eng.model, df)[0])
    d = eng.decide_live(df.iloc[0], p)
    out = d.__dict__ | {"action_label": ACTION_LABEL[d.action], "address_quality": df.address_quality.iat[0],
                         "name_fake": bool(df.name_fake.iat[0]), "checked_by": df.check_source.iat[0]}
    return out

if __name__ == "__main__":
    print(json.dumps(score_new_order(json.loads(sys.argv[1])), indent=2))
