"""python -m src.suggest_thresholds
Prints the risk cut-offs that earn the most Rs under config/economics.yaml, separately for
first-time and repeat customers, so whoever edits rules.yaml can see the money-optimal values."""
import numpy as np, yaml
from .econ import Econ
from .engine import load_rules

def best_action(e, p, v, first, lo, hi):
    d, _ = e.best_discount_pct(p, v, first, lo, hi)
    d = min(max(d, lo), hi)
    ev = {"SHIP": e.ev_ship(p, v, first), "CONFIRM": e.ev_confirm(p, v, first),
          "NUDGE": e.ev_nudge(p, v, first, d), "HOLD": e.ev_cancel(p, v, first)}
    return max(ev, key=ev.get), ev

def boundaries(v=649, first=False):
    e = Econ(); n = load_rules()["prepaid_nudge"]
    prev, out = None, []
    for p in np.arange(0.05, 0.99, 0.01):
        a, _ = best_action(e, p, v, first, n["min_discount_pct"], n["max_discount_pct"])
        if a != prev: out.append((round(float(p), 2), a)); prev = a
    return out

if __name__ == "__main__":
    for first in (False, True):
        print("FIRST-TIME customers" if first else "REPEAT customers")
        for v in (349, 649, 1199):
            print(f"  order value Rs {v}: " + "  ".join(f"from {p:.0%} -> {a}" for p, a in boundaries(v, first)))
