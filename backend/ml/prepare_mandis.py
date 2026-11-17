"""Build the mandi directory used for "best market to sell".

    python -m ml.prepare_mandis

Input : data/raw/mandi_snapshots/*.csv - nine single-day downloads of the Government of India
        "Current daily price of various commodities from various markets (Mandi)" feed
        (Agmarknet via data.gov.in), dated Aug 2024 to Sep 2025: 13,000 price reports from
        about 1,150 markets.
Output: agri/data/mandis.json

For each market and crop we keep the latest report and the market's usual price level
relative to the all-India median on the same day (1.08 = usually 8% above). The app multiplies
that level by today's national price to estimate what the market pays now. It is an
estimate from a handful of dated reports, not a live quote - set DATA_GOV_API_KEY to pull
today's actual prices instead.
"""
import json
from pathlib import Path

import pandas as pd

from ml.names import DistrictMatcher

BACKEND = Path(__file__).resolve().parent.parent
COLS = ["state", "district", "market", "commodity", "variety", "grade", "date", "min", "max", "modal"]

from agri.markets import COMMODITY  # Agmarknet commodity name -> our crop id


def load_snapshots() -> pd.DataFrame:
    frames = []
    for f in sorted((BACKEND / "data" / "raw" / "mandi_snapshots").glob("*.csv")):
        d = pd.read_csv(f)
        d.columns = COLS
        d["date"] = f.stem  # the file name is the report date
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    for c in ("state", "district", "market", "commodity", "variety"):
        df[c] = df[c].astype(str).str.strip()
    for c in ("min", "max", "modal"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["modal"])
    return df[(df["modal"] > 0) & (df["min"] <= df["max"])]


def main():
    df = load_snapshots()
    total = len(df)
    df["crop"] = df["commodity"].map(COMMODITY)
    df = df[df["crop"].notna()].copy()

    districts = json.loads((BACKEND / "agri" / "data" / "districts.json").read_text())
    centre = {(d["state"], d["district"]): (d["lat"], d["lng"]) for d in districts}
    matcher = DistrictMatcher(centre)
    df["geo"] = [matcher.match(s, d) for s, d in zip(df["state"], df["district"])]
    placed = df[df["geo"].notna()].copy()

    # one price per market / crop / day (several varieties -> take the median)
    daily = placed.groupby(["crop", "date", "geo", "market"], as_index=False).agg(
        modal=("modal", "median"), min=("min", "min"), max=("max", "max"), variety=("variety", "first"))
    ref = daily.groupby(["crop", "date"])["modal"].agg(["median", "count"]).rename(columns={"median": "ref", "count": "n_ref"})
    daily = daily.join(ref, on=["crop", "date"])
    daily["ratio"] = (daily["modal"] / daily["ref"]).where(daily["n_ref"] >= 8)

    out = {}
    for (crop, geo, market), g in daily.sort_values("date").groupby(["crop", "geo", "market"]):
        last = g.iloc[-1]
        ratios = g["ratio"].dropna().clip(0.4, 2.5)
        lat, lng = centre[geo]
        out.setdefault(crop, []).append({
            "market": market, "state": geo[0], "district": geo[1], "lat": lat, "lng": lng,
            "reports": int(len(g)), "level": round(float(ratios.mean()), 3) if len(ratios) else None,
            "last": {"date": last["date"], "modal": int(last["modal"]), "min": int(last["min"]), "max": int(last["max"]),
                     "variety": last["variety"]},
        })
    dest = BACKEND / "agri" / "data" / "mandis.json"
    meta = {"dates": sorted(df["date"].unique().tolist()), "reports": int(len(placed)),
            "markets": int(placed.groupby(["geo", "market"]).ngroups),
            "source": "Agmarknet daily mandi prices via data.gov.in (Government Open Data Licence - India)"}
    dest.write_text(json.dumps({"meta": meta, "crops": out}, separators=(",", ":")))
    print(f"{total:,} price reports, {len(df):,} for our crops, {len(placed):,} placed on the map")
    print({c: len(v) for c, v in sorted(out.items(), key=lambda kv: -len(kv[1]))})
    print(f"wrote {dest} ({dest.stat().st_size / 1e6:.2f} MB), meta {meta}")


if __name__ == "__main__":
    main()
