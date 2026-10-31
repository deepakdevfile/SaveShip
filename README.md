# COD Risk Guard - decide what to do with every Cash-on-Delivery order before it ships

Takes a new COD order and returns one of four actions - **Ship as-is / Ship after confirmation / Nudge to prepaid / Hold-cancel** -
with a one-line reason an ops person can read, plus a WhatsApp flow mock and a morning dashboard.

## Run it (about 5 minutes)

```bash
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m src.run_batch        # cleans data, trains model, decides all ~2,000 historical orders -> output/decisions.csv
python -m unittest tests.test_all   # 14 tests, a few seconds
python app.py                  # then open http://127.0.0.1:5000
```

| URL | What it is |
|---|---|
| `/` | **Founder dashboard** - 4 buckets, Rs saved, Rs lost, net. Defaults to the latest day in the data (30 Sep 2026 = "yesterday"); pick any day from the drop-down |
| `/chat` | **WhatsApp simulator** - pick an order, reply 1 / 2 / haan / random text, or jump the clock +6h / +24h |
| `POST /api/decide` | Score one new order (JSON in, decision out) |

Score one order from the terminal:
```bash
python -m src.score '{"order_id":"KT999","customer_name":"Asha Verma","phone":"9876543210","address":"near station","city":"Patna","state":"Bihar","pincode":800001,"order_value":799,"items":"Hair Oil 100ml","num_items":1,"customer_prior_orders":0,"customer_prior_rto":0,"utm_source":"meta_ads"}'
```

Other commands: `python -m src.backtest` (train Apr-Aug, score Sep, compare policies in Rs -> `output/backtest.json`),
`python -m src.suggest_thresholds` (Rs-optimal cut-offs), `python -m src.discount_table` (-> `docs/discount_maths.md`).

## Changing the rules WITHOUT touching code
Edit **`config/rules.yaml`** (risk cut-offs, first-order protection, repeat-offender rule, discount limits, WhatsApp timings) and
**`config/economics.yaml`** (costs and the assumptions behind the Rs numbers). Save, re-run `python -m src.run_batch` (or restart `app.py`). Every setting has a plain-English comment.

## Where the LLM is used, and where it is not
| Job | Tool | Why |
|---|---|---|
| Is this address findable? ("ph krke aana, Water Tank ke paas") Is this name fake? Hinglish landmarks | **LLM** (`src/llm_checks.py`) | No fixed pattern; needs language understanding |
| Phone format, duplicates, "." / "xyz" addresses, structured addresses, missing pincode | **Code** | A regex is cheaper, faster, and never wrong in a surprising way. A code gate settles ~76% of orders before the LLM is considered |
| RTO probability | **Logistic regression** | Explainable, calibrated, needs no API call. (An LLM cannot know our return rates) |
| Rs maths, thresholds, discount size | **Code** (`src/econ.py`) | Arithmetic |
| Reading "yes / haan / 1 / nahi" | **Code**, with an optional LLM hook for free text | Keyword rules handle the common replies |

**No API key? It still runs.** Without `ANTHROPIC_API_KEY` the grey-zone addresses use an offline rule-based stand-in.
To use the real LLM: `pip install anthropic`, `export ANTHROPIC_API_KEY=...`, delete `output/llm_cache.json`, re-run. Results are cached per order. If the API fails, the order is never blocked - it falls back to the offline judge.
> Honest note: the live-LLM call path was written and unit-tested with a fake client, but **not run against the real API** in the environment where this was built.

## Repo map
```
config/rules.yaml, economics.yaml   <- the only files a non-engineer edits
src/clean.py        data cleaning (dupes, phone formats, missing values)
src/llm_checks.py   code gate + LLM (or offline fallback) for address & name
src/features.py     model inputs        src/model.py   risk model + back-test AUC/calibration
src/econ.py         all Rs maths        src/impact.py  Rs saved / lost / net per decision
src/engine.py       risk + rules -> action + reason
src/whatsapp.py     conversation state machine + message templates (Hinglish / English)
src/backtest.py     Ops-policy vs ours vs ship-all, in Rs         app.py  dashboard + chat + API
docs/               decision_log.md, ai_usage_log.md, discount_maths.md, business_memo.pdf
```

## Known limits (also in the memo)
* The sample has no prepaid orders and no WhatsApp history, so **confirmation and prepaid-switch rates are assumptions** (`economics.yaml`). The Rs results move with them - see the sensitivity table in the memo.
* Labels exist only for orders we shipped; held orders never reveal their outcome (hence the 5% control group in `rules.yaml`).
* Brand name in WhatsApp templates is a placeholder (`whatsapp.brand_name`). Real WhatsApp needs Meta-approved templates and customer opt-in.

> Note: `orders_sample.csv` is a sample (~11 orders/day); the dashboard scales nothing, so a real day (~55 COD orders) will show bigger numbers. The memo scales September to a 1,650-order COD month.
