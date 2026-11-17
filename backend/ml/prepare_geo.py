"""Build agri/data/districts.json: every district's outline, centre point and rainfall normals.

    python -m ml.prepare_geo path/to/india-maps-data

Inputs
  * District boundaries: https://github.com/udit-001/india-maps-data  (geojson/states/*.geojson)
  * IMD district rainfall normals: data/raw/imd_district_rainfall_normals.csv (mm per month)

The outlines are simplified to about 1 km so the file stays small. They are used to turn a
GPS position into a district, and the centre points to measure distances to mandis.
"""
import csv
import json
import sys
from pathlib import Path

from shapely.geometry import mapping, shape

from ml.names import DistrictMatcher

BACKEND = Path(__file__).resolve().parent.parent
OUT = BACKEND / "agri" / "data" / "districts.json"
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def rings_of(geom):
    gj = mapping(geom)
    polys = [gj["coordinates"]] if gj["type"] == "Polygon" else gj["coordinates"]
    out = []
    for poly in polys:
        outer = [[round(x, 3), round(y, 3)] for x, y in poly[0]]
        if len(outer) >= 4:
            out.append(outer)  # holes are ignored: fine for "which district am I in"
    return out


def main(maps_dir: str) -> None:
    districts = []
    for f in sorted(Path(maps_dir, "geojson", "states").glob("*.geojson")):
        for feat in json.loads(f.read_text())["features"]:
            p = feat["properties"]
            geom = shape(feat["geometry"]).buffer(0)
            simple = geom.simplify(0.01, preserve_topology=True)
            c = geom.representative_point() if not geom.contains(geom.centroid) else geom.centroid
            districts.append({
                "state": p["st_nm"].strip(), "district": p["district"].strip(),
                "lat": round(c.y, 4), "lng": round(c.x, 4),
                "bbox": [round(v, 3) for v in geom.bounds],
                "rings": rings_of(simple),
            })

    matcher = DistrictMatcher((d["state"], d["district"]) for d in districts)
    index = {(d["state"], d["district"]): d for d in districts}
    matched = 0
    with open(BACKEND / "data" / "raw" / "imd_district_rainfall_normals.csv", newline="") as fh:
        for row in csv.DictReader(fh):
            hit = matcher.match(row["STATE_UT_NAME"].title(), row["DISTRICT"].title())
            if hit and "rain" not in index[hit]:
                index[hit]["rain"] = [float(row[m]) for m in MONTHS]
                matched += 1

    # Districts without their own normals (mostly districts created after the IMD table)
    # borrow the nearest district in the same state that has them.
    for d in districts:
        if "rain" in d:
            d["rain_source"] = "own"
            continue
        same = [o for o in districts if o["state"] == d["state"] and o.get("rain_source") == "own"]
        pool = same or [o for o in districts if o.get("rain_source") == "own"]
        if not pool:
            continue
        near = min(pool, key=lambda o: (o["lat"] - d["lat"]) ** 2 + (o["lng"] - d["lng"]) ** 2)
        d["rain"] = near["rain"]
        d["rain_source"] = f"nearest: {near['district']}"

    districts.sort(key=lambda d: (d["state"], d["district"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(districts, separators=(",", ":")))
    print(f"{len(districts)} districts, {matched} with their own rainfall normals, "
          f"{OUT.stat().st_size / 1e6:.2f} MB -> {OUT}")


if __name__ == "__main__":
    main(sys.argv[1])
