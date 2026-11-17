"""Weather: 7-day forecast from Open-Meteo, farm alerts, and a water-need estimate.

Open-Meteo (https://open-meteo.com) is free for non-commercial use and needs no API key.
If it cannot be reached, the app falls back to the district's long-term rainfall normals
(India Meteorological Department) and says so, instead of failing.
"""
from __future__ import annotations

import calendar
import datetime as dt
import time

import requests

from . import geo
from .config import Config
from .core import today

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
DAILY = ["weather_code", "temperature_2m_max", "temperature_2m_min", "precipitation_sum",
         "precipitation_probability_max", "wind_speed_10m_max", "relative_humidity_2m_mean",
         "et0_fao_evapotranspiration"]
CURRENT = ["temperature_2m", "relative_humidity_2m", "precipitation", "wind_speed_10m", "weather_code"]
CACHE_SECONDS = 30 * 60
_cache: dict[tuple, tuple[float, dict]] = {}

WMO = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle", 56: "Freezing drizzle", 57: "Freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain", 67: "Freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains", 80: "Light showers", 81: "Showers",
    82: "Violent showers", 85: "Snow showers", 86: "Snow showers", 95: "Thunderstorm",
    96: "Thunderstorm with hail", 99: "Thunderstorm with hail",
}


def describe(code) -> str:
    return WMO.get(int(code), "—") if code is not None else "—"


def icon_for(code) -> str:
    if code is None:
        return "cloud"
    code = int(code)
    if code == 0:
        return "sun"
    if code in (1, 2):
        return "partly"
    if code in (3, 45, 48):
        return "cloud"
    if code >= 95:
        return "storm"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    return "rain"


def parse_open_meteo(payload: dict) -> dict:
    """Turn Open-Meteo's column-style JSON into a list of days."""
    daily = payload.get("daily") or {}
    days = []
    for i, date in enumerate(daily.get("time", [])):
        def col(name):
            values = daily.get(name)
            return values[i] if values and i < len(values) else None

        days.append({
            "date": date, "code": col("weather_code"), "summary": describe(col("weather_code")),
            "icon": icon_for(col("weather_code")), "tmax": col("temperature_2m_max"), "tmin": col("temperature_2m_min"),
            "rain_mm": col("precipitation_sum") or 0.0, "rain_chance": col("precipitation_probability_max"),
            "wind_kmh": col("wind_speed_10m_max"), "humidity": col("relative_humidity_2m_mean"),
            "et0_mm": col("et0_fao_evapotranspiration"),
        })
    cur = payload.get("current") or {}
    current = None
    if cur:
        current = {"temp": cur.get("temperature_2m"), "humidity": cur.get("relative_humidity_2m"),
                   "rain_mm": cur.get("precipitation"), "wind_kmh": cur.get("wind_speed_10m"),
                   "summary": describe(cur.get("weather_code")), "icon": icon_for(cur.get("weather_code")),
                   "time": cur.get("time")}
    return {"source": "open-meteo", "live": True, "current": current, "days": days}


def _fetch(lat: float, lng: float) -> dict:
    params = {"latitude": round(lat, 3), "longitude": round(lng, 3), "daily": ",".join(DAILY),
              "current": ",".join(CURRENT), "timezone": "auto", "forecast_days": 7}
    resp = requests.get(FORECAST_URL, params=params, timeout=8)
    if resp.status_code == 400:  # a variable this API version does not know: ask for the core set only
        params["daily"] = ",".join(DAILY[:6])
        resp = requests.get(FORECAST_URL, params=params, timeout=8)
    resp.raise_for_status()
    return resp.json()


def from_normals(state: str | None, district: str | None) -> dict:
    """What a normal week looks like for this district at this time of year (rain only)."""
    normals = geo.rain_normals(state, district) if state and district else None
    start = today()
    days = []
    for i in range(7):
        d = start + dt.timedelta(days=i)
        per_day = None
        if normals:
            per_day = round(normals[d.month - 1] / calendar.monthrange(d.year, d.month)[1], 1)
        days.append({"date": d.isoformat(), "code": None, "summary": "Typical for the season", "icon": "cloud",
                     "tmax": None, "tmin": None, "rain_mm": per_day, "rain_chance": None, "wind_kmh": None,
                     "humidity": None, "et0_mm": None})
    month_total = round(normals[start.month - 1]) if normals else None
    return {"source": "imd-normals", "live": False, "current": None, "days": days,
            "normal_month_rain_mm": month_total, "month": calendar.month_name[start.month]}


def forecast(lat: float | None, lng: float | None, state: str | None = None, district: str | None = None) -> dict:
    if Config.WEATHER_MODE != "live" or lat is None or lng is None:
        return from_normals(state, district)
    key = (round(lat, 2), round(lng, 2))
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]
    try:
        data = parse_open_meteo(_fetch(lat, lng))
        if not data["days"]:
            raise ValueError("empty forecast")
    except Exception as exc:
        data = from_normals(state, district)
        data["error"] = f"Live forecast unavailable ({type(exc).__name__})"
        return data
    normals = geo.rain_normals(state, district) if state and district else None
    if normals:
        data["normal_month_rain_mm"] = round(normals[today().month - 1])
        data["month"] = calendar.month_name[today().month]
    _cache[key] = (time.time(), data)
    return data


def search_place(query: str) -> list[dict]:
    """Find a village or town in India by name (Open-Meteo geocoding)."""
    if Config.WEATHER_MODE != "live":
        return []
    try:
        resp = requests.get(GEOCODE_URL, params={"name": query, "count": 8, "language": "en", "format": "json",
                                                 "countryCode": "IN"}, timeout=8)
        resp.raise_for_status()
        results = resp.json().get("results") or []
    except Exception:
        return []
    out = []
    for r in results:
        if r.get("country_code") not in (None, "IN"):
            continue
        place = geo.locate(r["latitude"], r["longitude"])
        out.append({"name": r.get("name"), "admin": ", ".join(x for x in (r.get("admin2"), r.get("admin1")) if x),
                    "lat": r["latitude"], "lng": r["longitude"],
                    "state": place["state"] if place else None, "district": place["district"] if place else None})
    return out


# ------------------------------------------------------------------ alerts
def _weekday(date: str) -> str:
    return dt.date.fromisoformat(date).strftime("%a %d %b")


FROST_SENSITIVE = {"potato", "tomato", "mustard", "gram", "coriander", "chilli", "banana", "sugarcane", "tur", "masoor"}
WIND_SENSITIVE = {"banana", "sugarcane", "maize", "cotton", "tomato", "rice", "wheat"}


def alerts(fc: dict, crop: dict | None = None, stage: str | None = None, irrigation: str = "limited") -> list[dict]:
    """Plain-language warnings for the coming week, tuned to the crop and its growth stage."""
    if not fc.get("live"):
        return []
    days = fc["days"]
    out: list[dict] = []
    crop_id = crop["id"] if crop else None
    name = crop["name"].split(" (")[0].lower() if crop else "the crop"

    def add(level, title, text, date=None):
        out.append({"level": level, "title": title, "text": text, "date": date})

    heavy = [d for d in days if (d["rain_mm"] or 0) >= 50]
    soon_rain = [d for d in days[:3] if (d["rain_mm"] or 0) >= 10]
    week_rain = sum(d["rain_mm"] or 0 for d in days)
    tmaxes = [d["tmax"] for d in days if d["tmax"] is not None]
    tmins = [d["tmin"] for d in days if d["tmin"] is not None]

    if heavy:
        d = heavy[0]
        text = f"About {d['rain_mm']:.0f} mm is forecast. Clear field drains, and do not apply fertiliser or spray before it."
        if stage in ("maturation", "harvesting"):
            text += f" If {name} is ready, harvest before the rain or move cut produce under cover."
        elif stage in ("preparation", "sowing"):
            text += " Hold sowing until the field can be walked on without sinking."
        add("danger", f"Heavy rain on {_weekday(d['date'])}", text, d["date"])
    elif soon_rain:
        d = soon_rain[0]
        text = f"{d['rain_mm']:.0f} mm expected. Skip irrigation, and put off spraying and top-dressing until it has passed."
        if stage == "harvesting":
            text += " Cover harvested produce and delay cutting if you can."
        add("warn", f"Rain on {_weekday(d['date'])}", text, d["date"])

    if tmaxes and max(tmaxes) >= 40:
        d = max(days, key=lambda x: x["tmax"] or -99)
        add("danger", f"Heat wave: up to {d['tmax']:.0f}°C",
            "Irrigate in the evening or early morning, mulch where possible, and avoid field work from 12 to 4 pm.", d["date"])
    elif crop and tmaxes and max(tmaxes) >= crop["temp"][1] + 3 and stage in ("flowering", "maturation"):
        d = max(days, key=lambda x: x["tmax"] or -99)
        add("warn", f"Heat stress risk for {name}",
            f"{d['tmax']:.0f}°C is above what {name} tolerates at this stage ({crop['temp'][1]}°C). "
            "A light irrigation keeps the canopy cooler and protects grain or fruit set.", d["date"])

    if tmins and min(tmins) <= 4:
        d = min(days, key=lambda x: x["tmin"] if x["tmin"] is not None else 99)
        text = "Give a light irrigation the evening before; moist soil holds heat and protects the crop."
        if crop_id in FROST_SENSITIVE:
            text = f"{crop['name'].split(' (')[0]} is easily damaged by frost. " + text
        add("danger", f"Frost risk: {d['tmin']:.0f}°C on {_weekday(d['date'])}", text, d["date"])
    elif crop and tmins and min(tmins) < crop["temp"][0] - 5 and stage in ("germination", "flowering"):
        d = min(days, key=lambda x: x["tmin"] if x["tmin"] is not None else 99)
        add("warn", f"Cold nights for {name}",
            f"Night temperature near {d['tmin']:.0f}°C will slow growth at this stage. Expect slower emergence or "
            "flowering, and hold nitrogen top-dressing until nights warm up.", d["date"])

    windy = [d for d in days if (d["wind_kmh"] or 0) >= 40]
    if windy:
        d = windy[0]
        text = "Do not spray on windy days."
        if crop_id in WIND_SENSITIVE:
            text = f"Prop or tie up {name} where it can lodge, and do not spray."
        add("warn", f"Strong wind on {_weekday(d['date'])} ({d['wind_kmh']:.0f} km/h)", text, d["date"])

    humid = [d for d in days if d["humidity"] is not None and d["humidity"] >= 80
             and d["tmax"] is not None and d["tmin"] is not None and 15 <= (d["tmax"] + d["tmin"]) / 2 <= 30]
    if len(humid) >= 3 and stage in ("vegetative", "flowering", "maturation", None):
        text = "Several humid, mild days in a row favour blights, mildews and leaf spots. Walk the field and check the lower leaves."
        if crop and crop["pests"]:
            text += f" In {name}, watch for: {', '.join(crop['pests'][:3]).lower()}."
        add("warn", "Disease-friendly weather", text, humid[0]["date"])

    if week_rain < 5 and tmaxes and sum(tmaxes) / len(tmaxes) >= 30 and stage not in ("harvesting", "preparation"):
        level = "warn" if irrigation == "none" else "info"
        text = f"Only {week_rain:.0f} mm of rain is expected in 7 days."
        if crop and crop["critical_water"] and stage in ("vegetative", "flowering"):
            text += f" Water matters most for {name} at: {', '.join(crop['critical_water'])}."
        if irrigation == "none":
            text += " With no irrigation, conserve moisture: mulch, weed, and hoe lightly to break the soil crust."
        add(level, "Dry week ahead", text)

    if stage == "sowing" and not heavy and week_rain >= 15 and irrigation == "none":
        add("info", "Good sowing window", f"{week_rain:.0f} mm of rain is expected this week, enough to germinate a rainfed crop.")
    return out


# ------------------------------------------------------------------ water need
KC = {"sowing": 0.4, "germination": 0.4, "vegetative": 0.8, "flowering": 1.1, "maturation": 0.75,
      "harvesting": 0.0, "preparation": 0.0}


def water_need(fc: dict, stage: str | None, crop_id: str | None = None) -> dict | None:
    """This week's irrigation need: crop water use (ET0 x crop coefficient) minus useful rain."""
    if not fc.get("live") or stage not in KC or KC[stage] == 0:
        return None
    et0 = [d["et0_mm"] for d in fc["days"] if d["et0_mm"] is not None]
    if len(et0) < 5:
        return None
    kc = KC[stage]
    if crop_id == "rice" and stage in ("vegetative", "flowering"):
        kc = 1.2
    use = sum(et0) * kc
    rain = sum(d["rain_mm"] or 0 for d in fc["days"])
    useful_rain = min(rain * 0.8, use)  # some rain runs off or drains away
    need = max(0.0, use - useful_rain)
    return {"crop_use_mm": round(use, 1), "rain_mm": round(rain, 1), "irrigation_mm": round(need, 1),
            "litres_per_acre": int(round(need * 4047, -2)), "kc": kc}
