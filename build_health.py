"""
半導体セクターの状態（sector_health.json）を計算する（GitHub Actions で build_snapshot.py の後、build_signals.py の前に実行）

「半導体セクター自体が強いか弱いか」を、指数（SOXX）・中身（約40銘柄）・相対力（他のテクノロジーとの比較）の3つから機械的に出す。
判断はしない。売買の合図ではない。定義の説明と15年の検証結果は docs/sector_health.md。

出力 sector_health.json（config.json の sector_health で閾値を変えられる。無ければ下の既定値）
  breadth     中身：20日線・50日線・30週線（150本）の上にいる銘柄の割合、上昇中／下落中（簡易ステージ）の割合、13週高値・安値の割合、均等加重の対SOXX
  label       判定ラベル（健全／改善中／どちらとも／悪化中／弱い）。簡易ステージの分布から。market-data（米国株指標チェック）の
              E6.3 の規則と同じ順番で判定するが、ステージは簡易版（下記）なので値は一致しない。公式のステージ分布は market-data の
              signals.json の stages.breadth["監視：半導体"] を転記する（日次プロンプト 0節）
  risk        大きく下げる危険の目安：3条件（判定が悪化中か弱い／SOXXが30週線の下／市場と比べた13週がマイナス）のそろい数 0〜3
  washout     底の目安（売られ尽くし）：3条件（50日線上<5%／30週線上<15%／SOXXが30週線から−20%以下）のそろい数 0〜3
  strip       相対力の帯：SOXX÷比較相手（市場 SPY・テック全体 XLK・ソフト IGV・ハード均等加重）が、短期（21日EMA）・中期（50日EMA）の上なら緑
  subsectors  分野別（AI計算・製造／製造装置／メモリー／アナログ・汎用／光・後工程／設計ソフト）の上昇中−下落中と50日線上の割合

簡易ステージ（この観測の中だけの定義。market-data E6.2 の細区分とは別）
  上昇中（stage2相当）＝終値 > 150日線 かつ 150日線が20本前より上
  下落中（stage4相当）＝終値 < 150日線 かつ 150日線が20本前より下
  150日線が無い銘柄（上場1年未満）は分母に入れない

価格は close（分割調整済み・配当非調整。build_snapshot.py と同じ）。ハード均等加重は構成銘柄の日次騰落率の単純平均を積み上げた指数。
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

import build_snapshot as bs

HEALTH_VERSION = "1.0"
JST = timezone(timedelta(hours=9))
DEFAULT = {
    "index": "SOXX",
    "universe": "semis_broad",
    "ma_bars": 150, "slope_bars": 20, "compare_bars": 20,                      # 簡易ステージ、4週前との比較
    "label": {"weak_stage4_pct": 40, "deteriorate_pt": 10, "healthy_stage2_pct": 50, "healthy_stage4_max": 20, "improve_pt": 10},
    "risk": {"rs_bench": "SPY", "rs_bars": 65},
    "washout": {"above50_lt": 5, "above150_lt": 15, "index_vs_ma150_le": -20},
    "strip": {"benches": {"市場": "SPY", "テック全体": "XLK", "ソフト": "IGV", "ハード": "hardware_basket"}, "ema_spans": [21, 50], "confirm_days": 3},
    "subsectors": {
        "AI計算・製造": ["NVDA", "AMD", "AVGO", "MRVL", "TSM", "ARM", "ALAB", "CRDO"],
        "製造装置": ["ASML", "AMAT", "LRCX", "KLAC", "TER", "ENTG", "ONTO", "FORM", "NVMI", "CAMT"],
        "メモリー": ["MU", "SNDK", "SKHY", "WDC", "STX"],
        "アナログ・汎用": ["TXN", "ADI", "NXPI", "MCHP", "ON", "MPWR", "SWKS", "LSCC", "QCOM", "INTC", "RMBS", "SITM", "MTSI"],
        "光・後工程": ["COHR", "LITE", "AMKR", "ASX"],
        "設計ソフト": ["SNPS", "CDNS"],
    },
}
LABEL_JA = {"healthy": "健全", "improving": "改善中", "neutral": "どちらとも言えない", "deteriorating": "悪化中", "weak": "弱い"}
# 15年（2011〜2026-11）の検証値。docs/sector_health.md の表と同じ。読み方の目安として JSON に添える（再計算しない）
RISK_REF = {0: "翌13週に−15%超の下落が来た割合 9%", 1: "同 10%", 2: "同 17%", 3: "同 24%（基準は13%）"}
WASHOUT_REF = {0: "", 1: "過去15回：26週後 平均+18%、だまし（60営業日内にさらに−10%）40%", 2: "過去12回：26週後 平均+21%、だまし 42%",
               3: "過去6回：26週後 平均+40%、だまし 0%、60営業日内の最大下落は最悪−9%（2011/8、2020/3、2022/6・9、2025/4、2026/11）"}


def _pct(mask, denom):
    d = int(denom)
    return None if d == 0 else round(float(mask.sum()) / d * 100, 1)


def _streak(bools):
    """末尾から同じ値が何本続いているか（最後の値と本数）"""
    if len(bools) == 0 or pd.isna(bools.iloc[-1]):
        return None, 0
    last = bool(bools.iloc[-1])
    n = 0
    for v in bools.iloc[::-1]:
        if pd.isna(v) or bool(v) != last:
            break
        n += 1
    return last, n


def _last_date(bools, value):
    s = bools[bools == value]
    return None if s.empty else s.index[-1].strftime("%Y-%m-%d")


def closes_matrix(px, us_asof):
    C = px.pivot(index="date", columns="ticker", values="close").sort_index()
    C = C[C.index <= us_asof].astype(float)
    if "SPY" in C:                                  # 米国の取引日だけにそろえる（アジア株だけの日を除く。NaN の行があると移動平均が欠ける）
        C = C[C["SPY"].notna()]
    return C


def equal_weight_index(C, tickers):
    cols = [t for t in tickers if t in C]
    if not cols:
        return None, []
    r = C[cols].pct_change().mean(axis=1, skipna=True).fillna(0.0)
    return (1 + r).cumprod(), cols


def judge_label(cur, prev, p):
    """market-data E6.3 と同じ順番：弱い→悪化中→健全→改善中→どちらとも。cur/prev は {stage2, stage4}（%）"""
    if cur["stage4"] is None or prev is None or prev.get("stage2") is None:
        return None
    if cur["stage4"] >= p["weak_stage4_pct"]:
        return "weak"
    if cur["stage4"] - prev["stage4"] >= p["deteriorate_pt"] or (cur["stage2"] <= prev["stage2"] - p["deteriorate_pt"] and cur["stage4"] >= prev["stage4"]):
        return "deteriorating"
    if cur["stage2"] >= p["healthy_stage2_pct"] and cur["stage4"] < p["healthy_stage4_max"]:
        return "healthy"
    if cur["stage2"] - prev["stage2"] >= p["improve_pt"] and cur["stage4"] <= prev["stage4"]:
        return "improving"
    return "neutral"


def breadth_at(C, universe, i, p):
    """位置 i（当日）の中身。150日線が無い銘柄は分母に入れない。"""
    X = C[universe].iloc[: i + 1]
    last = X.iloc[-1]
    ok = last.notna()
    out = {"tickers": int(ok.sum())}
    for n, key in ((20, "above20"), (50, "above50"), (p["ma_bars"], "above150")):
        ma = X.rolling(n, min_periods=n).mean().iloc[-1]
        m = ma.notna() & ok
        out[key] = _pct(last[m] > ma[m], m.sum())
    ma = X.rolling(p["ma_bars"], min_periods=p["ma_bars"]).mean()
    sl = ma.iloc[-1] / ma.iloc[-1 - p["slope_bars"]] - 1 if len(ma) > p["slope_bars"] else pd.Series(np.nan, index=ma.columns)
    m = ma.iloc[-1].notna() & sl.notna() & ok
    out["stage_tickers"] = int(m.sum())
    out["stage2"] = _pct((last[m] > ma.iloc[-1][m]) & (sl[m] > 0), m.sum())
    out["stage4"] = _pct((last[m] < ma.iloc[-1][m]) & (sl[m] < 0), m.sum())
    out["net_2_minus_4"] = None if out["stage2"] is None else round(out["stage2"] - out["stage4"], 1)
    hi, lo = X.rolling(65, min_periods=65).max().iloc[-1], X.rolling(65, min_periods=65).min().iloc[-1]
    m2 = hi.notna() & ok
    out["new_high_13w"] = _pct(last[m2] >= hi[m2], m2.sum())
    out["new_low_13w"] = _pct(last[m2] <= lo[m2], m2.sum())
    return out


def compute_health(px, cfg, us_asof):
    p = {**DEFAULT, **cfg.get("sector_health", {})}
    for k in ("label", "risk", "washout", "strip"):
        p[k] = {**DEFAULT[k], **(cfg.get("sector_health", {}).get(k, {}))}
    C = closes_matrix(px, us_asof)
    idx = p["index"]
    if idx not in C or "SPY" not in C:
        return {"status": "missing", "note": f"{idx} または SPY の日足がありません"}
    universe = [t for t in cfg["breadth_sets"][p["universe"]] if t in C]
    i = len(C) - 1
    cb = p["compare_bars"]

    # ---- 中身と判定ラベル ----
    now = breadth_at(C, universe, i, p)
    prev4 = breadth_at(C, universe, i - cb, p) if i - cb >= p["ma_bars"] else None
    label = judge_label(now, prev4, p["label"])
    ew, ew_cols = equal_weight_index(C, universe)
    if ew is not None and i >= 65 and pd.notna(C[idx].iloc[i - 65]):
        now["equal_weight_vs_index_13w_pct"] = round(float(((ew.iloc[i] / ew.iloc[i - 65]) / (C[idx].iloc[i] / C[idx].iloc[i - 65]) - 1) * 100), 2)
    else:
        now["equal_weight_vs_index_13w_pct"] = None

    # ---- 指数 ----
    S = C[idx]
    ma150 = S.rolling(p["ma_bars"], min_periods=p["ma_bars"]).mean()
    ext150 = (S / ma150 - 1) * 100
    rb, rn = p["risk"]["rs_bench"], p["risk"]["rs_bars"]
    rs13 = ((S / S.shift(rn)) / (C[rb] / C[rb].shift(rn)) - 1) * 100 if rb in C else pd.Series(np.nan, index=S.index)
    index_block = {
        "ticker": idx, "close": bs.nz(S.iloc[i], 2), "ma150": bs.nz(ma150.iloc[i], 2), "pct_vs_ma150": bs.nz(ext150.iloc[i], 2),
        "above_ma150": None if pd.isna(ma150.iloc[i]) else bool(S.iloc[i] > ma150.iloc[i]),
        "ma150_slope_20d_pct": bs.nz((ma150.iloc[i] / ma150.iloc[i - cb] - 1) * 100, 2) if i >= cb else None,
        f"rs_{rb.lower()}_13w_pct": bs.nz(rs13.iloc[i], 2),
        "ret_13w_pct": bs.nz((S.iloc[i] / S.iloc[i - 65] - 1) * 100, 2) if i >= 65 else None,
        "official_stage_source": "market-data signals.json → stages.etfs（SOXX・SMH）と stages.breadth['監視：半導体']（転記する。ここでは計算しない）",
    }

    # ---- 危険の目安 ----
    risk_conds = {
        "label_weak_or_deteriorating": {"ja": "判定が悪化中か弱い", "met": None if label is None else label in ("weak", "deteriorating"), "value": LABEL_JA.get(label)},
        "index_below_ma150": {"ja": "SOXXが30週線（150日線）の下", "met": None if index_block["above_ma150"] is None else not index_block["above_ma150"], "value": index_block["pct_vs_ma150"]},
        "rs_vs_market_13w_negative": {"ja": f"市場（{rb}）と比べた13週がマイナス", "met": None if pd.isna(rs13.iloc[i]) else bool(rs13.iloc[i] < 0), "value": bs.nz(rs13.iloc[i], 2)},
    }
    met = [v["met"] for v in risk_conds.values()]
    risk_count = None if any(m is None for m in met) else int(sum(met))
    risk = {"count": risk_count, "of": 3, "conditions": risk_conds,
            "reading": None if risk_count is None else RISK_REF[risk_count],
            "note": "『予測』ではなく今の危険度。15年の検証で、3条件そろいの週は翌13週に−15%超の下落が24%（0個は9%）。2011〜2018年は3個でも12%で差が小さかった。売買の合図にしない"}

    # ---- 底の目安（売られ尽くし） ----
    w = p["washout"]
    wash_conds = {
        "above50_lt": {"ja": f"50日線の上が{w['above50_lt']}%未満", "met": None if now["above50"] is None else now["above50"] < w["above50_lt"], "value": now["above50"]},
        "above150_lt": {"ja": f"30週線の上が{w['above150_lt']}%未満", "met": None if now["above150"] is None else now["above150"] < w["above150_lt"], "value": now["above150"]},
        "index_vs_ma150_le": {"ja": f"SOXXが30週線から{w['index_vs_ma150_le']}%以下", "met": None if pd.isna(ext150.iloc[i]) else bool(ext150.iloc[i] <= w["index_vs_ma150_le"]), "value": index_block["pct_vs_ma150"]},
    }
    met = [v["met"] for v in wash_conds.values()]
    wash_count = None if any(m is None for m in met) else int(sum(met))
    # 履歴内で3条件そろった日（読み込んだ約3年分だけ）
    ab50_hist = pd.Series([np.nan] * len(C), index=C.index)
    hist3 = []
    if len(C) > p["ma_bars"] + 1:
        X = C[universe]
        s50 = X.rolling(50, min_periods=50).mean(); s150 = X.rolling(p["ma_bars"], min_periods=p["ma_bars"]).mean()
        a50 = (X > s50).sum(axis=1) / s50.notna().sum(axis=1).replace(0, np.nan) * 100
        a150 = (X > s150).sum(axis=1) / s150.notna().sum(axis=1).replace(0, np.nan) * 100
        all3 = (a50 < w["above50_lt"]) & (a150 < w["above150_lt"]) & (ext150 <= w["index_vs_ma150_le"])
        starts = all3 & ~all3.shift(1, fill_value=False)
        last_i = None
        for d in starts[starts].index:                 # 40営業日以内の再成立は同じ局面として1つにまとめる
            j = C.index.get_loc(d)
            if last_i is None or j - last_i >= 40:
                hist3.append(d.strftime("%Y-%m-%d"))
            last_i = j
    washout = {"count": wash_count, "of": 3, "conditions": wash_conds,
               "reading": None if wash_count is None else WASHOUT_REF[wash_count],
               "dates_all3_in_history": hist3,
               "note": "『売られ尽くし』の目安。1〜2条件は底探しの入口（だまし約4割）、3条件は過去6回で外れなし（うち1回は2026/11で結果待ち）。底の確定ではなく、買い下がる局面の目印。確認の工夫（20日線上の急増・21日EMA回復など）はだましを減らさなかった（docs/sector_health.md）"}

    # ---- 相対力の帯 ----
    sp = p["strip"]
    benches, bands, missing_b = {}, {}, []
    for ja, b in sp["benches"].items():
        if b in cfg["groups"] and b not in C:          # グループ名 → 均等加重
            series, cols = equal_weight_index(C, cfg["groups"][b])
            if series is None:
                missing_b.append(ja); continue
            benches[ja] = {"bench": b, "series": series, "components": cols}
        elif b in C:
            benches[ja] = {"bench": b, "series": C[b], "components": None}
        else:
            missing_b.append(ja)
    for ja, bb in benches.items():
        rs = S / bb["series"]
        row = {"bench": bb["bench"], "components": bb["components"]}
        for span in sp["ema_spans"]:
            e = rs.ewm(span=span, adjust=False, min_periods=span).mean()
            g = (rs > e).where(e.notna())
            last, n = _streak(g)
            row[f"ema{span}"] = {"green": last, "days": n, "dist_pct": bs.nz((rs.iloc[i] / e.iloc[i] - 1) * 100, 2) if pd.notna(e.iloc[i]) else None,
                                 "ema_slope_5d_pct": bs.nz((e.iloc[i] / e.iloc[i - 5] - 1) * 100, 2) if i >= 5 and pd.notna(e.iloc[i - 5]) else None}
        row["rel_13w_pct"] = bs.nz((rs.iloc[i] / rs.iloc[i - 65] - 1) * 100, 2) if i >= 65 and pd.notna(rs.iloc[i - 65]) else None
        bands[ja] = row
    strip = {"benches_missing": missing_b, "bands": bands, "summary": {}}
    for span in sp["ema_spans"]:
        greens = [bands[ja][f"ema{span}"]["green"] for ja in bands]
        if not greens or any(g is None for g in greens):
            strip["summary"][f"ema{span}"] = {"green_count": None, "of": len(bands)}
            continue
        # そろい状態の連続日数（履歴から）
        G = pd.DataFrame({ja: ((S / benches[ja]["series"]) > (S / benches[ja]["series"]).ewm(span=span, adjust=False, min_periods=span).mean()) for ja in bands})
        cnt = G.sum(axis=1)
        all_g, all_r = cnt == len(bands), cnt == 0
        k = sp["confirm_days"]
        on = all_g.rolling(k).sum() == k
        off = all_r.rolling(k).sum() == k
        st = pd.Series(np.nan, index=cnt.index); st[on] = 1; st[off] = 0; st = st.ffill()
        state = None if pd.isna(st.iloc[-1]) else ("半導体がテックの主役" if st.iloc[-1] == 1 else "主役ではない")
        strip["summary"][f"ema{span}"] = {
            "green_count": int(sum(greens)), "of": len(bands),
            "all_green_days": _streak(all_g)[1] if all_g.iloc[-1] else 0, "all_red_days": _streak(all_r)[1] if all_r.iloc[-1] else 0,
            "last_all_green": _last_date(all_g, True), "last_all_red": _last_date(all_r, True),
            "state": state, "state_since": None if pd.isna(st.iloc[-1]) else _since(st),
        }
    strip["note"] = ("帯＝SOXX÷比較相手のRS線がEMAの上（緑）か下（赤）か。表示だけ。15年の検証では、全部緑／全部赤で乗り換える戦略は持ちっぱなしに負けた"
                     "（年率+14%対+23%）。『主役ではない』は相対的に弱いという描写で、売りの合図ではない")

    # ---- 分野別 ----
    subs = {}
    for ja, tks in p["subsectors"].items():
        cols = [t for t in tks if t in C]
        if not cols:
            continue
        b = breadth_at(C, cols, i, p)
        subs[ja] = {"tickers": cols, "n": b["stage_tickers"], "stage2": b["stage2"], "stage4": b["stage4"], "net_2_minus_4": b["net_2_minus_4"], "above50": b["above50"]}

    return {
        "status": "ok",
        "health_version": HEALTH_VERSION,
        "us_as_of": us_asof.strftime("%Y-%m-%d"),
        "universe": {"set": p["universe"], "tickers": universe, "n": len(universe)},
        "label": label, "label_ja": LABEL_JA.get(label),
        "label_rule": "弱い＝下落中40%以上／悪化中＝4週前より下落中が10pt以上増、または上昇中が10pt以上減って下落中が減っていない／健全＝上昇中50%以上かつ下落中20%未満／改善中＝上昇中が10pt以上増かつ下落中が増えていない／それ以外どちらとも（market-data E6.3 と同じ順番。ステージは簡易版）",
        "breadth": now, "breadth_4w_ago": prev4,
        "breadth_meaning": (f"割合の分母は監視する半導体{len(universe)}銘柄（上昇中・下落中は150日線のある{now['stage_tickers']}銘柄）。"
                            "上昇中＝株価が30週線（150日線）の上で、その線も4週前より上向き。下落中＝株価が線の下で、線も下向き。残りは中間（線を割ったが線はまだ上向き、など）。"
                            "長い上昇の直後の急落では線がまだ上向きなので『下落中』が公式のステージ分布より少なく出る。公式（market-data）が取れる日はそちらを先に書く"),
        "index": index_block,
        "risk": risk, "washout": washout, "strip": strip, "subsectors": subs,
    }


def _since(st):
    v = st.iloc[-1]
    s = st[st != v]
    return st.index[0].strftime("%Y-%m-%d") if s.empty else st.index[st.index.get_loc(s.index[-1]) + 1].strftime("%Y-%m-%d")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--as-of", default=None, help="（補完用）この日付までの足だけで計算する。出力先は data ブランチ以外にする")
    a = ap.parse_args()
    with open(a.config, encoding="utf-8") as f:
        cfg = json.load(f)
    ppath = os.path.join(a.out, "prices_daily.csv.gz")
    if not os.path.exists(ppath):
        print("prices_daily.csv.gz がありません。", file=sys.stderr)
        sys.exit(1)
    px = bs.load_prices(ppath)
    if a.as_of:
        px = px[px["date"] <= pd.Timestamp(a.as_of)]
    spy = px[px["ticker"] == "SPY"]
    us_asof = spy["date"].max() if not spy.empty else px["date"].max()
    if a.as_of and us_asof.strftime("%Y-%m-%d") != a.as_of:
        print(json.dumps({"error": "as_of_not_trading_day", "as_of": a.as_of, "last_available": us_asof.strftime("%Y-%m-%d")}, ensure_ascii=False))
        sys.exit(2)
    h = compute_health(px, cfg, us_asof)
    nowt = datetime.now(timezone.utc)
    h["generated_utc"] = nowt.strftime("%Y-%m-%dT%H:%M:%SZ")
    h["generated_jst"] = nowt.astimezone(JST).strftime("%Y-%m-%d %H:%M JST")
    bs.write_atomic(h, os.path.join(a.out, "sector_health.json"))
    if h.get("status") == "ok":
        b, s = h["breadth"], h["strip"]["summary"]
        row = {"us_as_of": h["us_as_of"], "label": h["label"], "stage2": b["stage2"], "stage4": b["stage4"], "above50": b["above50"], "above150": b["above150"],
               "index_pct_vs_ma150": h["index"]["pct_vs_ma150"], "risk_count": h["risk"]["count"], "washout_count": h["washout"]["count"],
               "strip_green_ema21": s.get("ema21", {}).get("green_count"), "strip_green_ema50": s.get("ema50", {}).get("green_count")}
        bs.append_history(os.path.join(a.out, "history_health.csv"), [row], ["us_as_of"])
        print(json.dumps({"us_as_of": h["us_as_of"], "label": h["label_ja"], "risk": h["risk"]["count"], "washout": h["washout"]["count"],
                          "strip": {k: v.get("green_count") for k, v in s.items()}, "missing_benches": h["strip"]["benches_missing"]}, ensure_ascii=False))
    else:
        print(json.dumps(h, ensure_ascii=False))


if __name__ == "__main__":
    main()
