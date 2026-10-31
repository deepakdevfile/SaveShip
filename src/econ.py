"""All money maths lives here (plain arithmetic, no AI).
Every function returns expected Rs value of an action for ONE order, given
risk p (probability of RTO), order value v and whether it is a first order."""
import math, yaml, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

def load(path="config/economics.yaml"):
    with open(ROOT / path) as f:
        return yaml.safe_load(f)

class Econ:
    def __init__(self, cfg=None):
        cfg = cfg or load()
        self.f, self.a = cfg["facts"], cfg["assumptions"]
        f = self.f
        # What one RTO costs us
        self.L = (f["forward_shipping"] + f["return_shipping"] + f["packaging_handling"]
                  + f["damaged_share_of_returns"] * f["avg_product_cost_damaged"])

    def contribution(self, v):
        """Rs we keep on a delivered order: gross margin minus forward shipping & packing."""
        return self.f["gross_margin"] * v - self.f["forward_shipping"] - self.f["packaging_handling"]

    def lost_genuine_penalty(self, first):
        return self.a["first_order_replacement_cost"] if first else 0.0

    # ---- expected value of each action (Rs per order) ----
    def ev_ship(self, p, v, first=False):
        return (1 - p) * self.contribution(v) - p * self.L

    def ev_cancel(self, p, v, first=False):
        return -(1 - p) * self.lost_genuine_penalty(first)

    def ev_confirm(self, p, v, first=False):
        a = self.a
        genuine = (1 - p) * (a["confirm_rate_if_genuine"] * self.contribution(v)
                             - (1 - a["confirm_rate_if_genuine"]) * self.lost_genuine_penalty(first))
        bad = -p * a["confirm_rate_if_would_rto"] * self.L
        return genuine + bad - a["whatsapp_cost_per_conversation"]

    def conversion(self, discount_pct):
        a = self.a
        return a["prepaid_conversion_max"] * (1 - math.exp(-discount_pct / a["prepaid_conversion_k_pct"]))

    def ev_nudge(self, p, v, first=False, discount_pct=5.0):
        """Genuine customers switch to prepaid readily; would-be returners rarely do.
        Anyone who switches pays the discount (that is the 'subsidy leakage')."""
        a, f = self.a, self.f
        x_g = self.conversion(discount_pct)
        x_r = x_g * a["risky_conversion_relative"]
        d = v * discount_pct / 100
        fee = v * a["payment_gateway_fee_pct"] / 100
        m_paid = self.contribution(v) - d - fee
        g_conf = a["confirm_rate_if_genuine"] * self.contribution(v) - (1 - a["confirm_rate_if_genuine"]) * self.lost_genuine_penalty(first)
        genuine = x_g * m_paid + (1 - x_g) * g_conf
        r2 = a["risky_prepaid_rto_rate"]
        risky = x_r * ((1 - r2) * m_paid - r2 * self.L) + (1 - x_r) * (-a["confirm_rate_if_would_rto"] * self.L)
        return (1 - p) * genuine + p * risky - a["whatsapp_cost_per_conversation"]

    def best_discount_pct(self, p, v, first=False, lo=0.0, hi=15.0):
        best, bd = -1e9, 0.0
        d = lo
        while d <= hi + 1e-9:
            e = self.ev_nudge(p, v, first, d)
            if e > best: best, bd = e, d
            d += 0.25
        return bd, best

    def evs(self, p, v, first=False, discount_pct=5.0):
        return {
            "ship": self.ev_ship(p, v, first), 
            "confirm": self.ev_confirm(p, v, first),
            "nudge": self.ev_nudge(p, v, first, discount_pct), 
            "cancel": self.ev_cancel(p, v, first)
        }

if __name__ == "__main__":
    e = Econ()
    print(f"Cost of one RTO: Rs {e.L:.1f}; contribution on avg order: Rs {e.contribution(649):.0f}")
    for first in (False, True):
        print("first-time" if first else "repeat")
        for p in [0.1,0.2,0.25,0.3,0.35,0.4,0.5,0.6,0.7,0.8,0.9]:
            ev = e.evs(p, 649, first, 5)
            bd, _ = e.best_discount_pct(p, 649, first)
            print(f" p={p:.2f} " + " ".join(f"{k}={v:7.1f}" for k,v in ev.items()) + f"  best={max(ev,key=ev.get)} bestdisc={bd:.2f}%")