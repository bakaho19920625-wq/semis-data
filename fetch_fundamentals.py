"""
監視銘柄の四半期実績（売上・売上原価・在庫・設備投資・営業CF）を機械的に取る（GitHub Actions で毎日実行）。

取得元は2系統（--source auto が既定）:
  sec   : SEC EDGAR の公式API（XBRL companyconcept・提出一覧 submissions）。米国で 10-Q/10-K を出す会社。階層1・確認済み。
          最新の決算リリース（8-K Ex.99.1）・10-Q/10-K のURLも取る。名乗り User-Agent を付け、毎秒10回未満で呼ぶ。
          ※ GitHub Actions（クラウドのIP）からは 403「Undeclared Automated Tool」で拒否される（2026-11-02 確認。名乗りを変えても同じ）。
            到達できる環境（自前のVM等）で動かすときに使う。
  yahoo : Yahoo Finance の四半期財務諸表（yfinance 経由。非公式・階層4。直近5四半期ほど。海外企業も取れる）。
          レポート側（収集プロンプト第2節）が、判断に効く数字だけ SEC の XBRL API（レポート側からは読める）で確認して格上げする。
          そのための確認URL（sec_check_urls）をこのスクリプトが出す。
  auto  : SEC に1回だけ到達確認し、届けば sec、届かなければ yahoo。

出力（--out で指定したフォルダ。既定は out/）:
  fundamentals.csv          : ticker, cik, item, period_start, period_end, fiscal_year, fiscal_period, value, unit, derived, form, filed, accn, tag, source
  fundamentals_latest.json  : 会社ごとの直近四半期（値・前年比・前期比・在庫日数、source_kind と tier）、ハイパースケーラー4社の設備投資合計、
                              SEC 確認用URL（yahoo のとき）、最新提出のURL（sec のとき）、前回実行以降の新しい提出、エラー
書き込みは一時ファイル経由（途中で落ちても前回のファイルが残る）。全社失敗なら終了コード2。

注意（収集プロンプトはこの前提で使う）:
  - yahoo の値は Yahoo の提供元が決算資料から転記したもので、定義（設備投資の純額・総額、売上の区分）が SEC の XBRL と違うことがある。
    期間末は月末に丸められる（Micron の 8/28 → 8/31 など）。通貨は会社の報告通貨（TSM は TWD、ASML は EUR。config の yahoo_currency）。
  - sec の値は 10-Q/10-K の XBRL（次元なしのファクト）。決算発表（8-K）の数字は XBRL に含まれないため、10-Q/10-K の受理後に入る
    （MSFT・META・GOOGL・AMZN は発表当日〜数日、NVDA は1週間前後、MU は1〜2週間が目安）。
  - キャッシュフロー項目（設備投資・リース返済・営業CF）は年初来累計で開示されるため、累計の差分で四半期化する（derived=true）。
    損益計算書の第4四半期も「通期 − 9か月累計」で作る。
  - 同じ期間が複数の提出に載る場合（翌年の比較数値など）、値は最新の提出のもの、会計年度のラベルは最初の提出のもの。
  - 設備投資の項目名は会社で違う（Amazon は PaymentsToAcquireProductiveAssets＝売却収入等を差し引いた純額）。tag 列で区別する。
  - 20-F/6-K しか出さない海外企業（TSMC、ASML、ARM、SK hynix ADR、ASE）は対象外（四半期の XBRL がない）。
"""
import argparse
import csv
import gzip
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
# 名乗り（SEC の利用規約「名前 連絡先メール」の形）。リポジトリURLだけの名乗りは 403 で拒否された（2026-11-02 確認）。
# 既定は GitHub の noreply アドレス（公開情報のユーザー名から作られる。個人のメールは公開リポジトリに書かない）。
# 変えるときは GitHub の Settings → Secrets and variables → Actions に SEC_USER_AGENT（例 "semis-data you@example.com"）を置く（update.yml が env で渡す）
UA = os.environ.get("SEC_USER_AGENT") or "semis-data bakaho19920625-wq@users.noreply.github.com"
MIN_INTERVAL = 0.13  # 秒。SEC の上限（10回/秒）より十分遅く

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
CONCEPT_URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/{tag}.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE_DIR = "https://www.sec.gov/Archives/edgar/data/{cik}/{accn}/"

# 項目 → us-gaap タグの候補（先頭から試し、最新の期間を持つものを採用）。kind: duration（期間）/ instant（時点）
ITEMS = {
    "revenue": {"kind": "duration", "tags": [
        "RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax"]},
    "cost_of_revenue": {"kind": "duration", "tags": [
        "CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold",
        "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization"]},
    "inventory": {"kind": "instant", "tags": ["InventoryNet", "InventoryGross"]},
    "capex": {"kind": "duration", "tags": [
        "PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets",
        "PaymentsToAcquirePropertyPlantAndEquipmentAndIntangibleAssets", "PaymentsForCapitalImprovements"]},
    "finance_lease_principal": {"kind": "duration", "tags": ["FinanceLeasePrincipalPayments"]},
    "operating_cash_flow": {"kind": "duration", "tags": ["NetCashProvidedByUsedInOperatingActivities"]},
}
HYPERSCALERS_4 = ["MSFT", "GOOGL", "AMZN", "META"]

_last_call = [0.0]


def http_get(url, retries=3):
    """SEC へ GET（名乗り付き、間隔を空け、429/5xx は待って再試行）。404 は None。"""
    last = None
    for attempt in range(retries):
        wait = MIN_INTERVAL - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={
            "User-Agent": UA, "Accept-Encoding": "gzip, deflate", "Accept": "application/json,*/*"})
        try:
            _last_call[0] = time.time()
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return raw
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            body = ""
            try:
                raw = e.read()
                if raw[:2] == b"\x1f\x8b":
                    raw = gzip.decompress(raw)
                body = re.sub(r"<[^>]+>", " ", raw.decode("utf-8", "replace"))
                body = re.sub(r"\s+", " ", body)[:200]
            except Exception:
                pass
            last = f"HTTP {e.code} {body.strip()[:120]!r}"
            if e.code in (403, 429) or e.code >= 500:
                time.sleep(2.0 * (attempt + 1) + (10 if e.code == 429 else 0))
                continue
            raise RuntimeError(f"{last}: {url}")
        except Exception as e:
            last = f"{type(e).__name__}: {str(e)[:120]}"
            time.sleep(2.0 * (attempt + 1))
    raise RuntimeError(f"failed after retries ({last}): {url}")


def get_json(url):
    raw = http_get(url)
    return None if raw is None else json.loads(raw.decode("utf-8"))


def d(s):
    return date.fromisoformat(s)


def load_cik_map(cfg_cik, notes):
    """config.json の cik を正とする。company_tickers.json（www.sec.gov）は取れれば名前の補完と照合に使う（取れなくても続行）。"""
    out = {t.upper(): {"cik": int(c), "name": ""} for t, c in (cfg_cik or {}).items()}
    try:
        j = get_json(TICKERS_URL) or {}
        for v in j.values():
            t = str(v.get("ticker", "")).upper()
            if t in out:
                out[t]["name"] = v.get("title", "")
                if int(v["cik_str"]) != out[t]["cik"]:
                    notes.append(f"{t}: config の cik {out[t]['cik']} と company_tickers.json の {v['cik_str']} が違う（config を使用）")
    except Exception as e:
        notes.append(f"company_tickers.json は読めず（config の cik で続行）: {str(e)[:160]}")
    return out


def fetch_concept(cik, tag):
    j = get_json(CONCEPT_URL.format(cik=cik, tag=tag))
    if not j:
        return []
    facts = (j.get("units") or {}).get("USD") or []
    return [f for f in facts if f.get("form") in ("10-Q", "10-K", "10-Q/A", "10-K/A") and f.get("val") is not None]


def pick_tag(cik, item):
    """候補タグを順に試し、最新の期間末が最も新しいもの（同じなら候補順）を返す。"""
    best, best_tag, best_end = [], None, None
    for tag in ITEMS[item]["tags"]:
        facts = fetch_concept(cik, tag)
        if not facts:
            continue
        end = max(f["end"] for f in facts)
        if best_end is None or end > best_end:
            best, best_tag, best_end = facts, tag, end
        # 十分新しく十分な量があればそこで止める（呼び出し回数の節約）
        if best_end and (date.today() - d(best_end)).days < 400 and len(best) >= 8:
            break
    return best_tag, best


def dedupe(facts, key_fn):
    """同じ期間のファクトをまとめる。値は最新の提出、会計年度ラベルは最初の提出。"""
    groups = {}
    for f in facts:
        groups.setdefault(key_fn(f), []).append(f)
    out = {}
    for k, fs in groups.items():
        fs_sorted = sorted(fs, key=lambda f: (f.get("filed", ""), f.get("accn", "")))
        first, last = fs_sorted[0], fs_sorted[-1]
        out[k] = {"val": last["val"], "form": last.get("form"), "filed": last.get("filed"), "accn": last.get("accn"),
                  "fy": first.get("fy"), "fp": first.get("fp"), "first_form": first.get("form")}
    return out


def quarterize(facts):
    """期間ファクトから四半期の値を作る。戻り値: {end(date): {start, value, derived, fy, fp, form, filed, accn}}"""
    cum = dedupe(facts, lambda f: (f["start"], f["end"]))
    # 直接の四半期（75〜100日）
    q = {}
    for (s, e), f in cum.items():
        days = (d(e) - d(s)).days
        if 75 <= days <= 100:
            q[d(e)] = dict(start=s, value=f["val"], derived=False, fy=f["fy"], fp=f["fp"],
                           form=f["form"], filed=f["filed"], accn=f["accn"])

    def cum_value(s, e_target):
        """start=s から e_target までの累計。ファクトがあればそれ、なければ直接四半期の連結で作る。"""
        if (s, e_target.isoformat()) in cum:
            return cum[(s, e_target.isoformat())]["val"]
        total, cur = 0.0, d(s)
        qs = sorted(q.items())
        while True:
            nxt = [(e, v) for e, v in qs if abs((d(v["start"]) - cur).days) <= 7 and e <= e_target + timedelta(days=7)]
            if not nxt:
                return None
            e, v = nxt[0]
            total += v["value"]
            if abs((e - e_target).days) <= 7:
                return total
            cur = e

    # 累計（6か月・9か月・通期）から差分で四半期化
    for (s, e), f in sorted(cum.items(), key=lambda kv: (d(kv[0][1]) - d(kv[0][0])).days):
        e_d = d(e)
        days = (e_d - d(s)).days
        if not (165 <= days <= 200 or 255 <= days <= 290 or 350 <= days <= 380):
            continue
        if any(abs((e_d - k).days) <= 7 for k in q):
            continue  # 直接の四半期がある
        fp = "Q2" if days <= 200 else ("Q3" if days <= 290 else "Q4")
        prev_end = e_d - timedelta(days=91)
        # 直前の累計の末日を探す（同じ start で、91日ほど短いもの）
        cands = [d(e2) for (s2, e2) in cum if s2 == s and 75 <= (e_d - d(e2)).days <= 100]
        base = None
        if cands:
            base = cum_value(s, max(cands))
        if base is None:
            base = cum_value(s, prev_end)
        if base is None:
            continue
        q[e_d] = dict(start=((max(cands) if cands else prev_end) + timedelta(days=1)).isoformat(), value=f["val"] - base, derived=True,
                      fy=f["fy"], fp=fp, form=f["form"], filed=f["filed"], accn=f["accn"])
    return q


def instants(facts):
    inst = dedupe(facts, lambda f: f["end"])
    return {d(e): dict(start=None, value=f["val"], derived=False, fy=f["fy"], fp=f["fp"],
                       form=f["form"], filed=f["filed"], accn=f["accn"]) for e, f in inst.items()}


def nearest_key(series, target, tol=12):
    """series: {date: row}。target に最も近い日付（±tol日）のキーを返す。"""
    best = None
    for e in series:
        if abs((e - target).days) <= tol and (best is None or abs((e - target).days) < abs((best - target).days)):
            best = e
    return best


def nearest(series, target, tol=12):
    k = nearest_key(series, target, tol)
    return series.get(k) if k else None


def ratio(a, b):
    if a is None or b is None or b == 0:
        return None
    return round(a / b - 1.0, 4)


def fiscal_label(row):
    if row.get("fy") and row.get("fp"):
        return f"FY{row['fy']} {row['fp']}"
    return None


def archive_url(cik, accn, doc=None):
    base = ARCHIVE_DIR.format(cik=cik, accn=accn.replace("-", ""))
    return base + (doc or "")


def latest_filings(cik, sub):
    """提出一覧から最新の 10-Q/10-K と、決算の 8-K（Item 2.02）を取り、Ex.99.1 のURLを探す。"""
    rec = (sub.get("filings") or {}).get("recent") or {}
    n = len(rec.get("accessionNumber") or [])
    rows = [{k: rec[k][i] for k in rec if isinstance(rec[k], list) and len(rec[k]) == n} for i in range(n)]
    out = {"latest_10q_10k": None, "latest_8k_earnings": None, "forms_seen": sorted({r.get("form") for r in rows[:40] if r.get("form")})}
    for r in rows:
        if out["latest_10q_10k"] is None and r.get("form") in ("10-Q", "10-K"):
            out["latest_10q_10k"] = {"form": r["form"], "filed": r.get("filingDate"), "report_date": r.get("reportDate"),
                                     "accn": r.get("accessionNumber"), "url": archive_url(cik, r["accessionNumber"], r.get("primaryDocument"))}
        if out["latest_8k_earnings"] is None and r.get("form") == "8-K" and "2.02" in str(r.get("items", "")):
            out["latest_8k_earnings"] = {"filed": r.get("filingDate"), "report_date": r.get("reportDate"), "accn": r.get("accessionNumber"),
                                         "index_url": archive_url(cik, r["accessionNumber"]), "exhibit_99_url": None}
        if out["latest_10q_10k"] and out["latest_8k_earnings"]:
            break
    ek = out["latest_8k_earnings"]
    if ek:
        try:
            idx = get_json(archive_url(cik, ek["accn"], "index.json")) or {}
            names = [it.get("name", "") for it in (idx.get("directory") or {}).get("item", [])]
            cands = [nm for nm in names if re.search(r"(ex|exhibit)[-_]?99", nm, re.I) and re.search(r"\.(htm|html|pdf)$", nm, re.I)]
            cands.sort(key=lambda nm: (0 if re.search(r"99[-_.]?0?1\b", nm) else 1, len(nm)))
            if cands:
                ek["exhibit_99_url"] = archive_url(cik, ek["accn"], cands[0])
        except Exception as e:  # 索引が読めなくても 8-K の索引URLは残す
            ek["exhibit_99_error"] = str(e)[:120]
    return out


def process_company(ticker, cik, name, rows_out):
    comp = {"cik": cik, "name": name, "status": "ok", "fiscal_year_end": None, "latest_quarter": None,
            "items": {}, "filings": None, "errors": []}
    series = {}
    try:
        sub = get_json(SUBMISSIONS_URL.format(cik=cik)) or {}
        comp["fiscal_year_end"] = sub.get("fiscalYearEnd")
        comp["name"] = sub.get("name") or name
        sub_tickers = [str(x).upper() for x in (sub.get("tickers") or [])]
        if sub_tickers and ticker.upper() not in sub_tickers:
            comp["errors"].append(f"CIK {cik} の提出一覧の tickers {sub_tickers} に {ticker} がない（config.json の cik を確認）")
        comp["filings"] = latest_filings(cik, sub)
        if comp["filings"]["latest_10q_10k"] is None:
            comp["status"] = "no_10q_10k"
            comp["errors"].append("最近の提出に 10-Q/10-K がない（海外企業の 20-F/6-K は対象外）")
            return comp, series
    except Exception as e:
        comp["errors"].append(f"submissions: {str(e)[:160]}")

    for item, spec in ITEMS.items():
        try:
            tag, facts = pick_tag(cik, item)
            if not facts:
                comp["items"][item] = {"status": "no_data", "tags_tried": spec["tags"]}
                continue
            ser = quarterize(facts) if spec["kind"] == "duration" else instants(facts)
            series[item] = (tag, ser)
            for e, r in sorted(ser.items()):
                rows_out.append([ticker, cik, item, r.get("start") or "", e.isoformat(), r.get("fy") or "", r.get("fp") or "",
                                 r["value"], "USD", "true" if r["derived"] else "false", r.get("form") or "", r.get("filed") or "",
                                 r.get("accn") or "", tag, "sec_xbrl"])
        except Exception as e:
            comp["items"][item] = {"status": "error", "error": str(e)[:160]}
            comp["errors"].append(f"{item}: {str(e)[:120]}")

    comp["items"].update(summarize_series(series, cik, "USD", "sec_xbrl"))
    rev = comp["items"].get("revenue") or {}
    if rev.get("period_end"):
        comp["latest_quarter"] = {"period_end": rev["period_end"], "fiscal": rev.get("fiscal"), "form": rev.get("form"),
                                  "filed": rev.get("filed"), "url": rev.get("url")}
    if not series:
        comp["status"] = "failed" if comp["errors"] else "no_data"
    elif comp["errors"]:
        comp["status"] = "partial"
    return comp, series


# Yahoo（yfinance）の行ラベル → 項目。設備投資は支出が負で入るので絶対値にする
YF_ITEMS = {
    "revenue": ("income", ["Total Revenue", "Operating Revenue"], 1),
    "cost_of_revenue": ("income", ["Cost Of Revenue", "Reconciled Cost Of Revenue"], 1),
    "inventory": ("balance", ["Inventory"], 1),
    "capex": ("cashflow", ["Capital Expenditure", "Purchase Of PPE"], -1),
    "operating_cash_flow": ("cashflow", ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"], 1),
}


def yahoo_company(ticker, currency, rows_out):
    """Yahoo の四半期財務諸表から series（{item: (label, {date: row})}）を作る。"""
    import math
    import yfinance as yf
    t = yf.Ticker(ticker)
    frames = {}
    errs = []
    for kind, getter in (("income", "quarterly_income_stmt"), ("balance", "quarterly_balance_sheet"), ("cashflow", "quarterly_cashflow")):
        try:
            frames[kind] = getattr(t, getter)
        except Exception as e:
            errs.append(f"{kind}: {str(e)[:120]}")
            frames[kind] = None
    series = {}
    for item, (kind, labels, sign) in YF_ITEMS.items():
        df = frames.get(kind)
        if df is None or df.empty:
            continue
        label = next((l for l in labels if l in df.index), None)
        if label is None:
            continue
        ser = {}
        for col, v in df.loc[label].items():
            try:
                fv = float(v)
            except Exception:
                continue
            if math.isnan(fv):
                continue
            e = col.date() if hasattr(col, "date") else d(str(col)[:10])
            start = None
            if item != "inventory":
                start = (e - timedelta(days=91)).isoformat()  # Yahoo は期間の開始を出さないので約3か月前とする
            ser[e] = dict(start=start, value=fv * sign, derived=False, fy=None, fp=None, form="yahoo", filed=None, accn=None)
        if ser:
            series[item] = (label, ser)
            for e, r in sorted(ser.items()):
                rows_out.append([ticker, "", item, r.get("start") or "", e.isoformat(), "", "", r["value"], currency, "false",
                                 "yahoo", "", "", label, "yahoo"])
    return series, errs


def summarize_series(series, cik, currency, source_kind):
    """直近四半期のまとめ（sec／yahoo 共通）。"""
    items = {}
    for item, (tag, ser) in series.items():
        if not ser:
            continue
        e = max(ser)
        r = ser[e]
        prev_q = nearest({k: v for k, v in ser.items() if k < e}, e - timedelta(days=91))
        prev_y = nearest(ser, e - timedelta(days=365))
        items[item] = {"value": r["value"], "period_end": e.isoformat(), "period_start": r.get("start"), "fiscal": fiscal_label(r),
                       "qoq": ratio(r["value"], prev_q["value"] if prev_q else None),
                       "yoy": ratio(r["value"], prev_y["value"] if prev_y else None),
                       "prev_q": prev_q["value"] if prev_q else None, "prev_y": prev_y["value"] if prev_y else None,
                       "tag": tag, "derived": r["derived"], "form": r.get("form"), "filed": r.get("filed"),
                       "url": archive_url(cik, r["accn"]) if (cik and r.get("accn")) else None, "unit": currency,
                       "source_kind": source_kind, "tier": 1 if source_kind == "sec_xbrl" else 4,
                       "status": "confirmed" if source_kind == "sec_xbrl" else "reported_unverified"}
    inv, cor = series.get("inventory"), series.get("cost_of_revenue")
    if inv and cor and inv[1] and cor[1] and "inventory" in items:
        def days_at(e):
            c = nearest(cor[1], e)
            i = inv[1].get(e)
            if not c or not i or not c["value"]:
                return None
            qdays = (e - d(c["start"])).days if c.get("start") else 91
            return round(i["value"] / c["value"] * qdays, 1)
        e = max(inv[1])
        items["inventory"]["days"] = days_at(e)
        kq = nearest_key({k: v for k, v in inv[1].items() if k < e}, e - timedelta(days=91))
        ky = nearest_key(inv[1], e - timedelta(days=365))
        items["inventory"]["days_prev_q"] = days_at(kq) if kq else None
        items["inventory"]["days_prev_y"] = days_at(ky) if ky else None
        items["inventory"]["days_note"] = "在庫 ÷ 四半期の売上原価 × 四半期の日数"
    return items


def sec_check_urls(ticker, cik, items, checks):
    """レポート側が SEC の XBRL API で確認するためのURL（会社ごと・項目ごと）。AMZN の設備投資は項目名が違う。"""
    out = []
    for item, tickers in (checks or {}).items():
        if ticker not in tickers or cik is None:
            continue
        tags = list(ITEMS.get(item, {}).get("tags") or [])
        if item == "capex" and ticker == "AMZN":
            tags = ["PaymentsToAcquireProductiveAssets"] + [x for x in tags if x != "PaymentsToAcquireProductiveAssets"]
        it = items.get(item) or {}
        out.append({"ticker": ticker, "item": item, "url": CONCEPT_URL.format(cik=cik, tag=tags[0]), "alt_tags": tags[1:3],
                    "yahoo_value": it.get("value"), "yahoo_period_end": it.get("period_end"),
                    "how": "units.USD の配列で end が最新のもの（form 10-Q/10-K）。売上は start〜end が約90日の値。設備投資・営業CFは年初来累計なので、"
                           "同じ start の直前の累計を引いて四半期にする。在庫は時点値。1%以内で一致すれば confirmed（階層1）に格上げ"})
    return out


def hyperscalers_capex(capex_series, members):
    """4社の設備投資（各社の capex 項目。Amazon は純額）を、全社そろう最新の四半期末で合計し前年比を出す。
    capex_series: {ticker: (tag, {date: row})}"""
    per = {t: capex_series[t] for t in members if capex_series.get(t) and capex_series[t][1]}
    out = {"members": members, "available": sorted(per), "missing": [t for t in members if t not in per], "status": "ok",
           "basis": "各社の 10-Q/10-K キャッシュフローの設備投資（四半期化）。AMZN は PaymentsToAcquireProductiveAssets（売却収入等を差し引いた純額）。"
                    "MSFT・META のファイナンスリースは finance_lease_principal を別掲。発表直後は 10-Q 未受理の会社が欠ける"}
    if not per:
        out["status"] = "no_data"
        return out
    if out["missing"]:
        out["status"] = "partial"
    common = min(max(ser) for _, ser in per.values())  # 全社に共通する最新の四半期末
    out["quarter_end"] = common.isoformat()
    detail, s_now, s_prev, complete_now, complete_prev = {}, 0.0, 0.0, True, True
    for t, (tag, ser) in per.items():
        r = nearest(ser, common)
        ry = nearest(ser, common - timedelta(days=365))
        detail[t] = {"value": r["value"] if r else None, "prev_y": ry["value"] if ry else None,
                     "period_end": nearest_key(ser, common).isoformat() if r else None, "latest_period_end": max(ser).isoformat(), "tag": tag}
        if r is None:
            complete_now = False
        else:
            s_now += r["value"]
        if ry is None:
            complete_prev = False
        else:
            s_prev += ry["value"]
    out["per_company"] = detail
    out["sum"] = round(s_now) if complete_now else None
    out["sum_prev_year"] = round(s_prev) if complete_now and complete_prev else None
    out["yoy"] = ratio(s_now, s_prev) if complete_now and complete_prev else None
    if not complete_now:
        out["status"] = "partial"
    # 直近4四半期の合計（前年同期間比）も添える
    if complete_now and complete_prev:
        t4, t4p, okk = 0.0, 0.0, True
        for k in range(4):
            tgt = common - timedelta(days=91 * k)
            for t, (tag, ser) in per.items():
                r, ry = nearest(ser, tgt), nearest(ser, tgt - timedelta(days=365))
                if r is None or ry is None:
                    okk = False
                    break
                t4 += r["value"]; t4p += ry["value"]
            if not okk:
                break
        if okk:
            out["trailing_4q_sum"], out["trailing_4q_prev"], out["trailing_4q_yoy"] = round(t4), round(t4p), ratio(t4, t4p)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--only", default="", help="カンマ区切りのティッカー（試験用）")
    ap.add_argument("--source", default="auto", choices=["auto", "sec", "yahoo"])
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    cfg = json.load(open(a.config, encoding="utf-8")).get("fundamentals") or {}
    hyper = cfg.get("hyperscalers_4") or HYPERSCALERS_4
    cik_cfg = cfg.get("cik") or {}

    prev_path = os.path.join(a.out, "fundamentals_latest.json")
    prev = None
    if os.path.exists(prev_path):
        try:
            prev = json.load(open(prev_path, encoding="utf-8"))
        except Exception:
            prev = None

    errors, notes = [], []
    source = a.source
    sec_probe = None
    if source in ("auto", "sec"):
        # 到達確認：最初の1回で 403 等なら、全社分の再試行で1時間近く浪費しないようここで切り替える
        # （GitHub Actions からは data.sec.gov・www.sec.gov とも 403 で拒否される。2026-11-02 確認。名乗りを変えても同じ）
        probe_cik = next(iter(cik_cfg.values()), 789019)
        try:
            get_json(SUBMISSIONS_URL.format(cik=int(probe_cik)))
            sec_probe = "ok"
            source = "sec"
        except Exception as e:
            sec_probe = f"unreachable: {str(e)[:160]}"
            if a.source == "sec":
                print(f"SEC に到達できない（{sec_probe}）。--source sec のため打ち切り", file=sys.stderr)
                sys.exit(2)
            notes.append(f"SEC に到達できないため Yahoo に切り替え（{sec_probe}）")
            source = "yahoo"
    print(f"source={source} probe={sec_probe}", flush=True)

    rows, companies, capex_series = [], {}, {}
    if source == "sec":
        tickers = [t for t in cfg.get("sec_filers", []) if not a.only or t in a.only.split(",")]
        cik_map = load_cik_map(cik_cfg, notes)
        for t in tickers:
            m = cik_map.get(t.upper())
            if not m:
                companies[t] = {"status": "no_cik", "errors": ["config.json の fundamentals.cik に CIK がない"]}
                continue
            try:
                companies[t], ser = process_company(t, m["cik"], m["name"], rows)
                if ser.get("capex"):
                    capex_series[t] = ser["capex"]
            except Exception as e:
                companies[t] = {"cik": m["cik"], "status": "failed", "errors": [str(e)[:200]]}
            print(f"{t}: {companies[t].get('status')} {len(companies[t].get('errors') or [])} errors", flush=True)
    else:
        tickers = [t for t in (cfg.get("yahoo_tickers") or cfg.get("sec_filers", [])) if not a.only or t in a.only.split(",")]
        currencies = cfg.get("yahoo_currency") or {}
        checks = cfg.get("sec_check") or {}
        for t in tickers:
            cur = currencies.get(t, "USD")
            cik = cik_cfg.get(t)
            comp = {"cik": cik, "name": None, "status": "ok", "currency": cur, "items": {}, "filings": None, "errors": []}
            try:
                ser, errs = yahoo_company(t, cur, rows)
                comp["errors"].extend(errs)
                comp["items"] = summarize_series(ser, cik, cur, "yahoo")
                for item in YF_ITEMS:
                    comp["items"].setdefault(item, {"status": "no_data"})
                if ser.get("capex"):
                    capex_series[t] = ser["capex"]
                comp["sec_check_urls"] = sec_check_urls(t, cik, comp["items"], checks)
                if cik:
                    comp["edgar_filings_index"] = f"https://www.sec.gov/Archives/edgar/data/{cik}/"
                if not ser:
                    comp["status"] = "failed" if errs else "no_data"
                elif errs:
                    comp["status"] = "partial"
            except Exception as e:
                comp["status"] = "failed"
                comp["errors"].append(str(e)[:200])
            companies[t] = comp
            rev = comp["items"].get("revenue") or {}
            if rev.get("period_end"):
                comp["latest_quarter"] = {"period_end": rev["period_end"], "form": "yahoo"}
            print(f"{t}: {comp['status']} {len(comp['errors'])} errors", flush=True)
            time.sleep(0.5)

    ok = [t for t, c in companies.items() if c.get("status") in ("ok", "partial")]
    if rows:
        tmp = os.path.join(a.out, "fundamentals.csv.tmp")
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["ticker", "cik", "item", "period_start", "period_end", "fiscal_year", "fiscal_period", "value", "unit",
                        "derived", "form", "filed", "accn", "tag", "source"])
            w.writerows(sorted(rows, key=lambda r: (r[0], r[2], r[4])))
        os.replace(tmp, os.path.join(a.out, "fundamentals.csv"))

    # 前回実行以降の新しい提出
    new_filings = []
    prev_date = (prev or {}).get("generated_utc", "")[:10]
    for t, c in companies.items():
        f = c.get("filings") or {}
        for key in ("latest_10q_10k", "latest_8k_earnings"):
            x = f.get(key)
            if x and prev_date and x.get("filed") and x["filed"] >= prev_date:
                new_filings.append({"ticker": t, "form": x.get("form") or "8-K (Item 2.02)", "filed": x["filed"],
                                    "url": x.get("exhibit_99_url") or x.get("url") or x.get("index_url")})
    new_filings.sort(key=lambda x: (x["filed"], x["ticker"]), reverse=True)

    now = datetime.now(timezone.utc)
    latest = {
        "generated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_jst": now.astimezone(JST).strftime("%Y-%m-%d %H:%M JST"),
        "status": "ok" if ok and len(ok) == len(tickers) else ("partial" if ok else "failed"),
        "source_kind": "sec_xbrl" if source == "sec" else "yahoo",
        "tier": 1 if source == "sec" else 4,
        "source": ("SEC EDGAR XBRL API（companyconcept）と提出一覧API（submissions）。非公式の加工は四半期化と比率計算のみ" if source == "sec"
                   else "Yahoo Finance 四半期財務諸表（yfinance 経由、非公式・階層4）。判断に効く数字は sec_check_urls の SEC XBRL で確認して格上げする"),
        "sec_probe": sec_probe,
        "user_agent": UA,
        "prev_generated_utc": (prev or {}).get("generated_utc"),
        "note": ("値は 10-Q/10-K の XBRL。決算発表（8-K）の数字は含まれず、10-Q/10-K 受理後に入る。キャッシュフロー項目と第4四半期は累計の差分（derived=true）。"
                 "ガイダンス・ASP・ビット出荷・HBM比率などは XBRL にないため、latest_8k_earnings.exhibit_99_url（決算リリース）を開いて読む" if source == "sec"
                 else "値は Yahoo の四半期財務諸表（決算資料からの転記、非公式）。期間末は月末に丸められ、設備投資などの定義が会社の発表と違うことがある。"
                      "status は reported_unverified（階層4）。sec_check_urls の XBRL と1%以内で一致したものだけ confirmed（階層1）にする。"
                      "ガイダンス・ASP・ビット出荷・HBM比率は IR の決算資料から"),
        "companies_ok": len(ok), "companies_total": len(tickers),
        "hyperscalers_capex_4": hyperscalers_capex(capex_series, hyper),
        "new_filings_since_prev": new_filings,
        "companies": companies,
        "errors": errors,
        "notes": notes,
    }
    tmp = os.path.join(a.out, "fundamentals_latest.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(latest, f, ensure_ascii=False, indent=1, default=str)
    os.replace(tmp, prev_path)
    print(json.dumps({k: latest[k] for k in ("generated_jst", "status", "companies_ok", "companies_total", "errors", "notes")}, ensure_ascii=False))
    for t, c in companies.items():
        if c.get("errors"):
            print(f"  {t}: {c['errors']}")
    print(json.dumps(latest["hyperscalers_capex_4"], ensure_ascii=False, indent=1))
    if not ok:
        print("SEC の取得にすべて失敗しました。", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
