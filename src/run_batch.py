"""python -m src.run_batch  -> output/decisions.csv (+ summary).  Uses out-of-fold risk scores so the
back-test is honest (each order is scored by a model that never saw it)."""
import json, pandas as pd, sys
from .clean import load_orders
from .features import add_checks
from . import model as M
from .engine import Engine, ACTION_LABEL, feature_rates
from .econ import Econ

def run(csv="data/orders_sample.csv", out="output/decisions.csv"):
    df = add_checks(load_orders(csv))
    df["risk_oof"] = M.oof_predict(df)
    full = M.fit(df); M.save(full)
    rates = feature_rates(df); json.dump(rates, open("output/feature_rates.json", "w"))
    eng = Engine(full, rates)
    recs = []
    for (i, r), p in zip(df.iterrows(), df["risk_oof"]):
        d = eng.decide(r, p); recs.append(d.__dict__)
    dec = pd.DataFrame(recs).drop(columns=["risk"])
    res = pd.concat([df.reset_index(drop=True), dec.drop(columns=["order_id"])], axis=1)
    from .impact import table
    res = pd.concat([res, table(res, eng.econ)], axis=1)
    res["date"] = res["order_datetime"].dt.date
    res.to_csv(out, index=False)
    return res

if __name__ == "__main__":
    res = run()
    t = res.groupby("action").agg(orders=("rto", "size"), actual_rto_rate=("rto", "mean"), avg_risk=("risk_oof", "mean"))
    print(t.round(3)); print("\nrows:", len(res))