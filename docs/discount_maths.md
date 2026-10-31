# Prepaid discount: how much, and why

All numbers come from `config/economics.yaml`; regenerate with `python -m src.discount_table`.

## 1. What a returned COD order costs us

Forward Rs 65 + return Rs 65 + packing Rs 25 + damaged stock 8% x Rs 180 = **Rs 169.4 per return**.

## 2. The most we could ever afford to give away (break-even)

If a customer moves from COD to prepaid, their return chance falls from `p` to 4%, so the expected saving per order is `(p - 0.04) x Rs 169` minus the payment-gateway fee (2% of order value).

| Order value | Risk 25% | Risk 35% | Risk 50% | Risk 70% |
|---|---|---|---|---|
| Rs 349 | Rs 29 (8.2%) | Rs 46 (13.0%) | Rs 71 (20.3%) | Rs 105 (30.0%) |
| Rs 649 | Rs 23 (3.5%) | Rs 40 (6.1%) | Rs 65 (10.0%) | Rs 99 (15.2%) |
| Rs 999 | Rs 16 (1.6%) | Rs 33 (3.3%) | Rs 58 (5.8%) | Rs 92 (9.2%) |
| Rs 1499 | Rs 6 (0.4%) | Rs 23 (1.5%) | Rs 48 (3.2%) | Rs 82 (5.5%) |

This is an upper limit. Discounts also go to customers who would have paid COD and received the order anyway, so we should not give all of it away.

## 3. The discount that earns the most (what the engine actually offers)

The more we offer, the more people switch - but with diminishing returns. We model switching as `40% x (1 - e^(-discount% / 4))` for genuine buyers, and 30% of that for would-be returners. Every switcher costs us the discount, so the engine tries 3%...8% in 0.25% steps and picks the one with the highest expected Rs.

| Order value | Risk | Best discount | Rs off | Switch rate (genuine) | Expected Rs gain vs. confirm-only |
|---|---|---|---|---|---|
| Rs 349 | 35% | 3.25% | Rs 10 | 22% | Rs +3 |
| Rs 349 | 50% | 4.50% | Rs 20 | 27% | Rs +5 |
| Rs 349 | 70% | 6.50% | Rs 20 | 32% | Rs +8 |
| Rs 649 | 35% | 3.75% | Rs 20 | 24% | Rs +7 |
| Rs 649 | 50% | 4.75% | Rs 30 | 28% | Rs +11 |
| Rs 649 | 70% | 6.50% | Rs 40 | 32% | Rs +17 |
| Rs 1199 | 35% | 3.75% | Rs 40 | 24% | Rs +14 |
| Rs 1199 | 50% | 5.00% | Rs 60 | 29% | Rs +21 |
| Rs 1199 | 70% | 6.75% | Rs 80 | 33% | Rs +33 |

## 4. The number to remember

**About 4-6% (Rs 20-40 on an average Rs 649 order) for medium-risk orders, rising towards 8% (capped at Rs 150) only for the riskiest.** Below ~3% the offer is too small to notice; above ~8% we pay more in subsidies to people who would have paid anyway than we save in returns.

## 5. What this assumes (and how we will check)

The switch rates are **assumptions** - the sample data contains no prepaid orders. Week 1 of the pilot should A/B test 3%, 5% and 8% and replace `prepaid_conversion_max` / `prepaid_conversion_k_pct` with measured values.
