"""Build the price outlook: history, seasonal pattern and a 1-6 month forecast for each crop.

    python -m ml.train_prices

Data : data/raw/mandi_india_monthly.csv - for 166 crops, the India-wide median mandi price
       per quintal for every month since 2002 (Agmarknet via data.gov.in, summarised by
       todaymarketrates.com; Government Open Data Licence - India).

Test : the forecaster is trained on months up to the cut-off and then asked to predict the
       36 months after it, one forecast origin per month, exactly as it would be used. It is
       compared with two rules of thumb a trader would use:
         "no change"        next months' price = this month's price
         "seasonal"         this month's price adjusted by the crop's usual seasonal swing
       The raw model predicts moves that are too large, so only part of each predicted change
       is kept; how much is chosen on an earlier 36-month window, not on the test months.

Outputs
  agri/data/prices.json       what the app reads (history, seasonality, forecast, range)
  models/price_metrics.json   the accuracy report
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from agri.crops_kb import CROPS

BACKEND = Path(__file__).resolve().parent.parent
HORIZONS = [1, 2, 3, 4, 5, 6]
TEST_MONTHS = 36
MIN_HISTORY = 48  # months needed before a crop gets a model forecast
FEATURES = ["h", "target_month", "r1", "r3", "r6", "r12", "dev12", "dev24", "vol12", "seas_now", "seas_target", "crop_code"]


def load():
    df = pd.read_csv(BACKEND / "data" / "raw" / "mandi_india_monthly.csv", comment="#")
    df.columns = ["crop", "crop_id", "month", "price"]
    df["t"] = pd.PeriodIndex(df["month"], freq="M")
    built = None
    for line in (BACKEND / "data" / "raw" / "mandi_india_monthly.csv").read_text().splitlines()[:3]:
        if "Built" in line:
            built = line.split("Built")[1].split()[0]
    return df, built


def seasonal_index(series: pd.Series) -> np.ndarray:
    """Typical log-deviation of each calendar month from the 12-month centred average."""
    logp = np.log(series)
    trend = logp.rolling(12, center=True, min_periods=9).mean()
    dev = (logp - trend).dropna()
    idx = np.zeros(12)
    if len(dev) >= 24:
        med = dev.groupby(dev.index.month).median()
        for m in range(1, 13):
            idx[m - 1] = med.get(m, 0.0)
        idx -= idx.mean()
    return idx


def frame_for(series: pd.Series, seas: np.ndarray, crop_code: int, with_target=True) -> pd.DataFrame:
    """One row per (origin month, horizon). `series` is indexed by monthly Period, no gaps."""
    logp = np.log(series)
    rows = []
    base = pd.DataFrame({
        "logp": logp, "r1": logp.diff(1), "r3": logp.diff(3), "r6": logp.diff(6), "r12": logp.diff(12),
        "dev12": logp - logp.rolling(12, min_periods=6).mean(), "dev24": logp - logp.rolling(24, min_periods=12).mean(),
        "vol12": logp.diff(1).rolling(12, min_periods=6).std(),
    })
    months = np.array([p.month for p in series.index])
    for h in HORIZONS:
        f = base.copy()
        f["h"] = h
        f["target_month"] = ((months - 1 + h) % 12) + 1
        f["seas_now"] = seas[months - 1]
        f["seas_target"] = seas[f["target_month"].to_numpy() - 1]
        f["crop_code"] = crop_code
        f["origin"] = series.index
        f["y"] = logp.shift(-h) - logp if with_target else np.nan
        rows.append(f)
    return pd.concat(rows, ignore_index=True)


def mdape(actual, pred):
    return round(float(np.median(np.abs(pred - actual) / actual) * 100), 1)


def model():
    # absolute-error loss: aim for the typical move, not the mean (which onion/tomato spikes distort)
    return HistGradientBoostingRegressor(loss="absolute_error", learning_rate=0.05, max_iter=300, max_leaf_nodes=24,
                                         min_samples_leaf=60, categorical_features=[FEATURES.index("crop_code")],
                                         random_state=7)


def main():
    df, built = load()
    last_full = df["t"].max() - 1 if built and built[:7] == str(df["t"].max()) else df["t"].max()
    partial = df["t"].max() if last_full != df["t"].max() else None

    series = {}
    for crop, g in df.groupby("crop"):
        s = g.set_index("t")["price"].sort_index()
        s = s[s.index <= last_full]
        if len(s) == 0:
            continue
        full = s.reindex(pd.period_range(s.index.min(), last_full, freq="M")).interpolate(limit=3)
        # use the longest recent stretch without long gaps
        gaps = full.isna()
        if gaps.any():
            full = full.loc[gaps[gaps].index.max() + 1:]
        series[crop] = full.astype(float)

    eligible = sorted(c for c, s in series.items() if len(s) >= MIN_HISTORY)
    codes = {c: i for i, c in enumerate(eligible)}
    cutoff = last_full - TEST_MONTHS

    # ---------------- backtest
    # Step 1 (validation): train up to 72 months back, forecast the following 36 months, and pick
    #   how much of the model's predicted change to keep (the raw model overshoots).
    # Step 2 (test): train up to 36 months back, apply that setting to the last 36 months.
    def fit_predict(train_end, origin_end):
        tr, te = [], []
        for crop in eligible:
            s = series[crop]
            s = s[s.index <= origin_end]
            if (s.index <= train_end).sum() < 36:
                continue
            seas = seasonal_index(s[s.index <= train_end])
            f = frame_for(s, seas, codes[crop])
            f["crop"] = crop
            f["target_t"] = f["origin"] + f["h"]
            tr.append(f[f["target_t"] <= train_end])
            te.append(f[f["origin"] > train_end])
        tr = pd.concat(tr).dropna(subset=["y", "r12", "dev24"])
        te = pd.concat(te).dropna(subset=["y", "r12", "dev24"])
        fitted = model().fit(tr[FEATURES], tr["y"])
        return tr, te.assign(pred_raw=fitted.predict(te[FEATURES]))

    _, val = fit_predict(cutoff - TEST_MONTHS, cutoff)
    shrink = {}
    for h in HORIZONS:
        k = val["h"] == h
        a, base = np.exp(val.loc[k, "logp"] + val.loc[k, "y"]), np.exp(val.loc[k, "logp"])
        scores = {w: mdape(a, base * np.exp(w * val.loc[k, "pred_raw"])) for w in (0.0, 0.25, 0.5, 0.75, 1.0)}
        shrink[h] = min(scores, key=scores.get)
    print("share of the predicted change kept, chosen on the validation years:", shrink)

    train, test = fit_predict(cutoff, last_full)
    test = test.assign(pred_model=test["pred_raw"] * test["h"].map(shrink),
                       pred_seasonal=lambda d: d["seas_target"] - d["seas_now"])
    actual = np.exp(test["logp"] + test["y"])
    report, resid_q = {}, {}
    for h in HORIZONS:
        k = test["h"] == h
        a, base = actual[k], np.exp(test.loc[k, "logp"])
        report[str(h)] = {
            "no_change": mdape(a, base),
            "seasonal": mdape(a, base * np.exp(test.loc[k, "pred_seasonal"])),
            "model": mdape(a, base * np.exp(test.loc[k, "pred_model"])),
            "forecasts": int(k.sum()),
        }
        err = (test.loc[k, "y"] - test.loc[k, "pred_model"]).to_numpy()
        resid_q[h] = [float(np.quantile(err, 0.1)), float(np.quantile(err, 0.9))]
        print(f"h={h}: {report[str(h)]}  80% residual band {np.round(np.exp(resid_q[h]), 3)}")
    direction = {}
    for h in (1, 3, 6):
        k = (test["h"] == h) & (test["y"].abs() > 0.05) & (test["pred_model"].abs() > 0.01)
        direction[str(h)] = round(float((np.sign(test.loc[k, "pred_model"]) == np.sign(test.loc[k, "y"])).mean() * 100), 1)
    print("direction right when price moved >5%:", direction)

    # which crops in the app does it do well / badly on (3 months ahead)
    mandi_to_id = {c["mandi"]: cid for cid, c in CROPS.items() if c["mandi"]}
    per_crop = {}
    for crop, g in test[test["h"] == 3].groupby("crop"):
        if crop in mandi_to_id:
            a = np.exp(g["logp"] + g["y"])
            per_crop[mandi_to_id[crop]] = {"model": mdape(a, np.exp(g["logp"] + g["pred_model"])),
                                           "no_change": mdape(a, np.exp(g["logp"]))}

    # ---------------- final model on all months, forecasts from the latest complete month
    rows = []
    seas_all = {}
    for crop in eligible:
        s = series[crop]
        seas_all[crop] = seasonal_index(s)
        f = frame_for(s, seas_all[crop], codes[crop])
        f["crop"] = crop
        rows.append(f)
    allf = pd.concat(rows)
    final = model().fit(allf.dropna(subset=["y", "r12", "dev24"])[FEATURES], allf.dropna(subset=["y", "r12", "dev24"])["y"])
    latest = allf[allf["origin"] == last_full].dropna(subset=["r12", "dev24"]).copy()
    latest["pred"] = final.predict(latest[FEATURES]) * latest["h"].map(shrink)

    out = {"built": built, "last_full_month": str(last_full), "partial_month": str(partial) if partial else None,
           "source": "Agmarknet (Directorate of Marketing & Inspection) via data.gov.in, summarised by todaymarketrates.com",
           "crops": {}}
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    for crop, s in series.items():
        hist = s.iloc[-72:]
        entry = {
            "history": [[str(p), int(round(v))] for p, v in hist.items() if not np.isnan(v)],
            "latest": int(round(s.iloc[-1])), "latest_month": str(s.index[-1]), "months_of_history": int(len(s)),
        }
        if len(s) >= 3:
            entry["avg3"] = int(round(s.iloc[-3:].mean()))
        if len(s) >= 13:
            entry["change_12m_pct"] = round(float((s.iloc[-1] / s.iloc[-13] - 1) * 100), 1)
        raw_now = df[(df["crop"] == crop) & (df["t"] == partial)]["price"] if partial else []
        if len(raw_now):
            entry["month_to_date"] = int(raw_now.iloc[0])
        if crop in seas_all and len(s) >= MIN_HISTORY:
            seas = seas_all[crop]
            entry["seasonal_pct"] = [round(float((np.exp(v) - 1) * 100), 1) for v in seas]
            entry["best_month"] = month_names[int(np.argmax(seas))]
            entry["worst_month"] = month_names[int(np.argmin(seas))]
            entry["volatility_pct"] = round(float(np.log(s).diff().iloc[-36:].std() * 100), 1)
            fc = []
            for r in latest[latest["crop"] == crop].sort_values("h").itertuples():
                p0 = float(np.exp(r.logp))
                lo, hi = resid_q[int(r.h)]
                fc.append({"month": str(last_full + int(r.h)), "price": int(round(p0 * np.exp(r.pred))),
                           "low": int(round(p0 * np.exp(r.pred + lo))), "high": int(round(p0 * np.exp(r.pred + hi)))})
            entry["forecast"] = fc
        out["crops"][crop] = entry
    dest = BACKEND / "agri" / "data" / "prices.json"
    dest.write_text(json.dumps(out, separators=(",", ":")))

    metrics = {
        "data": {"crops": int(len(series)), "crops_with_forecast": int(len(eligible)), "monthly_prices": int(len(df)),
                 "first_month": str(df["t"].min()), "last_full_month": str(last_full)},
        "test": {"method": f"trained on months up to {cutoff}; forecasts made from each of the next {TEST_MONTHS} months",
                 "validation": f"how much of the model's predicted change to keep was chosen on the 36 months before {cutoff}",
                 "share_of_predicted_change_kept": {str(k): v for k, v in shrink.items()},
                 "median_error_pct_by_months_ahead": report, "direction_right_pct": direction,
                 "per_crop_3_months_ahead": per_crop},
        "training_rows": int(len(train)),
    }
    (BACKEND / "models" / "price_metrics.json").write_text(json.dumps(metrics, indent=1))
    print(f"wrote {dest.name} ({dest.stat().st_size / 1e6:.2f} MB), {len(eligible)} crops with forecasts of {len(series)}")


if __name__ == "__main__":
    main()
