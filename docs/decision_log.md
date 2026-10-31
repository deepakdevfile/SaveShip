# Decision log

Format: **Decision** - alternatives considered - why.

## Data
- **Cleaned before analysing**: removed 30 exact duplicate rows, 1 `IN_TRANSIT` order (no outcome), normalised status spellings (`Rto`, `delivered`), phones like `+91 61348 94572` -> 10 digits, 4 missing cities filled from state, 3 `order_value = 0` rows set to items x Rs 449, 12 missing pincodes left as-is. - Alternative: drop all imperfect rows (loses ~2%, and hides the fact that production data will be messy). - Kept rows so the engine has to cope with real mess.
- **9-digit phones treated as invalid, 15-char `+91` phones treated as valid** - they looked the same ("wrong length") but 17 are truly short (47% RTO) while 15 are just formatted. - Caught by looking at the raw values rather than just the length.

## Scoring
- **Logistic regression on ~11 features, not gradient boosting / not an LLM** - alternatives: gradient boosting (tested on the same features: AUC 0.733 vs 0.736 for logistic regression, so no gain), LLM scoring (can't know our return rates, slow, not reproducible). - We need reasons an ops person can read; each feature maps to a sentence.
- **City *tier* (metro / tier-2 / tier-3), not pincode** - Ops asked to block bad pincodes. The data has 1,066 distinct pincodes in ~1,990 orders; only 30 pincodes have 5+ orders (161 orders). A pincode "history" would be noise. - City is the finest level with enough orders; add pincode once we have 12+ months.
- **Did not use day-of-week, courier, hour of day** - Friday looks bad (35% vs Monday 22%) but adding it didn't improve out-of-sample AUC (0.730 vs 0.729); courier and hour showed nothing. - Avoid fitting noise; flagged for re-check on more data.
- **Honest evaluation**: 5-fold out-of-fold scores for the dashboard history, and a time split (train Apr-Aug, test Sep) for the memo. AUC ~0.74; predicted vs actual RTO within a few points in every band.

## Economics
- **Contribution per delivered order = 62% x value - Rs 65 forward shipping - Rs 25 packing** (not just 62% x value) - the brief lists forward shipping and packing as RTO costs, so a delivered order pays them too. Alternative (62% flat) overstates the value of shipping.
- **Cost of one RTO = Rs 169.4** (65 + 65 + 25 + 8% x 180) - straight from the brief.
- **Lost genuine first-time order costs profit + Rs 300** - Marketing's point. Strictly the Rs 300 is sunk; the real cost is the replacement CAC if growth is budget-limited. - Made it a switch (`first_order_replacement_cost`) and report results with and without it.
- **Confirmation / prepaid-switch rates are assumptions** (confirm: 90% of genuine, 55% of would-be returners; prepaid switch max 40%, would-be returners at 30% of that). - The sample has no WhatsApp or prepaid data. Chose deliberately modest values after my first version (35% / 45%) made WhatsApp look like a miracle. Sensitivity table in the memo.

## Rules
- **Thresholds differ for first-time vs repeat customers** (repeat: ship <26%, nudge to 82%, hold above; first-time: ship <37%, nudge to 90%) - alternative: one global set. My first global set (22/34/62%) turned the policy net-negative over the 1,987-order sample (about -Rs 7.7k): confirming 24-37% risk first-timers loses genuine buyers worth profit + CAC. `python -m src.suggest_thresholds` now derives the money-optimal values.
- **A narrow "confirm" band (4 points) before the prepaid band** - pure maths says prepaid-nudge beats confirm at every risk level *given my assumed switch rates*. Because those rates are unmeasured, I kept a cheap no-discount step as insurance until the pilot measures them. The confirm flow is also the fallback for anyone who declines prepaid, and the address-fix path.
- **Cancel is rare by design** - cancelling pays only above ~65% risk for repeat customers and ~85-90% for first-timers (CAC). In the back-test only 6 of 329 September orders reach that line (1 of them genuine).
- **First-order protection**: never auto-cancel a first-time customer unless risk >= 90% or the details are unusable (fake name + junk address, or junk address + invalid phone). Marketing's concern, implemented as a rule they can see and change.
- **COD block is per customer, not per pincode**: 2+ earlier returns -> prepaid only (these customers return 76% of orders, n=34). If they decline: hold.
- **Junk address alone != cancel**: ask for the full address on WhatsApp. 38% of junk-address orders were actually delivered; a courier-less address is a fixable problem.
- **Hold is recoverable**: held orders get a "send your name + address and we'll ship" message instead of silence.
- **5% random control group in live use** - held/confirmed orders never reveal their true outcome, so without a control group we can never tell if the rules still work.

## LLM use
- **Code gate first, LLM only for the grey zone** (Hinglish landmark-only addresses, odd names): clear-cut cases (structured addresses, "." / "xyz" / city-only, standard two-word names) never call the LLM. About 24% of orders reach it.
- **Offline fallback + disk cache + never block on LLM failure** - the repo must run in 10 minutes without an API key, and an API outage must not stop orders.
- **Model: a small/fast model (`claude-haiku-5-5`) by default**, overridable via `LLM_MODEL` - this is a classification task; paying for a large model buys nothing.
- **Not used for**: phone/pincode validation, scoring, thresholds, discounts, reading 1/2/yes/no.

## WhatsApp
- **Language: Hinglish (Roman script) for Hindi-belt states + Delhi/Maharashtra, English elsewhere**, set in config - no language field exists in the data; state is the best proxy. Replace with a customer language preference once collected.
- **Send within 5 minutes, only 9am-9pm**; reminder at 6h; decision at 24h.
- **Reply handling**: 1/yes/haan/ok -> confirm; 2/no/nahi/cancel -> cancel; anything else -> one gentle re-ask, second unclear reply -> human call task. In the prepaid offer, "2/no" means "keep COD" (-> confirm step), not cancel.
- **Silence after 24h**: cancel/hold if risk > 28%, otherwise ship COD anyway - low-risk customers who just didn't notice the message shouldn't be punished.
- **Prepaid discount 4-6% typically (Rs 20-40 on a Rs 649 order), capped 3-8% and Rs 150** - see `docs/discount_maths.md`. Upper bound is the saving (p - 4%) x Rs 169 minus 2% gateway fee; the engine picks the discount with the best expected Rs.

## Dashboard
- **"Yesterday" = latest day in the data (30 Sep)** because the sample ends there; `?date=` picks any day.
- **Estimated Rs (expected values), not actual outcomes** - on a live day the true outcome of a held or confirmed order is unknown, so the dashboard uses risk x cost, and the back-test checks the buckets against real outcomes.
- **Rejected**: showing only "Rs saved" - it hides what cancelling genuine customers costs; the founder needs the net.
