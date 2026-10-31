"""
日次シグナル検出（GitHub Actionsで build_snapshot.py の後に実行）

当日（T）と前営業日（T−1）の指標を日足から計算し直して比べ、売買タイミングの参考になる
「変化点」を機械的に検出する。判断はしない。出力は daily_signals.json。

検出するもの（config.json の daily_signals で閾値を変えられる）
  sma_cross      終値がSMA20/50/200を上抜け・下抜け
  rsi            RSI14が30/70を跨いだ、または25未満/75超
  new_high_low   終値が20/60/252本の高値・安値を更新
  big_move       1日の騰落率が閾値超（指数3%、個別4%、SOXL8%、為替1.5%）
  volume         出来高比1.5以上で、かつ1日の騰落率が±2%超（上昇日/下落日を区別）
  drawdown       高値からの下落率が−10/−20/−30%を跨いだ
  breadth        広がり（SMA50上比率）が10pt以上動いた、または段階の帯を跨いだ
  level_change   S1〜S5・D1〜D6の段階が変わった、S/Dスコアが5点以上動いた
  adr_premium    SKHYプレミアムが前日比5pt以上動いた、または20日平均との差が5pt超
  vix            VIXが25超、または1日で20%超上昇
  rates          10年実質金利の5営業日変化が±15bp以上
  fx             USD/KRW・USD/JPYの1日変化が±1.5%以上
  v6.1 追加（resilience.json の前日比）
  sector_rs_flip     セクター内区分（対SOXX）が leader⇄laggard に変わった
  next_candidate_new／next_candidate_out 調整耐性の「次の候補」に入った／外れた。late_break_new 「後崩れ」に新しく入った
  corr_state_change  SOXXの調整窓の状態（調整中・回復中・完了・なし）が変わった
  v6.2 追加（市場比のRS線）
  rs_line        RS線（銘柄÷SPY）が52週高値を更新（株価より先なら high）、主要銘柄のRS線が21日EMAを上抜け・下抜け

RS線（rs_lines。セクター内RS＝対SOXXとは別。こちらは市場全体＝SPY比）
  RS線 = 終値 ÷ SPY終値（同じ日付どうし）。補助にQQQ比も出す。米国上場の銘柄・ETFだけ（アジア株・為替・指数は対象外）。
  RS新高値 = 当日値が直近252本の過去値すべてを上回る（253本必要。米国株仕様v4.2 E7と同じ定義）。
  RSが株価に先行 = RS新高値の日に、株価が252日終値高値から rs_lead_price_gap_pct 以上下にある。
  SOXLは3倍レバで比率がゆがむため対象外（SOXXのRS線で代用）。
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

import build_snapshot as bs

JST = timezone(timedelta(hours=9))
DEFAULT_THR = {
    "big_move_index": 3.0, "big_move_stock": 4.0, "big_move_leveraged": 8.0, "big_move_fx": 1.5,
    "volume_ratio": 1.5, "volume_min_move": 2.0,
    "dd_thresholds": [-10, -20, -30],
    "breadth_shift_pt": 10,
    "score_shift": 5,
    "adr_premium_shift": 5, "adr_gap": 5,
    "vix_level": 25, "vix_spike_pct": 20,
    "real_rate_5d_bp": 15,
    "fx_move": 1.5,
    "rs_window": 252, "rs_ema": 21,
    "rs_lead_price_gap_pct": 2.0,   # RS新高値の日に株価がこれ以上（%）高値の下なら「先行」
    "rs_first_gap_days": 20,        # 前回のRS新高値からこの営業日数以上あいたら「久しぶり」と書く
}
INDEX_LIKE = {"^GSPC", "SPY", "QQQ", "^SOX", "SOXX", "SMH", "^VIX"}
RS_BENCH, RS_AUX = "SPY", "QQQ"
RS_EXCLUDE = {"^GSPC", "SPY", "QQQ", "^SOX", "^VIX", "SOXL"}           # 自分自身・指数・レバETF
RS_CORE = ["SOXX", "SMH", "DRAM", "NVDA", "TSM", "MU", "SNDK", "SKHY"]  # 21日EMAクロスをシグナルにする銘柄
RS_GROUPS = ["market", "memory_us", "ai_logic", "equipment", "packaging_network", "hyperscalers"]


def _r(x, nd=2):
    return None if x is None or pd.isna(x) else round(float(x), nd)


def rs_line_stats(c, b, i, thr):
    """c, b：同じ日付に揃えた銘柄とベンチマークの終値。i：基準日の位置。RS線の状態を返す。"""
    w, n_ema = int(thr["rs_window"]), int(thr["rs_ema"])
    rs = c / b
    prior_max = rs.shift(1).rolling(w, min_periods=w).max()     # 過去252本（当日を含まない）
    is_nh = rs > prior_max
    px_prior_max = c.shift(1).rolling(w, min_periods=w).max()
    px_hi = c.rolling(w, min_periods=w).max()                   # 当日を含む252日終値高値
    rs_hi = rs.rolling(w, min_periods=w).max()
    e = rs.ewm(span=n_ema, adjust=False, min_periods=n_ema).mean()
    if pd.isna(rs.iloc[i]):
        return None
    enough = pd.notna(prior_max.iloc[i])
    nh = bool(is_nh.iloc[i]) if enough else None
    past = np.where(is_nh.iloc[:i].fillna(False).values)[0]
    since = int(i - past[-1]) if len(past) else None
    px_gap = (c.iloc[i] / px_hi.iloc[i] - 1) * 100 if pd.notna(px_hi.iloc[i]) else np.nan
    px_nh = bool(c.iloc[i] > px_prior_max.iloc[i]) if pd.notna(px_prior_max.iloc[i]) else None
    above = None if pd.isna(e.iloc[i]) else bool(rs.iloc[i] > e.iloc[i])
    above_y = None if (i < 1 or pd.isna(e.iloc[i - 1]) or pd.isna(rs.iloc[i - 1])) else bool(rs.iloc[i - 1] > e.iloc[i - 1])
    cross = None if above is None or above_y is None or above == above_y else ("up" if above else "down")
    return {
        "rs_new_high": nh,
        "leads_price": None if nh is None else bool(nh and pd.notna(px_gap) and px_gap <= -thr["rs_lead_price_gap_pct"]),
        "price_new_high": px_nh,
        "days_since_prev_rs_high": since,   # None＝履歴内（最大約3年）にRS新高値なし
        "rs_pct_from_52w_high": _r((rs.iloc[i] / rs_hi.iloc[i] - 1) * 100 if pd.notna(rs_hi.iloc[i]) else np.nan, 1),
        "price_pct_from_52w_high": _r(px_gap, 1),
        "above_ema21": above,
        "cross_ema21": cross,
        "dist_ema21_pct": _r((rs.iloc[i] / e.iloc[i] - 1) * 100 if pd.notna(e.iloc[i]) else np.nan),
        "ema21_slope_5d_pct": _r((e.iloc[i] / e.iloc[i - 5] - 1) * 100 if i >= 5 and pd.notna(e.iloc[i - 5]) else np.nan),
        "rs_chg_21d_pct": _r((rs.iloc[i] / rs.iloc[i - 21] - 1) * 100 if i >= 21 and pd.notna(rs.iloc[i - 21]) else np.nan),
        "history_ok": bool(enough),
    }


def rs_lines(px, cfg, thr, us_asof):
    """米国上場銘柄のRS線（対SPY、補助で対QQQ）。返り値：(rs_lines の辞書, シグナルのリスト)"""
    C = px.pivot(index="date", columns="ticker", values="close").sort_index()
    if RS_BENCH not in C:
        return {"status": "missing", "note": "SPYの日足がありません"}, []
    C = C[C[RS_BENCH].notna() & (C.index <= us_asof)].astype(float)
    i = len(C) - 1
    asia, fx = tuple(cfg.get("asia_suffixes", [])), set(cfg["groups"].get("rates_fx", []))
    group_of = {t: g for g, ts in cfg["groups"].items() for t in ts}
    names = [t for g in RS_GROUPS for t in cfg["groups"].get(g, [])]
    names = [t for t in dict.fromkeys(names) if t in C and t not in RS_EXCLUDE and t not in fx and not t.endswith(asia)]
    spy = C[RS_BENCH]
    spy_hi = spy.rolling(int(thr["rs_window"]), min_periods=int(thr["rs_window"])).max().iloc[i]

    rows, sig = [], []
    for t in names:
        if pd.isna(C[t].iloc[i]):
            continue  # 基準日の終値がない（取得遅れ）
        s = rs_line_stats(C[t], spy, i, thr)
        if s is None:
            continue
        q = rs_line_stats(C[t], C[RS_AUX], i, thr) if RS_AUX in C and t != RS_AUX else None
        rows.append({"ticker": t, "group": group_of.get(t, ""), **s,
                     "qqq": None if q is None else {k: q[k] for k in ("rs_new_high", "above_ema21", "rs_pct_from_52w_high", "rs_chg_21d_pct")}})
        if s["rs_new_high"]:
            gap = s["days_since_prev_rs_high"]
            gap_txt = "（履歴内で初）" if gap is None else (f"（前回のRS新高値から{gap}営業日ぶり）" if gap >= thr["rs_first_gap_days"] else "")
            if s["leads_price"]:
                sig.append({"type": "rs_line", "ticker": t, "severity": "high", "value": s["price_pct_from_52w_high"],
                            "detail": f"RS線（対SPY）が52週高値を更新、株価は高値から{s['price_pct_from_52w_high']:+.1f}%（RSが株価に先行）{gap_txt}"})
            else:
                sig.append({"type": "rs_line", "ticker": t, "severity": "medium", "value": s["price_pct_from_52w_high"],
                            "detail": f"RS線（対SPY）が52週高値を更新、株価も高値圏（高値から{s['price_pct_from_52w_high']:+.1f}%）{gap_txt}"})
        if t in RS_CORE and s["cross_ema21"]:
            sig.append({"type": "rs_line", "ticker": t, "severity": "medium", "value": s["dist_ema21_pct"],
                        "detail": f"RS線（対SPY）が21日EMAを{'上抜け' if s['cross_ema21'] == 'up' else '下抜け'}（EMAとの差 {s['dist_ema21_pct']:+.2f}%）"})

    ok = [r for r in rows if r["above_ema21"] is not None]
    out = {
        "status": "ok",
        "as_of": C.index[i].strftime("%Y-%m-%d"),
        "bench": RS_BENCH, "aux_bench": RS_AUX,
        "definition": "RS線＝終値÷SPY終値。RS新高値＝当日値が過去252本すべてを上回る（253本必要）。"
                      f"先行＝RS新高値の日に株価が252日終値高値から{thr['rs_lead_price_gap_pct']}%以上下。SOXLは対象外（SOXXで代用）。",
        "spy_pct_from_52w_high": _r((spy.iloc[i] / spy_hi - 1) * 100 if pd.notna(spy_hi) else np.nan, 1),
        "summary": {
            "rs_new_high": [r["ticker"] for r in rows if r["rs_new_high"]],
            "rs_leads_price": [r["ticker"] for r in rows if r["leads_price"]],
            "rs_near_high_5pct": [r["ticker"] for r in rows if r["rs_pct_from_52w_high"] is not None and r["rs_pct_from_52w_high"] >= -5],
            "above_ema21": [r["ticker"] for r in ok if r["above_ema21"]],
            "below_ema21": [r["ticker"] for r in ok if not r["above_ema21"]],
            "above_ema21_count": f"{sum(r['above_ema21'] for r in ok)}/{len(ok)}",
            "crossed_up": [r["ticker"] for r in rows if r["cross_ema21"] == "up"],
            "crossed_down": [r["ticker"] for r in rows if r["cross_ema21"] == "down"],
            "history_short": [r["ticker"] for r in rows if not r["history_ok"]],
        },
        "rows": sorted(rows, key=lambda r: (not r["rs_new_high"], -(r["rs_pct_from_52w_high"] if r["rs_pct_from_52w_high"] is not None else -999))),
    }
    return out, sig


def side(a, b):
    if pd.isna(a) or pd.isna(b):
        return None
    return "above" if a > b else "below"


def row_of(snap, t):
    r = snap[snap["ticker"] == t]
    return r.iloc[0] if not r.empty else None


def detect(now, prev, cfg, thr, tickers):
    S, P = now["snap"], prev["snap"]
    sig = []

    def add(kind, ticker, detail, severity="medium", value=None):
        sig.append({"type": kind, "ticker": ticker, "detail": detail, "severity": severity, "value": value})

    lev = cfg.get("leveraged", {})
    fx = set(cfg["groups"].get("rates_fx", []))
    for t in tickers:
        n, p = row_of(S, t), row_of(P, t)
        if n is None or p is None:
            continue
        # SMA cross
        for w in (20, 50, 200):
            a, b = side(n["close"], n[f"sma{w}"]), side(p["close"], p[f"sma{w}"])
            if a and b and a != b:
                core = t in INDEX_LIKE or t in cfg["groups"].get("memory_us", []) or t in lev
                sev = "low" if t in fx else ("high" if (w in (50, 200) and core) else "medium")
                add("sma_cross", t, f"終値がSMA{w}を{'上抜け' if a == 'above' else '下抜け'}（終値 {n['close']:.2f}、SMA{w} {n[f'sma{w}']:.2f}）",
                    sev, round(float(n[f"dist_sma{w}"]), 2))
        # RSI
        r, rp = n["rsi14"], p["rsi14"]
        if pd.notna(r) and pd.notna(rp):
            for lvl in (30, 70):
                if (rp < lvl <= r) or (rp >= lvl > r):
                    add("rsi", t, f"RSI14が{lvl}を{'上抜け' if r >= lvl else '下抜け'}（{rp:.1f}→{r:.1f}）", "medium", round(float(r), 1))
            if r < 25 or r > 75:
                add("rsi", t, f"RSI14が極端な水準（{r:.1f}）", "medium", round(float(r), 1))
        # new high / low
        if t not in fx:
            for w in (60, 20):  # 60日が出たら20日は出さない
                hi_hit = pd.notna(n[f"high{w}"]) and n["close"] >= n[f"high{w}"] * 0.999 and n["close"] > p["close"]
                lo_hit = pd.notna(n[f"low{w}"]) and n["close"] <= n[f"low{w}"] * 1.001 and n["close"] < p["close"]
                if hi_hit:
                    add("new_high_low", t, f"{w}日高値を更新（{n['close']:.2f}）", "medium", round(float(n["close"]), 2))
                if lo_hit:
                    add("new_high_low", t, f"{w}日安値を更新（{n['close']:.2f}）", "high" if w == 60 else "medium", round(float(n["close"]), 2))
                if hi_hit or lo_hit:
                    break
            if pd.notna(n["high_close"]) and n["close"] >= n["high_close"] * 0.999 and n["high_window"] >= 200:
                add("new_high_low", t, f"52週終値高値を更新（{n['close']:.2f}）", "high", round(float(n["close"]), 2))
        # big move
        mv = n["ret_1d"]
        if pd.notna(mv):
            cap = thr["big_move_leveraged"] if t in lev else thr["big_move_fx"] if t in fx else thr["big_move_index"] if t in INDEX_LIKE else thr["big_move_stock"]
            if abs(mv) >= cap:
                add("big_move", t, f"1日で{mv:+.2f}%", "high" if abs(mv) >= cap * 1.5 else "medium", round(float(mv), 2))
        # volume
        if pd.notna(n["vol_ratio20"]) and n["vol_ratio20"] >= thr["volume_ratio"] and pd.notna(mv) and abs(mv) >= thr["volume_min_move"]:
            add("volume", t, f"出来高が20日平均の{n['vol_ratio20']:.2f}倍で{'上昇' if mv > 0 else '下落'}（{mv:+.2f}%）",
                "high" if mv < 0 else "medium", round(float(n["vol_ratio20"]), 2))
        # drawdown thresholds
        for d in thr["dd_thresholds"]:
            if pd.notna(n["dd_from_high"]) and pd.notna(p["dd_from_high"]) and (p["dd_from_high"] > d >= n["dd_from_high"] or p["dd_from_high"] <= d < n["dd_from_high"]):
                add("drawdown", t, f"高値からの下落率が{d}%を{'下回った' if n['dd_from_high'] <= d else '回復した'}（{n['dd_from_high']:.1f}%）", "medium", round(float(n["dd_from_high"]), 1))

    # breadth
    for k in cfg["breadth_sets"]:
        bn, bp = now["breadth"][k]["above_sma50"].get("pct"), prev["breadth"][k]["above_sma50"].get("pct")
        if bn is not None and bp is not None and abs(bn - bp) >= thr["breadth_shift_pt"]:
            add("breadth", k, f"SMA50上の比率が{bp:.0f}%→{bn:.0f}%", "medium", round(bn - bp, 1))

    # levels / scores
    for k, v in now["levels"].items():
        a, b = v["level"], prev["levels"].get(k, {}).get("level")
        if a is not None and b is not None and a != b:
            add("level_change", k, f"{k}（{v.get('name', cfg['levels'][k]['name'])}）の段階 {b:+d}→{a:+d}", "high" if abs(a - b) >= 2 else "medium", a)
    for k in ("S", "D"):
        a, b = now["scores"][k]["score"], prev["scores"][k]["score"]
        if a is not None and b is not None and abs(a - b) >= thr["score_shift"]:
            add("level_change", f"{k}_score", f"{k}スコア {b:.1f}→{a:.1f}", "medium", round(a - b, 1))

    # ADR
    for an in now["adr_sum"]:
        if an.get("status") != "ok":
            continue
        ap_ = next((x for x in prev["adr_sum"] if x.get("ads") == an["ads"] and x.get("status") == "ok"), None)
        if ap_ and abs(an["premium_pct"] - ap_["premium_pct"]) >= thr["adr_premium_shift"]:
            add("adr_premium", an["ads"], f"ADRプレミアム {ap_['premium_pct']:.1f}%→{an['premium_pct']:.1f}%", "high", round(an["premium_pct"] - ap_["premium_pct"], 1))
        if abs(an["premium_pct"] - an["premium_avg20"]) > thr["adr_gap"]:
            add("adr_premium", an["ads"], f"プレミアムが20日平均から{an['premium_pct'] - an['premium_avg20']:+.1f}pt乖離（{an['premium_pct']:.1f}% vs {an['premium_avg20']:.1f}%）", "medium", round(an["premium_pct"] - an["premium_avg20"], 1))

    # v6.1: セクター内区分・調整耐性の変化点（判断はしない）
    rn, rp = now.get("resilience") or {}, prev.get("resilience") or {}
    cn, cp = (rn.get("sector_rs") or {}).get("classes", {}), (rp.get("sector_rs") or {}).get("classes", {})
    for t, c_now in cn.items():
        c_prev = cp.get(t)
        if c_now and c_prev and {c_now, c_prev} == {"leader", "laggard"}:
            add("sector_rs_flip", t, f"セクター内区分（対SOXX）が {c_prev}→{c_now}", "medium", c_now)
    rows_n = {x["ticker"]: x for x in rn.get("rows", [])}
    rows_p = {x["ticker"]: x for x in rp.get("rows", [])}
    for t, x in rows_n.items():
        y = rows_p.get(t, {})
        if x.get("tier") and not y.get("tier"):
            add("next_candidate_new", t, f"調整耐性の次の候補に入った（{x['tier']}：{x.get('held_class')}×{x.get('rebound_class')}、R_held {x.get('r_held')}、R_now {x.get('r_now')}）",
                "medium", x["tier"])
        if y.get("tier") and not x.get("tier"):
            add("next_candidate_out", t, f"調整耐性の次の候補から外れた（{y['tier']}→なし：{x.get('held_class')}×{x.get('rebound_class')}、R_now {x.get('r_now')}、高値から {x.get('own_dd_now_pct')}%）",
                "medium", x.get("r_now"))
        if x.get("late_break") and not y.get("late_break"):
            add("late_break_new", t, f"後崩れ：下げには耐えた（R_held {x.get('r_held')}）が戻りで遅れ（R_now {x.get('r_now')}、高値から {x.get('own_dd_now_pct')}%）", "high", x.get("r_now"))
    wn, wp = rn.get("window") or {}, rp.get("window") or {}
    if wn and wp and wn.get("state") != wp.get("state"):
        add("corr_state_change", wn.get("bench", "SOXX"),
            f"調整窓の状態が {wp.get('state')}→{wn.get('state')}（高値 {wn.get('high_date')}、安値 {wn.get('low_date')}、dd_low {wn.get('dd_low_pct')}%、dd_now {wn.get('dd_now_pct')}%）",
            "high", wn.get("state"))

    # VIX
    v, vp = row_of(S, "^VIX"), row_of(P, "^VIX")
    if v is not None:
        if v["close"] > thr["vix_level"]:
            add("vix", "^VIX", f"VIXが{thr['vix_level']}超（{v['close']:.1f}）", "high", round(float(v["close"]), 1))
        if pd.notna(v["ret_1d"]) and v["ret_1d"] >= thr["vix_spike_pct"]:
            add("vix", "^VIX", f"VIXが1日で{v['ret_1d']:+.1f}%", "high", round(float(v["ret_1d"]), 1))

    # FX
    for t in ("KRW=X", "USDJPY=X"):
        n = row_of(S, t)
        if n is not None and pd.notna(n["ret_1d"]) and abs(n["ret_1d"]) >= thr["fx_move"]:
            add("fx", t, f"1日で{n['ret_1d']:+.2f}%", "medium", round(float(n["ret_1d"]), 2))
    return sig


def rates_signal(macro, thr):
    out = []
    d = macro.get("latest", {}).get("DFII10")
    if d and d.get("chg_5obs") is not None and abs(d["chg_5obs"]) * 100 >= thr["real_rate_5d_bp"]:
        out.append({"type": "rates", "ticker": "DFII10", "detail": f"10年実質金利が5営業日で{d['chg_5obs']*100:+.0f}bp（{d['value']:.2f}%、{d['date']}）",
                    "severity": "high", "value": round(d["chg_5obs"] * 100)})
    return out


def table_rows(snap, tickers):
    cols = ["close", "ret_1d", "ret_1w", "ret_1m", "dist_sma20", "dist_sma50", "dist_sma200", "sma50_slope", "rsi14", "vol_ratio20",
            "updown_vol_ratio10", "dd_from_high", "rv20", "rs_spy_20", "rs_soxx_20", "low20", "high20", "low60", "high60", "last_date"]
    rows = []
    for t in tickers:
        r = row_of(snap, t)
        if r is None:
            continue
        rows.append({"ticker": t, **{c: (None if pd.isna(r[c]) else (r[c] if isinstance(r[c], str) else round(float(r[c]), 3))) for c in cols if c in r}})
    return rows


def watch_levels(snap):
    """翌営業日に意識される水準：主要銘柄のSMAと直近高安、そこまでの距離。"""
    out = {}
    for t in ("^SOX", "SOXX", "SMH", "SOXL", "DRAM", "MU", "SNDK", "SKHY", "NVDA", "TSM"):
        r = row_of(snap, t)
        if r is None:
            continue
        out[t] = {"close": round(float(r["close"]), 2),
                  **{f"sma{w}": (None if pd.isna(r[f"sma{w}"]) else round(float(r[f"sma{w}"]), 2)) for w in (20, 50, 200)},
                  **{f"dist_sma{w}": (None if pd.isna(r[f"dist_sma{w}"]) else round(float(r[f"dist_sma{w}"]), 2)) for w in (20, 50, 200)},
                  "low20": None if pd.isna(r["low20"]) else round(float(r["low20"]), 2), "high20": None if pd.isna(r["high20"]) else round(float(r["high20"]), 2),
                  "low60": None if pd.isna(r["low60"]) else round(float(r["low60"]), 2), "high60": None if pd.isna(r["high60"]) else round(float(r["high60"]), 2),
                  **{f"dist_{k}": (None if pd.isna(r[k]) else round((float(r[k]) / float(r["close"]) - 1) * 100, 2)) for k in ("low20", "high20", "low60", "high60")},
                  "rsi14": None if pd.isna(r["rsi14"]) else round(float(r["rsi14"]), 1),
                  "dd_from_high": None if pd.isna(r["dd_from_high"]) else round(float(r["dd_from_high"]), 1)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    ap.add_argument("--config", default="config.json")
    a = ap.parse_args()
    with open(a.config, encoding="utf-8") as f:
        cfg = json.load(f)
    thr = {**DEFAULT_THR, **cfg.get("daily_signals", {})}

    ppath = os.path.join(a.out, "prices_daily.csv.gz")
    if not os.path.exists(ppath):
        print("prices_daily.csv.gz がありません。", file=sys.stderr)
        sys.exit(1)
    px = bs.load_prices(ppath)
    now = bs.compute_all(px, cfg)
    us_asof = now["us_asof"]
    # 前営業日：us_asof の足を全銘柄から外して再計算（アジア株・為替は us_asof 以降の足を外す）
    px_prev = px[px["date"] < us_asof]
    prev = bs.compute_all(px_prev, cfg)

    tickers = list(dict.fromkeys(cfg["groups"]["market"] + cfg["groups"]["rates_fx"] + cfg["groups"]["memory_us"] + cfg["groups"]["memory_asia"]
                                 + cfg["groups"]["ai_logic"] + cfg["groups"]["equipment"] + cfg["groups"]["hyperscalers"]))
    sig = detect(now, prev, cfg, thr, tickers)
    macro = bs.macro_summary(a.out)
    sig += rates_signal(macro, thr)
    try:
        rsl, rs_sig = rs_lines(px, cfg, thr, us_asof)
    except Exception as e:  # RS線の失敗で日次シグナル全体を止めない
        rsl, rs_sig = {"status": "error", "note": f"{type(e).__name__}: {e}"}, []
    sig += rs_sig
    order = {"high": 0, "medium": 1, "low": 2}
    sig = [x for x in sig if x["severity"] != "low" or x["type"] != "sma_cross" or x["ticker"] in ("KRW=X",)]  # 為替のSMAクロスはUSD/KRWだけ残す
    sig.sort(key=lambda s: (order.get(s["severity"], 9), s["type"], s["ticker"]))

    nowt = datetime.now(timezone.utc)
    out = {
        "generated_utc": nowt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_jst": nowt.astimezone(JST).strftime("%Y-%m-%d %H:%M JST"),
        "us_as_of": us_asof.strftime("%Y-%m-%d"),
        "prev_as_of": prev["us_asof"].strftime("%Y-%m-%d"),
        "signal_count": {"high": sum(s["severity"] == "high" for s in sig), "medium": sum(s["severity"] == "medium" for s in sig)},
        "signals": sig,
        "levels_now": {k: v["level"] for k, v in now["levels"].items()},
        "levels_prev": {k: v["level"] for k, v in prev["levels"].items()},
        "scores_now": {k: now["scores"][k]["score"] for k in ("S", "D")} | {"TECHNICAL": now["scores"]["TECHNICAL"]},
        "scores_prev": {k: prev["scores"][k]["score"] for k in ("S", "D")} | {"TECHNICAL": prev["scores"]["TECHNICAL"]},
        "breadth_now": {k: v["above_sma50"].get("pct") for k, v in now["breadth"].items()},
        "breadth_prev": {k: v["above_sma50"].get("pct") for k, v in prev["breadth"].items()},
        "table": table_rows(now["snap"], cfg["groups"]["market"] + cfg["groups"]["rates_fx"] + cfg["groups"]["memory_us"] + cfg["groups"]["memory_asia"] + ["NVDA", "TSM", "AMD", "AVGO", "ASML", "AMAT", "LRCX", "KLAC"]),
        "watch_levels": watch_levels(now["snap"]),
        "rs_lines": rsl,
        "adr": [{k: x.get(k) for k in ("ads", "date", "premium_pct", "premium_avg20", "ads_ret_1w", "local_ret_1w", "ratio_or_data_suspect")} for x in now["adr_sum"] if x.get("status") == "ok"],
        "macro": macro.get("latest", {}),
        "flags": now["flags"],
        "thresholds": thr,
        # v6.1: セクター内の強弱と調整耐性（resilience.json の要約。判断はしない）
        "sector_rs": {k: now["resilience"]["sector_rs"].get(k) for k in ("bench", "counts", "leaders", "laggards")}
        | {"leaders_top5": now["resilience"]["sector_rs"]["leaders"][:5], "laggards_bottom5": now["resilience"]["sector_rs"]["laggards"][:5]},
        "resilience": {"window": now["resilience"]["window"], "held_ratio": now["resilience"]["held_ratio"],
                       "next_candidates": now["resilience"]["next_candidates"][:8], "late_breaks": now["resilience"]["late_breaks"],
                       "note": now["resilience"]["note"]},
    }
    bs.write_atomic(out, os.path.join(a.out, "daily_signals.json"))
    print(json.dumps({"us_as_of": out["us_as_of"], "prev_as_of": out["prev_as_of"], "signal_count": out["signal_count"],
                      "signals": [f"[{s['severity']}] {s['ticker']}: {s['detail']}" for s in sig]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
