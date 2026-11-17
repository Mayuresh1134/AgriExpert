"""Prices and where to sell.

Price outlook: national monthly mandi prices since 2002, the crop's usual seasonal swing,
and a 1-6 month forecast with a likely range (ml/train_prices.py).

Best market: every mandi that has reported the crop, with an estimate of what it pays now
(its usual level against the national median x the latest national price), minus the cost
of getting the produce there. With DATA_GOV_API_KEY set, today's actual reports from the
Agmarknet feed on data.gov.in are fetched and used instead of the estimate where available.
"""
from __future__ import annotations

import json
import time
from functools import lru_cache

import requests

from . import geo
from .config import Config, DATA_DIR
from .crops_kb import CROPS
from .recommend import prices

DATA_GOV_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
DEFAULT_TRANSPORT = 3.0  # Rs per quintal per 10 km, a typical tractor-trolley / small truck rate
STORAGE_COST_MONTH_PCT = 1.0  # rough cost of storing a month (bags, losses, interest)
STORABLE = {"wheat", "rice", "maize", "jowar", "bajra", "ragi", "barley", "gram", "tur", "moong", "urad", "masoor",
            "groundnut", "soybean", "mustard", "sunflower", "sesame", "safflower", "castor", "cotton", "jute", "onion",
            "potato", "chilli", "turmeric", "garlic", "coriander"}
_live_cache: dict = {}

# Agmarknet commodity name -> our crop id
COMMODITY = {
    "Onion": "onion", "Potato": "potato", "Tomato": "tomato", "Banana": "banana", "Wheat": "wheat",
    "Paddy(Dhan)(Common)": "rice", "Maize": "maize", "Bengal Gram(Gram)(Whole)": "gram",
    "Bajra(Pearl Millet/Cumbu)": "bajra", "Soyabean": "soybean", "Mustard": "mustard", "Cotton": "cotton",
    "Black Gram (Urd Beans)(Whole)": "urad", "Groundnut": "groundnut", "Jowar(Sorghum)": "jowar",
    "Castor Seed": "castor", "Sesamum(Sesame,Gingelly,Til)": "sesame", "Green Gram (Moong)(Whole)": "moong",
    "Arhar (Tur/Red Gram)(Whole)": "tur", "Barley (Jau)": "barley", "Dry Chillies": "chilli",
    "Lentil (Masur)(Whole)": "masoor", "Jute": "jute", "Corriander seed": "coriander", "Garlic": "garlic",
    "Turmeric": "turmeric", "Ragi (Finger Millet)": "ragi", "Sunflower": "sunflower", "Safflower": "safflower",
}


@lru_cache(maxsize=1)
def mandis() -> dict:
    return json.loads((DATA_DIR / "mandis.json").read_text())


def outlook(crop_id: str) -> dict | None:
    crop = CROPS.get(crop_id)
    if not crop or not crop["mandi"]:
        return None
    entry = prices()["crops"].get(crop["mandi"])
    if not entry:
        return None
    out = {"crop": crop_id, "name": crop["name"], "commodity": crop["mandi"], "msp": crop["msp"],
           "msp_note": crop["msp_note"], "source": prices()["source"], **entry}
    fc = entry.get("forecast") or []
    advice = None
    if fc:
        now = entry["latest"]
        best = max(fc, key=lambda f: f["price"])
        months_ahead = fc.index(best) + 1
        gain = (best["price"] / now - 1) * 100
        storage = STORAGE_COST_MONTH_PCT * months_ahead
        if crop_id in STORABLE and gain > storage + 3:
            advice = {"action": "hold", "months": months_ahead,
                      "text": f"Prices are forecast to rise about {gain:.0f}% by {best['month']}, more than the ~{storage:.0f}% "
                              f"it costs to store that long. If you can store it safely and do not need cash now, holding "
                              f"part of the harvest may pay. The range is wide (₹{best['low']:,}-₹{best['high']:,}), so "
                              f"consider selling in instalments."}
        elif gain < -3:
            advice = {"action": "sell", "text": f"Prices are forecast to ease over the coming months (about {abs((fc[-1]['price'] / now - 1) * 100):.0f}% "
                                                f"by {fc[-1]['month']}). Selling soon after harvest looks sensible."}
        else:
            advice = {"action": "neutral", "text": "No strong move is expected in the next few months. Sell when you need to, "
                                                   "and compare nearby mandis first."}
        if crop["msp"]:
            advice["text"] += f" The MSP is ₹{crop['msp']:,} per quintal; if mandi prices are below it, check for a government procurement centre."
    out["advice"] = advice
    return out


def _live_reports(crop_id: str, state: str) -> list[dict]:
    """Today's reports for the crop in one state from data.gov.in (needs DATA_GOV_API_KEY)."""
    if not Config.DATA_GOV_API_KEY:
        return []
    names = [k for k, v in COMMODITY.items() if v == crop_id]
    key = (crop_id, state)
    if key in _live_cache and time.time() - _live_cache[key][0] < 3600:
        return _live_cache[key][1]
    out = []
    for name in names:
        try:
            resp = requests.get(DATA_GOV_URL, params={"api-key": Config.DATA_GOV_API_KEY, "format": "json", "limit": 500,
                                                      "filters[state.keyword]": state, "filters[commodity]": name}, timeout=10)
            resp.raise_for_status()
            out += resp.json().get("records", [])
        except Exception:
            continue
    _live_cache[key] = (time.time(), out)
    return out


def best_markets(crop_id: str, lat: float, lng: float, state: str | None = None, radius_km: float = 150,
                 transport_rate: float = DEFAULT_TRANSPORT, quantity_q: float | None = None, limit: int = 12) -> dict:
    crop = CROPS.get(crop_id)
    if not crop:
        return {"markets": [], "reason": "Unknown crop"}
    national = prices()["crops"].get(crop["mandi"]) if crop["mandi"] else None
    ref_price = national["latest"] if national else None
    ref_month = national["latest_month"] if national else None
    candidates = mandis()["crops"].get(crop_id, [])

    live = {}
    if state:
        for r in _live_reports(crop_id, state):
            live[(r.get("district", "").strip().lower(), r.get("market", "").strip().lower())] = r

    rows = []
    for m in candidates:
        dist = geo.distance_km(lat, lng, m["lat"], m["lng"]) * 1.25  # road distance is longer than straight line
        if dist > radius_km:
            continue
        lv = live.get((m["district"].lower(), m["market"].lower()))
        if lv:
            price, basis = float(lv.get("modal_price") or 0), f"reported today ({lv.get('arrival_date')})"
        elif m["level"] and ref_price:
            price, basis = m["level"] * ref_price, f"estimate: usual level × {ref_month} national price"
        else:
            price, basis = m["last"]["modal"], f"last report {m['last']['date']}"
        transport = transport_rate * dist / 10
        net = price - transport
        rows.append({"market": m["market"], "district": m["district"], "state": m["state"], "distance_km": round(dist),
                     "price": int(round(price)), "price_basis": basis, "transport_per_q": int(round(transport)),
                     "net_per_q": int(round(net)), "level_pct": round((m["level"] - 1) * 100) if m["level"] else None,
                     "reports": m["reports"], "last_report": m["last"], "lat": m["lat"], "lng": m["lng"],
                     "net_total": int(round(net * quantity_q)) if quantity_q else None})
    rows.sort(key=lambda r: -r["net_per_q"])
    nearest = min(rows, key=lambda r: r["distance_km"]) if rows else None
    for r in rows:
        r["gain_vs_nearest_per_q"] = r["net_per_q"] - nearest["net_per_q"] if nearest else 0
    return {"crop": crop_id, "name": crop["name"], "reference_price": ref_price, "reference_month": ref_month,
            "msp": crop["msp"], "transport_rate": transport_rate, "radius_km": radius_km,
            "markets": rows[:limit], "nearest": nearest, "total_found": len(rows),
            "live": bool(live), "snapshot_dates": mandis()["meta"]["dates"],
            "note": "Prices are estimates from past Agmarknet reports scaled to the latest national price. "
                    "Call the mandi or check enam.gov.in before travelling."}
