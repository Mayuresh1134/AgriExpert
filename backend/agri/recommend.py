"""Crop recommendation.

For a farm (district, soil, water, land, budget) and a season, every crop the district's
state grows is scored on six things a farmer would weigh, and the scores are added up:

  25%  track record   how many years and how widely the crop has been grown in the district
  15%  yield          the district's expected yield against the national average
  12%  soil           soil type and, if known, soil pH against what the crop likes
  13%  water          normal seasonal rainfall plus irrigation against the crop's water need
  25%  profit         expected yield x current price, minus the cost of cultivation,
                      per month the crop occupies the field
  10%  budget         whether the whole area can be planted within the stated budget

Yields come from the model trained on district statistics (ml/train_yield.py), prices from
the mandi price file (ml/train_prices.py), costs and MSPs from agri/crops_kb.py.
Every number that feeds a score is returned, so the screen can show its working.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache

from . import geo
from .config import DATA_DIR
from .core import today
from .crops_kb import CROPS, SEASONS

Q_PER_ACRE = 10 / 2.471  # tonnes per hectare -> quintals per acre
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WEIGHTS = {"track": 0.25, "yield": 0.15, "soil": 0.12, "water": 0.13, "profit": 0.25, "budget": 0.10}
IRRIGATION = {"none": "Rainfed (no irrigation)", "limited": "Limited (2-3 irrigations)", "assured": "Assured (canal / borewell)"}


@lru_cache(maxsize=1)
def stats() -> dict:
    return json.loads((DATA_DIR / "crop_stats.json").read_text())


@lru_cache(maxsize=1)
def prices() -> dict:
    return json.loads((DATA_DIR / "prices.json").read_text())


def default_season(month: int | None = None) -> str:
    """The season a farmer would be planning for in this month."""
    month = month or today().month
    if 5 <= month <= 8:
        return "kharif"
    if month >= 9 or month == 1:
        return "rabi"
    return "summer"


def stats_district(state: str, district: str) -> tuple[dict, str | None]:
    """A district's crop table. New districts with no records borrow the nearest one in the state."""
    table = stats()["districts"]
    key = f"{state}|{district}"
    if key in table and any(e.get("n", 0) > 0 for s in table[key].values() for e in s.values()):
        return table[key], None
    here = geo.get(state, district)
    if not here:
        return table.get(key, {}), None
    best, best_d = None, 1e9
    for other in geo.districts_of(state):
        k = f"{state}|{other}"
        if other == district or k not in table:
            continue
        if not any(e.get("n", 0) > 0 for s in table[k].values() for e in s.values()):
            continue
        o = geo.get(state, other)
        d = geo.distance_km(here["lat"], here["lng"], o["lat"], o["lng"])
        if d < best_d:
            best, best_d = other, d
    if best:
        return table[f"{state}|{best}"], best
    return table.get(key, {}), None


def price_for(crop_id: str) -> dict:
    """Current selling price per quintal and where the figure comes from."""
    crop = CROPS[crop_id]
    entry = prices()["crops"].get(crop["mandi"]) if crop["mandi"] else None
    out = {"msp": crop["msp"], "msp_note": crop["msp_note"], "market": None, "price": None, "basis": None}
    if entry:
        out["market"] = entry.get("avg3") or entry["latest"]
        out["market_month"] = entry["latest_month"]
        out["change_12m_pct"] = entry.get("change_12m_pct")
        out["volatility_pct"] = entry.get("volatility_pct")
    if out["market"]:
        out["price"], out["basis"] = out["market"], "average mandi price, last 3 months"
        if crop["farmgate"] != 1.0:
            out["price"] = round(out["market"] * crop["farmgate"])
            out["basis"] = f"{round(crop['farmgate'] * 100)}% of the 3-month mandi average (typical farm-gate price)"
    elif crop["msp"]:
        out["price"], out["basis"] = crop["msp"], crop["msp_note"]
    return out


def cost_per_acre(crop_id: str) -> tuple[int, str]:
    crop = CROPS[crop_id]
    if crop["cost_acre"]:
        return int(crop["cost_acre"]), "rough typical figure"
    nat = stats()["national_yield_t_ha"].get(crop_id)
    return int(round(crop["cost_qtl"] * nat * Q_PER_ACRE, -2)), "CACP cost per quintal x national average yield"


def growing_months(crop_id: str, season: str) -> list[int]:
    crop = CROPS[crop_id]
    sow = crop["sow_months"].get(season) or crop["sow_months"].get("annual") or SEASONS.get(season, {}).get("sow_months") or [6]
    start = sow[0]
    n = max(1, math.ceil(crop["days"]["maturity"] / 30))
    return [((start - 1 + i) % 12) + 1 for i in range(min(n, 12))]


def _soil_score(crop: dict, soil_type: str | None, ph: float | None) -> tuple[float, str | None, str | None]:
    good = caution = None
    score = 0.7
    if soil_type:
        if soil_type in crop["soils"][:2]:
            score, good = 1.0, f"Does best on {soil_type} soil like yours"
        elif soil_type in crop["soils"]:
            score = 0.8
        else:
            score, caution = 0.35, f"Prefers {', '.join(crop['soils'][:3])} soil, not {soil_type}"
    if ph is not None:
        lo, hi = crop["ph"]
        if lo <= ph <= hi:
            pass
        elif lo - 0.5 <= ph <= hi + 0.5:
            score *= 0.7
            caution = caution or f"Soil pH {ph:g} is just outside its range ({lo:g}-{hi:g})"
        else:
            score *= 0.3
            caution = f"Soil pH {ph:g} is well outside its range ({lo:g}-{hi:g})"
    return score, good, caution


def _water_score(crop: dict, crop_id: str, season: str, rain: list[float] | None, irrigation: str):
    need = crop["water_mm"][0]
    months = growing_months(crop_id, season)
    season_rain = sum(rain[m - 1] for m in months) if rain else None
    if irrigation == "assured":
        return 1.0, season_rain, None
    if season_rain is None:
        return 0.6, None, None
    supply = season_rain * 0.7 + (200 if irrigation == "limited" else 0)
    score = max(0.0, min(1.0, supply / need))
    caution = None
    if score < 0.6:
        caution = (f"Needs about {need} mm of water; normal rainfall in its season here is {season_rain:.0f} mm"
                   + (" and you have no irrigation" if irrigation == "none" else ""))
    return score, season_rain, caution


def recommend(farm: dict, season: str | None = None, experience: str = "experienced") -> dict:
    season = season or default_season()
    state, district = farm["state"], farm["district"]
    table, borrowed_from = stats_district(state, district)
    rain = geo.rain_normals(state, district)
    area = float(farm.get("land_area_acres") or 1)
    budget = farm.get("budget")
    irrigation = farm.get("irrigation") or "limited"
    nat_yield = stats()["national_yield_t_ha"]

    rows = []
    for crop_id, crop in CROPS.items():
        if not crop["apy"]:
            continue
        in_season = season in crop["seasons"]
        is_annual = "annual" in crop["seasons"]
        entry = (table.get(season) or {}).get(crop_id)
        annual_entry = (table.get("annual") or {}).get(crop_id)
        if entry and entry.get("n", 0) == 0 and annual_entry and annual_entry.get("n", 0) > 0 and (in_season or is_annual):
            entry = annual_entry  # some states report the crop only as "whole year"
        if not entry and annual_entry and (in_season or is_annual):
            entry = annual_entry
        if not entry or not (in_season or is_annual or entry.get("n", 0) >= 5):
            continue

        n = entry.get("n", 0)
        share = entry.get("share") or 0.0
        y_q = entry["y"] * Q_PER_ACRE
        price = price_for(crop_id)
        if not price["price"]:
            continue
        cost, cost_basis = cost_per_acre(crop_id)
        revenue = y_q * price["price"]
        profit = revenue - cost

        if n > 0:
            s_track = 0.25 + 0.75 * min(1, n / 8) * (0.4 + 0.6 * min(1, math.sqrt(share / 0.15)))
        else:
            s_track = 0.10
        ratio = entry["y"] / nat_yield[crop_id] if nat_yield.get(crop_id) else 1.0
        s_yield = max(0.0, min(1.0, 0.5 + (ratio - 1.0)))
        s_soil, soil_good, soil_caution = _soil_score(crop, farm.get("soil_type"), farm.get("ph"))
        s_water, season_rain, water_caution = _water_score(crop, crop_id, season, rain, irrigation)
        total_cost = cost * area
        if budget:
            s_budget = 1.0 if total_cost <= budget else max(0.0, budget / total_cost)
        else:
            s_budget = 0.7

        rows.append({
            "id": crop_id, "name": crop["name"], "local": crop["local"], "category": crop["category"],
            "duration_days": crop["days"]["maturity"], "long_duration": is_annual and not in_season,
            "sow_months": [MONTHS[m - 1] for m in (crop["sow_months"].get(season) or crop["sow_months"].get("annual") or [])],
            "yield_q_acre": round(y_q, 1), "yield_low": round(entry["lo"] * Q_PER_ACRE, 1),
            "yield_high": round(entry["hi"] * Q_PER_ACRE, 1), "product": crop["product"],
            "district_years": n, "district_last_year": entry.get("last"), "area_share_pct": round(share * 100, 1),
            "yield_vs_national_pct": round((ratio - 1) * 100),
            "price": price["price"], "price_basis": price["basis"], "msp": crop["msp"], "msp_note": crop["msp_note"],
            "price_change_12m_pct": price.get("change_12m_pct"), "price_volatility_pct": price.get("volatility_pct"),
            "cost_acre": cost, "cost_basis": cost_basis, "revenue_acre": int(round(revenue, -2)),
            "profit_acre": int(round(profit, -2)), "total_cost": int(round(total_cost, -2)),
            "total_profit": int(round(profit * area, -2)),
            "months_in_field": round(crop["days"]["maturity"] / 30, 1),
            "profit_per_month": int(round(profit / max(1.0, crop["days"]["maturity"] / 30), -1)),
            "fits_budget": (total_cost <= budget) if budget else None,
            "affordable_acres": round(min(area, budget / cost), 1) if budget else None,
            "season_rain_mm": round(season_rain) if season_rain is not None else None,
            "water_need_mm": crop["water_mm"],
            "_s": {"track": s_track, "yield": s_yield, "soil": s_soil, "water": s_water, "budget": s_budget},
            "_soil_good": soil_good, "_cautions": [c for c in (soil_caution, water_caution) if c],
        })

    # profit is scored by rank among the candidates (so one huge number cannot dominate), and per
    # month in the field, so a 12-month crop is compared fairly with a 4-month one
    ranked = sorted(rows, key=lambda r: r["profit_per_month"])
    for i, r in enumerate(ranked):
        s_profit = (i / (len(ranked) - 1)) if len(ranked) > 1 else 0.5
        if r["profit_acre"] <= 0:
            s_profit = 0.0
        r["_s"]["profit"] = s_profit
        r["score"] = round(100 * sum(WEIGHTS[k] * r["_s"][k] for k in WEIGHTS))
        r["parts"] = {k: round(r["_s"][k] * 100) for k in WEIGHTS}

    for r in rows:
        reasons, cautions = [], list(r.pop("_cautions"))
        s = r.pop("_s")
        if r["district_years"] >= 8 and r["area_share_pct"] >= 10:
            reasons.append(f"A main crop here: {r['area_share_pct']:g}% of the season's recorded area, {r['district_years']} years of records")
        elif r["district_years"] >= 5:
            reasons.append(f"Grown in the district in {r['district_years']} recorded years")
        elif r["district_years"] == 0:
            cautions.append("No record of it being grown in this district; the yield is estimated from nearby districts")
        if r["yield_vs_national_pct"] >= 10:
            reasons.append(f"Yields here run about {r['yield_vs_national_pct']}% above the national average")
        elif r["yield_vs_national_pct"] <= -25:
            cautions.append(f"Yields here run about {abs(r['yield_vs_national_pct'])}% below the national average")
        soil_good = r.pop("_soil_good")
        if soil_good:
            reasons.append(soil_good)
        if s["profit"] >= 0.7 and r["profit_acre"] > 0:
            reasons.append(f"Among the better earners: about ₹{r['profit_acre']:,} per acre at current prices")
        if r["profit_acre"] <= 0:
            cautions.append("At current prices and average costs it does not cover its costs")
        if r["msp"] and r["price"] < r["msp"] * 0.95:
            cautions.append(f"Mandi price (₹{r['price']:,}) is below the MSP (₹{r['msp']:,}); sell at a procurement centre if one operates near you")
        if r["fits_budget"] is False:
            cautions.append(f"Your budget covers about {r['affordable_acres']:g} of your {area:g} acres")
        if r["price_volatility_pct"] and r["price_volatility_pct"] >= 12:
            cautions.append("Prices swing a lot from month to month")
        if r["long_duration"]:
            cautions.append(f"Long-duration crop: occupies the field for about {round(r['duration_days'] / 30)} months")
        risk_points = (r["price_volatility_pct"] or 6) / 6 + (1 if r["district_years"] < 5 else 0) + (1 if s["water"] < 0.6 else 0)
        r["risk"] = "low" if risk_points < 1.6 else "medium" if risk_points < 2.6 else "high"
        r["beginner_friendly"] = r["cost_acre"] <= 25000 and r["duration_days"] <= 130 and r["risk"] != "high"
        r["reasons"], r["cautions"] = reasons[:3], cautions[:3]

    rows.sort(key=lambda r: (-r["score"], -r["profit_acre"]))
    if experience == "new":  # for first-time farmers, nudge the simpler crops up among near-equals
        rows.sort(key=lambda r: -(r["score"] + (4 if r["beginner_friendly"] else 0)))
    return {
        "season": season, "season_label": SEASONS[season]["label"], "state": state, "district": district,
        "borrowed_from": borrowed_from, "data_years": stats()["data_years"],
        "price_month": prices()["last_full_month"], "irrigation": irrigation, "land_area_acres": area, "budget": budget,
        "weights": {k: round(v * 100) for k, v in WEIGHTS.items()},
        "crops": rows[:8], "considered": len(rows),
    }


def fertilizer_plan(crop_id: str, area_acres: float, status: dict | None = None) -> dict:
    """Recommended nutrients for the area, converted to bags of urea, DAP and MOP.

    status: optional Soil Health Card ratings {"n": "low|medium|high", "p": ..., "k": ...}.
    The usual rule is applied: 25% more of a nutrient rated low, 25% less of one rated high.
    """
    crop = CROPS[crop_id]
    adj = {"low": 1.25, "medium": 1.0, "high": 0.75}
    status = status or {}
    factors = [adj.get(status.get(k) or "medium", 1.0) for k in ("n", "p", "k")]
    ha = area_acres / 2.471
    n, p, k = (crop["npk"][i] * factors[i] * ha for i in range(3))
    dap = p / 0.46
    urea = max(0.0, n - dap * 0.18) / 0.46
    mop = k / 0.60
    splits = crop["split_n"]
    labels = ["At sowing (basal)", "First top-dressing", "Second top-dressing"]
    schedule = []
    for i, frac in enumerate(splits):
        if frac <= 0:
            continue
        item = {"when": labels[i], "urea_kg": round(urea * frac, 1)}
        if i == 0:
            item.update({"dap_kg": round(dap, 1), "mop_kg": round(mop, 1)})
        schedule.append(item)
    return {
        "crop": crop_id, "area_acres": area_acres, "nutrients_kg": {"n": round(n, 1), "p2o5": round(p, 1), "k2o": round(k, 1)},
        "per_hectare": {"n": crop["npk"][0], "p2o5": crop["npk"][1], "k2o": crop["npk"][2]},
        "adjusted_for": {key: status.get(key) for key in ("n", "p", "k") if status.get(key) in adj and status.get(key) != "medium"},
        "products": {"urea_kg": round(urea, 1), "dap_kg": round(dap, 1), "mop_kg": round(mop, 1),
                     "urea_bags_45kg": math.ceil(urea / 45), "dap_bags_50kg": math.ceil(dap / 50),
                     "mop_bags_50kg": math.ceil(mop / 50)},
        "schedule": schedule,
        "note": "General recommendation. Where you have a Soil Health Card, follow its doses; add farmyard manure "
                "or compost (4-5 tonnes per acre) before sowing if you can.",
    }
