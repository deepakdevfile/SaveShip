"""Rs impact of each decision vs. today's behaviour (ship every COD order).
Pure arithmetic on the assumptions in config/economics.yaml - no AI.
Identity (checked in tests):  net = saved_rto + recovered_sales - lost_genuine - costs
which equals EV(action) - EV(ship)."""
import pandas as pd
from .econ import Econ
from .engine import SHIP, CONFIRM, NUDGE, HOLD

def order_impact(econ, action, p, v, first, discount_pct=0.0, cod_blocked=False):
    a, f, L = econ.a, econ.f, econ.L
    M = econ.contribution(v); pen = econ.lost_genuine_penalty(first)
    c_g, c_r = a["confirm_rate_if_genuine"], a["confirm_rate_if_would_rto"]
    z = dict(saved_rto=0.0, recovered_sales=0.0, lost_genuine=0.0, costs=0.0)
    if action == SHIP:
        return z
    if action == HOLD:
        z["saved_rto"] = p * L; z["lost_genuine"] = (1 - p) * (M + pen); return z
    if action == CONFIRM:
        z["saved_rto"] = p * (1 - c_r) * L
        z["lost_genuine"] = (1 - p) * (1 - c_g) * (M + pen)
        z["costs"] = a["whatsapp_cost_per_conversation"]; return z
    # NUDGE
    x_g = econ.conversion(discount_pct); x_r = x_g * a["risky_conversion_relative"]
    d = v * discount_pct / 100; fee = v * a["payment_gateway_fee_pct"] / 100
    r2 = a["risky_prepaid_rto_rate"]
    # customers who decline prepaid: confirm flow normally, hold if COD is blocked
    c_g2, c_r2 = (0.0, 0.0) if cod_blocked else (c_g, c_r)
    z["saved_rto"] = p * (x_r * (1 - r2) + (1 - x_r) * (1 - c_r2)) * L
    z["recovered_sales"] = p * x_r * (1 - r2) * M
    z["lost_genuine"] = (1 - p) * (1 - x_g) * (1 - c_g2) * (M + pen)
    z["costs"] = ((1 - p) * x_g * (d + fee) + p * x_r * (1 - r2) * (d + fee) + a["whatsapp_cost_per_conversation"])
    return z

def table(dec, econ=None, action_col="action"):
    """dec: dataframe with risk_oof (or risk), order_value, first_order, discount_pct, cod_blocked."""
    econ = econ or Econ()
    pcol = "risk_oof" if "risk_oof" in dec else "risk"
    rows = [order_impact(econ, r[action_col], r[pcol], r["order_value"], bool(r["first_order"]),
                         r.get("discount_pct", 0.0), bool(r.get("cod_blocked", False))) for _, r in dec.iterrows()]
    out = pd.DataFrame(rows, index=dec.index)
    out["net"] = out.saved_rto + out.recovered_sales - out.lost_genuine - out.costs
    return out
