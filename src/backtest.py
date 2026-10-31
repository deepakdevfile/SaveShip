"""python -m src.backtest  -> output/backtest.json
Honest back-test: train on Apr-Aug, score September (a month the model never saw), compare policies in Rs."""
import json, copy, numpy as np, pandas as pd
from .clean import load_orders, city_tier
from .features import add_checks
from . import model as M
from .engine import Engine, feature_rates, SHIP, CONFIRM, NUDGE, HOLD
from .econ import Econ, load as load_econ
from .impact import table

def decisions(df, p, eng):
    recs = [eng.decide(r, pp).__dict__ for (_, r), pp in zip(df.iterrows(), p)]
    d = pd.DataFrame(recs).drop(columns=["risk", "order_id"]).set_index(df.index)
    out = pd.concat([df, d], axis=1); out["risk"] = p
    return out

def policy_ops(df, p, thresh=0.34, block_tier3=True):
    """Head of Ops: cancel anything risky; stop COD in small-town cities."""
    act = np.where((p >= thresh) | ((df.city.map(city_tier) == "tier3") & block_tier3), HOLD, SHIP)
    return pd.DataFrame({"action": act, "discount_pct": 0.0, "cod_blocked": False}, index=df.index)

def net(df, p, acts, econ):
    d = df.assign(risk=p, **{c: acts[c] for c in ["action", "discount_pct", "cod_blocked"]})
    t = table(d, econ); return t

def run(split="2026-09-01"):
    df = add_checks(load_orders())
    tr, te = df[df.order_datetime < split], df[df.order_datetime >= split]
    m = M.fit(tr); p = M.predict(m, te); rates = feature_rates(tr)
    out = {"train_n": len(tr), "test_n": len(te), "test_actual_rto": float(te.rto.mean())}
    econ0 = load_econ()
    scale = econ0["facts"]["orders_per_month"] * 0.55 / len(te)      # sample month -> real COD month
    res = {}
    for label, pen in [("with_CAC_penalty_300", 300), ("no_CAC_penalty", 0)]:
        cfg = copy.deepcopy(econ0); cfg["assumptions"]["first_order_replacement_cost"] = pen
        econ = Econ(cfg); eng = Engine(m, rates, econ=econ)
        ours = decisions(te, p, eng)
        t_ours = table(ours, econ)
        t_ops = net(te, p, policy_ops(te, p), econ)
        res[label] = {
            "ours_net_sample": float(t_ours.net.sum()), "ours_net_month": float(t_ours.net.sum() * scale),
            "ops_net_sample": float(t_ops.net.sum()), "ops_net_month": float(t_ops.net.sum() * scale),
            "marketing_ship_all_month": 0.0,
            "ours_components_month": {k: float(t_ours[k].sum() * scale) for k in ["saved_rto", "recovered_sales", "lost_genuine", "costs"]},
            "ops_components_month": {k: float(t_ops[k].sum() * scale) for k in ["saved_rto", "recovered_sales", "lost_genuine", "costs"]},
        }
        if pen == 300:
            ours["net"] = t_ours.net
            g = ours.groupby("action").agg(orders=("rto", "size"), actual_rto_rate=("rto", "mean"), net=("net", "sum"),
                                           first_time=("first_order", "sum"))
            out["buckets_sep"] = g.round(3).reset_index().to_dict("records")
            out["ours_sep_orders"] = ours[["order_id", "action", "risk", "rto", "first_order"]].to_dict("records")
            ops_h = int((policy_ops(te, p).action == HOLD).sum())
            out["ops_cancelled_orders"] = ops_h
            out["ops_cancelled_first_time"] = int(((policy_ops(te, p).action == HOLD) & te.first_order).sum())
            out["ops_cancelled_actual_rto_rate"] = float(te[policy_ops(te, p).action == HOLD].rto.mean())
            out["ops_cancelled_genuine"] = int(((policy_ops(te, p).action == HOLD) & (te.rto == 0)).sum())
            out["ours_hold_genuine"] = int(((ours.action == HOLD) & (te.rto == 0)).sum())
            out["ours_hold_n"] = int((ours.action == HOLD).sum())
    out["policies"] = res
    out["baseline_rto_loss_month"] = float(te.rto.mean() * econ0["facts"]["orders_per_month"] * 0.55 * Econ(econ0).L)
    # sensitivity of OUR policy to the unmeasured assumptions (month, with CAC penalty)
    sens = []
    for cr in (0.35, 0.55, 0.75):
        for cm in (0.2, 0.4, 0.6):
            cfg = copy.deepcopy(econ0); cfg["assumptions"]["confirm_rate_if_would_rto"] = cr; cfg["assumptions"]["prepaid_conversion_max"] = cm
            econ = Econ(cfg); eng = Engine(m, rates, econ=econ)
            sens.append({"confirm_rate_if_would_rto": cr, "prepaid_conversion_max": cm,
                         "ours_net_month": float(table(decisions(te, p, eng), econ).net.sum() * scale)})
    out["sensitivity"] = sens
    json.dump(out, open("output/backtest.json", "w"), indent=1, default=str)
    return out

if __name__ == "__main__":
    o = run()
    print({k: v for k, v in o.items() if k not in ("ours_sep_orders", "sensitivity", "policies")})
    print(json.dumps(o["policies"], indent=1))
    print(pd.DataFrame(o["sensitivity"]).pivot(index="confirm_rate_if_would_rto", columns="prepaid_conversion_max", values="ours_net_month").round(0))
