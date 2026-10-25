"""
半導体・メモリー定点観測用の日足取得（GitHub Actionsで毎日実行）

出力（--out で指定したフォルダ。既定は out/）:
  prices_daily.csv.gz : tickers.txt の銘柄の日足（約3年分、縦持ち）
                        close は分割調整済み・配当非調整（Yahooの終値）。配当込みは adj_close。
  prices_manifest.json: 基準日、取得できた銘柄数、失敗・遅延銘柄

安全設計:
  - 書き込みは一時ファイルに出してから置き換える（途中で落ちても前回のファイルが残る）
  - 失敗銘柄が3割を超えたら何も書かずに終了コード2（前回のデータを残し、Actionsが失敗を知らせる）
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
                df = yf.download(part, period=PERIOD, interval="1d", auto_adjust=False, actions=False,
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

    px = px.sort_values(["ticker", "date"]).reset_index(drop=True)
    last = px.groupby("ticker")["date"].max()
    us_asof = last.get("SPY", last.max())
    stale = sorted(last[last < us_asof].index.tolist())

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
    }
    write_atomic(manifest, os.path.join(a.out, "prices_manifest.json"))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
