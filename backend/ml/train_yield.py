"""Train the yield model and write the table the app reads.

    python -m ml.train_yield

What it learns from: 250,000+ district records of area and production (1997-2019).
What it predicts : tonnes per hectare for a crop, in a district, in a season.

It is tested the honest way for a forecast: trained on years up to 2016 and scored on
2017-2019, which it never saw, against two simple baselines.

Outputs
  agri/data/crop_stats.json   expected yield, likely range and history for every district
  models/yield_metrics.json   accuracy report shown on the app's "About the models" page
"""
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from agri.crops_kb import CROPS
from ml.prepare_crops import load_clean

BACKEND = Path(__file__).resolve().parent.parent
TEST_FROM = 2017
SEASONS = ["kharif", "rabi", "summer", "annual"]
RAIN_BLOCKS = {"rain_annual": range(12), "rain_monsoon": [5, 6, 7, 8], "rain_postmonsoon": [9, 10, 11], "rain_winter": [0, 1], "rain_summer": [2, 3, 4]}
FEATURES = ["crop_code", "season_code", "state_code", "year", "lat", "lng", *RAIN_BLOCKS,
            "hist5", "hist_all", "hist_last", "n_hist", "state_hist", "nat_hist", "area_share"]
CATEGORICAL = ["crop_code", "season_code", "state_code"]


def add_geo(df: pd.DataFrame) -> pd.DataFrame:
    districts = json.loads((BACKEND / "agri" / "data" / "districts.json").read_text())
    geo = pd.DataFrame([{"state": d["state"], "district": d["district"], "lat": d["lat"], "lng": d["lng"],
                         **{k: float(sum(d["rain"][i] for i in idx)) for k, idx in RAIN_BLOCKS.items()}}
                        for d in districts])
    return df.merge(geo, on=["state", "district"], how="left")


def add_history(df: pd.DataFrame) -> pd.DataFrame:
    """Features describing what happened in EARLIER years only (no peeking at the target year)."""
    df = df.sort_values(["state", "district", "crop", "season", "year"]).reset_index(drop=True)
    key = ["state", "district", "crop", "season"]
    g = df.groupby(key, sort=False)["yield_t_ha"]
    df["hist_last"] = g.shift(1)
    df["hist5"] = g.transform(lambda s: s.shift(1).rolling(5, min_periods=1).mean())
    df["hist_all"] = g.transform(lambda s: s.shift(1).expanding().mean())
    df["n_hist"] = g.cumcount()

    # share of the district's cropped area (among our crops, that season) in earlier years
    tot = df.groupby(["state", "district", "season", "year"])["area_ha"].transform("sum")
    df["_share"] = df["area_ha"] / tot
    df["area_share"] = df.groupby(key, sort=False)["_share"].transform(lambda s: s.shift(1).rolling(5, min_periods=1).mean())

    for name, cols in (("state_hist", ["state", "crop", "season"]), ("nat_hist", ["crop", "season"])):
        yearly = df.groupby(cols + ["year"], as_index=False).agg(_p=("prod_t", "sum"), _a=("area_ha", "sum"))
        yearly = yearly.sort_values(cols + ["year"])
        yg = yearly.groupby(cols, sort=False)
        cp, ca = yg["_p"].cumsum() - yearly["_p"], yg["_a"].cumsum() - yearly["_a"]
        yearly[name] = (cp / ca).where(ca > 0)
        df = df.merge(yearly[cols + ["year", name]], on=cols + ["year"], how="left")
    return df.drop(columns=["_share"])


def encode(df: pd.DataFrame, cats: dict) -> pd.DataFrame:
    df = df.copy()
    df["crop_code"] = df["crop"].map(cats["crop"]).astype(float)
    df["season_code"] = df["season"].map(cats["season"]).astype(float)
    df["state_code"] = df["state"].map(cats["state"]).astype(float)
    return df


def make_model(loss="squared_error", quantile=None):
    return HistGradientBoostingRegressor(
        loss=loss, quantile=quantile, learning_rate=0.06, max_iter=400, max_leaf_nodes=48,
        min_samples_leaf=40, l2_regularization=1.0, categorical_features=[FEATURES.index(c) for c in CATEGORICAL],
        early_stopping=True, validation_fraction=0.1, n_iter_no_change=25, random_state=7)


def score(y_true, y_pred):
    ape = np.abs(y_pred - y_true) / y_true
    lt, lp = np.log(y_true), np.log(np.clip(y_pred, 1e-6, None))
    r2 = 1 - ((lt - lp) ** 2).sum() / ((lt - lt.mean()) ** 2).sum()
    return {"median_error_pct": round(float(np.median(ape) * 100), 1),
            "within_25_pct": round(float((ape <= 0.25).mean() * 100), 1),
            "r2_log": round(float(r2), 3)}


def main():
    t0 = time.time()
    df = load_clean(verbose=False)
    steps = df.attrs.get("steps", [])
    df["prod_t"] = df["yield_t_ha"] * df["area_ha"]
    df = add_history(add_geo(df))
    cats = {"crop": {c: i for i, c in enumerate(sorted(df["crop"].unique()))},
            "season": {s: i for i, s in enumerate(SEASONS)},
            "state": {s: i for i, s in enumerate(sorted(df["state"].unique()))}}
    df = encode(df, cats)
    df["target"] = np.log(df["yield_t_ha"])

    train, test = df[df["year"] < TEST_FROM], df[df["year"] >= TEST_FROM]
    print(f"{len(df):,} rows; train {len(train):,} (1997-{TEST_FROM - 1}), test {len(test):,} ({TEST_FROM}-2019)")

    # ---- baselines on the test years
    y = test["yield_t_ha"].to_numpy()
    overall = float(train["yield_t_ha"].median())
    b_nat = test["nat_hist"].fillna(overall).to_numpy()
    b_dist = test["hist5"].fillna(test["state_hist"]).fillna(test["nat_hist"]).fillna(overall).to_numpy()
    report = {"National average for the crop": score(y, b_nat),
              "District's own average of its last 5 records": score(y, b_dist)}

    model = make_model().fit(train[FEATURES], train["target"])
    pred = np.exp(model.predict(test[FEATURES]))
    report["Gradient boosting (used in the app)"] = score(y, pred)
    seen = test["n_hist"].to_numpy() >= 3
    by_history = {
        "3+ earlier records in the district": {"model": score(y[seen], pred[seen]), "district_average": score(y[seen], b_dist[seen]),
                                               "share_of_test_pct": round(float(seen.mean() * 100), 1)},
        "fewer than 3 earlier records": {"model": score(y[~seen], pred[~seen]), "district_average": score(y[~seen], b_dist[~seen]),
                                         "share_of_test_pct": round(float((~seen).mean() * 100), 1)},
    }

    # ---- likely range: how far off was an earlier model on years it had not seen?
    # Model A (trained to 2013) is checked on 2014-2016 to learn the typical miss; that band is
    # then put around the test model's 2017-2019 predictions to see if it really holds ~80%.
    def band(frame, predicted):
        err = np.log(frame["yield_t_ha"].to_numpy()) - np.log(predicted)
        out = {}
        for name, mask in (("seen", frame["n_hist"].to_numpy() >= 3), ("new", frame["n_hist"].to_numpy() < 3)):
            out[name] = [float(np.quantile(err[mask], 0.1)), float(np.quantile(err[mask], 0.9))]
        return out

    early, calib = df[df["year"] < TEST_FROM - 3], df[(df["year"] >= TEST_FROM - 3) & (df["year"] < TEST_FROM)]
    model_a = make_model().fit(early[FEATURES], early["target"])
    band_a = band(calib, np.exp(model_a.predict(calib[FEATURES])))
    lo = pred * np.exp(np.where(seen, band_a["seen"][0], band_a["new"][0]))
    hi = pred * np.exp(np.where(seen, band_a["seen"][1], band_a["new"][1]))
    coverage = float(((y >= lo) & (y <= hi)).mean() * 100)
    for name, r in report.items():
        print(f"  {name:52s} {r}")
    print(f"  80% range contains {coverage:.1f}% of test yields")
    print(f"  by history: {json.dumps(by_history)}")

    per_crop = {}
    for crop, grp in test.assign(pred=pred).groupby("crop"):
        per_crop[crop] = {**score(grp["yield_t_ha"].to_numpy(), grp["pred"].to_numpy()), "rows": int(len(grp))}

    # ---- final model on every year; its range uses the misses of the test model on 2017-2019
    final = make_model().fit(df[FEATURES], df["target"])
    band_final = band(test, pred)

    # "next year" feature rows: one per district x season x crop that the district's state grows
    last_year = int(df["year"].max())
    key = ["state", "district", "crop", "season"]
    hist = df.groupby(key).agg(n_hist=("year", "count"), hist_all=("yield_t_ha", "mean"), last_year=("year", "max"),
                               first_year=("year", "min")).reset_index()
    tail = df.sort_values("year").groupby(key).tail(5)
    hist5 = tail.groupby(key).agg(hist5=("yield_t_ha", "mean"), area5=("area_ha", "mean")).reset_index()
    lastv = df.sort_values("year").groupby(key).tail(1)[key + ["yield_t_ha"]].rename(columns={"yield_t_ha": "hist_last"})
    hist = hist.merge(hist5, on=key).merge(lastv, on=key)
    tot5 = hist.groupby(["state", "district", "season"])["area5"].transform("sum")
    hist["area_share"] = hist["area5"] / tot5

    state_hist = df.groupby(["state", "crop", "season"]).agg(p=("prod_t", "sum"), a=("area_ha", "sum"), n=("year", "count")).reset_index()
    state_hist["state_hist"] = state_hist["p"] / state_hist["a"]
    nat = df.groupby(["crop", "season"]).agg(p=("prod_t", "sum"), a=("area_ha", "sum")).reset_index()
    nat["nat_hist"] = nat["p"] / nat["a"]

    districts = add_geo(pd.DataFrame(json.loads((BACKEND / "agri" / "data" / "districts.json").read_text()))[["state", "district"]])
    # every district x (crop, season) that its state has at least 20 records of
    combos = state_hist[state_hist["n"] >= 20][["state", "crop", "season", "state_hist"]]
    grid = districts.merge(combos, on="state")
    grid = grid.merge(hist, on=key, how="left").merge(nat[["crop", "season", "nat_hist"]], on=["crop", "season"], how="left")
    grid["n_hist"] = grid["n_hist"].fillna(0)
    grid["year"] = last_year + 1
    grid = encode(grid, cats)
    grid["pred"] = np.exp(final.predict(grid[FEATURES]))
    known = grid["n_hist"].to_numpy() >= 3
    grid["lo"] = grid["pred"] * np.exp(np.where(known, band_final["seen"][0], band_final["new"][0]))
    grid["hi"] = grid["pred"] * np.exp(np.where(known, band_final["seen"][1], band_final["new"][1]))

    # recent national yields (last 5 data years), used to turn cost per quintal into cost per acre
    rec = df[df["year"] >= last_year - 4]
    nat_recent = (rec.groupby("crop")["prod_t"].sum() / rec.groupby("crop")["area_ha"].sum()).round(3).to_dict()

    table = {}
    for r in grid.itertuples(index=False):
        entry = {"y": round(float(r.pred), 3), "lo": round(float(r.lo), 3), "hi": round(float(r.hi), 3), "n": int(r.n_hist)}
        if r.n_hist > 0:
            entry.update({"last": int(r.last_year), "share": round(float(r.area_share), 4), "area": round(float(r.area5), 1),
                          "avg5": round(float(r.hist5), 3)})
        table.setdefault(f"{r.state}|{r.district}", {}).setdefault(r.season, {})[r.crop] = entry

    stats = {"data_years": [int(df["year"].min()), last_year], "national_yield_t_ha": nat_recent, "districts": table}
    out = BACKEND / "agri" / "data" / "crop_stats.json"
    out.write_text(json.dumps(stats, separators=(",", ":")))

    metrics = {
        "trained_on": {"rows": int(len(df)), "districts": int(df[["state", "district"]].drop_duplicates().shape[0]),
                       "crops": int(df["crop"].nunique()), "years": [int(df["year"].min()), last_year]},
        "cleaning_steps": steps,
        "test": {"method": f"trained on 1997-{TEST_FROM - 1}, scored on {TEST_FROM}-2019", "rows": int(len(test)),
                 "models": report, "by_history": by_history, "range_80_coverage_pct": round(coverage, 1),
                 "range_method": "band = 10th-90th percentile of an earlier model's misses on 2014-2016, checked on 2017-2019",
                 "per_crop": per_crop},
        "features": FEATURES,
    }
    (BACKEND / "models" / "yield_metrics.json").write_text(json.dumps(metrics, indent=1))
    print(f"wrote {out.name} ({out.stat().st_size / 1e6:.2f} MB, {len(table)} districts, {len(grid):,} predictions) in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
