"""Decision engine: risk score + business rules -> one of 4 actions + plain-English reason."""
import yaml
import  pathlib
import numpy as np
import pandas as pd
from dataclasses import dataclass, asdict
from .econ import Econ
from .features import build_X, FEATURES
from .clean import city_tier

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHIP, CONFIRM, NUDGE, HOLD = "SHIP_AS_IS", "SHIP_AFTER_CONFIRMATION", "NUDGE_TO_PREPAID", "HOLD_CANCEL"
ACTION_LABEL = {SHIP: "Ship as-is", CONFIRM: "Ship after confirmation", NUDGE: "Nudge to prepaid", HOLD: "Hold / cancel"}

def load_rules(path="config/rules.yaml"):
    with open(ROOT / path) as f:
        return yaml.safe_load(f)

PHRASE = {
    "tier_tier3": "delivery area is a small town where {r:.0%} of past COD orders came back",
    "tier_tier2": "delivery city has a higher return rate ({r:.0%} of past COD orders)",
    "addr_unusable": "address is unusable for a courier ('{addr}')",
    "addr_partial": "address has only a landmark / directions, no house number",
    "name_fake": "name looks fake ('{name}')",
    "phone_invalid": "phone number is not a valid 10-digit mobile",
    "prior_rto_1": "customer returned 1 earlier order",
    "prior_rto_2plus": "customer returned {n} earlier orders ({r:.0%} of such orders come back)",
    "high_value": "high order value (Rs {v:,.0f}); orders above Rs 1,500 return {r:.0%} of the time",
    "meta_first": "first order from a Meta ad (these return {r:.0%} of the time)",
}

@dataclass
class Decision:
    order_id: str
    action: str
    risk: float
    reason: str
    discount_pct: float = 0.0
    discount_rs: float = 0.0
    cod_blocked: bool = False
    message_template: str = ""
    ev_ship: float = 0.0

class Engine:
    def __init__(self, model, rates, rules=None, econ=None):
        self.model, self.rates = model, rates
        self.rules = rules or load_rules()
        self.econ = econ or Econ()

    def _reasons(self, row, X_row):
        contrib = dict(zip(FEATURES, self.model.coef_[0] * X_row[FEATURES].values))
        pos = sorted([(c, f) for f, c in contrib.items() if c > 0.25], reverse=True)[:3]
        out = []
        for _, f in pos:
            out.append(PHRASE[f].format(r=self.rates.get(f, 0), addr=str(row["address"])[:25], name=row["customer_name"],
                                         n=int(row["customer_prior_rto"]), v=row["order_value"]))
        return out

    def decide(self, row, p):
        R = self.rules
        X_row = build_X(pd.DataFrame([row]))
        X_row = X_row.iloc[0]
        why = self._reasons(row, X_row)
        first = bool(row["first_order"])
        dq = R["data_quality"]
        pct = f"{p:.0%}"
        oid = row["order_id"]
        junk_addr = row["address_quality"] == "unusable"

        # 1) hard data-quality rules
        if junk_addr and row["name_fake"] and dq["hold_if_junk_address_and_fake_name"]:
            return Decision(oid, HOLD, p, f"Hold: fake name and unusable address - nothing a courier can deliver to. Risk {pct}.")
        if junk_addr and not row["phone_valid"] and dq["hold_if_phone_invalid_and_address_junk"]:
            return Decision(oid, HOLD, p, f"Hold: unusable address and invalid phone - we cannot reach or find the customer. Risk {pct}.")

        # 2) repeat offender: customer-level COD block
        if row["customer_prior_rto"] >= R["repeat_offender"]["prior_rto_count_to_block_cod"]:
            d_pct, d_rs = self._discount(p, row, first)
            return Decision(oid, NUDGE, p, f"COD switched off for this customer: {int(row['customer_prior_rto'])} earlier returns. "
                            f"Offer prepaid with Rs {d_rs:.0f} off; if declined, hold. Risk {pct}.", d_pct, d_rs, True, "prepaid_offer_repeat")

        # 3) unusable address alone -> get a proper address first (prepaid won't fix this)
        if junk_addr:
            if p >= R["risk_bands"]["repeat_customers"]["nudge_below"] and not first:
                return Decision(oid, HOLD, p, f"Hold: unusable address on a high-risk order (risk {pct}), repeat customer so no acquisition cost at stake.")
            return Decision(oid, CONFIRM, p, f"Ask customer for a full address on WhatsApp ({'; '.join(why[:2]) or 'address unusable'}). Risk {pct}.",
                            message_template="address_fix")

        # 4) risk bands
        b = R["risk_bands"]["first_time_customers" if first else "repeat_customers"]
        fp = R["first_order_protection"]
        if p < b["ship_as_is_below"]:
            return Decision(oid, SHIP, p, f"Low risk ({pct}): " + ("; ".join(why) if why else "metro city, full address, nothing unusual") + ".")
        if p < b["confirm_below"]:
            return Decision(oid, CONFIRM, p, f"Medium risk ({pct}): quick WhatsApp confirm is cheaper than a possible Rs {self.econ.L:.0f} return"
                            + (f" - {'; '.join(why)}" if why else "") + ".", message_template="confirm_cod")
        if p < b["nudge_below"]:
            d_pct, d_rs = self._discount(p, row, first)
            return Decision(oid, NUDGE, p, f"Higher risk ({pct}): offer Rs {d_rs:.0f} off to pay online"
                            + (f" - {'; '.join(why)}" if why else "") + ". If they decline, falls back to WhatsApp confirm.",
                            d_pct, d_rs, False, "prepaid_offer")

        # risk above the hold line
        if first and fp["enabled"] and p < fp["cancel_first_orders_only_above"]:
            d_pct, d_rs = self._discount(p, row, first)
            return Decision(oid, NUDGE, p, f"Very high risk ({pct}) but first-time customer: offer Rs {d_rs:.0f} off for prepaid instead of cancelling "
                            f"(protects the ~Rs {self.econ.f['cac_meta']} acquisition cost). {'; '.join(why)}.", d_pct, d_rs, True, "prepaid_offer")
        return Decision(oid, HOLD, p, f"Hold: very high risk ({pct}) - {'; '.join(why)}.")

    def decide_live(self, row, p):
        """Same as decide() plus the random control group used in production."""
        d = self.decide(row, p)
        pct = self.rules.get("measurement", {}).get("holdout_pct", 0)
        if d.action != SHIP and pct and (int(__import__("hashlib").md5(str(row["order_id"]).encode()).hexdigest(), 16) % 100) < pct:
            return Decision(row["order_id"], SHIP, p, f"Random control group ({pct}% of flagged orders ship as-is so we can measure the rules). "
                            f"It would otherwise have been: {ACTION_LABEL[d.action]}.")
        return d

    
    def _discount(self, p, row, first):
        n = self.rules["prepaid_nudge"]
        pct, _ = self.econ.best_discount_pct(p, row["order_value"], first, lo=n["min_discount_pct"], hi=n["max_discount_pct"])
        pct = min(max(pct, n["min_discount_pct"]), n["max_discount_pct"])
        step = n["round_to_rupees"]
        rs = round(row["order_value"] * pct / 100 / step) * step
        rs = min(max(rs, step), n.get("max_discount_rs", 1e9))
        return round(rs / row["order_value"] * 100, 2), float(rs)

def feature_rates(df):
    X = build_X(df)
    out = {}
    for f in FEATURES:
        m = X[f] == 1
        out[f] = float(df.loc[m, "rto"].mean()) if m.sum() else 0.0
    return out