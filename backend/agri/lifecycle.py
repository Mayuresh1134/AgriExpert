"""Crop cycle: which stage a crop is in, and what to do at each stage.

A cycle starts on the sowing (or transplanting/planting) date. Stage boundaries come from
the crop's typical durations in crops_kb.py; the farmer can move to the next stage by hand
if their crop is ahead or behind.
"""
from __future__ import annotations

import datetime as dt

from .crops_kb import CROPS, STAGES
from .recommend import fertilizer_plan

STAGE_IDS = [s[0] for s in STAGES]


def stage_windows(crop: dict) -> list[dict]:
    """Day ranges (from sowing) for each stage."""
    d = crop["days"]
    emergence = max(4, d["emergence"])
    bounds = [
        ("preparation", -21, 0),
        ("sowing", 0, 3),
        ("germination", 3, emergence + 10),
        ("vegetative", emergence + 10, d["vegetative"]),
        ("flowering", d["vegetative"], d["flowering"]),
        ("maturation", d["flowering"], max(d["flowering"] + 7, d["maturity"] - 7)),
        ("harvesting", max(d["flowering"] + 7, d["maturity"] - 7), d["maturity"] + 21),
    ]
    labels = dict(STAGES)
    return [{"id": sid, "label": crop["stage_labels"].get(sid, labels[sid]), "start_day": a, "end_day": b}
            for sid, a, b in bounds]


def stage_for_day(crop: dict, day: int) -> str:
    for w in stage_windows(crop):
        if day < w["end_day"]:
            return w["id"]
    return "harvesting"


def progress(cycle: dict, on: dt.date) -> dict:
    crop = {"id": cycle["crop"], **CROPS[cycle["crop"]]}
    sow = dt.date.fromisoformat(cycle["sowing_date"])
    day = (on - sow).days
    auto = stage_for_day(crop, day)
    stage = cycle.get("stage_override") or auto
    # an override only holds while it is not behind the calendar
    if cycle.get("stage_override") and STAGE_IDS.index(cycle["stage_override"]) < STAGE_IDS.index(auto):
        stage = auto
    windows = stage_windows(crop)
    maturity = crop["days"]["maturity"]
    return {
        "day": day, "stage": stage, "stage_label": next(w["label"] for w in windows if w["id"] == stage),
        "stage_index": STAGE_IDS.index(stage), "windows": windows, "percent": max(0, min(100, round(day / maturity * 100))),
        "expected_harvest": (sow + dt.timedelta(days=maturity)).isoformat(),
        "days_to_harvest": maturity - day,
    }


def _task(tid, stage, title, detail, due=None, kind="task"):
    return {"id": tid, "stage": stage, "title": title, "detail": detail, "due_day": due, "kind": kind}


def tasks_for(cycle: dict, farm: dict | None = None) -> list[dict]:
    """The full checklist for a cycle, every stage. Due days count from sowing."""
    cid = cycle["crop"]
    crop = CROPS[cid]
    area = float(cycle.get("area_acres") or 1)
    soil_status = (farm or {}).get("soil_status") or {}
    fert = fertilizer_plan(cid, area, soil_status)
    prod = fert["products"]
    d = crop["days"]
    name = crop["name"].split(" (")[0]
    t = []

    # -------- preparation
    t.append(_task("prep_soiltest", "preparation", "Get a soil test",
                   "Collect soil from 8-10 spots in a zigzag, 15 cm deep, mix and send about 500 g to the nearest soil "
                   "testing lab or KVK. The Soil Health Card gives exact fertiliser doses for your field.", -21))
    t.append(_task("prep_plough", "preparation", "Plough and level the field",
                   "One deep ploughing followed by 2-3 harrowings to a fine tilth; level the field so water spreads evenly "
                   "and does not stand in low spots.", -14))
    t.append(_task("prep_fym", "preparation", "Add farmyard manure or compost",
                   f"About {round(4 * area, 1):g} tonnes for {area:g} acres (4 t per acre), spread and mixed in at the last ploughing.", -10))
    if cid == "rice":
        t.append(_task("prep_nursery", "preparation", "Raise the nursery",
                       "Sow the nursery about 25 days before transplanting, on raised beds near a water source.", -25))
        t.append(_task("prep_puddle", "preparation", "Puddle the main field",
                       "Flood and puddle the field 1-2 days before transplanting to cut water loss and weeds.", -2))
    elif crop["nursery_days"]:
        t.append(_task("prep_nursery", "preparation", "Raise seedlings in a nursery",
                       f"Sow the nursery about {crop['nursery_days']} days before transplanting; use raised beds and "
                       "insect netting if whitefly or thrips are common.", -crop["nursery_days"]))
    t.append(_task("prep_seed", "preparation", "Buy certified seed",
                   f"Seed needed: {crop['seed_rate']} per acre, so plan for {area:g} acres. Buy from a licensed dealer and keep the bill and tag.", -10))
    if crop["category"] == "pulse" or cid in ("soybean", "groundnut"):
        t.append(_task("prep_rhizobium", "preparation", "Treat seed with Rhizobium",
                       "Treat seed with a fungicide first (e.g. thiram + carbendazim 2 g/kg), dry, then coat with Rhizobium "
                       "and PSB culture just before sowing. Cheap, and it adds nitrogen.", -1))
    else:
        t.append(_task("prep_seedtreat", "preparation", "Treat the seed",
                       "Treat seed with a fungicide (e.g. carbendazim 2 g or Trichoderma 4-10 g per kg) to protect against "
                       "seed and soil-borne disease.", -1))
    t.append(_task("prep_inputs", "preparation", "Buy basal fertiliser",
                   f"For {area:g} acres: about {prod['dap_bags_50kg']} bags of DAP and {prod['mop_bags_50kg']} bags of MOP "
                   "for sowing time (see the fertiliser plan).", -7))
    if "annual" not in crop["seasons"]:
        t.append(_task("prep_insure", "preparation", "Insure the crop (PMFBY)",
                       "Enrol before the season's cut-off date through your bank, a CSC centre or pmfby.gov.in.", -5))

    # -------- sowing
    depth = f"{crop['depth_cm'][0]}-{crop['depth_cm'][1]} cm deep, " if crop["depth_cm"] else ""
    t.append(_task("sow_sow", "sowing", "Sow at the right depth and spacing",
                   f"Sow {depth}spacing {crop['spacing']}. Soil temperature of {crop['germ_temp'][0]}-{crop['germ_temp'][1]}°C suits germination.", 0))
    t.append(_task("sow_basal", "sowing", "Apply basal fertiliser",
                   f"At sowing: {prod['dap_kg']:g} kg DAP and {prod['mop_kg']:g} kg MOP"
                   + (f" plus {fert['schedule'][0]['urea_kg']:g} kg urea" if fert["schedule"] and fert["schedule"][0]["urea_kg"] else "")
                   + ", placed in the furrow below and beside the seed, not touching it.", 0))
    t.append(_task("sow_irrigate", "sowing", "Light irrigation if the soil is dry",
                   "A light irrigation right after sowing helps even germination; skip it if rain is forecast.", 1))

    # -------- germination
    t.append(_task("germ_gap", "germination", "Check germination and fill gaps",
                   "Count plants in a few 1 m rows. Re-sow or transplant into gaps within 10 days of sowing.", d["emergence"] + 3))
    t.append(_task("germ_weed", "germination", "First weeding",
                   "Weeds take the most from a young crop. Hand weed or hoe around 20-25 days, or use a recommended herbicide.",
                   min(25, d["emergence"] + 15)))

    # -------- vegetative
    splits = [s for s in fert["schedule"] if s["when"] != "At sowing (basal)"]
    veg_end = d["vegetative"]
    if splits:
        t.append(_task("veg_topdress1", "vegetative", "First nitrogen top-dressing",
                       f"About {splits[0]['urea_kg']:g} kg urea for {area:g} acres. Apply on moist soil, ideally just before a light irrigation, not before heavy rain.",
                       round((d["emergence"] + veg_end) / 2)))
    if crop["critical_water"]:
        t.append(_task("veg_water", "vegetative", "Irrigate at the critical stages",
                       f"Water matters most for {name.lower()} at: {', '.join(crop['critical_water'])}. Check the weekly water estimate on this page.",
                       veg_end - 10))
    t.append(_task("veg_scout", "vegetative", "Scout for pests and disease weekly",
                   f"Walk the field in a W pattern. Watch for: {', '.join(crop['pests'][:4])}. Scan a leaf with the disease checker if you see spots.",
                   veg_end - 20, "repeat"))
    t.append(_task("veg_weed2", "vegetative", "Second weeding / earthing up",
                   "A second weeding around 40-45 days; earth up where the crop needs it (maize, potato, sugarcane, groundnut).",
                   min(45, veg_end - 5)))

    # -------- flowering
    if len(splits) > 1:
        t.append(_task("flw_topdress2", "flowering", "Second nitrogen top-dressing",
                       f"About {splits[1]['urea_kg']:g} kg urea for {area:g} acres, before or at the start of flowering.", veg_end))
    if cid == "gram":
        t.append(_task("flw_nowater", "flowering", "Do not irrigate at flowering",
                       "Irrigating gram at flowering makes flowers drop. Irrigate before flowering and at pod filling only.", veg_end + 5))
    elif crop["category"] == "oilseed" or cid in ("tur", "moong", "urad"):
        t.append(_task("flw_bees", "flowering", "Protect pollinators",
                       "Avoid spraying insecticides during flowering hours; if you must, spray late in the evening.", veg_end + 3))
    t.append(_task("flw_water", "flowering", "Keep the soil moist",
                   "Water stress now costs the most yield. Irrigate if there has been no rain for a week and the topsoil is dry.", veg_end + 7))
    if crop["notes"]:
        t.append(_task("flw_note", "flowering", f"{name} tip", crop["notes"], veg_end + 2, "tip"))

    # -------- maturation
    t.append(_task("mat_stopwater", "maturation", "Stop irrigating before harvest",
                   "Stop irrigation 10-15 days before the expected harvest so the crop dries down evenly.", d["maturity"] - 15))
    t.append(_task("mat_labour", "maturation", "Arrange harvest labour or machine",
                   "Book the harvester or labour early; harvest delayed past maturity loses grain and quality.", d["maturity"] - 12))
    t.append(_task("mat_market", "maturation", "Compare prices and markets",
                   "Check the price outlook and nearby mandis now, so you can decide where and when to sell before harvest.", d["maturity"] - 10))

    # -------- harvesting
    t.append(_task("har_sign", "harvesting", "Harvest at the right time", crop["harvest_sign"], d["maturity"]))
    if crop["store_moisture"]:
        t.append(_task("har_dry", "harvesting", f"Dry to {crop['store_moisture']}% moisture",
                       crop["storage"], d["maturity"] + 3))
    else:
        t.append(_task("har_store", "harvesting", "Handle and store the produce", crop["storage"], d["maturity"] + 2))
    t.append(_task("har_record", "harvesting", "Record your harvest and sale",
                   "Log the quantity harvested and the sale price below. It shows your real profit for the season.", d["maturity"] + 7))
    t.append(_task("har_residue", "harvesting", "Manage crop residue",
                   "Do not burn residue: incorporate it, compost it, or use a happy seeder / mulcher. Burning destroys soil organic matter.",
                   d["maturity"] + 10))
    return t


LOG_KINDS = {
    "irrigation": "Irrigation", "fertilizer": "Fertiliser", "spray": "Spray", "weeding": "Weeding",
    "observation": "Observation", "expense": "Other expense", "harvest": "Harvest", "sale": "Sale",
}


def summary(cycle: dict, logs: list[dict]) -> dict:
    cost = sum(float(l.get("cost") or 0) for l in logs)
    harvested = sum(float(l.get("quantity_q") or 0) for l in logs if l["kind"] == "harvest")
    sold_q = sum(float(l.get("quantity_q") or 0) for l in logs if l["kind"] == "sale")
    revenue = sum(float(l.get("quantity_q") or 0) * float(l.get("price") or 0) for l in logs if l["kind"] == "sale")
    area = float(cycle.get("area_acres") or 1)
    return {"cost": round(cost), "harvested_q": round(harvested, 2), "sold_q": round(sold_q, 2), "revenue": round(revenue),
            "profit": round(revenue - cost), "yield_q_acre": round(harvested / area, 2) if harvested else None,
            "avg_sale_price": round(revenue / sold_q) if sold_q else None,
            "irrigations": sum(1 for l in logs if l["kind"] == "irrigation")}
