"""Clean the district crop production statistics.

    python -m ml.prepare_crops

Input : data/raw/india_crop_production_1997_2020.csv.gz
        District-wise, season-wise area and production published by the Directorate of
        Economics & Statistics (Ministry of Agriculture) on data.gov.in, 1997-2020.
Output: data/clean/crop_yields.csv.gz   one row per district, crop, season and year
"""
from pathlib import Path

import json
import pandas as pd

from agri.crops_kb import CROPS
from ml.names import DistrictMatcher, norm

BACKEND = Path(__file__).resolve().parent.parent
RAW = BACKEND / "data" / "raw" / "india_crop_production_1997_2020.csv.gz"
OUT = BACKEND / "data" / "clean" / "crop_yields.csv.gz"

SEASON_MAP = {"kharif": "kharif", "autumn": "kharif", "rabi": "rabi", "summer": "summer", "whole year": "annual"}


def load_clean(verbose: bool = True) -> pd.DataFrame:
    raw = pd.read_csv(RAW)
    for col in ("state", "district", "crop", "season"):
        raw[col] = raw[col].astype(str).str.strip()
    steps = [("Raw rows", len(raw))]

    # 1. keep the crops in our knowledge base
    apy_to_id = {norm(a): cid for cid, c in CROPS.items() for a in c["apy"]}
    raw["crop_id"] = raw["crop"].map(lambda s: apy_to_id.get(norm(s)))
    df = raw[raw["crop_id"].notna()].copy()
    steps.append(("Rows for the crops we cover", len(df)))

    # 2. put every row on today's district map
    districts = json.loads((BACKEND / "agri" / "data" / "districts.json").read_text())
    matcher = DistrictMatcher((d["state"], d["district"]) for d in districts)
    pairs = df[["state", "district"]].drop_duplicates()
    lookup = {(s, d): matcher.match(s, d) for s, d in pairs.itertuples(index=False)}
    hits = df[["state", "district"]].apply(lambda r: lookup[(r["state"], r["district"])], axis=1)
    df["geo_state"] = hits.map(lambda h: h[0] if h else None)
    df["geo_district"] = hits.map(lambda h: h[1] if h else None)
    unmatched = sorted({k for k, v in lookup.items() if v is None})
    df = df[df["geo_state"].notna()]
    steps.append(("Rows whose district is on the map", len(df)))

    # 3. seasons: "Winter" rice is the main monsoon (aman) crop; other winter crops are rabi
    s = df["season"].str.lower()
    df["season_id"] = s.map(SEASON_MAP)
    winter = s == "winter"
    df.loc[winter, "season_id"] = df.loc[winter, "crop_id"].map(lambda c: "kharif" if c == "rice" else "rabi")

    # 4. yields in tonnes of the product farmers sell, per hectare
    df = df[(df["area"] >= 1) & (df["production"] > 0)].copy()
    factor = df["crop_id"].map(lambda c: CROPS[c]["yield_factor"])
    df["yield_t_ha"] = df["production"] / df["area"] * factor
    steps.append(("Rows with at least 1 ha and some production", len(df)))

    # 5. drop implausible yields (unit slips in the source): outside the 0.5-99.5% band per crop
    lo = df.groupby("crop_id")["yield_t_ha"].transform(lambda v: v.quantile(0.005))
    hi = df.groupby("crop_id")["yield_t_ha"].transform(lambda v: v.quantile(0.995))
    df = df[(df["yield_t_ha"] >= lo) & (df["yield_t_ha"] <= hi)]
    steps.append(("Rows after removing extreme yields", len(df)))

    # 6. one row per district / crop / season / year (seasons merged above can collide)
    df["prod_t"] = df["yield_t_ha"] * df["area"]
    g = df.groupby(["geo_state", "geo_district", "crop_id", "season_id", "year"], as_index=False).agg(
        area_ha=("area", "sum"), prod_t=("prod_t", "sum"))
    g["yield_t_ha"] = g["prod_t"] / g["area_ha"]
    g = g.rename(columns={"geo_state": "state", "geo_district": "district", "crop_id": "crop", "season_id": "season"})
    g = g[g["year"] <= 2019]  # 2020 has only 305 rows in the source
    steps.append(("Clean rows (1997-2019)", len(g)))

    if verbose:
        for label, n in steps:
            print(f"{label:48s} {n:>8,}")
        print(f"{len(unmatched)} source districts not placed on the map: {unmatched[:12]}{' ...' if len(unmatched) > 12 else ''}")
    g.attrs["steps"] = steps
    return g[["state", "district", "crop", "season", "year", "area_ha", "yield_t_ha"]]


if __name__ == "__main__":
    out = load_clean()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.round({"area_ha": 1, "yield_t_ha": 4}).to_csv(OUT, index=False)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")
    print(out.groupby("crop")["yield_t_ha"].median().round(2).to_dict())
    print(out.groupby("season").size().to_dict(), out[["state", "district"]].drop_duplicates().shape[0], "districts")
