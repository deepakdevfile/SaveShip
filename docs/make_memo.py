from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
D = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("B", D + "DejaVuSans.ttf")); pdfmetrics.registerFont(TTFont("BB", D + "DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("BI", D + "DejaVuSans-Oblique.ttf"))
pdfmetrics.registerFontFamily("B", normal="B", bold="BB", italic="BI", boldItalic="BB")
INK = colors.HexColor("#17222b"); MUTE = colors.HexColor("#5d6b73"); LINE = colors.HexColor("#c9d0cc"); ACC = colors.HexColor("#1e7f74")
body = ParagraphStyle("b", fontName="B", fontSize=8.1, leading=11, textColor=INK, spaceAfter=3)
bul = ParagraphStyle("bl", parent=body, leftIndent=9, bulletIndent=0, spaceAfter=2)
h = ParagraphStyle("h", fontName="BB", fontSize=10, leading=13, textColor=ACC, spaceBefore=6, spaceAfter=3)
title = ParagraphStyle("t", fontName="BB", fontSize=14.5, leading=18, textColor=INK, spaceAfter=1)
meta = ParagraphStyle("m", parent=body, textColor=MUTE, fontSize=7.6)
cell = ParagraphStyle("c", parent=body, fontSize=7.4, leading=9.4, spaceAfter=0)
cellb = ParagraphStyle("cb", parent=cell, fontName="BB")
def P(t, s=body): return Paragraph(t, s)
def B(t): return Paragraph(t, bul, bulletText="•")
def T(rows, widths, head=True):
    data = [[Paragraph(str(c), cellb if (head and i == 0) else cell) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1)
    st = [("LINEBELOW", (0, 0), (-1, 0), 0.8, INK), ("LINEBELOW", (0, 1), (-1, -1), 0.3, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2), ("LEFTPADDING", (0, 0), (-1, -1), 2)]
    t.setStyle(TableStyle(st)); return t

S = []
S += [P("Memo: what to do with risky Cash-on-Delivery orders", title),
      P("To: Founder &nbsp;|&nbsp; Date: 31 Oct 2026 &nbsp;|&nbsp; Basis: 1,987 past COD orders (Apr–Sep 2026), 28% returned (RTO). Rupee figures are estimates; the assumptions behind them are listed in section 4.", meta), Spacer(1, 3)]
S += [P("<b>The short version.</b> A returned COD order costs us <b>₹169</b>, but a delivered one earns about <b>₹312</b> after shipping and packing. So even an order with a 50% chance of coming back is still worth shipping, and cancelling “risky” orders destroys more profit than it saves. "
        "Had Operations’ rule (cancel risky orders, stop COD in bad areas) been live in September, it would have cost us roughly <b>₹82,000–1,32,000 a month</b>. Doing nothing keeps losing about <b>₹73,000 a month</b> to returns. "
        "The system I built leaves 74% of orders alone, asks a few for WhatsApp confirmation or an online-payment discount, and cancels almost none. It is a <b>modest win (+₹3,500 to +₹9,500 a month)</b>, not a miracle. "
        "How much more it can earn depends on two numbers we have never measured: how many customers confirm on WhatsApp, and how many switch to prepaid.")]

S += [P("1. What surprised me in the data", h)]
S += [B("<b>The problem is small towns, not individual pincodes.</b> Small-town orders return <b>53%</b> of the time vs <b>22%</b> in the seven big metros (Gorakhpur 62%, Bareilly 61%, Darbhanga 59%; Mumbai 18%). "
        "But pincode blacklists would be guesswork: 1,987 orders cover 1,066 different pincodes and only 30 pincodes have five or more orders."),
      B("<b>A junk address is the cheapest warning sign – and half of them still get delivered.</b> 183 orders had an address like “.”, “xyz”, “home”, “call me” or just the city name: <b>62%</b> came back, versus <b>23%</b> for addresses with a house number. "
        "Still, 38% were delivered, so the right move is to ask for the full address, not cancel."),
      B("<b>Marketing is half right.</b> First-time buyers do return more (<b>30%</b> vs <b>14%</b> for repeat customers with a clean record), and first orders from Meta ads return 34%. "
        "But what really predicts a return is a <i>previous</i> return: customers with two earlier returns send back <b>76%</b> of orders (34 orders), one earlier return 35%."),
      B("<b>Shipping a risky COD order usually still pays.</b> Break-even is about 65% risk (≈ 85–90% for a new customer once you count the ₹300 to replace them). Our average COD order is at 28%."),
      B("<b>Orders above ₹1,500 return 39%</b> (281 orders) vs 20% for ₹1,000–1,500. The data was also messy: 30 duplicate rows, status typed four ways, 17 phone numbers with 9 digits (47% returned), 12 missing pincodes.")]

S += [P("2. Recommended rules, and what they would have done to September", h),
      P("Every order gets a risk score (chance of return) from past patterns plus an AI check of the address and name. The cut-offs are in <i>config/rules.yaml</i> and can be edited without code. Scored with a model trained only on April–August (329 September orders):", body),
      T([["Action", "Rule in plain words", "Sept orders", "Actually returned"],
         ["Ship as-is", "Risk under 26% (repeat customers) or 37% (first-time)", "244 (74%)", "18%"],
         ["Ship after WhatsApp confirm", "Slightly higher risk; <b>unusable address</b> (we ask for the full address); anyone who declines the prepaid offer", "37 (11%)", "49%"],
         ["Nudge to prepaid", "Risk up to 82% / 90%. Discount ≈ 4–6% (₹20–40 on a ₹649 order), max 8% or ₹150. <b>2+ earlier returns: COD off, prepaid only</b>", "42 (13%)", "43%"],
         ["Hold / cancel", "Fake name + junk address, or junk address + invalid phone, or risk above 82% (repeat) / 90% (first-time). Held customers get a “send us your details” message", "6 (2%)", "83%"]],
        [33, 90, 22, 29]),
      Spacer(1, 2), P("Sorted this way, the orders we leave alone return 18% against 26% overall, while the orders we hold return 83%. Only 1 of the 6 held orders was actually genuine.")]

S += [P("3. Operations vs Marketing, in rupees (September, scaled to ~1,650 COD orders a month)", h),
      T([["Policy", "Returns avoided", "Genuine sales lost", "Other costs", "Net per month"],
         ["Marketing as-is: ship everything", "₹0", "₹0", "₹0", "₹0 (and ₹73k of returns continue)"],
         ["Operations: cancel risky + stop small-town COD", "+₹38,900", "−₹1,21,000 (−₹1,71,000 incl. ₹300 per lost new customer)", "₹0", "<b>−₹82,000 to −₹1,32,000</b>"],
         ["This system", "+₹20,600 (+₹3,500 sales recovered via prepaid)", "−₹11,900 (−₹17,800 incl. ₹300 per lost new customer)", "−₹2,500 (discounts, fees, WhatsApp)", "<b>+₹3,500 to +₹9,500</b>"]],
        [38, 30, 44, 28, 34]),
      Spacer(1, 2),
      P("Operations’ rule would have cancelled 89 of 329 orders; <b>45 of them (51%) were genuine and 71 were first-time customers</b>. It saves more in returns (₹38,900) but throws away far more in profit. "
        "<b>What each side gets:</b> Operations gets COD switched off for repeat returners (customer-level, which is where the data shows the damage), prepaid-first handling of small-town risk, and no blind shipping to junk addresses. "
        "Marketing gets a hard rule that a first-time customer is never auto-cancelled unless the details are unusable or risk is above 90%, a more lenient first-time cut-off, and a recovery message for anyone held.")]

S += [P("4. What could go wrong, and how we will notice", h),
      B("<b>The confirm and prepaid numbers are assumptions</b> (the sample has no WhatsApp or prepaid data). If WhatsApp barely filters bad orders (75% of would-be returners still confirm), the system loses about ₹400–4,800 a month; if only 20% of customers would ever switch to prepaid it earns about ₹1,400. "
        "<i>We notice:</i> track confirm rate and prepaid take-up in week 1 and replace the assumptions in <i>economics.yaml</i>."),
      B("<b>Held and cancelled orders never reveal what would have happened.</b> 5% of flagged orders ship as-is at random as a control group. <i>We notice:</i> return rate of the “ship as-is” bucket rising above ~24% (it was 18%)."),
      B("<b>The AI misreads an address</b> (not yet tested against the live API; the sample runs on a rule-based stand-in). <i>We notice:</i> spot-check 50 AI-judged addresses a week against courier “address not found” reasons."),
      B("<b>Hurting good customers:</b> extra WhatsApp friction in small towns. <i>We notice:</i> cancellation rate of first-time buyers, complaints, and repeat-purchase rate of confirmed vs unconfirmed customers. Patterns also drift (festivals, new couriers): check predicted vs actual return rate per bucket weekly.")]

S += [P("5. If I had two more weeks", h),
      B("Run a real pilot: A/B test 3% / 5% / 8% prepaid discounts and confirm vs no-confirm, to replace my guesses with measured rates – the single biggest lever on the numbers above."),
      B("Connect Shopify and the WhatsApp Cloud API (approved templates, opt-in), and read courier return-reason codes (“refused”, “address not found”)."),
      B("Fix the root causes at checkout: pincode and address validation, prepaid as the default for small towns, and a small ₹49 advance for high-risk COD orders."),
      B("Add pincode and courier-level signals once we have 12 months of data; evaluate the real AI check on 300 hand-labelled addresses; retrain monthly.")]

doc = SimpleDocTemplate("docs/business_memo.pdf", pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=12 * mm, bottomMargin=11 * mm,
                        title="COD risk memo", author="")
doc.build(S)
