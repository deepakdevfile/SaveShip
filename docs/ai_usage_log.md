# AI usage log

> DRAFT written from the build session - edit anything that doesn't match what you personally did before submitting.

## Tools and what I used them for
- **Claude (chat, with a code sandbox)** - the only AI tool used. Used for: profiling the CSV and finding RTO drivers; writing the cleaning / model / engine / WhatsApp / dashboard code; drafting the config comments, decision log, README and memo; unit tests.
- **Runtime AI inside the product**: an LLM (default `claude-haiku-5-5`) is *designed* to judge grey-zone addresses and names. In this build it was **not run against the real API** (no key in the sandbox); the offline rule-based stand-in produced all numbers, and the live path is covered only by a fake-client test.

## Where the AI was wrong or weak, and how it was caught
1. **Prepaid nudge looked magic.** The first economics model assumed genuine buyers and would-be returners switch to prepaid at the same rate. Result: "nudge" beat "cancel" even at 90% risk, so cancelling was never optimal. That looked too good, so I printed the Rs table by risk level, saw cancel never won, and traced it to the equal-conversion assumption. Fix: would-be returners switch at 30% of the genuine rate, and 15% of them still return after paying. Cancel now wins only above ~85% risk, which matches intuition.
2. **First policy lost money.** With guessed global thresholds (ship <22%, confirm <34%, nudge <62%) the back-test over 1,987 orders was about -Rs 7.7k net: WhatsApp confirmation costs genuine first-timers (profit + Rs 300 replacement). The AI had picked those numbers by feel, not from the economics. Fix: wrote `suggest_thresholds.py`, which derives the Rs-optimal cut-offs, and made thresholds different for first-time vs repeat customers (net became positive).
3. **Wrong column access.** `df.items` returns the pandas method, not the column, and crashed the exploration script. Fixed with `df['items']`. (Reminder to avoid column names that collide with DataFrame attributes.)
4. **Over-confident claim in the log.** An early draft of the decision log said gradient boosting gave "no better AUC" without having run it. I ran it (0.733 vs 0.736 for logistic regression) and kept the claim only because the number supported it.
5. **Hidden data traps the AI's first pass missed.** The 30 duplicate rows, `Rto` / `delivered` spellings, `+91` phone formats (which look like "wrong length" but are valid) and zero-value orders only showed up after profiling values rather than types. The 15-character phones are fine; the 9-digit ones (47% RTO) are not.

## What I checked myself
- Cost of an RTO re-derived by hand (Rs 169.4); the Rs identity `net = saved + recovered - lost - costs = EV(action) - EV(ship)` is a unit test.
- Back-test uses out-of-fold or time-split scores so the model never scores orders it was trained on.
- Pincode-level blocking (Ops' idea) was rejected after checking the data: 1,066 pincodes, only 30 with 5+ orders.
