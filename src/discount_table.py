"""python -m src.discount_table  -> docs/discount_maths.md  (the 'how much discount and why' maths)"""
from .econ import Econ, load
from .engine import load_rules

def main():
    e = Econ(); a, f = e.a, e.f; n = load_rules()["prepaid_nudge"]; lo, hi = n["min_discount_pct"], n["max_discount_pct"]
    L = []
    L.append("# Prepaid discount: how much, and why\n")
    L.append("All numbers come from `config/economics.yaml`; regenerate with `python -m src.discount_table`.\n")
    L.append("## 1. What a returned COD order costs us\n")
    L.append(f"Forward Rs {f['forward_shipping']} + return Rs {f['return_shipping']} + packing Rs {f['packaging_handling']} + damaged stock "
             f"{f['damaged_share_of_returns']:.0%} x Rs {f['avg_product_cost_damaged']} = **Rs {e.L:.1f} per return**.\n")
    L.append("## 2. The most we could ever afford to give away (break-even)\n")
    L.append("If a customer moves from COD to prepaid, their return chance falls from `p` to 4%, so the expected saving per order is "
             "`(p - 0.04) x Rs 169` minus the payment-gateway fee (2% of order value).\n")
    L.append("| Order value | Risk 25% | Risk 35% | Risk 50% | Risk 70% |\n|---|---|---|---|---|")
    for v in (349, 649, 999, 1499):
        cells = []
        for p in (.25, .35, .5, .7):
            be = (p - f["prepaid_rto_rate"]) * e.L - v * a["payment_gateway_fee_pct"] / 100
            cells.append(f"Rs {be:.0f} ({be / v:.1%})")
        L.append(f"| Rs {v} | " + " | ".join(cells) + " |")
    L.append("\nThis is an upper limit. Discounts also go to customers who would have paid COD and received the order anyway, so we should not give all of it away.\n")
    L.append("## 3. The discount that earns the most (what the engine actually offers)\n")
    L.append("The more we offer, the more people switch - but with diminishing returns. We model switching as "
             f"`{a['prepaid_conversion_max']:.0%} x (1 - e^(-discount% / {a['prepaid_conversion_k_pct']:.0f}))` for genuine buyers, and "
             f"{a['risky_conversion_relative']:.0%} of that for would-be returners. Every switcher costs us the discount, so the engine tries 3%...8% "
             "in 0.25% steps and picks the one with the highest expected Rs.\n")
    L.append("| Order value | Risk | Best discount | Rs off | Switch rate (genuine) | Expected Rs gain vs. confirm-only |\n|---|---|---|---|---|---|")
    for v in (349, 649, 1199):
        for p in (.35, .50, .70):
            d, ev = e.best_discount_pct(p, v, False, lo, hi); d = min(max(d, lo), hi)
            rs = round(v * d / 100 / n["round_to_rupees"]) * n["round_to_rupees"]
            L.append(f"| Rs {v} | {p:.0%} | {d:.2f}% | Rs {rs:.0f} | {e.conversion(d):.0%} | Rs {e.ev_nudge(p, v, False, d) - e.ev_confirm(p, v, False):+.0f} |")
    L.append("\n## 4. The number to remember\n")
    L.append("**About 4-6% (Rs 20-40 on an average Rs 649 order) for medium-risk orders, rising towards 8% (capped at Rs 150) only for the riskiest.** "
             "Below ~3% the offer is too small to notice; above ~8% we pay more in subsidies to people who would have paid anyway than we save in returns.\n")
    L.append("## 5. What this assumes (and how we will check)\n")
    L.append("The switch rates are **assumptions** - the sample data contains no prepaid orders. Week 1 of the pilot should A/B test 3%, 5% and 8% and replace `prepaid_conversion_max` / `prepaid_conversion_k_pct` with measured values.\n")
    open("docs/discount_maths.md", "w").write("\n".join(L)); print("\n".join(L[:12]))

if __name__ == "__main__":
    main()
