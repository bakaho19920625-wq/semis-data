"""
半導体・メモリー定点観測用の日足取得（GitHub Actionsで毎日実行）

出力（--out で指定したフォルダ。既定は out/）:
  prices_daily.csv.gz : tickers.txt の銘柄の日足（約3年分、縦持ち）
                        close は分割調整済み・配当非調整（Yahooの終値）。配当込みは adj_close。
  prices_manifest.json: 基準日、取得できた銘柄数、失敗・遅延銘柄

安全設計:
  - 書き込みは一時ファイルに出してから置き換える（途中で落ちても前回のファイルが残る）
  - 失敗銘柄が3割を超えたら何も書かずに終了コード2（前回のデータを残し、Actionsが失敗を知らせる）
  - 前回のファイルとマージする（今回取れなかった日付の行は前回の値を残す）。基準日が前回より古くなる場合は書かない
データ元: Yahoo Finance（yfinance経由の非公式な取得。仕様変更で止まることがある）
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import yfinance as yf

PERIOD = "3y"
PRICE_BASIS = "split_adjusted_ex_dividends(yahoo_close)"
FIELDS = {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Adj Close": "adj_close", "Volume": "volume"}
COLUMNS = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]
JST = timezone(timedelta(hours=9))
MAX_FAIL_RATIO = 0.3


def read_tickers(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.split("#")[0].strip().upper()
            if s:
                out.append(s)
    return list(dict.fromkeys(out))


def write_atomic(df_or_obj, path, **kw):
    tmp = path + ".tmp"
    if isinstance(df_or_obj, pd.DataFrame):
        df_or_obj.to_csv(tmp, index=False, **kw)
    else:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(df_or_obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def one_ticker_frame(df, ticker):
    """yf.download の結果から1銘柄分を縦持ちにする。取れていなければ空。"""
    try:
        sub = df[ticker] if isinstance(df.columns, pd.MultiIndex) else df
    except KeyError:
        return pd.DataFrame(columns=COLUMNS)
    sub = sub.rename(columns=FIELDS)
    if "close" not in sub.columns:
        return pd.DataFrame(columns=COLUMNS)
    sub = sub.dropna(subset=["close"])
    if sub.empty:
        return pd.DataFrame(columns=COLUMNS)
    idx = pd.to_datetime(sub.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    sub = sub.copy()
    sub.index = idx.strftime("%Y-%m-%d")
    sub.index.name = "date"
    sub = sub.reset_index()
    sub.insert(1, "ticker", ticker)
    for c in COLUMNS:
        if c not in sub.columns:
            sub[c] = pd.NA
    return sub[COLUMNS]


def download(tickers, chunk=40, retries=3, pause=3.0):
    frames, failed = [], []
    for i in range(0, len(tickers), chunk):
        part = tickers[i:i + chunk]
        df = None
        for attempt in range(retries):
            try:
                end = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d")
                start = (datetime.now(timezone.utc) - timedelta(days=3 * 365 + 7)).strftime("%Y-%m-%d")
                df = yf.download(part, start=start, end=end, interval="1d", auto_adjust=False, actions=False,
                                 group_by="ticker", threads=True, progress=False)
                break
            except Exception as e:  # 通信エラーや一時的な制限
                print(f"retry {attempt + 1}/{retries}: {e}", file=sys.stderr)
                time.sleep(pause * (attempt + 1))
        if df is None or df.empty:
            failed += part
            continue
        for t in part:
            f = one_ticker_frame(df, t)
            if f.empty:
                failed.append(t)
            else:
                frames.append(f)
        time.sleep(pause)
    data = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLUMNS)
    return data, failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    ap.add_argument("--tickers", default="tickers.txt")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    started = datetime.now(timezone.utc)

    tickers = read_tickers(a.tickers)
    px, failed = download(tickers)
    if len(failed) > MAX_FAIL_RATIO * len(tickers) or px.empty:
        print(f"取得失敗が多すぎます（{len(failed)}/{len(tickers)}）。前回のファイルを残して終了します。", file=sys.stderr)
        print("failed:", failed, file=sys.stderr)
        sys.exit(2)

    # 前回のファイルとマージする。Yahooが最新日の足を一時的に返さないことがあるため、
    # 今回取れなかった日付の行は前回の値を残す（同じ日付は今回の値で上書き）
    prev_path = os.path.join(a.out, "prices_daily.csv.gz")
    merged_from_prev = 0
    if os.path.exists(prev_path):
        try:
            old = pd.read_csv(prev_path, dtype={"date": str})
            old = old[old["ticker"].isin(set(tickers))][COLUMNS]
            key_new = set(zip(px["ticker"], px["date"]))
            keep = old[[(t, d) not in key_new for t, d in zip(old["ticker"], old["date"])]]
            cutoff = (datetime.now(timezone.utc) - timedelta(days=3 * 365 + 7)).strftime("%Y-%m-%d")
            keep = keep[keep["date"] >= cutoff]
            merged_from_prev = int(len(keep))
            px = pd.concat([px, keep], ignore_index=True)
        except Exception as e:  # 前回ファイルが壊れていても今回分で続行
            print(f"前回ファイルとのマージをスキップ: {e}", file=sys.stderr)
    px = px.sort_values(["ticker", "date"]).reset_index(drop=True)
    last = px.groupby("ticker")["date"].max()
    us_asof = last.get("SPY", last.max())
    stale = sorted(last[last < us_asof].index.tolist())

    # 前回より古い基準日のデータで上書きしない（Yahooが最新日を返さないことがある）
    prev = None
    try:
        with open(os.path.join(a.out, "prices_manifest.json"), encoding="utf-8") as f:
            prev = json.load(f).get("us_as_of")
    except (OSError, ValueError):
        prev = None
    if prev and us_asof < prev:
        print(f"取得したデータの基準日 {us_asof} が前回 {prev} より古いため、前回のファイルを残して終了します。", file=sys.stderr)
        sys.exit(2)

    write_atomic(px, os.path.join(a.out, "prices_daily.csv.gz"), compression="gzip")
    finished = datetime.now(timezone.utc)
    manifest = {
        "generated_utc": finished.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_jst": finished.astimezone(JST).strftime("%Y-%m-%d %H:%M JST"),
        "runtime_sec": round((finished - started).total_seconds()),
        "source": "Yahoo Finance via yfinance (unofficial)",
        "yfinance_version": yf.__version__,
        "price_basis": PRICE_BASIS,
        "period": PERIOD,
        "us_as_of": us_asof,
        "rows": int(len(px)),
        "tickers_requested": len(tickers),
        "tickers_ok": int(px["ticker"].nunique()),
        "tickers_failed": failed,
        "tickers_behind_us": stale,
        "rows_kept_from_previous": merged_from_prev,
    }
    write_atomic(manifest, os.path.join(a.out, "prices_manifest.json"))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
