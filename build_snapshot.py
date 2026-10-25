"""
半導体・メモリー定点観測のテクニカル指標・モメンタム段階を計算する（GitHub Actionsで毎日実行）

入力（--out のフォルダ）: prices_daily.csv.gz, prices_manifest.json, macro_daily.csv, macro_manifest.json
出力:
  semis_snapshot.csv  : 銘柄ごとの最新指標（1行1銘柄）
  adr_premium.csv     : ADRプレミアムの日次推移（直近60営業日）
  levels.json         : S1〜S5・D1〜D6 の段階（−2〜+2）、入力値、S/Dスコア
  history_levels.csv  : 段階とスコアの日次履歴（追記）
  history_key.csv     : 主要銘柄の終値・SMA・RSI等の日次履歴（追記）
  semis_manifest.json : 基準日、欠損、品質フラグ、騰落の広がり、ADR要約、マクロ最新値
書き込みは一時ファイル経由。途中で落ちても前回のファイルが残る。

指標の定義（DEFINITIONS 1.1。判定基準の「テクニカル定義」と同じ。変えたら両方を更新する）
  価格        : close（分割調整済み・配当非調整）
  騰落率      : 1d=1本前、1w=5本前、1m=21本前、3m=63本前の終値比（%）
  SMA         : 単純移動平均20/50/200本。本数不足はN/A。乖離率＝close/SMA−1（%）
  SMA傾き     : SMA20・SMA50は10本前比、SMA200は20本前比（%）
  RSI14       : Wilder方式（alpha=1/14の指数平滑）
  出来高比    : 当日出来高/直前20本の平均（当日を含まない）
  上昇/下落出来高比 : 直近10本の上昇日の平均出来高/下落日の平均出来高
  高値下落率  : close/直近252本（不足時は全期間）の終値最高値−1（%）
  実現ボラ    : 対数リターンの標準偏差×√252（20本・60本、%）
  相対強度    : 銘柄のN本騰落率−同じ暦日区間のベンチマーク騰落率（%pt、N=20・60）
  S/R候補     : 直近20本・60本の安値・高値
  段階の閾値  : config.json の levels（帯は「値 < 境界」で下の段階）
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

DEFINITIONS_VERSION = "1.1"
JST = timezone(timedelta(hours=9))
RET = {"ret_1d": 1, "ret_1w": 5, "ret_1m": 21, "ret_3m": 63}
JUMP = {"default": 0.35, "leveraged": 0.60, "fx_rates": 0.10}


# ---------- 共通 ----------
def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write_atomic(obj, path, **kw):
    tmp = path + ".tmp"
    if isinstance(obj, pd.DataFrame):
        obj.to_csv(tmp, index=False, **kw)
    else:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2, default=_json_default)
    os.replace(tmp, path)


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, (pd.Timestamp,)):
        return o.strftime("%Y-%m-%d")
    raise TypeError(str(type(o)))


def band_level(v, bands):
    """bands=[b0,b1,b2,b3]: v<b0→−2, <b1→−1, <b2→0, <b3→+1, それ以外+2。NaNはNone"""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    for lvl, b in zip((-2, -1, 0, 1), bands):
        if v < b:
            return lvl
    return 2


def clamp(x):
    return max(-2, min(2, x))


def nz(x, nd=4):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), nd)


# ---------- 指標 ----------
def rsi_wilder(close, n=14):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rsi = 100 - 100 / (1 + up / dn)
    return rsi.where(dn != 0, 100.0)


def wret(s, n):
    return (s.iloc[-1] / s.iloc[-1 - n] - 1) * 100 if len(s) > n else np.nan


def bench_ret(b, start, end):
    b0, b1 = b.loc[:start], b.loc[:end]
    return (b1.iloc[-1] / b0.iloc[-1] - 1) * 100 if not (b0.empty or b1.empty) else np.nan


def updown_ratio(c, v, n=10):
    chg, vv = c.diff().iloc[-n:], v.iloc[-n:]
    up, dn = vv[chg > 0].mean(), vv[chg < 0].mean()
    return up / dn if pd.notna(up) and pd.notna(dn) and dn > 0 else np.nan


def metrics_for(t, g, benches, no_volume, jump_thr):
    g = g.set_index("date").sort_index()
    c = g["close"].astype(float)
    n, last = len(c), c.iloc[-1]
    row = {"last_date": c.index[-1].strftime("%Y-%m-%d"), "n_obs": n, "close": last}
    for k, w in RET.items():
        row[k] = wret(c, w)
    for w in (20, 50, 200):
        sma = c.rolling(w, min_periods=w).mean()
        row[f"sma{w}"] = sma.iloc[-1]
        row[f"dist_sma{w}"] = (last / sma.iloc[-1] - 1) * 100 if pd.notna(sma.iloc[-1]) else np.nan
        lag = 20 if w == 200 else 10
        row[f"sma{w}_slope"] = (sma.iloc[-1] / sma.iloc[-1 - lag] - 1) * 100 if n > w + lag and pd.notna(sma.iloc[-1 - lag]) else np.nan
    row["rsi14"] = rsi_wilder(c).iloc[-1] if n > 14 else np.nan

    vol = g["volume"].astype(float) if "volume" in g else pd.Series(np.nan, index=g.index)
    vol = vol.where(vol > 0)
    if t in no_volume or vol.iloc[-21:].notna().sum() < 21:
        row["volume"], row["vol_ratio20"], row["updown_vol_ratio10"] = np.nan, np.nan, np.nan
    else:
        prev20 = vol.iloc[-21:-1].mean()
        row["volume"] = vol.iloc[-1]
        row["vol_ratio20"] = vol.iloc[-1] / prev20 if prev20 > 0 else np.nan
        row["updown_vol_ratio10"] = updown_ratio(c, vol)

    hw = min(252, n)
    hi = c.iloc[-hw:].max()
    row["high_window"], row["high_close"], row["dd_from_high"] = hw, hi, (last / hi - 1) * 100
    lr = np.log(c).diff()
    row["rv20"] = lr.iloc[-20:].std() * np.sqrt(252) * 100 if n > 20 else np.nan
    row["rv60"] = lr.iloc[-60:].std() * np.sqrt(252) * 100 if n > 60 else np.nan
    lo = g["low"].astype(float) if "low" in g else c
    hs = g["high"].astype(float) if "high" in g else c
    for w in (20, 60):
        row[f"low{w}"] = lo.iloc[-w:].min() if n >= w else np.nan
        row[f"high{w}"] = hs.iloc[-w:].max() if n >= w else np.nan
    end = c.index[-1]
    for bname, b in benches.items():
        for w in (20, 60):
            key = f"rs_{bname.lower().replace('^', '')}_{w}"
            row[key] = wret(c, w) - bench_ret(b, c.index[-1 - w], end) if (b is not None and n > w) else np.nan

    flags = []
    rets = c.pct_change().iloc[-63:]
    jumps = rets[rets.abs() > jump_thr]
    if not jumps.empty:
        flags.append("jump:" + ",".join(d.strftime("%Y-%m-%d") for d in jumps.index))
    if n < 200:
        flags.append(f"short_history:{n}")
    return row, flags


# ---------- 段階（S/D） ----------
def trend_level(r, near_pct, long_key="sma200", mid_key="sma50"):
    """+2: 両SMA上で傾き上向き／+1: 長期SMA上だが条件不足／0: 長期SMA±near%／−1: 長期SMA下だが中期傾き上／−2: それ以外"""
    c, mid, lng = r["close"], r[mid_key], r[long_key]
    if pd.isna(lng) or pd.isna(mid):
        return None
    mid_slope, lng_slope = r.get(f"{mid_key}_slope", np.nan), r.get(f"{long_key}_slope", np.nan)
    if c > mid and c > lng and (mid_slope or 0) > 0 and (lng_slope if pd.notna(lng_slope) else 1) > 0:
        return 2
    if c > lng:
        return 1
    if abs(c / lng - 1) * 100 <= near_pct:
        return 0
    if (mid_slope or 0) > 0:
        return -1
    return -2


def breadth_stats(snap, names):
    d = snap[snap["ticker"].isin(names)]
    out = {"tickers_with_data": int(len(d))}
    for col, key in (("dist_sma20", "above_sma20"), ("dist_sma50", "above_sma50"), ("dist_sma200", "above_sma200"), ("ret_1w", "up_1w"), ("ret_1m", "up_1m")):
        v = d[col].dropna()
        out[key] = {"positive": int((v > 0).sum()), "valid": int(len(v)),
                    "pct": round(float((v > 0).mean() * 100), 1) if len(v) else None}
    out["median_ret_1m"] = nz(d["ret_1m"].median(), 2) if d["ret_1m"].notna().any() else None
    return out


def compute_levels(snap, cfg, adr_summary, breadth):
    L, row = {}, snap.set_index("ticker")
    lv = cfg["levels"]

    # S1 トレンド
    s1 = lv["S1"]
    per = {t: trend_level(row.loc[t], s1["near_pct"]) for t in s1["tickers"] if t in row.index}
    vals = [v for v in per.values() if v is not None]
    if vals:
        lvl = per.get(s1["tiebreak"]) if len(set(vals)) > 1 and per.get(s1["tiebreak"]) is not None else int(round(np.median(vals)))
        L["S1"] = {"level": lvl, "inputs": per}
    else:
        L["S1"] = {"level": None, "inputs": per}

    # S2 広がり
    b = breadth.get(lv["S2"]["set"], {}).get("above_sma50", {})
    L["S2"] = {"level": band_level(b.get("pct"), lv["S2"]["bands"]), "inputs": b}

    # S3 上昇/下落出来高比
    t = lv["S3"]["ticker"]
    v = row.loc[t, "updown_vol_ratio10"] if t in row.index else np.nan
    L["S3"] = {"level": band_level(v, lv["S3"]["bands"]), "inputs": {t: nz(v)}}

    # S4 相対強度
    s4 = lv["S4"]
    t, bn, cb = s4["ticker"], s4["bench"].lower(), s4["confirm_bench"].lower()
    if t in row.index:
        r60, r20 = row.loc[t, f"rs_{bn}_60"], row.loc[t, f"rs_{bn}_20"]
        q60 = row.loc[t, f"rs_{cb}_60"]
        lvl = band_level(r60, s4["bands_60"])
        if lvl is not None:
            if lvl == 2 and not r20 > 0:
                lvl = 1
            if lvl == -2 and r20 > 0:
                lvl = -1
            if pd.notna(q60) and np.sign(q60) != np.sign(r60) and lvl != 0:
                lvl += -1 if lvl > 0 else 1
        L["S4"] = {"level": lvl, "inputs": {f"rs_{bn}_60": nz(r60), f"rs_{bn}_20": nz(r20), f"rs_{cb}_60": nz(q60)}}
    else:
        L["S4"] = {"level": None, "inputs": {}}

    # S5 ボラ環境（VIX水準 + 実現ボラ比。金利はXで採点するためここでは使わない）
    s5 = lv["S5"]
    vix = row.loc[s5["vix"], "close"] if s5["vix"] in row.index else np.nan
    rr = (row.loc[s5["ticker"], "rv20"] / row.loc[s5["ticker"], "rv60"]) if s5["ticker"] in row.index else np.nan
    if pd.notna(vix) and pd.notna(rr):
        a = 1 if vix < s5["vix_bands"][0] else (0 if vix <= s5["vix_bands"][1] else -1)
        bb = 1 if rr < s5["rv_ratio_bands"][0] else (0 if rr <= s5["rv_ratio_bands"][1] else -1)
        L["S5"] = {"level": a + bb, "inputs": {"vix": nz(vix, 2), "rv20_rv60": nz(rr, 3), "vix_part": a, "rv_part": bb}}
    else:
        L["S5"] = {"level": None, "inputs": {"vix": nz(vix, 2), "rv20_rv60": nz(rr, 3)}}

    # D1 DRAM絶対トレンド（SMA20/50。SMA200は運用期間が短くN/Aになり得る）
    t = lv["D1"]["ticker"]
    if t in row.index:
        r = row.loc[t]
        lvl = trend_level(r, lv["D1"]["near_pct"], long_key="sma50", mid_key="sma20")
        L["D1"] = {"level": lvl, "inputs": {"close": nz(r["close"], 2), "sma20": nz(r["sma20"], 2), "sma50": nz(r["sma50"], 2),
                                            "sma20_slope": nz(r["sma20_slope"], 2), "sma50_slope": nz(r["sma50_slope"], 2)}}
    else:
        L["D1"] = {"level": None, "inputs": {}}

    # D2 DRAM相対強度（4本のうちプラスの本数）
    t = lv["D2"]["ticker"]
    if t in row.index:
        keys = [f"rs_{b.lower()}_{w}" for b in lv["D2"]["benches"] for w in (20, 60)]
        vals = {k: nz(row.loc[t, k]) for k in keys}
        valid = [v for v in vals.values() if v is not None]
        L["D2"] = {"level": (sum(v > 0 for v in valid) - 2) if len(valid) == 4 else None, "inputs": vals}
    else:
        L["D2"] = {"level": None, "inputs": {}}

    # D3 メモリー株の広がり
    b = breadth.get(lv["D3"]["set"], {}).get("above_sma50", {})
    L["D3"] = {"level": band_level(b.get("pct"), lv["D3"]["bands"]) if b.get("valid", 0) >= 5 else None, "inputs": b}

    # D4 メモリー株の上昇/下落出来高比
    vals = {t: nz(row.loc[t, "updown_vol_ratio10"]) for t in lv["D4"]["tickers"] if t in row.index}
    valid = [v for v in vals.values() if v is not None]
    L["D4"] = {"level": band_level(float(np.mean(valid)), lv["D4"]["bands"]) if valid else None, "inputs": vals}

    # D5 ADR整合性（プレミアムと20日平均の差。1週騰落の方向が逆なら1段階下げ）
    a = next((x for x in adr_summary if x.get("ads") == lv["D5"]["ads"] and x.get("status") == "ok"), None)
    if a:
        gap = abs(a["premium_pct"] - a["premium_avg20"])
        # band_level は値が小さいほど低段階なので反転する: gap<1→+2 … gap≥6→−2
        lvl = {-2: 2, -1: 1, 0: 0, 1: -1, 2: -2}[band_level(gap, lv["D5"]["gap_bands"])]
        same_dir = a.get("direction_match")
        if same_dir is False:
            lvl = clamp(lvl - 1)
        L["D5"] = {"level": lvl, "inputs": {"premium_pct": a["premium_pct"], "premium_avg20": a["premium_avg20"], "gap": round(gap, 2), "direction_match": same_dir}}
    else:
        L["D5"] = {"level": None, "inputs": {}}

    # D6 DRAMドローダウン・ボラ
    t = lv["D6"]["ticker"]
    if t in row.index and pd.notna(row.loc[t, "dd_from_high"]):
        dd, rr = row.loc[t, "dd_from_high"], row.loc[t, "rv20"] / row.loc[t, "rv60"] if pd.notna(row.loc[t, "rv60"]) else np.nan
        lvl = band_level(dd, lv["D6"]["dd_bands"])
        if pd.notna(rr) and rr > lv["D6"]["rv_penalty_ratio"]:
            lvl = clamp(lvl - 1)
        L["D6"] = {"level": lvl, "inputs": {"dd_from_high": nz(dd, 2), "rv20_rv60": nz(rr, 3), "high_window": int(row.loc[t, "high_window"])}}
    else:
        L["D6"] = {"level": None, "inputs": {}}

    # スコア（欠損は除外して配点を再按分）
    scores = {}
    for name, w in cfg["weights"].items():
        tot, got, miss = 0.0, 0.0, []
        for k, pts in w.items():
            lvl = L.get(k, {}).get("level")
            if lvl is None:
                miss.append(k)
                continue
            tot += pts
            got += pts * (lvl + 2) / 4
        scores[name] = {"score": round(got / tot * 100, 1) if tot else None, "coverage_pct": round(tot / sum(w.values()) * 100), "missing": miss}
    scores["TECHNICAL"] = (round(0.7 * scores["S"]["score"] + 0.3 * scores["D"]["score"], 1)
                           if scores["S"]["score"] is not None and scores["D"]["score"] is not None else None)
    return L, scores


# ---------- ADR ----------
def adr_tables(px, cfg):
    rows, summary = [], []
    for a in cfg.get("adr", []):
        s = {k: px[px["ticker"] == a[k]].set_index("date")["close"].astype(float).sort_index() for k in ("ads", "local", "fx")}
        missing = [a[k] for k in ("ads", "local", "fx") if s[k].empty]
        if missing:
            summary.append({"ads": a["ads"], "status": "missing", "missing": missing})
            continue
        df = pd.concat({"ads_close": s["ads"], "local_close": s["local"]}, axis=1, join="inner")
        fx = s["fx"]
        df["usdkrw"] = [fx.loc[:d].iloc[-1] if not fx.loc[:d].empty else np.nan for d in df.index]
        df = df.dropna()
        df["theoretical_usd"] = df["local_close"] * a["local_shares_per_ads"] / df["usdkrw"]
        df["premium_pct"] = (df["ads_close"] / df["theoretical_usd"] - 1) * 100
        df = df.tail(60)
        if df.empty:
            summary.append({"ads": a["ads"], "status": "no_overlap"})
            continue
        last20 = df["premium_pct"].tail(20)
        w_ads, w_loc = wret(s["ads"], 5), wret(s["local"], 5)
        direction_match = bool(np.sign(w_ads) == np.sign(w_loc)) if pd.notna(w_ads) and pd.notna(w_loc) else None
        susp = (df["premium_pct"].tail(a["suspect_days"]).abs() > a["suspect_abs_premium_pct"]).all() and len(df) >= a["suspect_days"]
        summary.append({
            "ads": a["ads"], "local": a["local"], "fx": a["fx"], "status": "ok",
            "date": df.index[-1].strftime("%Y-%m-%d"),
            "premium_pct": round(float(df["premium_pct"].iloc[-1]), 2),
            "premium_avg20": round(float(last20.mean()), 2),
            "premium_min20": round(float(last20.min()), 2),
            "premium_max20": round(float(last20.max()), 2),
            "ads_ret_1w": nz(w_ads, 2), "local_ret_1w": nz(w_loc, 2), "direction_match": direction_match,
            "ratio_or_data_suspect": bool(susp),
            "observations": int(len(df)),
            "local_shares_per_ads": a["local_shares_per_ads"],
            "ratio_source": a.get("ratio_source"), "timing_note": a.get("timing_note"),
        })
        out = df.reset_index()
        out.insert(0, "ads", a["ads"])
        out["local_shares_per_ads"] = a["local_shares_per_ads"]
        rows.append(out)
    table = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    if not table.empty:
        table["date"] = pd.to_datetime(table["date"]).dt.strftime("%Y-%m-%d")
    return table, summary


# ---------- マクロ ----------
def macro_summary(out_dir):
    status = read_json(os.path.join(out_dir, "macro_manifest.json")) or {}
    path, latest = os.path.join(out_dir, "macro_daily.csv"), {}
    if os.path.exists(path):
        m = pd.read_csv(path).dropna(subset=["value"])
        for sid, g in m.sort_values("date").groupby("series"):
            v = g["value"].astype(float).reset_index(drop=True)
            item = {"date": g["date"].iloc[-1], "value": round(float(v.iloc[-1]), 3)}
            for lag, name in ((5, "chg_5obs"), (21, "chg_21obs"), (63, "chg_63obs")):
                if len(v) > lag:
                    item[name] = round(float(v.iloc[-1] - v.iloc[-1 - lag]), 3)
            latest[sid] = item
    return {"status": status.get("status", "not_run"), "generated_utc": status.get("generated_utc"),
            "latest": latest, "failed": status.get("failed", [])}


# ---------- 履歴 ----------
def append_history(path, new_rows, keys):
    new = pd.DataFrame(new_rows)
    if os.path.exists(path):
        old = pd.read_csv(path)
        new = pd.concat([old, new], ignore_index=True)
    new = new.drop_duplicates(subset=keys, keep="last").sort_values(keys)
    write_atomic(new, path)
    return int(len(new))


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    ap.add_argument("--config", default="config.json")
    a = ap.parse_args()
    with open(a.config, encoding="utf-8") as f:
        cfg = json.load(f)

    ppath = os.path.join(a.out, "prices_daily.csv.gz")
    if not os.path.exists(ppath):
        print("prices_daily.csv.gz がありません。", file=sys.stderr)
        sys.exit(1)
    px = pd.read_csv(ppath)
    px["date"] = pd.to_datetime(px["date"])
    px = px.drop_duplicates(subset=["ticker", "date"], keep="last").sort_values(["ticker", "date"])
    pman = read_json(os.path.join(a.out, "prices_manifest.json")) or {}

    no_volume, lev = set(cfg.get("no_volume", [])), cfg.get("leveraged", {})
    asia = tuple(cfg.get("asia_suffixes", []))
    closes = {t: g.set_index("date")["close"].astype(float).sort_index() for t, g in px.groupby("ticker")}
    benches = {b: closes.get(b) for b in cfg["benchmarks"]}
    wanted = list(dict.fromkeys([t for ts in cfg["groups"].values() for t in ts] + [t for ts in cfg["breadth_sets"].values() for t in ts]))
    group_of = {t: g for g, ts in cfg["groups"].items() for t in ts}

    rows, flags, missing = [], {}, []
    for t in wanted:
        g = px[px["ticker"] == t]
        if g.empty:
            missing.append(t)
            continue
        thr = JUMP["leveraged"] if t in lev else (JUMP["fx_rates"] if t in cfg["groups"].get("rates_fx", []) else JUMP["default"])
        row, fl = metrics_for(t, g, benches, no_volume, thr)
        rows.append({"group": group_of.get(t, "breadth_only"), "ticker": t, **row})
        if fl:
            flags[t] = fl
    snap = pd.DataFrame(rows)

    us_asof = closes["SPY"].index[-1] if "SPY" in closes else pd.to_datetime(snap["last_date"]).max()
    snap["days_behind_us"] = [int(np.busday_count(pd.Timestamp(d).date(), us_asof.date())) for d in snap["last_date"]]
    for t, d in zip(snap["ticker"], snap["days_behind_us"]):
        limit = 3 if t.endswith(asia) else (2 if t in cfg["groups"].get("rates_fx", []) else 1)
        if d < 0:
            flags.setdefault(t, []).append("ahead_of_us_close(intraday_bar?)")
        elif d >= limit:
            flags.setdefault(t, []).append(f"stale:{d}d")
    num = snap.select_dtypes("number").columns.difference(["n_obs", "high_window", "days_behind_us"])
    snap[num] = snap[num].astype(float).round(4)
    write_atomic(snap, os.path.join(a.out, "semis_snapshot.csv"))

    adr, adr_sum = adr_tables(px, cfg)
    if not adr.empty:
        write_atomic(adr.round(4), os.path.join(a.out, "adr_premium.csv"))
    for s in adr_sum:
        if s.get("ratio_or_data_suspect"):
            flags.setdefault(s["ads"], []).append("adr_ratio_or_data_suspect")

    breadth = {k: breadth_stats(snap, v) for k, v in cfg["breadth_sets"].items()}
    levels, scores = compute_levels(snap, cfg, adr_sum, breadth)
    asof_str = us_asof.strftime("%Y-%m-%d")
    write_atomic({"us_as_of": asof_str, "definitions_version": DEFINITIONS_VERSION, "config_version": cfg.get("config_version"),
                  "levels": levels, "scores": scores}, os.path.join(a.out, "levels.json"))

    hist_levels = {"us_as_of": asof_str, **{k: v["level"] for k, v in levels.items()},
                   "S_score": scores["S"]["score"], "D_score": scores["D"]["score"], "TECHNICAL": scores["TECHNICAL"],
                   "S_coverage": scores["S"]["coverage_pct"], "D_coverage": scores["D"]["coverage_pct"]}
    n_hl = append_history(os.path.join(a.out, "history_levels.csv"), [hist_levels], ["us_as_of"])
    keycols = ["close", "ret_1d", "ret_1w", "ret_1m", "sma20", "sma50", "sma200", "rsi14", "vol_ratio20", "updown_vol_ratio10",
               "dd_from_high", "rv20", "rs_spy_20", "rs_spy_60", "rs_soxx_20", "rs_soxx_60"]
    kh = [{"us_as_of": asof_str, "ticker": r["ticker"], "last_date": r["last_date"], **{c: r.get(c) for c in keycols if c in snap.columns}}
          for _, r in snap.iterrows() if r["ticker"] in cfg["history_tickers"]]
    n_kh = append_history(os.path.join(a.out, "history_key.csv"), kh, ["us_as_of", "ticker"])

    now = datetime.now(timezone.utc)
    manifest = {
        "generated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_jst": now.astimezone(JST).strftime("%Y-%m-%d %H:%M JST"),
        "definitions_version": DEFINITIONS_VERSION,
        "config_version": cfg.get("config_version"),
        "us_as_of": asof_str,
        "prices_generated_utc": pman.get("generated_utc"),
        "prices_failed": pman.get("tickers_failed"),
        "rows": int(len(snap)),
        "missing_tickers": missing,
        "flags": flags,
        "scores": scores,
        "levels": {k: v["level"] for k, v in levels.items()},
        "breadth": breadth,
        "adr": adr_sum,
        "macro": macro_summary(a.out),
        "history_rows": {"levels": n_hl, "key": n_kh},
        "files": ["semis_snapshot.csv", "levels.json", "adr_premium.csv", "macro_daily.csv", "history_levels.csv", "history_key.csv"],
        "price_basis": pman.get("price_basis", "split_adjusted_ex_dividends(yahoo_close)"),
        "source": "Yahoo Finance via yfinance (unofficial) / FRED",
    }
    write_atomic(manifest, os.path.join(a.out, "semis_manifest.json"))
    print(json.dumps({k: manifest[k] for k in ("us_as_of", "missing_tickers", "flags", "scores", "levels")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
