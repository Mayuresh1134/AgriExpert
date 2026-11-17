"""Districts: lists for the forms, GPS position -> district, and distances."""
from __future__ import annotations

import json
import math
from functools import lru_cache

from .config import DATA_DIR


@lru_cache(maxsize=1)
def _load():
    districts = json.loads((DATA_DIR / "districts.json").read_text())
    index = {(d["state"], d["district"]): d for d in districts}
    return districts, index


def states() -> list[str]:
    return sorted({d["state"] for d in _load()[0]})


def districts_of(state: str) -> list[str]:
    return sorted(d["district"] for d in _load()[0] if d["state"] == state)


def get(state: str, district: str) -> dict | None:
    return _load()[1].get((state, district))


def _inside(ring, lng, lat) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lng < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def distance_km(lat1, lng1, lat2, lng2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def locate(lat: float, lng: float) -> dict | None:
    """Which district is this point in? Falls back to the nearest district centre within 60 km."""
    all_districts = _load()[0]
    for d in all_districts:
        x0, y0, x1, y1 = d["bbox"]
        if x0 <= lng <= x1 and y0 <= lat <= y1 and any(_inside(r, lng, lat) for r in d["rings"]):
            return {"state": d["state"], "district": d["district"], "exact": True}
    near = min(all_districts, key=lambda d: distance_km(lat, lng, d["lat"], d["lng"]))
    if distance_km(lat, lng, near["lat"], near["lng"]) <= 60:
        return {"state": near["state"], "district": near["district"], "exact": False}
    return None


def rain_normals(state: str, district: str) -> list[float] | None:
    d = get(state, district)
    return d.get("rain") if d else None
