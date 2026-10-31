"""Where the LLM is used - and where it is NOT.

LLM  : judging free-text that has no fixed pattern (is this address something a
       courier could find? is this name fake? what is a Hinglish landmark?).
CODE : everything with a rule or a number (phone format, pincode<->state match,
       junk strings, duplicates, all money maths, risk scoring, thresholds).

A cheap code gate runs first. Only the 'grey zone' goes to the LLM, so cost stays small.
If ANTHROPIC_API_KEY is not set the same function falls back to `offline_judge`
(a rule-based imitation) so the repo runs anywhere. Results are cached on disk.
"""

import os, re, json, hashlib, pathlib

CACHE = pathlib.Path(__file__).resolve().parent.parent / "output" / "llm_cache.json"
MODEL = os.environ.get("LLM_MODEL", "claude-haiku-5-5")
JUNK_ADDR = {".", "xyz", "home", "near station", "call me", "na", "n/a", "-", "x", "abc", "test", "asdf", "none", "address"}
FAKE_TOKENS = {"test", "asdf", "qwerty", "abc", "xyz", "aaa", "na", "demo", "fake", "dummy", "name", "user", "hjk", "zzz"}
STRUCTURED = re.compile(r"^(b-\d+|house no\.|\d+/\d+|flat \d+)", re.I)

PROMPT = """You check Indian COD order details for a haircare brand. Input may be Hinglish
(Hindi written in Roman letters). Return ONLY JSON:
{{"address_quality":"complete|partial|unusable","name_fake":true|false,"reason":"<=15 words"}}
- complete: house/flat number AND locality a courier can find.
- partial: only a landmark / directions / house nickname, no house number or street.
- unusable: placeholder, city name only, or no way to find the place.
- name_fake: keyboard mash, 'test', 'asdf', single junk word, not a plausible person name.
Name: {name}
Address: {address}
City: {city}, State: {state}, Pincode: {pincode}"""

def _cache():
    return json.loads(CACHE.read_text()) if CACHE.exists() else {}

def code_gate(name, address, city):
    """Return a verdict if code alone is certain, else None (-> ask the LLM)."""
    a = str(address).strip().lower()
    n = str(name).strip()
    verdict = {}
    if a in JUNK_ADDR or len(a) < 8 or a == str(city).strip().lower():
        verdict["address_quality"] = "unusable"
    elif STRUCTURED.match(a):
        verdict["address_quality"] = "complete"
    toks = {t.lower() for t in n.split()}
    if toks & FAKE_TOKENS or len(n) < 3 or len(set(n.lower().replace(" ", ""))) <= 2:
        verdict["name_fake"] = True
    elif re.fullmatch(r"[A-Z][a-z]+ [A-Z][a-z]+", n):
        verdict["name_fake"] = False
    return verdict if len(verdict) == 2 else (verdict or None)

def offline_judge(name, address, city):
    """Rule-based stand-in for the LLM (used when no API key is set)."""
    a = str(address).strip().lower()
    q = "partial"
    if "ghar ka naam" in a or "ke paas" in a or "ke saamne" in a or "ke peeche" in a or "krke aana" in a \
       or "chowk se left" in a or "gali no" in a:
        q = "partial"
    n = str(name).strip()
    fake = not re.fullmatch(r"[A-Z][a-z]+ [A-Z][a-z]+", n)
    return {"address_quality": q, "name_fake": fake, "reason": "offline rule-based judge"}

def llm_judge(name, address, city, state, pincode):
    import anthropic  # pip install anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(model=MODEL, max_tokens=120, messages=[{
        "role": "user", "content": PROMPT.format(name=name, address=address, city=city, state=state, pincode=pincode)}])
    txt = msg.content[0].text.strip().strip("`").replace("json", "", 1)
    return json.loads(txt)

def assess(name, address, city, state, pincode, use_llm=None, client_fn=None):
    """Main entry. Returns dict(address_quality, name_fake, reason, source)."""
    gate = code_gate(name, address, city)
    if gate and len(gate) == 2:
        return {**gate, "reason": "clear-cut by code rules", "source": "code"}
    key = hashlib.md5(f"{name}|{address}|{city}".encode()).hexdigest()
    cache = _cache()
    if key in cache:
        return {**cache[key], "source": cache[key].get("source", "cache")}
    use_llm = bool(os.environ.get("ANTHROPIC_API_KEY")) if use_llm is None else use_llm
    fn = client_fn or (llm_judge if use_llm else None)
    try:
        res = fn(name, address, city, state, pincode) if fn else offline_judge(name, address, city)
        res["source"] = "llm" if fn else "offline"
    except Exception as e:                        # never block an order because the LLM failed
        res = offline_judge(name, address, city); res["source"] = f"offline (llm error: {type(e).__name__})"
    if gate:                                     # code's certain half overrides
        res.update(gate)
    cache[key] = res 
    CACHE.parent.mkdir(exist_ok=True); CACHE.write_text(json.dumps(cache))
    return res