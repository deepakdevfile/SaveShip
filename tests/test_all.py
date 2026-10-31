import copy, datetime as dt, unittest, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import pandas as pd
from src.econ import Econ, load as load_econ
from src.impact import order_impact
from src.engine import Engine, load_rules, SHIP, CONFIRM, NUDGE, HOLD
from src.whatsapp import Conversation
from src import llm_checks

class FakeModel:      # stand-in so engine tests don't depend on training
    import numpy as np
    coef_ = __import__("numpy").zeros((1, 11))

def row(**kw):
    r = dict(order_id="T1", customer_name="Asha Verma", address="B-1, Green Society, MG Road", city="Pune", state="Maharashtra",
             order_value=649.0, first_order=True, customer_prior_orders=0, customer_prior_rto=0, phone_valid=True,
             address_quality="complete", name_fake=False, utm_source="direct")
    r.update(kw); return pd.Series(r)

class T(unittest.TestCase):
    def setUp(self):
        self.eng = Engine(FakeModel(), {}, rules=load_rules(), econ=Econ())

    def test_rto_cost_matches_brief(self):          # 65+65+25+0.08*180 = 169.4
        self.assertAlmostEqual(Econ().L, 169.4)

    def test_impact_identity(self):                 # net == EV(action) - EV(ship) for every action
        e = Econ()
        for first in (True, False):
            for p in (0.1, 0.4, 0.8):
                v = 649
                self.assertAlmostEqual(sum(order_impact(e, CONFIRM, p, v, first)[k] * s for k, s in
                    [("saved_rto", 1), ("recovered_sales", 1), ("lost_genuine", -1), ("costs", -1)]), e.ev_confirm(p, v, first) - e.ev_ship(p, v, first))
                self.assertAlmostEqual(sum(order_impact(e, HOLD, p, v, first)[k] * s for k, s in
                    [("saved_rto", 1), ("lost_genuine", -1)]), e.ev_cancel(p, v, first) - e.ev_ship(p, v, first))

    def test_bands(self):
        self.assertEqual(self.eng.decide(row(first_order=False), 0.10).action, SHIP)
        self.assertEqual(self.eng.decide(row(first_order=False), 0.28).action, CONFIRM)
        self.assertEqual(self.eng.decide(row(first_order=False), 0.55).action, NUDGE)
        self.assertEqual(self.eng.decide(row(first_order=False), 0.90).action, HOLD)

    def test_first_time_protection(self):           # same risk: repeat customer is held, first-timer is nudged
        self.assertEqual(self.eng.decide(row(first_order=False), 0.85).action, HOLD)
        self.assertEqual(self.eng.decide(row(first_order=True), 0.85).action, NUDGE)

    def test_thresholds_editable_without_code(self):
        r = copy.deepcopy(load_rules()); r["risk_bands"]["repeat_customers"]["ship_as_is_below"] = 0.60
        r["risk_bands"]["repeat_customers"]["confirm_below"] = 0.61
        eng = Engine(FakeModel(), {}, rules=r, econ=Econ())
        self.assertEqual(eng.decide(row(first_order=False), 0.40).action, SHIP)

    def test_repeat_offender_blocks_cod(self):
        d = self.eng.decide(row(first_order=False, customer_prior_rto=2), 0.30)
        self.assertEqual(d.action, NUDGE); self.assertTrue(d.cod_blocked)

    def test_junk_address_gets_address_request_not_cancel(self):
        d = self.eng.decide(row(address="xyz", address_quality="unusable"), 0.70)
        self.assertEqual((d.action, d.message_template), (CONFIRM, "address_fix"))

    def test_fake_name_and_junk_address_held(self):
        self.assertEqual(self.eng.decide(row(address="xyz", address_quality="unusable", name_fake=True), 0.5).action, HOLD)

    def test_llm_not_called_for_clear_cases(self):
        calls = []
        llm_checks.assess("Asha Verma", "B-12, Green Park Society, MG Road", "Pune", "MH", 411001, client_fn=lambda *a: calls.append(a))
        llm_checks.assess("asdf", ".", "Pune", "MH", 411001, client_fn=lambda *a: calls.append(a))
        self.assertEqual(calls, [])

    def test_llm_failure_never_blocks(self):
        def boom(*a): raise RuntimeError("api down")
        r = llm_checks.assess("Zed Quux", "ph krke aana, test mandir ke paas %s" % dt.datetime.now().timestamp(), "Pune", "MH", 411001, client_fn=boom)
        self.assertIn("offline", r["source"])

    # ---- WhatsApp flow
    def conv(self, action="SHIP_AFTER_CONFIRMATION", risk=0.3, tmpl="confirm_cod", blocked=False, hour=14):
        o = dict(order_id="T1", customer_name="Asha Verma", city="Pune", state="Maharashtra", address="B-1 Road", order_value=649.0,
                 risk=risk, placed_at=dt.datetime(2026, 9, 30, hour, 0))
        return Conversation(o, dict(action=action, discount_rs=40, cod_blocked=blocked, message_template=tmpl), dt.datetime.now()).start()

    def test_yes_no_random_silence(self):
        self.assertEqual(self.conv().reply("yes").final, "SHIP_COD")
        self.assertEqual(self.conv().reply("2").final, "CANCELLED")
        c = self.conv().reply("hmm what"); self.assertEqual(c.final, ""); self.assertEqual(c.reply("??").final, "HANDOFF")
        self.assertEqual(self.conv(risk=0.5).advance(24).final, "CANCELLED")
        self.assertEqual(self.conv(risk=0.2).advance(24).final, "SHIP_COD")

    def test_night_order_waits_for_morning(self):
        c = self.conv(hour=23); self.assertEqual(c.started_at.hour, 9); self.assertEqual(c.started_at.day, 1)

    def test_prepaid_flow(self):
        c = self.conv("NUDGE_TO_PREPAID", 0.5, "prepaid_offer"); c.reply("1"); self.assertEqual(c.final, "SHIP_PREPAID_PENDING")
        c = self.conv("NUDGE_TO_PREPAID", 0.5, "prepaid_offer"); c.reply("2"); self.assertEqual(c.state, "AWAIT_CONFIRM")  # falls back to confirm
        c = self.conv("NUDGE_TO_PREPAID", 0.5, "prepaid_offer_repeat", blocked=True); c.reply("2"); self.assertEqual(c.final, "CANCELLED")

    def test_address_fix(self):
        c = self.conv(tmpl="address_fix"); c.reply("Flat 4B, Shanti Nagar, near Metro, Pune 411001")
        self.assertEqual(c.final, "SHIP_COD")

if __name__ == "__main__":
    unittest.main(verbosity=1)
