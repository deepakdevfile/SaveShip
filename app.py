"""Run:  python app.py   then open http://localhost:5000  (dashboard)  and  /chat  (WhatsApp simulator)."""
import datetime as dt, os, pandas as pd
from flask import Flask, jsonify, request, render_template_string, abort
from src.whatsapp import Conversation
from src.engine import ACTION_LABEL, SHIP, CONFIRM, NUDGE, HOLD
from src.run_batch import run

app = Flask(__name__)
CSV = "output/decisions.csv"
if not os.path.exists(CSV):
    run()

def load():
    d = pd.read_csv(CSV, parse_dates=["order_datetime"])
    d["date"] = d["order_datetime"].dt.date.astype(str)
    return d

# ------------------------------------------------------------------ dashboard
def summarise(d, day):
    x = d[d.date == day]
    counts = {a: int((x.action == a).sum()) for a in (SHIP, CONFIRM, NUDGE, HOLD)}
    sums = {k: float(x[k].sum()) for k in ("saved_rto", "recovered_sales", "lost_genuine", "costs", "net")}
    return x, counts, sums

@app.route("/")
def dashboard():
    d = load(); days = sorted(d.date.unique())
    day = request.args.get("date") or days[-1]            # default = latest day in the data ("yesterday")
    x, counts, s = summarise(d, day)
    last14 = [(k, float(d[d.date == k].net.sum())) for k in days[-14:]]
    total = max(len(x), 1)
    return render_template_string(DASH, day=day, days=days[-30:], n=len(x), counts=counts, s=s, total=total,
                                  labels=ACTION_LABEL, last14=last14, hold_rows=x[x.action == HOLD].head(6).to_dict("records"),
                                  rto_rate=float(x.rto.mean()) if len(x) else 0, order=(SHIP, CONFIRM, NUDGE, HOLD))

# ------------------------------------------------------------------ WhatsApp mock API
CONVOS = {}
def _order(oid):
    d = load(); r = d[d.order_id == oid]
    if r.empty: abort(404)
    r = r.iloc[0]
    return ({**r.to_dict(), "placed_at": r.order_datetime.to_pydatetime(), "risk": float(r.risk_oof)},
            {"action": r.action, "discount_rs": float(r.discount_rs), "cod_blocked": bool(r.cod_blocked),
             "message_template": r.message_template if isinstance(r.message_template, str) else ""})

def _view(c):
    return {"order_id": c.order["order_id"], "state": c.state, "final": c.final, "lang": c.lang,
            "log": [{"at": m.at.strftime("%d %b %H:%M"), "who": m.who, "text": m.text} for m in c.log]}

@app.get("/api/queue")
def queue():
    d = load(); q = d[d.action.isin([CONFIRM, NUDGE, HOLD])].sort_values("order_datetime").tail(40)
    return jsonify([{"order_id": r.order_id, "label": f"{r.order_id} - {r.customer_name} - {r.city} - Rs {r.order_value:.0f} - {ACTION_LABEL[r.action]}",
                     "reason": r.reason} for r in q.itertuples()])

@app.post("/api/chat/start")
def start():
    oid = request.json["order_id"]; o, dec = _order(oid)
    CONVOS[oid] = Conversation(o, dec, dt.datetime.now()).start()
    return jsonify(_view(CONVOS[oid]) | {"reason": o["reason"]})

@app.post("/api/chat/reply")
def reply():
    j = request.json; c = CONVOS.get(j["order_id"]) or abort(404); c.reply(j["text"]); return jsonify(_view(c))

@app.post("/api/chat/advance")
def advance():
    j = request.json; c = CONVOS.get(j["order_id"]) or abort(404); c.advance(float(j["hours"])); return jsonify(_view(c))

@app.post("/api/decide")
def decide_api():
    from src.score import score_new_order
    return jsonify(score_new_order(request.json))

@app.route("/chat")
def chat():
    return render_template_string(CHAT)

# ------------------------------------------------------------------ templates
DASH = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>COD orders - morning view</title><style>
:root{--paper:#f5f6f4;--ink:#17222b;--mute:#5d6b73;--line:#d9dedb;--ship:#1e7f74;--confirm:#b8791b;--nudge:#2f5da8;--hold:#a63d3d;--good:#1e7f74;--bad:#a63d3d}
@media(prefers-color-scheme:dark){:root{--paper:#12181c;--ink:#e8edf0;--mute:#97a5ad;--line:#2a343a;--ship:#4fc1b3;--confirm:#e0a248;--nudge:#7ea6e8;--hold:#e57b7b;--good:#4fc1b3;--bad:#e57b7b}}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:860px;margin:0 auto;padding:28px 20px 60px}
h1{font:400 15px system-ui;color:var(--mute);margin:0 0 6px}
.lead{font:400 34px/1.2 Georgia,'Times New Roman',serif;margin:0 0 28px;max-width:30ch}
.lead b{font-weight:700;color:var(--c)}
form{margin:0 0 22px}select{font:inherit;padding:6px 8px;background:var(--paper);color:var(--ink);border:1px solid var(--line);border-radius:6px}
.bar{display:flex;height:14px;border-radius:7px;overflow:hidden;margin:6px 0 14px;background:var(--line)}
.row{display:grid;grid-template-columns:14px 1fr auto;gap:10px;align-items:baseline;padding:9px 0;border-bottom:1px solid var(--line)}
.dot{width:10px;height:10px;border-radius:50%}.n{font:700 22px Georgia,serif}.sub{color:var(--mute);font-size:13px}
h2{font:600 17px system-ui;margin:34px 0 4px}
table{width:100%;border-collapse:collapse}td{padding:8px 0;border-bottom:1px solid var(--line)}td:last-child{text-align:right;font-variant-numeric:tabular-nums}
tr.total td{font-weight:700;border-bottom:2px solid var(--ink);border-top:2px solid var(--ink)}
.spark{display:flex;align-items:flex-end;gap:4px;height:70px;margin-top:8px}.spark i{flex:1;border-radius:3px 3px 0 0;min-height:2px}
.note{color:var(--mute);font-size:13px;max-width:70ch}a{color:var(--nudge)}
.hold{font-size:14px;margin:6px 0;color:var(--mute)}
</style></head><body><main>
<h1>Cash-on-delivery orders on {{day}} ({{n}} orders; {{'%.0f'|format(rto_rate*100)}}% of them actually came back)</h1>
<p class="lead" style="--c:{{'var(--good)' if s.net>=0 else 'var(--bad)'}}">The system {{'made' if s.net>=0 else 'cost'}} <b>Rs {{'{:,.0f}'.format(s.net|abs)}}</b> {{'more' if s.net>=0 else 'more'}} than shipping everything as-is.</p>
<form><label class="sub">Day&nbsp;<select name="date" onchange="this.form.submit()">{% for k in days|reverse %}<option {{'selected' if k==day}}>{{k}}</option>{% endfor %}</select></label></form>

<h2>Where the orders on {{day}} went</h2>
<div class="bar">{% for a,c in [(order[0],'--ship'),(order[1],'--confirm'),(order[2],'--nudge'),(order[3],'--hold')] %}<span style="width:{{counts[a]/total*100}}%;background:var({{c}})"></span>{% endfor %}</div>
{% for a,c in [(order[0],'--ship'),(order[1],'--confirm'),(order[2],'--nudge'),(order[3],'--hold')] %}
<div class="row"><span class="dot" style="background:var({{c}})"></span><span>{{labels[a]}}<br><span class="sub">{{ {'SHIP_AS_IS':'Low risk, goes out untouched','SHIP_AFTER_CONFIRMATION':'WhatsApp "please confirm" first','NUDGE_TO_PREPAID':'Offered a discount to pay online','HOLD_CANCEL':'Not shipped unless customer fixes details'}[a] }}</span></span><span class="n">{{counts[a]}}</span></div>
{% endfor %}

<h2>Money, in rupees</h2>
<table>
<tr><td>Returns avoided (shipping both ways, packing, damaged stock)</td><td>+ Rs {{'{:,.0f}'.format(s.saved_rto)}}</td></tr>
<tr><td>Sales recovered from would-be returners who paid online</td><td>+ Rs {{'{:,.0f}'.format(s.recovered_sales)}}</td></tr>
<tr><td>Possibly genuine orders lost (held, or never confirmed)</td><td>- Rs {{'{:,.0f}'.format(s.lost_genuine)}}</td></tr>
<tr><td>Discounts, payment fees and WhatsApp messages</td><td>- Rs {{'{:,.0f}'.format(s.costs)}}</td></tr>
<tr class="total"><td>Net impact</td><td>{{'+' if s.net>=0 else '-'}} Rs {{'{:,.0f}'.format(s.net|abs)}}</td></tr></table>
<p class="note">These are estimates: each order's chance of returning (from past data) times the cost of a return, and a lost genuine order is valued at its profit plus Rs 300 to replace the customer. How many people confirm or switch to prepaid is an assumption until we measure it - edit it in <code>config/economics.yaml</code>.</p>

<h2>Net impact, last 14 days</h2>
<div class="spark">{% set mx = (last14|map(attribute=1)|map('abs')|max) or 1 %}{% for k,v in last14 %}<i title="{{k}}: Rs {{'{:,.0f}'.format(v)}}" style="height:{{(v|abs)/mx*100}}%;background:var({{'--good' if v>=0 else '--bad'}})"></i>{% endfor %}</div>
{% if hold_rows %}<h2>Orders on hold</h2>{% for r in hold_rows %}<p class="hold"><b>{{r.order_id}}</b> {{r.customer_name}}, {{r.city}} - {{r.reason}}</p>{% endfor %}{% endif %}
<p class="note" style="margin-top:30px">Thresholds live in <code>config/rules.yaml</code>. WhatsApp simulator: <a href="/chat">/chat</a>.</p>
</main></body></html>"""

CHAT = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WhatsApp simulator</title><style>
:root{--bg:#efeae2;--out:#d9fdd3;--in:#fff;--ink:#111b21}@media(prefers-color-scheme:dark){:root{--bg:#0b141a;--out:#005c4b;--in:#202c33;--ink:#e9edef}}
body{margin:0;font:15px system-ui;background:var(--bg);color:var(--ink)}main{max-width:520px;margin:0 auto;padding:14px}
select,input,button{font:inherit;padding:8px;border-radius:8px;border:1px solid #8884;background:var(--in);color:var(--ink)}select{width:100%}
#why{font-size:13px;opacity:.75;margin:8px 0}#log{min-height:320px;padding:10px 0}
.m{max-width:82%;padding:7px 10px;border-radius:10px;margin:6px 0;white-space:pre-wrap;box-shadow:0 1px 1px #0002}
.bot{background:var(--in)}.customer{background:var(--out);margin-left:auto}.system{background:none;box-shadow:none;font-size:12px;opacity:.7;text-align:center;max-width:100%}
.t{display:block;font-size:11px;opacity:.55}.bar{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}.bar button{flex:none;cursor:pointer}
#send{display:flex;gap:6px}#send input{flex:1}</style></head><body><main>
<h3>WhatsApp flow simulator (mock - no real WhatsApp)</h3>
<select id="q"></select><div id="why"></div><div id="log"></div>
<div class="bar"><button onclick="r('1')">1</button><button onclick="r('2')">2</button><button onclick="r('haan')">haan</button><button onclick="r('nahi')">nahi</button><button onclick="r('kal bhej dena')">random text</button></div>
<div class="bar"><button onclick="adv(6)">+6 hours</button><button onclick="adv(24)">+24 hours (no reply)</button></div>
<form id="send" onsubmit="return s()"><input id="t" placeholder="Type a reply (for address-fix: send full address)"><button>Send</button></form>
<script>
let oid=null;const $=id=>document.getElementById(id);
async function api(p,b){const x=await fetch(p,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});return x.json()}
function draw(v){oid=v.order_id;$('log').innerHTML=v.log.map(m=>`<div class="m ${m.who}">${m.text.replace(/\*(.+?)\*/g,'<b>$1</b>')}<span class="t">${m.who==='system'?'':m.at}</span></div>`).join('')+(v.final?`<div class="m system">Outcome: ${v.final}</div>`:'')}
async function init(){const q=await (await fetch('/api/queue')).json();$('q').innerHTML=q.map(o=>`<option value="${o.order_id}" data-why="${o.reason.replace(/"/g,'&quot;')}">${o.label}</option>`).join('');$('q').onchange=go;go()}
async function go(){const o=$('q').selectedOptions[0];$('why').textContent='Why: '+o.dataset.why;draw(await api('/api/chat/start',{order_id:o.value}))}
async function r(t){if(oid)draw(await api('/api/chat/reply',{order_id:oid,text:t}))}
async function adv(h){if(oid)draw(await api('/api/chat/advance',{order_id:oid,hours:h}))}
function s(){const t=$('t').value.trim();if(t){r(t);$('t').value=''}return false}
init()</script></main></body></html>"""

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=False)
