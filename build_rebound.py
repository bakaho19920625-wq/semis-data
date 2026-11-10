"""
戻りの質（rebound_quality.json）を計算する（GitHub Actions で build_health.py の後に実行。build_signals.py とは独立）

大きく下げた後の上げが「売りすぎた人の買い戻し中心」なのか「新しい買いが入っている」のかを、値動きと売買代金から描写する。
判断はしない。売買の合図ではない。定義と読み方、検証の結果（この指標だけでは先の上げ下げを分けられなかった）は docs/rebound_quality.md。

出力 rebound_quality.json
  context     基準の指数（SOXX）が高値から何%下か、調整局面か（−10%以下）、直近の投げ売りの日（直近10営業日で最も下げた日。−4%以下のときだけ）
  indexes     S&P500・QQQ（ナスダック100）・SOX：前日比、売買代金の比（5日平均・50日平均・投げ売りの日）、高値からの下げ幅のうち何%戻したか
              S&P500 と SOX は指数に出来高がないので、売買代金は SPY・SOXX で代用する（volume_ticker に明記）
  semis       半導体約40銘柄：上げ・下げの数、普段より少ない売買代金で上げた数、1.5倍以上で上げた数、合計の売買代金の比、
              売買代金が最大の1銘柄を除いた比、売られた銘柄ほど上げたか（直前20日の騰落率と今日の騰落率の順位相関、下位・上位3分の1の平均）
  memory_us   米国のメモリー5銘柄：同じ項目（銘柄ごとの値つき）
  names       主要銘柄ごとの前日比と売買代金の比
  leveraged   レバレッジETFの過熱：SOXL・SOXS の売買代金と手元の期間での順位、（SOXL＋SOXS）÷SOXX
  summary_ja  レポートにそのまま転記できる文（描写だけ。予測の言葉は入れない）

売買代金＝終値×出来高（close は分割調整済み・配当非調整。build_snapshot.py と同じ）。「普段」は直前50営業日の平均（当日を含めない）。
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

import build_snapshot as bs

REBOUND_VERSION = "1.0"
JST = timezone(timedelta(hours=9))
DEFAULT = {
    "index": "SOXX", "universe": "semis_broad", "memory_group": "memory_us",
    "high_bars": 252, "correction_pct": -10,                       # 高値は直近252営業日の終値、調整局面は高値から−10%以下
    "selloff": {"lookback": 10, "min_drop_pct": -4},               # 投げ売りの日：直近10営業日（当日を除く）で基準の指数が最も下げた日。−4%以下のときだけ
    "avg_short": 5, "avg_long": 50, "prior_bars": 20,
    "thin_lt": 1.0, "heavy_ge": 1.5,                               # 普段（50日平均）より少ない／1.5倍以上
    "volume_words": {"low_lt": 0.8, "high_gt": 1.2},               # 50日平均比の言葉：少ない／普段並み／多い
    "lead_corr": 0.3,                                              # 順位相関がこれ以下（マイナス）なら「売られた銘柄ほど上げた」
    "indexes": [{"name": "S&P500", "price": "^GSPC", "volume": "SPY"},
                {"name": "QQQ（ナスダック100）", "price": "QQQ", "volume": "QQQ"},
                {"name": "SOX", "price": "^SOX", "volume": "SOXX"}],
    "key_names": ["NVDA", "AMD", "AVGO", "TSM", "MU", "SNDK", "SKHY", "WDC", "STX"],
    "leveraged": {"bull": "SOXL", "bear": "SOXS", "base": "SOXX"},
}
READING = ("描写であり予測ではない。手元の約3年（高値から10%以上下げた局面で1日+4%以上上げた18回）では、売買代金の比や"
           "「売られた銘柄ほど上げた」の強さだけで、その後の上げ下げは分けられなかった（docs/rebound_quality.md）。"
           "底の局面（売られ尽くした後の経過）は sector_health.json の washout.phase を見る")


def _r(x, nd=2):
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if (np.isnan(x) or np.isinf(x)) else round(x, nd)


def matrices(px, us_asof):
    """終値と売買代金（終値×出来高）の表。米国の取引日（SPYのある日）だけ、us_asof まで。"""
    px = px[px["date"] <= us_asof]
    C = px.pivot(index="date", columns="ticker", values="close").sort_index().astype(float)
    V = px.pivot(index="date", columns="ticker", values="volume").sort_index().astype(float)
    if "SPY" in C:
        keep = C["SPY"].notna()
        C, V = C[keep], V[keep]
    return C, C * V


def ratio_to_avg(s, n):
    """当日の値 ÷ 直前 n 営業日の平均（当日を含めない）。足りなければ None。"""
    s = s.dropna()
    if len(s) < n + 1 or s.iloc[-1] <= 0:
        return None
    base = s.iloc[-1 - n:-1].mean()
    return None if not base or base <= 0 else float(s.iloc[-1] / base)


def retrace(c, bars):
    """高値（直近 bars 本の終値の最大）→ その後の安値 → いま。下げ幅のうち何%戻したか。"""
    c = c.dropna()
    if len(c) < 30:
        return {"high": None, "high_date": None, "low": None, "low_date": None, "dd_low_pct": None, "dd_now_pct": None, "retrace_pct": None}
    w = c.iloc[-bars:]
    ih = w.idxmax()
    after = w.loc[ih:]
    il = after.idxmin()
    hi, lo, now = float(w.loc[ih]), float(after.loc[il]), float(c.iloc[-1])
    rt = None if hi <= lo else (now - lo) / (hi - lo) * 100
    return {"high": _r(hi), "high_date": ih.strftime("%Y-%m-%d"), "low": _r(lo), "low_date": il.strftime("%Y-%m-%d"),
            "dd_low_pct": _r((lo / hi - 1) * 100, 1), "dd_now_pct": _r((now / hi - 1) * 100, 1), "retrace_pct": _r(rt, 1)}


def volume_word(x, p):
    if x is None:
        return None
    return "少ない" if x < p["low_lt"] else ("多い" if x > p["high_gt"] else "普段並み")


def group_stats(C, DV, names, p, with_rows=False):
    """銘柄の集まりについて、上げ下げの数・売買代金の比・売られた銘柄ほど上げたか。"""
    cols = [t for t in names if t in C.columns and C[t].notna().iloc[-1] and C[t].notna().iloc[-2]]
    if len(cols) < 3:
        return {"n": len(cols), "status": "insufficient"}
    ret = (C[cols].iloc[-1] / C[cols].iloc[-2] - 1) * 100
    r50 = pd.Series({t: ratio_to_avg(DV[t], p["avg_long"]) for t in cols}, dtype=float)
    r5 = pd.Series({t: ratio_to_avg(DV[t], p["avg_short"]) for t in cols}, dtype=float)
    up, down = ret > 0, ret < 0
    tot = DV[cols].sum(axis=1, min_count=1)
    today = DV[cols].iloc[-1].dropna()
    top = today.idxmax() if not today.empty else None
    ex = DV[[t for t in cols if t != top]].sum(axis=1, min_count=1) if top else tot
    out = {
        "n": len(cols), "status": "ok",
        "up": int(up.sum()), "down": int(down.sum()), "avg_ret_pct": _r(ret.mean()), "median_ret_pct": _r(ret.median()),
        "up_on_thin": int((up & (r50 < p["thin_lt"])).sum()), "up_on_heavy": int((up & (r50 >= p["heavy_ge"])).sum()),
        "down_on_thin": int((down & (r50 < p["thin_lt"])).sum()), "down_on_heavy": int((down & (r50 >= p["heavy_ge"])).sum()),
        "median_dv_vs_50d": _r(r50.median()), "median_dv_vs_5d": _r(r5.median()),
        "agg_dv_vs_5d": _r(ratio_to_avg(tot, p["avg_short"])), "agg_dv_vs_50d": _r(ratio_to_avg(tot, p["avg_long"])),
        "top_dv_ticker": top,
        "top_dv_share_pct": _r(today[top] / today.sum() * 100, 1) if top else None,
        "agg_ex_top_dv_vs_5d": _r(ratio_to_avg(ex, p["avg_short"])), "agg_ex_top_dv_vs_50d": _r(ratio_to_avg(ex, p["avg_long"])),
    }
    # 売られた銘柄ほど上げたか：直前 prior_bars 営業日（前日まで）の騰落率と、今日の騰落率
    n = p["prior_bars"]
    lead = {"prior_bars": n, "rank_corr": None, "worst_third_avg_ret_pct": None, "best_third_avg_ret_pct": None, "word": None, "n": 0}
    if len(C) > n + 2:
        prior = (C[cols].iloc[-2] / C[cols].iloc[-2 - n] - 1) * 100
        m = prior.notna() & ret.notna()
        k = int(m.sum())
        lead["n"] = k
        if k >= 9:
            a, b = prior[m], ret[m]
            corr = a.rank().corr(b.rank())
            order = a.sort_values()
            third = k // 3
            lead.update({"rank_corr": _r(corr), "worst_third_avg_ret_pct": _r(b[order.index[:third]].mean()),
                         "best_third_avg_ret_pct": _r(b[order.index[-third:]].mean())})
            if corr is not None and not np.isnan(corr):
                lead["word"] = ("売られた銘柄ほど上げた" if corr <= -p["lead_corr"] and ret.mean() > 0 else
                                "強かった銘柄ほど上げた" if corr >= p["lead_corr"] and ret.mean() > 0 else
                                "売られていた銘柄ほど下げた" if corr >= p["lead_corr"] and ret.mean() < 0 else
                                "強かった銘柄ほど下げた" if corr <= -p["lead_corr"] and ret.mean() < 0 else "偏りなし")
    out["laggard_lead"] = lead
    if with_rows:
        out["rows"] = [{"ticker": t, "ret_1d_pct": _r(ret[t]), "dv_vs_50d": _r(r50[t]), "dv_vs_5d": _r(r5[t])} for t in cols]
    return out


def compute(px, cfg, us_asof):
    p = {**DEFAULT, **(cfg.get("rebound") or {})}
    C, DV = matrices(px, us_asof)
    if C.empty or len(C) < 60:
        return {"version": REBOUND_VERSION, "status": "insufficient_history", "us_as_of": us_asof.strftime("%Y-%m-%d")}
    idx_t = p["index"]
    if idx_t not in C or C[idx_t].dropna().empty:
        return {"version": REBOUND_VERSION, "status": "index_missing", "us_as_of": us_asof.strftime("%Y-%m-%d")}
    today, prev = C.index[-1], C.index[-2]

    # ---- 文脈：調整局面か、直近の投げ売りの日 ----
    rt_idx = retrace(C[idx_t], p["high_bars"])
    in_corr = rt_idx["dd_now_pct"] is not None and rt_idx["dd_now_pct"] <= p["correction_pct"]
    r_idx = C[idx_t].pct_change() * 100
    look = r_idx.iloc[-1 - p["selloff"]["lookback"]:-1].dropna()
    selloff = None
    if not look.empty and look.min() <= p["selloff"]["min_drop_pct"]:
        d = look.idxmin()
        selloff = {"date": d.strftime("%Y-%m-%d"), "index_ret_pct": _r(look.min()),
                   "bars_ago": int(len(C) - 1 - C.index.get_loc(d)),
                   "rule": f"直近{p['selloff']['lookback']}営業日で{idx_t}が最も下げた日（{p['selloff']['min_drop_pct']}%以下のときだけ）"}
    sd = pd.Timestamp(selloff["date"]) if selloff else None

    def vs_selloff(s):
        if sd is None or sd not in s.index or pd.isna(s.loc[sd]) or pd.isna(s.iloc[-1]) or s.loc[sd] <= 0:
            return None
        return float(s.iloc[-1] / s.loc[sd])

    # ---- 指数 ----
    indexes = []
    for it in p["indexes"]:
        pt, vt = it["price"], it["volume"]
        if pt not in C or C[pt].dropna().shape[0] < 30 or pd.isna(C[pt].iloc[-1]):
            indexes.append({"name": it["name"], "price_ticker": pt, "volume_ticker": vt, "status": "missing"})
            continue
        c = C[pt]
        dv = DV[vt] if vt in DV else pd.Series(dtype=float)
        r50, r5 = ratio_to_avg(dv, p["avg_long"]), ratio_to_avg(dv, p["avg_short"])
        row = {"name": it["name"], "price_ticker": pt, "volume_ticker": vt, "status": "ok",
               "close": _r(c.iloc[-1]), "ret_1d_pct": _r((c.iloc[-1] / c.iloc[-2] - 1) * 100),
               "ret_5d_pct": _r((c.iloc[-1] / c.iloc[-6] - 1) * 100) if len(c.dropna()) > 6 else None,
               "dv_vs_5d": _r(r5), "dv_vs_50d": _r(r50), "dv_vs_selloff_day": _r(vs_selloff(dv)),
               "volume_word": volume_word(r50, p["volume_words"])}
        row.update({k: v for k, v in retrace(c, p["high_bars"]).items() if k in ("high_date", "low_date", "dd_low_pct", "dd_now_pct", "retrace_pct")})
        indexes.append(row)

    # ---- 半導体・メモリー ----
    semis = group_stats(C, DV, cfg["breadth_sets"].get(p["universe"], []), p)
    mem = group_stats(C, DV, cfg["groups"].get(p["memory_group"], []), p, with_rows=True)
    for g, members in ((semis, cfg["breadth_sets"].get(p["universe"], [])), (mem, cfg["groups"].get(p["memory_group"], []))):
        if g.get("status") == "ok":
            tot = DV[[t for t in members if t in DV]].sum(axis=1, min_count=1)
            g["agg_dv_vs_selloff_day"] = _r(vs_selloff(tot))
    names = []
    for t in p["key_names"]:
        if t in C and not pd.isna(C[t].iloc[-1]) and not pd.isna(C[t].iloc[-2]):
            names.append({"ticker": t, "ret_1d_pct": _r((C[t].iloc[-1] / C[t].iloc[-2] - 1) * 100),
                          "dv_vs_50d": _r(ratio_to_avg(DV[t], p["avg_long"])), "dv_vs_5d": _r(ratio_to_avg(DV[t], p["avg_short"])),
                          "dv_vs_selloff_day": _r(vs_selloff(DV[t]))})

    # ---- レバレッジETFの過熱 ----
    lv, lev = p["leveraged"], {}
    for key in ("bull", "bear"):
        t = lv[key]
        if t in DV and DV[t].dropna().shape[0] > 0 and not pd.isna(DV[t].iloc[-1]):
            s = DV[t].dropna()
            lev[t] = {"dv_usd_bn": _r(s.iloc[-1] / 1e9), "ret_1d_pct": _r((C[t].iloc[-1] / C[t].iloc[-2] - 1) * 100),
                      "dv_vs_50d": _r(ratio_to_avg(s, p["avg_long"])),
                      "rank_in_history": int((s > s.iloc[-1]).sum() + 1), "history_days": int(len(s)),
                      "record_date": s.idxmax().strftime("%Y-%m-%d"), "record_usd_bn": _r(s.max() / 1e9)}
        else:
            lev[t] = {"status": "missing", "note": "まだ取得されていない（tickers.txt に追加後、次の自動更新で入る）"}
    comb = None
    if all(t in DV for t in (lv["bull"], lv["bear"], lv["base"])):
        part = (DV[lv["bull"]] + DV[lv["bear"]]) / DV[lv["base"]]
        part = part.replace([np.inf, -np.inf], np.nan).dropna()
        if len(part) > 60 and part.index[-1] == today:
            comb = {"ratio": _r(part.iloc[-1]), "avg_50d": _r(part.iloc[-51:-1].mean()),
                    "percentile_in_history": _r((part < part.iloc[-1]).mean() * 100, 0), "history_days": int(len(part)),
                    "meaning": f"（{lv['bull']}＋{lv['bear']}）の売買代金 ÷ {lv['base']} の売買代金。高いほど短期の値幅取りが多い"}
    lev["combined_vs_base"] = comb

    # ---- 転記用の文（描写だけ） ----
    ok_idx = [x for x in indexes if x.get("status") == "ok"]
    md = pd.Timestamp(selloff["date"]).strftime("%-m/%-d") if selloff else None

    def f(x, suffix="倍"):
        return "N/A" if x is None else f"{x:.2f}{suffix}"

    lines = []
    if ok_idx:
        lines.append("指数：" + "、".join(
            f"{x['name']} {x['ret_1d_pct']:+.2f}%（売買代金は普段の{f(x['dv_vs_50d'])}＝{x['volume_word'] or 'N/A'}、5日平均の{f(x['dv_vs_5d'])}）" for x in ok_idx)
            + "。S&P500とSOXの売買代金はSPY・SOXXで代用")
        if selloff:
            lines.append(f"投げ売りの日（{md}、{idx_t} {selloff['index_ret_pct']:+.1f}%）と比べた売買代金：" + "、".join(f"{x['name']} {f(x['dv_vs_selloff_day'])}" for x in ok_idx)
                         + (f"、半導体の合計 {f(semis.get('agg_dv_vs_selloff_day'))}" if semis.get("status") == "ok" else ""))
        lines.append("高値からの下げ幅のうち戻した割合：" + "、".join(
            f"{x['name']} {'N/A' if x['retrace_pct'] is None else str(x['retrace_pct']) + '%'}（高値から{x['dd_now_pct']:+.1f}%）" for x in ok_idx if x.get("dd_now_pct") is not None))
    if semis.get("status") == "ok":
        s = semis
        side = (f"上げた銘柄のうち、普段より少ない売買代金は{s['up_on_thin']}、1.5倍以上は{s['up_on_heavy']}" if s["up"] >= s["down"] else
                f"下げた銘柄のうち、売買代金が1.5倍以上は{s['down_on_heavy']}、普段より少ないのは{s['down_on_thin']}")
        lines.append(f"半導体{s['n']}銘柄：上げ{s['up']}・下げ{s['down']}（平均{s['avg_ret_pct']:+.1f}%）。{side}。"
                     f"合計の売買代金は5日平均の{f(s['agg_dv_vs_5d'])}"
                     + (f"、うち{s['top_dv_ticker']}が{s['top_dv_share_pct']}%を占め、除くと{f(s['agg_ex_top_dv_vs_5d'])}" if s.get("top_dv_ticker") else ""))
        ll = s["laggard_lead"]
        if ll.get("word"):
            tail = "（買い戻しが中心の日に出やすい形。これだけで先の上げ下げは分からない）" if ll["word"] == "売られた銘柄ほど上げた" else ""
            lines.append(f"主役：{ll['word']}（直前{ll['prior_bars']}日の騰落率が下位3分の1の銘柄は今日平均{ll['worst_third_avg_ret_pct']:+.1f}%、上位3分の1は{ll['best_third_avg_ret_pct']:+.1f}%、順位相関{ll['rank_corr']:+.2f}）{tail}")
    if mem.get("status") == "ok":
        lines.append("メモリー（米国5銘柄）：" + "、".join(f"{r['ticker']} {r['ret_1d_pct']:+.1f}%（普段の{f(r['dv_vs_50d'])}）" for r in mem["rows"]))
    lb = [f"{t} 売買代金 約{v['dv_usd_bn'] * 10:.0f}億ドル（普段の{f(v['dv_vs_50d'])}、手元の{v['history_days']}日で{v['rank_in_history']}番目）"
          for t, v in lev.items() if isinstance(v, dict) and v.get("dv_usd_bn") is not None]
    if lb:
        lines.append("レバレッジETF：" + "、".join(lb) + (f"。（{lv['bull']}＋{lv['bear']}）÷{lv['base']} は{comb['ratio']}（50日平均{comb['avg_50d']}、手元の期間で下から{comb['percentile_in_history']:.0f}%の位置）" if comb else ""))

    return {
        "version": REBOUND_VERSION, "status": "ok",
        "us_as_of": today.strftime("%Y-%m-%d"), "prev_date": prev.strftime("%Y-%m-%d"),
        "context": {"index": idx_t, "dd_from_high_pct": rt_idx["dd_now_pct"], "dd_low_pct": rt_idx["dd_low_pct"], "high_date": rt_idx["high_date"], "low_date": rt_idx["low_date"],
                    "in_correction": bool(in_corr), "correction_rule": f"{idx_t}が直近{p['high_bars']}営業日の高値（終値）から{p['correction_pct']}%以下", "selloff_day": selloff},
        "indexes": indexes, "semis": semis, "memory_us": mem, "names": names, "leveraged": lev,
        "summary_ja": lines, "reading": READING,
        "definitions": {"dv": "売買代金＝終値×出来高", "dv_vs_50d": "当日の売買代金÷直前50営業日の平均（普段の何倍か）", "dv_vs_5d": "同÷直前5営業日の平均",
                        "dv_vs_selloff_day": "同÷投げ売りの日の売買代金", "retrace_pct": "高値→その後の安値の下げ幅のうち、いままでに戻した割合（終値）",
                        "thin": f"普段の{p['thin_lt']}倍未満", "heavy": f"普段の{p['heavy_ge']}倍以上",
                        "volume_word": f"50日平均比 {p['volume_words']['low_lt']}未満＝少ない、{p['volume_words']['high_gt']}超＝多い、その間＝普段並み"},
    }


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
    q = compute(px, cfg, us_asof)
    nowt = datetime.now(timezone.utc)
    q["generated_utc"] = nowt.strftime("%Y-%m-%dT%H:%M:%SZ")
    q["generated_jst"] = nowt.astimezone(JST).strftime("%Y-%m-%d %H:%M JST")
    bs.write_atomic(q, os.path.join(a.out, "rebound_quality.json"))
    if q.get("status") == "ok":
        by = {x["name"]: x for x in q["indexes"] if x.get("status") == "ok"}
        s = q["semis"] if q["semis"].get("status") == "ok" else {}
        row = {"us_as_of": q["us_as_of"], "in_correction": q["context"]["in_correction"], "index_dd_pct": q["context"]["dd_from_high_pct"]}
        for key, name in (("sp500", "S&P500"), ("qqq", "QQQ（ナスダック100）"), ("sox", "SOX")):
            x = by.get(name, {})
            row.update({f"{key}_ret": x.get("ret_1d_pct"), f"{key}_dv50": x.get("dv_vs_50d"), f"{key}_dv5": x.get("dv_vs_5d"), f"{key}_retrace": x.get("retrace_pct")})
        row.update({"semis_up": s.get("up"), "semis_n": s.get("n"), "semis_up_on_thin": s.get("up_on_thin"), "semis_up_on_heavy": s.get("up_on_heavy"),
                    "semis_agg_dv5": s.get("agg_dv_vs_5d"), "semis_lead_corr": (s.get("laggard_lead") or {}).get("rank_corr")})
        bs.append_history(os.path.join(a.out, "history_rebound.csv"), [row], ["us_as_of"])
        print(json.dumps({"us_as_of": q["us_as_of"], "in_correction": q["context"]["in_correction"], "selloff_day": (q["context"]["selloff_day"] or {}).get("date"),
                          "summary": q["summary_ja"]}, ensure_ascii=False, indent=1))
    else:
        print(json.dumps(q, ensure_ascii=False))


if __name__ == "__main__":
    main()
