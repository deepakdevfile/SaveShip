"""WhatsApp confirmation / prepaid-nudge flow (mock - no real WhatsApp account needed).

Design in one paragraph
  Message goes out within 5 minutes of the order, but only between 9am and 9pm (else 9am next day).
  Language: Hinglish (Roman script) for Hindi-belt states, simple English elsewhere - set in config/rules.yaml.
  Customer replies are read by plain keyword rules first (yes / haan / 1 ...). An LLM can be plugged in via
  `intent_fn` for free-text we cannot read, but the default flow never needs it.
  No reply: reminder after 6h, decision after 24h (cancel if risk is above the line in rules.yaml, else ship COD).
"""
import re, datetime as dt
from dataclasses import dataclass, field
from .engine import load_rules

YES = {"yes", "y", "yep", "yeah", "ya", "haan", "han", "ha", "haa", "ji", "ji haan", "ok", "okay", "confirm", "confirmed",
       "theek", "thik", "theek hai", "sahi", "done", "1"}
NO = {"no", "n", "nahi", "nahin", "nhi", "nope", "cancel", "cancel kardo", "cancel karo", "mat bhejo", "2"}
PAY = {"pay", "paid", "link", "online", "prepaid", "upi", "pay now", "yes", "haan", "1", "ok", "okay", "ha", "ji"}
KEEP_COD = {"cod", "cash", "no", "nahi", "nhi", "2", "later", "baad me"}

T = {
 "confirm_cod": {
  "hinglish": "Namaste {name}! Aapka {brand} order #{oid} (Rs {value:,.0f}) COD ke saath ready hai.\nShip karne se pehle confirm karein:\nReply *1* = Haan, bhej do\nReply *2* = Cancel",
  "en": "Hi {name}! Your {brand} order #{oid} (Rs {value:,.0f}, cash on delivery) is ready.\nPlease confirm before we ship:\nReply *1* = Yes, ship it\nReply *2* = Cancel"},
 "prepaid_offer": {
  "hinglish": "Namaste {name}! Aapka {brand} order #{oid} (Rs {value:,.0f}) ready hai.\nOnline pay karein aur *Rs {disc:.0f} off* payein (sirf Rs {pay:,.0f}) + fast dispatch.\nReply *1* = Pay online (link bhejte hain)\nReply *2* = COD hi rakhein",
  "en": "Hi {name}! Your {brand} order #{oid} (Rs {value:,.0f}) is ready.\nPay online and get *Rs {disc:.0f} off* (just Rs {pay:,.0f}) + priority dispatch.\nReply *1* = Pay online (we'll send a link)\nReply *2* = Keep cash on delivery"},
 "prepaid_offer_repeat": {
  "hinglish": "Namaste {name}! Is baar aapke order #{oid} (Rs {value:,.0f}) ke liye hum sirf online payment le rahe hain, aur *Rs {disc:.0f} off* de rahe hain (Rs {pay:,.0f}).\nReply *1* = Pay online\nReply *2* = Order cancel",
  "en": "Hi {name}! For order #{oid} (Rs {value:,.0f}) we can only accept online payment this time - with *Rs {disc:.0f} off* (Rs {pay:,.0f}).\nReply *1* = Pay online\nReply *2* = Cancel order"},
 "address_fix": {
  "hinglish": "Namaste {name}! Aapke order #{oid} ka address poora nahi hai ('{addr}'). Courier ko ghar dhundhne ke liye kripya poora address bhejein: ghar/flat number, gali/society, landmark, pincode.",
  "en": "Hi {name}! The address on order #{oid} looks incomplete ('{addr}'). Please reply with the full address: house/flat no., street/society, landmark, pincode."},
 "hold_recover": {
  "hinglish": "Namaste! Hum aapka order #{oid} verify nahi kar paaye. Kripya apna poora naam aur address bhejein, hum turant dispatch kar denge.",
  "en": "Hi! We couldn't verify order #{oid}. Please reply with your full name and address and we'll dispatch right away."},
 "reminder": {
  "hinglish": "Reminder: order #{oid} abhi bhi aapke jawab ka intezaar kar raha hai. {ask}",
  "en": "Reminder: order #{oid} is still waiting for your reply. {ask}"},
 "ack_confirm": {"hinglish": "Shukriya! Order #{oid} confirm ho gaya - aaj hi dispatch hoga.", "en": "Thank you! Order #{oid} is confirmed and ships today."},
 "ack_cancel": {"hinglish": "Theek hai, order #{oid} cancel kar diya. Kabhi bhi dobara order kar sakte hain!", "en": "No problem - order #{oid} is cancelled. Come back any time!"},
 "pay_link": {"hinglish": "Ye lijiye payment link: https://pay.example/{oid} (Rs {pay:,.0f}). Payment ke baad order turant dispatch hoga.", "en": "Here's your payment link: https://pay.example/{oid} (Rs {pay:,.0f}). We dispatch right after payment."},
 "fallback_cod": {"hinglish": "Koi baat nahi! COD hi rakhte hain. Kya order #{oid} ship kar dein?\nReply *1* = Haan  |  *2* = Cancel", "en": "No problem - we'll keep COD. Shall we ship order #{oid}?\nReply *1* = Yes  |  *2* = Cancel"},
 "unclear": {"hinglish": "Maaf kijiye, samajh nahi aaya. Kripya *1* (haan) ya *2* (nahi) reply karein.", "en": "Sorry, I didn't catch that. Please reply *1* (yes) or *2* (no)."},
 "handoff": {"hinglish": "Humari team aapko jaldi call karegi. Dhanyavaad!", "en": "Our team will call you shortly. Thank you!"},
 "expired_cancel": {"hinglish": "Humein jawab nahi mila, isliye order #{oid} abhi hold par hai. Dobara order karne ke liye reply karein *1*.", "en": "We didn't hear back, so order #{oid} is on hold. Reply *1* any time to reactivate it."},
 "expired_ship": {"hinglish": "Order #{oid} aaj dispatch ho raha hai (COD). Kuch badalna ho to turant reply karein.", "en": "Order #{oid} is shipping today (COD). Reply right away if you need changes."},
}

@dataclass
class Msg:
    at: dt.datetime
    who: str          # 'bot' or 'customer' or 'system'
    text: str

@dataclass
class Conversation:
    order: dict                    # order_id, customer_name, city, state, address, order_value, risk, ...
    decision: dict                 # action, discount_rs, cod_blocked, message_template
    now: dt.datetime
    brand: str = "KT Haircare"   # placeholder - set whatsapp.brand_name in config/rules.yaml
    state: str = "NEW"
    log: list = field(default_factory=list)
    unclear: int = 0
    started_at: dt.datetime | None = None
    reminded: bool = False
    final: str = ""                # SHIP_COD | SHIP_PREPAID_PENDING | CANCELLED | HANDOFF | ""
    intent_fn: object = None       # optional LLM classifier: fn(text, context)->'yes'|'no'|'other'
    rules: dict = field(default_factory=load_rules)

    def __post_init__(self):
        self.brand = self.rules.get('whatsapp', {}).get('brand_name', self.brand)

    # -------- helpers
    @property
    def lang(self):
        return "hinglish" if self.order.get("state") in self.rules["whatsapp"]["hinglish_states"] else "en"

    def _fmt(self, key, **extra):
        o, d = self.order, self.decision
        disc = float(d.get("discount_rs") or 0)
        return T[key][self.lang].format(name=str(o["customer_name"]).split()[0].title() if not o.get("name_fake") else "there",
                                        oid=o["order_id"], value=o["order_value"], disc=disc, pay=o["order_value"] - disc,
                                        brand=self.brand, addr=str(o["address"])[:30], **extra)

    def _bot(self, text): self.log.append(Msg(self.now, "bot", text))

    def _send_time(self, t):
        w = self.rules["whatsapp"]; lo, hi = w["send_window_start_hour"], w["send_window_end_hour"]
        if t.hour < lo: return t.replace(hour=lo, minute=0)
        if t.hour >= hi: return (t + dt.timedelta(days=1)).replace(hour=lo, minute=0)
        return t

    # -------- lifecycle
    def start(self):
        """Called ~5 minutes after the order is placed."""
        self.started_at = self._send_time(self.order["placed_at"] + dt.timedelta(minutes=5))
        self.now = self.started_at
        act, tmpl = self.decision["action"], self.decision.get("message_template") or ""
        if act == "HOLD_CANCEL":
            key, self.state = "hold_recover", "AWAIT_DETAILS"
        elif tmpl == "address_fix":
            key, self.state = "address_fix", "AWAIT_ADDRESS"
        elif act == "NUDGE_TO_PREPAID":
            key, self.state = ("prepaid_offer_repeat" if self.decision.get("cod_blocked") and tmpl == "prepaid_offer_repeat" else "prepaid_offer"), "AWAIT_PREPAID"
        else:
            key, self.state = "confirm_cod", "AWAIT_CONFIRM"
        self._bot(self._fmt(key)); return self

    def _intent(self, text):
        t = re.sub(r"[^\w\s]", "", text.lower()).strip()
        if self.state in ("AWAIT_PREPAID",):
            if t in PAY: return "pay"
            if t in KEEP_COD: return "keep_cod"
        else:
            if t in YES: return "yes"
            if t in NO: return "no"
        if self.intent_fn:                      # optional LLM for free text (Hinglish etc.)
            r = self.intent_fn(text, self.state)
            if r in ("yes", "no", "pay", "keep_cod"): return r
        return "other"

    def reply(self, text, at=None):
        if self.final: return self
        self.now = at or self.now + dt.timedelta(minutes=2)
        self.log.append(Msg(self.now, "customer", text))
        oid = self.order["order_id"]
        if self.state in ("AWAIT_ADDRESS", "AWAIT_DETAILS"):
            if len(text) >= 15 and re.search(r"\d", text):
                self.order["address"] = text; self.state, self.final = "DONE", "SHIP_COD"
                self._bot(self._fmt("ack_confirm")); self.log.append(Msg(self.now, "system", "Address updated -> order released to ship"))
                return self
            return self._unclear()
        intent = self._intent(text)
        if self.state == "AWAIT_PREPAID":
            if intent == "pay":
                self.state, self.final = "DONE", "SHIP_PREPAID_PENDING"; self._bot(self._fmt("pay_link"))
                self.log.append(Msg(self.now, "system", "Payment link sent; ships after payment (unpaid link expires in 12h -> falls back to COD confirm)"))
            elif intent == "keep_cod":
                if self.decision.get("cod_blocked"):
                    self.state, self.final = "DONE", "CANCELLED"; self._bot(self._fmt("ack_cancel"))
                else:
                    self.state = "AWAIT_CONFIRM"; self._bot(self._fmt("fallback_cod"))
            else: return self._unclear()
        else:  # AWAIT_CONFIRM
            if intent == "yes": self.state, self.final = "DONE", "SHIP_COD"; self._bot(self._fmt("ack_confirm"))
            elif intent == "no": self.state, self.final = "DONE", "CANCELLED"; self._bot(self._fmt("ack_cancel"))
            else: return self._unclear()
        self.unclear = 0
        return self

    def _unclear(self):
        self.unclear += 1
        if self.unclear >= self.rules["whatsapp"]["max_unclear_replies"]:
            self.state, self.final = "DONE", "HANDOFF"; self._bot(self._fmt("handoff"))
            self.log.append(Msg(self.now, "system", "Two unclear replies -> task created for a human to call the customer"))
        elif self.state == "AWAIT_PREPAID":
            self._bot("Reply *1* to pay online with the discount, or *2* to keep cash on delivery." if self.lang == "en"
                      else "Kripya *1* (online pay, discount ke saath) ya *2* (COD) reply karein.")
        else:
            self._bot(self._fmt("unclear"))
        return self

    def advance(self, hours):
        """Move the clock forward; fires reminder at 6h and the 24h decision."""
        if self.final: return self
        w = self.rules["whatsapp"]
        target = self.now + dt.timedelta(hours=hours)
        rem_at = self.started_at + dt.timedelta(hours=w["reminder_after_hours"])
        end_at = self.started_at + dt.timedelta(hours=w["give_up_after_hours"])
        if not self.reminded and self.now < rem_at <= target:
            self.reminded = True; self.now = rem_at
            ask = {"AWAIT_PREPAID": "Reply 1 to pay online / 2 to keep COD.", "AWAIT_ADDRESS": "Please send your full address.",
                   "AWAIT_DETAILS": "Please send your full name and address."}.get(self.state, "Reply 1 = yes / 2 = cancel.")
            self._bot(self._fmt("reminder", ask=ask))
        if target >= end_at:
            self.now = end_at
            risk = float(self.order.get("risk", 1.0))
            ship_ok = (risk <= w["no_reply_cancel_if_risk_above"] and self.state in ("AWAIT_CONFIRM", "AWAIT_PREPAID")
                       and not self.decision.get("cod_blocked"))
            self.state = "DONE"
            if ship_ok:
                self.final = "SHIP_COD"; self._bot(self._fmt("expired_ship"))
                self.log.append(Msg(self.now, "system", f"No reply in 24h; risk {risk:.0%} <= {w['no_reply_cancel_if_risk_above']:.0%} -> ship COD"))
            else:
                self.final = "CANCELLED"; self._bot(self._fmt("expired_cancel"))
                self.log.append(Msg(self.now, "system", f"No reply in 24h; risk {risk:.0%} above line (or address/COD-block case) -> order held"))
        else:
            self.now = target
        return self
