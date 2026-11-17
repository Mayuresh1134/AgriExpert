import datetime as dt
import io
import os

os.environ["AGRI_DB"] = "memory"
os.environ["WEATHER_MODE"] = "offline"
os.environ["GEMINI_API_KEY"] = ""
os.environ["DATA_GOV_API_KEY"] = ""

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from PIL import Image  # noqa: E402

from agri import create_app, db, geo, lifecycle, recommend, weather  # noqa: E402
from agri.config import Config  # noqa: E402
from agri.core import today  # noqa: E402
from agri.crops_kb import CROPS  # noqa: E402

Config.DB_MODE, Config.WEATHER_MODE, Config.GEMINI_API_KEY = "memory", "offline", ""
FARM = {"state": "Maharashtra", "district": "Nashik", "land_area_acres": 4, "soil_type": "black",
        "irrigation": "limited", "budget": 150000, "ownership": "owned"}


@pytest.fixture
def client():
    db.reset_for_tests()
    Config.JWT_SECRET = "test-secret-" + "x" * 40
    return create_app(testing=True).test_client()


def signup(client, login="9876543210", name="Ramesh Patil"):
    r = client.post("/api/auth/register", json={"name": name, "login": login, "password": "secret12"})
    assert r.status_code == 201, r.json
    return {"Authorization": "Bearer " + r.json["token"]}


def with_farm(client, **extra):
    h = signup(client, **extra)
    r = client.put("/api/farm", json=FARM, headers=h)
    assert r.status_code == 200, r.json
    return h


def leaf_jpeg(color=(40, 140, 40)):
    img = Image.new("RGB", (320, 240), color)
    for x in range(60, 120):
        for y in range(80, 140):
            img.putpixel((x, y), (120, 80, 30))
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return buf.getvalue()


# ------------------------------------------------------------------ accounts
def test_register_login_and_bad_password(client):
    signup(client, login="+91 98765 43210")
    r = client.post("/api/auth/login", json={"login": "9876543210", "password": "secret12"})
    assert r.status_code == 200 and r.json["user"]["name"] == "Ramesh Patil"
    assert client.post("/api/auth/login", json={"login": "9876543210", "password": "nope"}).status_code == 401


def test_duplicate_and_invalid_signup(client):
    signup(client)
    r = client.post("/api/auth/register", json={"name": "Again", "login": "9876543210", "password": "secret12"})
    assert r.status_code == 409
    r = client.post("/api/auth/register", json={"name": "X Y", "login": "12345", "password": "secret12"})
    assert r.status_code == 400
    r = client.post("/api/auth/register", json={"name": "X Y", "login": "a@b.in", "password": "123"})
    assert r.status_code == 400


def test_routes_need_login(client):
    assert client.get("/api/dashboard").status_code == 401
    assert client.get("/api/dashboard", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_password_is_hashed(client):
    signup(client)
    user = db.get_db().users.find_one({"login": "9876543210"})
    assert "secret12" not in user["password"] and user["password"].startswith("pbkdf2:")


# ------------------------------------------------------------------ farm
def test_farm_validation(client):
    h = signup(client)
    bad = dict(FARM, district="Pune city")
    assert client.put("/api/farm", json=bad, headers=h).status_code == 400
    bad = dict(FARM, land_area_acres=-1)
    assert client.put("/api/farm", json=bad, headers=h).status_code == 400
    r = client.put("/api/farm", json=FARM, headers=h)
    assert r.json["farm"]["location_source"] == "district"
    r = client.put("/api/farm", json=dict(FARM, lat=20.0, lng=73.8), headers=h)
    assert r.json["farm"]["location_source"] == "gps"


def test_locate_and_districts():
    assert geo.locate(19.9975, 73.7898)["district"] == "Nashik"
    assert geo.locate(30.90, 75.85)["district"] == "Ludhiana"
    assert geo.locate(51.5, 0.1) is None
    assert "Nashik" in geo.districts_of("Maharashtra")
    assert len(geo.states()) >= 30


# ------------------------------------------------------------------ recommendations
def test_recommendations_are_plausible(client):
    h = with_farm(client)
    r = client.get("/api/recommend?season=kharif", headers=h)
    assert r.status_code == 200
    crops = r.json["crops"]
    assert crops and all(0 <= c["score"] <= 100 for c in crops)
    assert [c["score"] for c in crops] == sorted([c["score"] for c in crops], reverse=True)
    assert any(c["id"] in ("soybean", "maize", "bajra", "cotton") for c in crops[:4])
    assert all(c["reasons"] or c["cautions"] for c in crops)


def test_punjab_rabi_prefers_wheat():
    r = recommend.recommend({"state": "Punjab", "district": "Ludhiana", "land_area_acres": 5, "irrigation": "assured"}, "rabi")
    assert r["crops"][0]["id"] == "wheat"


def test_rainfed_penalises_thirsty_crops():
    farm = {"state": "Rajasthan", "district": "Jaipur", "land_area_acres": 5}
    dry = {c["id"]: c for c in recommend.recommend({**farm, "irrigation": "none"}, "kharif")["crops"]}
    wet = {c["id"]: c for c in recommend.recommend({**farm, "irrigation": "assured"}, "kharif")["crops"]}
    common = set(dry) & set(wet)
    assert common and all(dry[c]["parts"]["water"] <= wet[c]["parts"]["water"] for c in common)


def test_budget_limits_area():
    r = recommend.recommend({"state": "Maharashtra", "district": "Nashik", "land_area_acres": 10, "budget": 10000,
                             "irrigation": "limited"}, "kharif")
    assert any(c["fits_budget"] is False and c["affordable_acres"] < 10 for c in r["crops"])


def test_fertilizer_plan_maths():
    p = recommend.fertilizer_plan("wheat", 2.471)  # one hectare
    assert p["nutrients_kg"] == {"n": 120.0, "p2o5": 60.0, "k2o": 40.0}
    # DAP supplies all the P and some N; urea makes up the rest of the N
    assert abs(p["products"]["dap_kg"] * 0.18 + p["products"]["urea_kg"] * 0.46 - 120) < 0.5
    low = recommend.fertilizer_plan("wheat", 2.471, {"n": "low"})
    assert low["nutrients_kg"]["n"] == 150.0


# ------------------------------------------------------------------ crop cycles
def test_cycle_lifecycle(client):
    h = with_farm(client)
    sow = (today() - dt.timedelta(days=40)).isoformat()
    r = client.post("/api/cycles", json={"crop": "wheat", "sowing_date": sow, "area_acres": 2}, headers=h)
    assert r.status_code == 201, r.json
    cid = r.json["cycle"]["id"]
    assert r.json["cycle"]["progress"]["stage"] == "vegetative"
    r = client.get(f"/api/cycles/{cid}", headers=h)
    tasks = r.json["cycle"]["tasks"]
    assert any(t["id"] == "veg_topdress1" for t in tasks)

    r = client.post(f"/api/cycles/{cid}/tasks/veg_topdress1", json={"done": True}, headers=h)
    assert r.json["done"] and r.json["points"] == 10
    r = client.post(f"/api/cycles/{cid}/tasks/veg_topdress1", json={"done": True}, headers=h)
    assert r.json["points"] == 0  # no double points
    r = client.post(f"/api/cycles/{cid}/tasks/veg_topdress1", json={"done": False}, headers=h)
    assert not r.json["done"]
    assert client.post(f"/api/cycles/{cid}/tasks/nope", json={}, headers=h).status_code == 404

    for entry in ({"kind": "fertilizer", "cost": 2700, "product": "Urea"},
                  {"kind": "harvest", "quantity_q": 36},
                  {"kind": "sale", "quantity_q": 30, "price": 2600}):
        assert client.post(f"/api/cycles/{cid}/logs", json=entry, headers=h).status_code == 201
    s = client.get(f"/api/cycles/{cid}", headers=h).json["cycle"]["summary"]
    assert s == {**s, "cost": 2700, "revenue": 78000, "profit": 75300, "yield_q_acre": 18.0, "avg_sale_price": 2600}

    r = client.patch(f"/api/cycles/{cid}", json={"stage": "flowering"}, headers=h)
    assert r.json["cycle"]["progress"]["stage"] == "flowering"
    assert client.post(f"/api/cycles/{cid}/logs", json={"kind": "sale", "quantity_q": 1}, headers=h).status_code == 400
    assert client.delete(f"/api/cycles/{cid}", headers=h).status_code == 200


def test_cycle_rules(client):
    h = with_farm(client)
    too_big = {"crop": "rice", "sowing_date": today().isoformat(), "area_acres": 50}
    assert client.post("/api/cycles", json=too_big, headers=h).status_code == 400
    other = with_farm(client, login="other@example.com", name="Other farmer")
    r = client.post("/api/cycles", json={"crop": "rice", "sowing_date": today().isoformat(), "area_acres": 1}, headers=h)
    assert client.get(f"/api/cycles/{r.json['cycle']['id']}", headers=other).status_code == 404
    assert client.get("/api/cycles/not-an-id", headers=h).status_code == 404


@pytest.mark.parametrize("crop_id", list(CROPS))
def test_every_crop_has_ordered_stages_and_tasks(crop_id):
    crop = {"id": crop_id, **CROPS[crop_id]}
    windows = lifecycle.stage_windows(crop)
    assert [w["id"] for w in windows] == lifecycle.STAGE_IDS
    assert all(w["start_day"] < w["end_day"] for w in windows)
    assert all(a["end_day"] == b["start_day"] for a, b in zip(windows, windows[1:]))
    tasks = lifecycle.tasks_for({"crop": crop_id, "area_acres": 1})
    assert len({t["id"] for t in tasks}) == len(tasks)
    assert {t["stage"] for t in tasks} == set(lifecycle.STAGE_IDS)


# ------------------------------------------------------------------ weather
def test_weather_parsing_and_alerts():
    days = [dt.date(2026, 11, 17) + dt.timedelta(days=i) for i in range(7)]
    payload = {"daily": {"time": [d.isoformat() for d in days], "weather_code": [61] * 7,
                         "temperature_2m_max": [24] * 7, "temperature_2m_min": [3, 12, 12, 12, 12, 12, 12],
                         "precipitation_sum": [0, 65, 2, 0, 0, 0, 0], "precipitation_probability_max": [10] * 7,
                         "wind_speed_10m_max": [10] * 7, "relative_humidity_2m_mean": [60] * 7,
                         "et0_fao_evapotranspiration": [3.0] * 7}}
    fc = weather.parse_open_meteo(payload)
    assert len(fc["days"]) == 7 and fc["days"][1]["rain_mm"] == 65
    crop = {"id": "potato", **CROPS["potato"]}
    titles = " | ".join(a["title"] for a in weather.alerts(fc, crop, "maturation"))
    assert "Heavy rain" in titles and "Frost" in titles
    need = weather.water_need(fc, "flowering", "potato")
    assert need["crop_use_mm"] == pytest.approx(7 * 3.0 * 1.1)


def test_offline_weather_uses_normals():
    fc = weather.forecast(20.0, 73.8, "Maharashtra", "Nashik")
    assert fc["live"] is False and len(fc["days"]) == 7 and fc["normal_month_rain_mm"] is not None


# ------------------------------------------------------------------ disease scan
def test_scan(client):
    h = signup(client)
    r = client.post("/api/scan", data={"image": (io.BytesIO(leaf_jpeg()), "leaf.jpg"), "crop": "tomato"},
                    headers=h, content_type="multipart/form-data")
    assert r.status_code == 200, r.json
    assert r.json["result"]["id"].startswith("tomato_")
    assert 0 <= r.json["result"]["confidence"] <= 1 and len(r.json["alternatives"]) == 2
    assert r.json["result"]["symptoms"]
    r = client.post("/api/scan", data={"image": (io.BytesIO(b"not an image"), "x.jpg")}, headers=h,
                    content_type="multipart/form-data")
    assert r.status_code == 400
    assert len(client.get("/api/scans", headers=h).json["scans"]) == 1


def test_disease_model_on_real_photo():
    """A rice blast photo from the Paddy Doctor test split, if the dataset is on this machine."""
    from agri.disease import model

    path = "/home/claude/data_src/paddy/paddies/blast/images"
    if not os.path.isdir(path):
        pytest.skip("dataset not available")
    import pathlib

    test_ids = (pathlib.Path(path).parent / "sets" / "test.txt").read_text().split()[:5]
    hits = sum(model().predict((pathlib.Path(path) / f"{i}.jpg").read_bytes(), "rice")["result"]["id"] == "rice_blast"
               for i in test_ids)
    assert hits >= 3


# ------------------------------------------------------------------ markets, schemes, assistant
def test_markets(client):
    h = with_farm(client)
    r = client.get("/api/markets/onion?radius=300", headers=h)
    assert r.status_code == 200
    o, m = r.json["outlook"], r.json["markets"]
    assert o["latest"] > 0 and len(o["forecast"]) == 6
    assert all(f["low"] <= f["price"] <= f["high"] for f in o["forecast"])
    nets = [x["net_per_q"] for x in m["markets"]]
    assert nets == sorted(nets, reverse=True)
    assert all(x["distance_km"] <= 300 for x in m["markets"])
    assert client.get("/api/markets/plutonium", headers=h).status_code == 404


def test_schemes_use_farm(client):
    h = with_farm(client)
    s = {x["id"]: x for x in client.get("/api/schemes", headers=h).json["schemes"]}
    assert s["pm_kisan"]["match"] == "yes" and s["shc"]["match"] == "yes"
    client.put("/api/farm", json=dict(FARM, land_area_acres=20, ownership="tenant"), headers=h)
    s = {x["id"]: x for x in client.get("/api/schemes", headers=h).json["schemes"]}
    assert s["pm_kisan"]["match"] == "no" and s["pm_kmy"]["match"] == "no"


@pytest.mark.parametrize("question,expect", [
    ("what is the onion price", "Onion"),
    ("how much urea for wheat", "urea"),
    ("which crop should i grow", "best fits"),
    ("tell me about kisan credit card loan", "Kisan Credit Card"),
    ("my tomato leaves have spots", "photo"),
])
def test_offline_assistant(client, question, expect):
    h = with_farm(client)
    r = client.post("/api/assistant", json={"message": question}, headers=h)
    assert r.status_code == 200 and r.json["mode"] == "built-in"
    assert expect.lower() in r.json["answer"].lower(), r.json["answer"]
    assert len(client.get("/api/assistant", headers=h).json["messages"]) == 2


# ------------------------------------------------------------------ community and points
def test_community_flow(client):
    asker = with_farm(client)
    helper = with_farm(client, login="helper@example.com", name="Sunita Jadhav")
    r = client.post("/api/community", json={"kind": "question", "title": "Yellow leaves on soybean",
                                            "body": "Lower leaves turning yellow after rain.", "crop": "soybean"},
                    headers=asker)
    pid = r.json["post"]["id"]
    assert client.post(f"/api/community/{pid}/upvote", headers=asker).status_code == 400
    assert client.post(f"/api/community/{pid}/upvote", headers=helper).json["upvoted"] is True
    rid = client.post(f"/api/community/{pid}/replies", json={"body": "Check drainage; likely waterlogging."},
                      headers=helper).json["reply"]["id"]
    assert client.post(f"/api/community/{pid}/replies/{rid}/accept", headers=helper).status_code == 403
    r = client.post(f"/api/community/{pid}/replies/{rid}/accept", headers=asker)
    assert r.json["post"]["solved"] and r.json["replies"][0]["accepted"]
    pts = client.get("/api/me/points", headers=helper).json["summary"]["points"]
    assert pts == 10 + 25  # reply + solved
    assert len(client.get("/api/community?scope=district&crop=soybean", headers=helper).json["posts"]) == 1
    assert client.delete(f"/api/community/{pid}", headers=helper).status_code == 403


def test_dashboard(client):
    h = with_farm(client)
    client.post("/api/cycles", json={"crop": "gram", "sowing_date": (today() - dt.timedelta(days=5)).isoformat(),
                                     "area_acres": 2}, headers=h)
    r = client.get("/api/dashboard", headers=h)
    assert r.status_code == 200
    d = r.json
    assert d["weather"]["days"] and d["cycles"][0]["progress"]["stage"] == "germination"
    assert d["prices"][0]["crop"] == "gram"


def test_local_store_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "LOCAL_FILE", tmp_path / "local_db.json")
    monkeypatch.setattr(db, "APP_DATA_DIR", tmp_path)
    monkeypatch.setattr(Config, "DB_MODE", "local")
    db.reset_for_tests()
    store = db.get_db()
    store.users.insert_one({"login": "a@b.in", "name": "A"})
    db.save_local(force=True)
    db.reset_for_tests()
    assert db.get_db().users.find_one({"login": "a@b.in"})["name"] == "A"
    (tmp_path / "local_db.json").write_text("{broken")
    db.reset_for_tests()
    assert db.get_db().users.count_documents({}) == 0  # started empty
    assert (tmp_path / "local_db.unreadable.json").exists()  # and kept the damaged file
    monkeypatch.setattr(Config, "DB_MODE", "memory")
    db.reset_for_tests()


def test_models_report(client):
    r = client.get("/api/meta/models").json
    assert r["yield"]["test"]["models"] and r["price"]["test"] and r["disease"]["results"]
    assert np.isfinite(r["yield"]["test"]["range_80_coverage_pct"])
