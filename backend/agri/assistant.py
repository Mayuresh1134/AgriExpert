"""Farming assistant.

With GEMINI_API_KEY set, questions go to Gemini together with the farmer's own context (farm,
current crops and stages, this week's weather, prices), so answers are about their field and
not generic. Without a key, a built-in assistant answers the common questions from the app's
own data: weather, prices, what to grow, fertiliser, the current stage, diseases and schemes.
"""
from __future__ import annotations

import re

from . import markets, recommend, weather
from .config import Config
from .core import today
from .crops_kb import CROPS, SEASONS
from .diseases_kb import DISEASES, KISAN_CALL_CENTRE
from .schemes import SCHEMES

LANGUAGES = {"en": "English", "hi": "Hindi", "mr": "Marathi", "ta": "Tamil", "te": "Telugu", "kn": "Kannada",
             "gu": "Gujarati", "pa": "Punjabi", "bn": "Bengali"}

SYSTEM = """You are Krishi Mitra, a practical farming advisor for small and medium farmers in India.
Answer in {language}. Use simple words, short sentences and concrete numbers (doses per litre or
per acre, days, rupees). Prefer low-cost and organic options first, then chemical ones with the
active ingredient and dose. Never invent prices, scheme amounts or weather: use the facts below
and say when you do not know. For pesticide questions remind the farmer to read the label and
wear protection. For serious problems suggest the local KVK or the Kisan Call Centre (1800-180-1551).
Keep answers under 200 words unless the farmer asks for detail.

Facts about this farmer (from the app, current as of {date}):
{context}"""


def _crop_mentioned(text: str) -> str | None:
    t = text.lower()
    aliases = {"paddy": "rice", "dhan": "rice", "chawal": "rice", "gehu": "wheat", "gehun": "wheat", "makka": "maize",
               "corn": "maize", "chana": "gram", "chickpea": "gram", "arhar": "tur", "pigeon": "tur", "tuar": "tur",
               "green gram": "moong", "black gram": "urad", "lentil": "masoor", "masur": "masoor", "sarson": "mustard",
               "rapeseed": "mustard", "til": "sesame", "kapas": "cotton", "ganna": "sugarcane", "pyaz": "onion",
               "kanda": "onion", "aloo": "potato", "tamatar": "tomato", "mirchi": "chilli", "chili": "chilli",
               "haldi": "turmeric", "lahsun": "garlic", "dhaniya": "coriander", "kela": "banana", "soya": "soybean",
               "peanut": "groundnut", "moongphali": "groundnut", "bajri": "bajra", "millet": "bajra", "sorghum": "jowar",
               "jau": "barley", "nachni": "ragi"}
    for cid in CROPS:
        if re.search(rf"\b{cid}\b", t):
            return cid
    for word, cid in aliases.items():
        if re.search(rf"\b{word}\b", t):
            return cid
    return None


def build_context(ctx: dict) -> str:
    lines = []
    farm = ctx.get("farm")
    if farm:
        lines.append(f"- Farm: {farm.get('land_area_acres')} acres in {farm.get('district')}, {farm.get('state')}; "
                     f"soil {farm.get('soil_type') or 'unknown'}"
                     + (f", pH {farm['ph']}" if farm.get("ph") else "")
                     + f"; irrigation {recommend.IRRIGATION.get(farm.get('irrigation'), 'unknown')}.")
    for c in ctx.get("cycles", []):
        lines.append(f"- Growing {CROPS[c['crop']]['name']} on {c.get('area_acres')} acres, sown {c['sowing_date']}, "
                     f"day {c['progress']['day']}, stage: {c['progress']['stage_label']}.")
    fc = ctx.get("weather")
    if fc and fc.get("live"):
        days = "; ".join(f"{d['date']}: {d['summary']}, {d['tmin']:.0f}-{d['tmax']:.0f}°C, rain {d['rain_mm']:.0f} mm"
                         for d in fc["days"][:5] if d["tmax"] is not None)
        lines.append(f"- Weather next days: {days}.")
    for cid in {c["crop"] for c in ctx.get("cycles", [])}:
        o = markets.outlook(cid)
        if o:
            lines.append(f"- {CROPS[cid]['name']} national mandi median {o['latest_month']}: ₹{o['latest']:,}/quintal"
                         + (f"; MSP ₹{o['msp']:,}" if o.get("msp") else "") + ".")
    return "\n".join(lines) or "- No farm profile yet."


def ask_gemini(question: str, history: list[dict], ctx: dict, language: str, image: bytes | None = None) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=Config.GEMINI_API_KEY)
    contents = []
    for h in history[-8:]:
        contents.append(types.Content(role="user" if h["role"] == "user" else "model", parts=[types.Part(text=h["text"])]))
    parts = [types.Part(text=question)]
    if image:
        parts.append(types.Part.from_bytes(data=image, mime_type="image/jpeg"))
    contents.append(types.Content(role="user", parts=parts))
    resp = client.models.generate_content(
        model=Config.GEMINI_MODEL, contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM.format(language=LANGUAGES.get(language, "English"), date=today().isoformat(),
                                             context=build_context(ctx)),
            temperature=0.4, max_output_tokens=900),
    )
    return (resp.text or "").strip() or "Sorry, I could not produce an answer. Please ask again."


# --------------------------------------------------------------------- offline assistant
def _cycle_for(ctx, crop_id):
    for c in ctx.get("cycles", []):
        if crop_id is None or c["crop"] == crop_id:
            return c
    return None


def offline_answer(question: str, ctx: dict) -> dict:
    q = question.lower()
    crop_id = _crop_mentioned(q)
    farm = ctx.get("farm")
    cycle = _cycle_for(ctx, crop_id)
    if crop_id is None and cycle:
        crop_id = cycle["crop"]

    def reply(text, links=None):
        return {"text": text, "links": links or []}

    if re.search(r"\b(hello|hi|namaste|namaskar|hey)\b", q) and len(q) < 30:
        return reply("Namaste! Ask me about your crop's stage, the weather, fertiliser, prices, diseases or government "
                     "schemes. For example: “How much urea for my wheat?” or “What is the onion price?”")

    if re.search(r"\b(weather|rain|rains|raining|barish|baarish|mausam|temperature|forecast|frost|heat ?wave|hot|cold)\b", q):
        fc = ctx.get("weather")
        if not fc or not fc.get("live"):
            return reply("I could not reach the live forecast. Normal rainfall for your district this month is "
                         f"{fc.get('normal_month_rain_mm', '—')} mm." if fc else "Add your farm location first so I can fetch the forecast.",
                         [{"label": "Farm profile", "to": "/farm"}])
        days = fc["days"]
        rain = sum(d["rain_mm"] or 0 for d in days)
        wet = [d for d in days if (d["rain_mm"] or 0) >= 5]
        text = (f"Next 7 days: {min(d['tmin'] for d in days):.0f}-{max(d['tmax'] for d in days):.0f}°C, about {rain:.0f} mm of rain in total. ")
        text += (f"Rain is likely on {', '.join(weather._weekday(d['date']) for d in wet[:3])}. " if wet else "No significant rain expected. ")
        stage = cycle["progress"]["stage"] if cycle else None
        al = weather.alerts(fc, {"id": crop_id, **CROPS[crop_id]} if crop_id else None, stage, (farm or {}).get("irrigation", "limited"))
        if al:
            text += " ".join(f"{a['title']}: {a['text']}" for a in al[:2])
        return reply(text, [{"label": "Full forecast", "to": "/"}])

    if re.search(r"\b(price|prices|rate|rates|bhav|bhaav|mandi|sell|selling|market|markets|msp)\b", q):
        if not crop_id:
            return reply("Which crop? For example: “wheat price” or “onion mandi rate”.", [{"label": "Markets", "to": "/markets"}])
        o = markets.outlook(crop_id)
        if not o:
            return reply(f"I have no mandi price series for {CROPS[crop_id]['name']}."
                         + (f" Its MSP is ₹{CROPS[crop_id]['msp']:,} per quintal." if CROPS[crop_id]["msp"] else ""))
        text = f"{o['name']}: the national median mandi price was ₹{o['latest']:,} per quintal in {o['latest_month']}"
        if o.get("change_12m_pct") is not None:
            text += f" ({'+' if o['change_12m_pct'] >= 0 else ''}{o['change_12m_pct']}% on a year earlier)"
        text += "."
        if o.get("msp"):
            text += f" MSP: ₹{o['msp']:,} ({o['msp_note']})."
        if o.get("best_month"):
            text += f" Prices are usually highest around {o['best_month']} and lowest around {o['worst_month']}."
        if o.get("advice"):
            text += " " + o["advice"]["text"]
        return reply(text, [{"label": f"{o['name']} prices & best mandi", "to": f"/markets?crop={crop_id}"}])

    if re.search(r"\b(schemes?|yojana|subsid\w*|loans?|insurance|bima|pm.?kisan|kcc|credit)\b", q):
        hits = [s for s in SCHEMES if any(w in q for w in (s["id"].replace("_", " "), s["name"].lower().split()[0]))]
        if not hits:
            hits = [s for s in SCHEMES if s["category"] in ("insurance" if "insur" in q or "bima" in q else "",
                                                           "credit" if "loan" in q or "credit" in q else "",
                                                           "irrigation" if "subsid" in q else "")] or SCHEMES[:3]
        text = " ".join(f"{s['name']}: {s['benefit']} Apply: {s['how']}" for s in hits[:2])
        return reply(text, [{"label": "All schemes and eligibility", "to": "/schemes"}])

    if re.search(r"what (should|to|can) i (grow|sow|plant)|which crop|best crop|kya ugaye|recommend", q):
        if not farm:
            return reply("Fill in your farm profile first (district, land, soil, water) and I will rank the crops for you.",
                         [{"label": "Farm profile", "to": "/farm"}])
        season = next((s for s in SEASONS if s in q), None) or recommend.default_season()
        r = recommend.recommend(farm, season)
        top = r["crops"][:3]
        text = f"For {r['season_label']} in {farm['district']}, the best fits are: " + "; ".join(
            f"{c['name']} (score {c['score']}, about ₹{c['profit_acre']:,} profit per acre)" for c in top) + "."
        return reply(text, [{"label": "See the full comparison", "to": f"/recommend?season={season}"}])

    if re.search(r"\b(fertili[sz]ers?|urea|dap|npk|potash|khad|manure|nutrients?)\b", q):
        if not crop_id:
            return reply("Which crop is it for? For example: “fertiliser for wheat”.")
        area = float((cycle or {}).get("area_acres") or (farm or {}).get("land_area_acres") or 1)
        plan = recommend.fertilizer_plan(crop_id, area, (farm or {}).get("soil_status"))
        p = plan["products"]
        sched = "; ".join(f"{s['when']}: " + ", ".join(f"{v:g} kg {k.split('_')[0].upper()}" for k, v in s.items()
                                                       if k.endswith("_kg") and v) for s in plan["schedule"])
        text = (f"For {area:g} acres of {CROPS[crop_id]['name']}: about {p['urea_kg']:g} kg urea, {p['dap_kg']:g} kg DAP and "
                f"{p['mop_kg']:g} kg MOP in total ({p['urea_bags_45kg']} + {p['dap_bags_50kg']} + {p['mop_bags_50kg']} bags). "
                f"Schedule: {sched}. {plan['note']}")
        return reply(text)

    disease_hit = None
    for did, d in DISEASES.items():
        name = d["name"].lower().split(" (")[0]
        if d["kind"] != "healthy" and (name in q or (crop_id and did.startswith(crop_id) and did.split("_", 1)[1].replace("_", " ") in q)):
            disease_hit = d
            break
    if disease_hit:
        d = disease_hit
        text = (f"{d['name']}: {d['symptoms']} Cause: {d['cause']} What to do: {' '.join(d['organic'][:2])} "
                + (f"If needed: {d['chemical'][0]} " if d["chemical"] else "") + f"Prevent: {d['prevention'][0]}")
        return reply(text, [{"label": "Scan a leaf photo", "to": "/scan"}])
    if re.search(r"\b(diseases?|spots?|yellow\w*|leaf|leaves|pests?|insects?|keeda|rog|blight|fungus|curl\w*|wilt\w*)\b", q):
        return reply("Take a clear photo of one affected leaf in daylight and scan it: I will tell you the likely problem "
                     f"and how to treat it. For an urgent problem, call the Kisan Call Centre on {KISAN_CALL_CENTRE} (free).",
                     [{"label": "Scan a leaf", "to": "/scan"}])

    if cycle or re.search(r"\b(stage|what (should|to) i do|next|kaam|tasks?|irrigat\w*|water\w*)\b", q):
        if not cycle:
            return reply("Start tracking a crop and I will tell you what to do at each stage.", [{"label": "My crops", "to": "/crops"}])
        p = cycle["progress"]
        crop = CROPS[cycle["crop"]]
        text = (f"Your {crop['name']} is on day {p['day']}: {p['stage_label'].lower()}. ")
        pending = [t for t in cycle.get("tasks", []) if not t.get("done") and t["stage"] == p["stage"]]
        if pending:
            text += "Next: " + "; ".join(f"{t['title']} — {t['detail']}" for t in pending[:2])
        if crop["critical_water"] and re.search(r"\b(irrigat\w*|water\w*|pani)\b", q):
            text += f" Water matters most at: {', '.join(crop['critical_water'])}."
        return reply(text, [{"label": "Open crop", "to": f"/crops/{cycle['id']}"}])

    return reply("I can help with your crop's stage, weather, fertiliser, prices and best mandi, diseases and "
                 "government schemes. Try: “What should I do this week?” or “Wheat price”. "
                 "(Add a Gemini API key on the server for open-ended questions in your language.)")
