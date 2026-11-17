"""All API routes. Every route except /api/auth/*, /api/meta/* and /api/health needs a login token."""
from __future__ import annotations

import datetime as dt
import json
import re

from flask import Blueprint, g, jsonify, request

from . import assistant, geo, lifecycle, markets, recommend, schemes, weather
from .config import Config, MODELS_DIR
from .core import (POINTS, ApiError, award, body, choice, clean, hash_password, level_for, login_required, long_text,
                   make_token, now, number, oid, parse_date, revoke, text, today, verify_password)
from .crops_kb import CROPS, SEASONS, SOIL_TYPES, public_summary
from .db import get_db, mark_dirty

api = Blueprint("api", __name__, url_prefix="/api")


def ok(data=None, status=200):
    return jsonify(clean(data) if data is not None else {"ok": True}), status


def current_farm():
    return get_db().farms.find_one({"user_id": g.user["_id"]})


def require_farm():
    farm = current_farm()
    if not farm:
        raise ApiError("Add your farm details first", 409)
    return farm


# ============================================================ meta (public)
@api.get("/health")
def health():
    return ok({"ok": True, "db": Config.DB_MODE, "assistant": "gemini" if Config.GEMINI_API_KEY else "built-in",
               "weather": Config.WEATHER_MODE, "live_mandi": bool(Config.DATA_GOV_API_KEY)})


@api.get("/meta/options")
def meta_options():
    from .disease import supported_crops

    return ok({"states": geo.states(), "soil_types": SOIL_TYPES, "irrigation": recommend.IRRIGATION,
               "seasons": {k: v["label"] for k, v in SEASONS.items()},
               "crops": [public_summary(c) for c in CROPS], "scan_crops": supported_crops(),
               "languages": assistant.LANGUAGES, "log_kinds": lifecycle.LOG_KINDS,
               "stages": [{"id": s, "label": l} for s, l in lifecycle.STAGES]})


@api.get("/meta/districts")
def meta_districts():
    state = request.args.get("state", "")
    if state not in geo.states():
        raise ApiError("Unknown state")
    return ok({"districts": geo.districts_of(state)})


@api.get("/meta/locate")
def meta_locate():
    try:
        lat, lng = float(request.args["lat"]), float(request.args["lng"])
    except (KeyError, ValueError):
        raise ApiError("lat and lng are required")
    place = geo.locate(lat, lng)
    if not place:
        raise ApiError("That location is not in India", 404)
    return ok(place)


@api.get("/meta/places")
def meta_places():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return ok({"results": []})
    return ok({"results": weather.search_place(q[:60])})


@api.get("/meta/models")
def meta_models():
    out = {}
    for name in ("yield", "price", "disease"):
        p = MODELS_DIR / f"{name}_metrics.json"
        if p.exists():
            out[name] = json.loads(p.read_text())
    if "disease" in out:
        out["disease"].pop("per_class", None)
    return ok(out)


# ============================================================ accounts
LOGIN_RE = re.compile(r"^([6-9]\d{9}|[^@\s]+@[^@\s]+\.[^@\s]+)$")


def normalise_login(value: str) -> str:
    value = value.strip().lower().replace(" ", "")
    digits = re.sub(r"\D", "", value)
    if "@" not in value and len(digits) in (10, 12) and digits[-10] in "6789":
        return digits[-10:]
    return value


@api.post("/auth/register")
def register():
    data = body()
    name = text(data, "name", max_len=60, min_len=2)
    login = normalise_login(text(data, "login", max_len=120, label="Mobile number or email"))
    if not LOGIN_RE.match(login):
        raise ApiError("Enter a 10-digit mobile number or an email address")
    password = str(data.get("password") or "")
    if len(password) < 6:
        raise ApiError("Password must be at least 6 characters")
    if len(password) > 128:
        raise ApiError("Password is too long")
    language = choice(data, "language", list(assistant.LANGUAGES), required=False) or "en"
    db = get_db()
    if db.users.find_one({"login": login}):
        raise ApiError("An account with this mobile number or email already exists. Please log in.", 409)
    user = {"name": name, "login": login, "password": hash_password(password), "language": language,
            "points": 0, "created_at": now()}
    user["_id"] = db.users.insert_one(user).inserted_id
    mark_dirty()
    return ok({"token": make_token(user["_id"]), "user": public_user(user)}, 201)


@api.post("/auth/login")
def login():
    data = body()
    login_value = normalise_login(text(data, "login", max_len=120, label="Mobile number or email"))
    user = get_db().users.find_one({"login": login_value})
    if not user or not verify_password(user["password"], str(data.get("password") or "")):
        raise ApiError("Wrong mobile number / email or password", 401)
    return ok({"token": make_token(user["_id"]), "user": public_user(user)})


def public_user(user):
    return {"id": user["_id"], "name": user["name"], "login": user["login"], "language": user.get("language", "en"),
            "age": user.get("age"), "village": user.get("village"), **level_for(user.get("points", 0))}


@api.get("/me")
@login_required
def me():
    return ok({"user": public_user(g.user), "farm": current_farm()})


@api.put("/me")
@login_required
def update_me():
    data = body()
    changes = {}
    if "name" in data:
        changes["name"] = text(data, "name", max_len=60, min_len=2)
    if "language" in data:
        changes["language"] = choice(data, "language", list(assistant.LANGUAGES))
    if "age" in data:
        age = number(data, "age", required=False, lo=14, hi=100)
        changes["age"] = int(age) if age else None
    if data.get("new_password"):
        if not verify_password(g.user["password"], str(data.get("current_password") or "")):
            raise ApiError("Current password is wrong", 403)
        if len(str(data["new_password"])) < 6:
            raise ApiError("New password must be at least 6 characters")
        changes["password"] = hash_password(str(data["new_password"]))
    if changes:
        get_db().users.update_one({"_id": g.user["_id"]}, {"$set": changes})
        mark_dirty()
    return ok({"user": public_user(get_db().users.find_one({"_id": g.user["_id"]}))})


@api.get("/me/points")
@login_required
def my_points():
    entries = list(get_db().points.find({"user_id": g.user["_id"]}).sort("created_at", -1).limit(50))
    return ok({"summary": level_for(g.user.get("points", 0)), "entries": entries, "rules": POINTS})


# ============================================================ farm profile
@api.put("/farm")
@login_required
def save_farm():
    data = body()
    state = choice(data, "state", geo.states())
    district = choice(data, "district", geo.districts_of(state))
    farm = {
        "name": text(data, "name", required=False, max_len=60) or "My farm",
        "state": state, "district": district,
        "village": text(data, "village", required=False, max_len=80),
        "land_area_acres": number(data, "land_area_acres", lo=0.1, hi=1000, label="Land area"),
        "soil_type": choice(data, "soil_type", list(SOIL_TYPES), required=False),
        "ph": number(data, "ph", required=False, lo=3, hi=10, label="Soil pH"),
        "irrigation": choice(data, "irrigation", list(recommend.IRRIGATION)),
        "water_source": text(data, "water_source", required=False, max_len=40),
        "budget": number(data, "budget", required=False, lo=0, hi=1e8, label="Budget"),
        "ownership": choice(data, "ownership", ["owned", "tenant", "both"], required=False),
        "experience": choice(data, "experience", ["new", "experienced"], required=False) or "experienced",
        "soil_status": {k: choice(data.get("soil_status") or {}, k, ["low", "medium", "high"], required=False,
                                  label=f"Soil {k.upper()}") for k in ("n", "p", "k")},
        "updated_at": now(),
    }
    lat = number(data, "lat", required=False, lo=6, hi=38, label="Latitude")
    lng = number(data, "lng", required=False, lo=68, hi=98, label="Longitude")
    if lat is not None and lng is not None:
        farm["lat"], farm["lng"], farm["location_source"] = lat, lng, "gps"
    else:
        d = geo.get(state, district)
        farm["lat"], farm["lng"], farm["location_source"] = d["lat"], d["lng"], "district"
    db = get_db()
    db.farms.update_one({"user_id": g.user["_id"]}, {"$set": farm, "$setOnInsert": {"user_id": g.user["_id"], "created_at": now()}},
                        upsert=True)
    mark_dirty()
    return ok({"farm": current_farm()})


@api.get("/farm")
@login_required
def get_farm():
    return ok({"farm": current_farm()})


# ============================================================ weather & dashboard
@api.get("/weather")
@login_required
def get_weather():
    farm = require_farm()
    return ok(weather.forecast(farm.get("lat"), farm.get("lng"), farm["state"], farm["district"]))


def cycle_view(cycle, farm, fc=None, with_tasks=True):
    prog = lifecycle.progress(cycle, today())
    view = {**cycle, "progress": prog, "crop_name": CROPS[cycle["crop"]]["name"], "crop_local": CROPS[cycle["crop"]]["local"]}
    if with_tasks:
        done = set(cycle.get("done_tasks", []))
        view["tasks"] = [{**t, "done": t["id"] in done} for t in lifecycle.tasks_for(cycle, farm)]
    if fc is not None:
        crop = {"id": cycle["crop"], **CROPS[cycle["crop"]]}
        view["alerts"] = weather.alerts(fc, crop, prog["stage"], farm.get("irrigation", "limited"))
        view["water"] = weather.water_need(fc, prog["stage"], cycle["crop"])
    return view


@api.get("/dashboard")
@login_required
def dashboard():
    farm = current_farm()
    out = {"user": public_user(g.user), "farm": farm, "today": today().isoformat()}
    if not farm:
        return ok(out)
    fc = weather.forecast(farm.get("lat"), farm.get("lng"), farm["state"], farm["district"])
    cycles = list(get_db().cycles.find({"user_id": g.user["_id"], "status": "active"}).sort("sowing_date", 1))
    views = [cycle_view(c, farm, fc) for c in cycles]
    for v in views:
        stage = v["progress"]["stage"]
        day = v["progress"]["day"]
        here = lifecycle.STAGE_IDS.index(stage)
        v["next_tasks"] = sorted([t for t in v["tasks"] if not t["done"] and t["due_day"] is not None
                                  and day - 14 <= t["due_day"] <= day + 10
                                  and here <= lifecycle.STAGE_IDS.index(t["stage"]) <= here + 1],
                                 key=lambda t: t["due_day"])[:4]
        del v["tasks"]
    prices = []
    for cid in dict.fromkeys([v["crop"] for v in views]):
        o = markets.outlook(cid)
        if o:
            prices.append({"crop": cid, "name": o["name"], "latest": o["latest"], "month": o["latest_month"],
                           "change_12m_pct": o.get("change_12m_pct"), "msp": o.get("msp"),
                           "next": (o.get("forecast") or [None])[0]})
    general = weather.alerts(fc, None, None, farm.get("irrigation", "limited")) if not views else []
    out.update({"weather": fc, "cycles": views, "prices": prices, "alerts": general,
                "season": recommend.default_season(), "season_label": SEASONS[recommend.default_season()]["label"]})
    return ok(out)


# ============================================================ recommendations
@api.get("/recommend")
@login_required
def get_recommendations():
    farm = require_farm()
    season = request.args.get("season") or recommend.default_season()
    if season not in SEASONS:
        raise ApiError("Unknown season")
    # optional what-if overrides from the screen, not saved to the profile
    what_if = dict(farm)
    for key in ("land_area_acres", "budget"):
        if request.args.get(key):
            try:
                what_if[key] = float(request.args[key])
            except ValueError:
                raise ApiError(f"{key} must be a number")
    if request.args.get("irrigation") in recommend.IRRIGATION:
        what_if["irrigation"] = request.args["irrigation"]
    result = recommend.recommend(what_if, season, farm.get("experience", "experienced"))
    return ok(result)


@api.get("/crops/<crop_id>")
@login_required
def crop_detail(crop_id):
    if crop_id not in CROPS:
        raise ApiError("Unknown crop", 404)
    farm = current_farm()
    c = CROPS[crop_id]
    area = float(request.args.get("area") or (farm or {}).get("land_area_acres") or 1)
    out = {"id": crop_id, **{k: c[k] for k in ("name", "local", "category", "seasons", "days", "npk", "water_mm", "soils",
                                                 "ph", "temp", "seed_rate", "spacing", "critical_water", "pests",
                                                 "harvest_sign", "storage", "notes", "msp", "msp_note", "product")},
           "fertilizer": recommend.fertilizer_plan(crop_id, area, (farm or {}).get("soil_status")),
           "price": markets.outlook(crop_id),
           "stages": lifecycle.stage_windows({"id": crop_id, **c})}
    if farm:
        table, borrowed = recommend.stats_district(farm["state"], farm["district"])
        out["district"] = {s: v[crop_id] for s, v in table.items() if crop_id in v}
        out["district_borrowed_from"] = borrowed
    return ok(out)


# ============================================================ crop cycles (lifecycle tracking)
def own_cycle(cycle_id):
    cycle = get_db().cycles.find_one({"_id": oid(cycle_id), "user_id": g.user["_id"]})
    if not cycle:
        raise ApiError("Not found", 404)
    return cycle


@api.get("/cycles")
@login_required
def list_cycles():
    farm = current_farm()
    cycles = list(get_db().cycles.find({"user_id": g.user["_id"]}).sort("created_at", -1))
    return ok({"cycles": [cycle_view(c, farm or {}, with_tasks=False) for c in cycles]})


@api.post("/cycles")
@login_required
def create_cycle():
    farm = require_farm()
    data = body()
    crop_id = choice(data, "crop", list(CROPS))
    sowing = parse_date(data.get("sowing_date"), "Sowing date")
    if sowing > today() + dt.timedelta(days=120):
        raise ApiError("Sowing date is too far in the future")
    if sowing < today() - dt.timedelta(days=400):
        raise ApiError("Sowing date is too far in the past")
    area = number(data, "area_acres", lo=0.05, hi=1000, label="Area")
    if area > float(farm["land_area_acres"]) * 1.001:
        raise ApiError(f"Area cannot be more than your farm ({farm['land_area_acres']:g} acres)")
    season = choice(data, "season", list(SEASONS) + ["annual"], required=False) or (
        recommend.default_season(sowing.month) if recommend.default_season(sowing.month) in CROPS[crop_id]["seasons"]
        else CROPS[crop_id]["seasons"][0])
    cycle = {"user_id": g.user["_id"], "crop": crop_id, "season": season, "sowing_date": sowing.isoformat(),
             "area_acres": area, "variety": text(data, "variety", required=False, max_len=60),
             "field_name": text(data, "field_name", required=False, max_len=40), "status": "active",
             "done_tasks": [], "stage_override": None, "created_at": now()}
    cycle["_id"] = get_db().cycles.insert_one(cycle).inserted_id
    mark_dirty()
    award(g.user["_id"], "plan", f"Started tracking {CROPS[crop_id]['name']}", str(cycle["_id"]))
    return ok({"cycle": cycle_view(cycle, farm)}, 201)


@api.get("/cycles/<cycle_id>")
@login_required
def get_cycle(cycle_id):
    farm = current_farm() or {}
    cycle = own_cycle(cycle_id)
    fc = weather.forecast(farm.get("lat"), farm.get("lng"), farm.get("state"), farm.get("district")) if farm else None
    view = cycle_view(cycle, farm, fc)
    logs = list(get_db().logs.find({"cycle_id": cycle["_id"]}).sort([("date", -1), ("created_at", -1)]))
    view["logs"] = logs
    view["summary"] = lifecycle.summary(cycle, logs)
    view["fertilizer"] = recommend.fertilizer_plan(cycle["crop"], float(cycle["area_acres"]), farm.get("soil_status"))
    view["weather"] = fc
    return ok({"cycle": view})


@api.patch("/cycles/<cycle_id>")
@login_required
def update_cycle(cycle_id):
    cycle = own_cycle(cycle_id)
    data = body()
    changes = {}
    if "sowing_date" in data:
        changes["sowing_date"] = parse_date(data["sowing_date"], "Sowing date").isoformat()
    if "area_acres" in data:
        changes["area_acres"] = number(data, "area_acres", lo=0.05, hi=1000, label="Area")
    if "stage" in data:
        changes["stage_override"] = choice(data, "stage", lifecycle.STAGE_IDS) if data["stage"] else None
    if "status" in data:
        changes["status"] = choice(data, "status", ["active", "completed", "abandoned"])
        if changes["status"] == "completed":
            changes["completed_at"] = now()
            award(g.user["_id"], "harvest", f"Completed a {CROPS[cycle['crop']]['name']} season", str(cycle["_id"]))
    for key in ("variety", "field_name"):
        if key in data:
            changes[key] = text(data, key, required=False, max_len=60)
    if changes:
        get_db().cycles.update_one({"_id": cycle["_id"]}, {"$set": changes})
        mark_dirty()
    return get_cycle(cycle_id)


@api.delete("/cycles/<cycle_id>")
@login_required
def delete_cycle(cycle_id):
    cycle = own_cycle(cycle_id)
    db = get_db()
    db.logs.delete_many({"cycle_id": cycle["_id"]})
    db.cycles.delete_one({"_id": cycle["_id"]})
    mark_dirty()
    return ok()


@api.post("/cycles/<cycle_id>/tasks/<task_id>")
@login_required
def toggle_task(cycle_id, task_id):
    cycle = own_cycle(cycle_id)
    valid = {t["id"] for t in lifecycle.tasks_for(cycle, current_farm())}
    if task_id not in valid:
        raise ApiError("Unknown task", 404)
    done = bool(body().get("done", True))
    op = "$addToSet" if done else "$pull"
    get_db().cycles.update_one({"_id": cycle["_id"]}, {op: {"done_tasks": task_id}})
    mark_dirty()
    ref = f"{cycle['_id']}:{task_id}"
    points = award(g.user["_id"], "task", "Completed a task", ref) if done else (revoke(g.user["_id"], "task", ref) or 0)
    return ok({"done": done, "points": points, "user": public_user(get_db().users.find_one({"_id": g.user["_id"]}))})


@api.post("/cycles/<cycle_id>/logs")
@login_required
def add_log(cycle_id):
    cycle = own_cycle(cycle_id)
    data = body()
    kind = choice(data, "kind", list(lifecycle.LOG_KINDS), label="Entry type")
    entry = {"cycle_id": cycle["_id"], "user_id": g.user["_id"], "kind": kind,
             "date": parse_date(data.get("date") or today().isoformat()).isoformat(),
             "note": long_text(data, "note", required=False, max_len=1000),
             "cost": number(data, "cost", required=False, lo=0, hi=1e8),
             "created_at": now()}
    if kind in ("harvest", "sale"):
        entry["quantity_q"] = number(data, "quantity_q", lo=0.01, hi=1e6, label="Quantity (quintals)")
    if kind == "sale":
        entry["price"] = number(data, "price", lo=1, hi=1e6, label="Price per quintal")
        entry["buyer"] = text(data, "buyer", required=False, max_len=80)
    if kind in ("fertilizer", "spray"):
        entry["product"] = text(data, "product", required=False, max_len=80)
        entry["amount"] = text(data, "amount", required=False, max_len=40)
    if parse_date(entry["date"]) > today() + dt.timedelta(days=1):
        raise ApiError("Date cannot be in the future")
    entry["_id"] = get_db().logs.insert_one(entry).inserted_id
    mark_dirty()
    award(g.user["_id"], "log", "Added to the field diary", f"{cycle['_id']}:{entry['date']}:{kind}")
    return ok({"log": entry}, 201)


@api.delete("/cycles/<cycle_id>/logs/<log_id>")
@login_required
def delete_log(cycle_id, log_id):
    cycle = own_cycle(cycle_id)
    res = get_db().logs.delete_one({"_id": oid(log_id), "cycle_id": cycle["_id"]})
    if not res.deleted_count:
        raise ApiError("Not found", 404)
    mark_dirty()
    return ok()


# ============================================================ disease scan
ALLOWED_IMAGE = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif", "application/octet-stream"}


@api.post("/scan")
@login_required
def scan():
    from .disease import model
    from PIL import UnidentifiedImageError

    file = request.files.get("image")
    if not file:
        raise ApiError("Attach a photo of the leaf")
    data = file.read()
    if not data:
        raise ApiError("The photo is empty")
    crop = request.form.get("crop") or None
    try:
        result = model().predict(data, crop)
    except (UnidentifiedImageError, OSError, ValueError):
        raise ApiError("Could not read that file as a photo. Use a JPG or PNG.")
    record = {"user_id": g.user["_id"], "crop": crop, "result_id": result["result"]["id"],
              "result_name": result["result"]["name"], "confidence": result["result"]["confidence"],
              "unsure": result["unsure"], "cycle_id": request.form.get("cycle_id") or None, "created_at": now()}
    record["_id"] = get_db().scans.insert_one(record).inserted_id
    mark_dirty()
    award(g.user["_id"], "scan", "Checked a leaf", str(record["_id"]))
    return ok({**result, "scan_id": record["_id"]})


@api.get("/scans")
@login_required
def list_scans():
    return ok({"scans": list(get_db().scans.find({"user_id": g.user["_id"]}).sort("created_at", -1).limit(30))})


# ============================================================ markets
@api.get("/markets/<crop_id>")
@login_required
def market_view(crop_id):
    if crop_id not in CROPS:
        raise ApiError("Unknown crop", 404)
    farm = require_farm()
    radius = float(request.args.get("radius") or 250)
    rate = float(request.args.get("transport") or markets.DEFAULT_TRANSPORT)
    qty = float(request.args["quantity"]) if request.args.get("quantity") else None
    return ok({"outlook": markets.outlook(crop_id),
               "markets": markets.best_markets(crop_id, farm["lat"], farm["lng"], farm["state"], max(10, min(radius, 800)),
                                               max(0, min(rate, 50)), qty)})


# ============================================================ schemes
@api.get("/schemes")
@login_required
def list_schemes():
    return ok({"schemes": schemes.check(current_farm(), g.user), "checked": schemes.CHECKED})


# ============================================================ assistant
@api.get("/assistant")
@login_required
def chat_history():
    msgs = list(get_db().chats.find({"user_id": g.user["_id"]}).sort("created_at", -1).limit(40))[::-1]
    return ok({"messages": msgs, "mode": "gemini" if Config.GEMINI_API_KEY else "built-in"})


@api.delete("/assistant")
@login_required
def clear_chat():
    get_db().chats.delete_many({"user_id": g.user["_id"]})
    mark_dirty()
    return ok()


@api.post("/assistant")
@login_required
def ask():
    data = body()
    question = long_text(data, "message", max_len=1500, label="Message")
    language = data.get("language") if data.get("language") in assistant.LANGUAGES else g.user.get("language", "en")
    farm = current_farm()
    db = get_db()
    ctx = {"farm": farm, "cycles": []}
    if farm:
        ctx["weather"] = weather.forecast(farm.get("lat"), farm.get("lng"), farm["state"], farm["district"])
        for c in db.cycles.find({"user_id": g.user["_id"], "status": "active"}):
            ctx["cycles"].append(cycle_view(c, farm))
    history = list(db.chats.find({"user_id": g.user["_id"]}).sort("created_at", -1).limit(8))[::-1]
    mode, links = "built-in", []
    if Config.GEMINI_API_KEY:
        try:
            answer = assistant.ask_gemini(question, history, ctx, language)
            mode = "gemini"
        except Exception as exc:
            r = assistant.offline_answer(question, ctx)
            answer, links = r["text"], r["links"]
            answer += f"\n\n(The online assistant is unavailable right now: {type(exc).__name__}.)"
    else:
        r = assistant.offline_answer(question, ctx)
        answer, links = r["text"], r["links"]
    t = now()
    db.chats.insert_many([{"user_id": g.user["_id"], "role": "user", "text": question, "created_at": t},
                          {"user_id": g.user["_id"], "role": "assistant", "text": answer, "links": links, "mode": mode,
                           "created_at": t + dt.timedelta(milliseconds=1)}])
    mark_dirty()
    return ok({"answer": answer, "links": links, "mode": mode})


# ============================================================ community
def post_view(p, my_id, users):
    author = users.get(p["user_id"], {})
    return {**{k: v for k, v in p.items() if k not in ("upvoters",)}, "author": author.get("name", "Farmer"),
            "author_level": level_for(author.get("points", 0))["level"], "upvotes": len(p.get("upvoters", [])),
            "upvoted": my_id in p.get("upvoters", []), "mine": p["user_id"] == my_id}


def users_by_id(ids):
    return {u["_id"]: u for u in get_db().users.find({"_id": {"$in": list(set(ids))}}, {"name": 1, "points": 1})}


@api.get("/community")
@login_required
def list_posts():
    q = {}
    crop = request.args.get("crop")
    if crop in CROPS:
        q["crop"] = crop
    scope = request.args.get("scope")
    farm = current_farm()
    if scope == "district" and farm:
        q.update({"state": farm["state"], "district": farm["district"]})
    elif scope == "state" and farm:
        q["state"] = farm["state"]
    elif scope == "mine":
        q["user_id"] = g.user["_id"]
    if request.args.get("kind") in ("question", "tip"):
        q["kind"] = request.args["kind"]
    posts = list(get_db().posts.find(q).sort("created_at", -1).limit(60))
    users = users_by_id([p["user_id"] for p in posts])
    return ok({"posts": [post_view(p, g.user["_id"], users) for p in posts]})


@api.post("/community")
@login_required
def create_post():
    data = body()
    farm = current_farm() or {}
    post = {"user_id": g.user["_id"], "kind": choice(data, "kind", ["question", "tip"]),
            "title": text(data, "title", max_len=140, min_len=5), "body": long_text(data, "body", max_len=3000),
            "crop": choice(data, "crop", list(CROPS), required=False), "state": farm.get("state"),
            "district": farm.get("district"), "upvoters": [], "replies": 0, "solved": False, "created_at": now()}
    post["_id"] = get_db().posts.insert_one(post).inserted_id
    mark_dirty()
    award(g.user["_id"], "post", "Shared with the community", str(post["_id"]))
    return ok({"post": post_view(post, g.user["_id"], users_by_id([g.user["_id"]]))}, 201)


def find_post(post_id):
    post = get_db().posts.find_one({"_id": oid(post_id)})
    if not post:
        raise ApiError("Not found", 404)
    return post


@api.get("/community/<post_id>")
@login_required
def get_post(post_id):
    post = find_post(post_id)
    replies = list(get_db().replies.find({"post_id": post["_id"]}).sort("created_at", 1))
    users = users_by_id([post["user_id"]] + [r["user_id"] for r in replies])
    return ok({"post": post_view(post, g.user["_id"], users),
               "replies": [post_view(r, g.user["_id"], users) for r in replies]})


@api.delete("/community/<post_id>")
@login_required
def delete_post(post_id):
    post = find_post(post_id)
    if post["user_id"] != g.user["_id"]:
        raise ApiError("You can only delete your own posts", 403)
    db = get_db()
    db.replies.delete_many({"post_id": post["_id"]})
    db.posts.delete_one({"_id": post["_id"]})
    mark_dirty()
    return ok()


@api.post("/community/<post_id>/replies")
@login_required
def add_reply(post_id):
    post = find_post(post_id)
    data = body()
    reply = {"post_id": post["_id"], "user_id": g.user["_id"], "body": long_text(data, "body", max_len=2000),
             "upvoters": [], "accepted": False, "created_at": now()}
    db = get_db()
    reply["_id"] = db.replies.insert_one(reply).inserted_id
    db.posts.update_one({"_id": post["_id"]}, {"$inc": {"replies": 1}})
    mark_dirty()
    if post["user_id"] != g.user["_id"]:
        award(g.user["_id"], "reply", "Answered a fellow farmer", str(reply["_id"]))
    return ok({"reply": post_view(reply, g.user["_id"], users_by_id([g.user["_id"]]))}, 201)


@api.post("/community/<post_id>/upvote")
@login_required
def upvote(post_id):
    post = find_post(post_id)
    if post["user_id"] == g.user["_id"]:
        raise ApiError("You cannot upvote your own post")
    on = g.user["_id"] not in post.get("upvoters", [])
    get_db().posts.update_one({"_id": post["_id"]}, {"$addToSet" if on else "$pull": {"upvoters": g.user["_id"]}})
    mark_dirty()
    return ok({"upvoted": on, "upvotes": len(post.get("upvoters", [])) + (1 if on else -1)})


@api.post("/community/<post_id>/replies/<reply_id>/accept")
@login_required
def accept_reply(post_id, reply_id):
    post = find_post(post_id)
    if post["user_id"] != g.user["_id"]:
        raise ApiError("Only the person who asked can mark the answer", 403)
    db = get_db()
    reply = db.replies.find_one({"_id": oid(reply_id), "post_id": post["_id"]})
    if not reply:
        raise ApiError("Not found", 404)
    db.replies.update_many({"post_id": post["_id"]}, {"$set": {"accepted": False}})
    db.replies.update_one({"_id": reply["_id"]}, {"$set": {"accepted": True}})
    db.posts.update_one({"_id": post["_id"]}, {"$set": {"solved": True}})
    mark_dirty()
    if reply["user_id"] != g.user["_id"]:
        award(reply["user_id"], "solved", "Your answer solved a problem", str(post["_id"]))
    return get_post(post_id)
