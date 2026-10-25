"""
FREDから金利などの日次データを取得する（GitHub Actionsで毎日実行。APIキー不要）

出力（--out で指定したフォルダ。既定は out/）:
  macro_daily.csv     : date, series, value, source（直近約3年）
  macro_manifest.json : 取得結果（成功・失敗、各系列の最新日）
書き込みは一時ファイル経由（途中で落ちても前回のファイルが残る）。全系列失敗なら終了コード2。

系列:
  DGS10    : 米10年国債利回り（名目、%）
  DFII10   : 米10年TIPS利回り（実質金利、%）
  DTWEXBGS : 名目ドル指数（Broad）
"""
import argparse
import io
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

import pandas as pd

SERIES = ["DGS10", "DFII10", "DTWEXBGS"]
URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}"
JST = timezone(timedelta(hours=9))


def parse_fred_csv(text, sid):
    """FREDのCSV（1列目が日付、2列目が値。欠損は '.' か空欄）を縦持ちに直す。"""
    df = pd.read_csv(io.StringIO(text), dtype=str)
    if df.shape[1] < 2:
        raise ValueError("unexpected FRED csv")
    df = df.iloc[:, :2]
    df.columns = ["date", "value"]
    df["value"] = pd.to_numeric(df["value"].str.strip().replace({".": None, "": None}), errors="coerce")
    df = df.dropna(subset=["value"])
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df.insert(1, "series", sid)
    df["source"] = "FRED"
    return df


def fetch(sid, start, retries=3, pause=3.0):
    req = urllib.request.Request(URL.format(sid=sid, start=start),
                                 headers={"User-Agent": "market-data-bot/1.0"})
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return parse_fred_csv(r.read().decode("utf-8"), sid)
        except Exception as e:  # 通信エラーや一時的な制限
            last = e
            time.sleep(pause * (attempt + 1))
    raise last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    start = (datetime.now(timezone.utc) - timedelta(days=3 * 365)).strftime("%Y-%m-%d")

    frames, failed, latest = [], [], {}
    for sid in SERIES:
        try:
            df = fetch(sid, start)
            frames.append(df)
            latest[sid] = df["date"].iloc[-1] if not df.empty else None
        except Exception as e:
            failed.append({"series": sid, "error": str(e)[:200]})

    if frames:
        tmp = os.path.join(a.out, "macro_daily.csv.tmp")
        pd.concat(frames, ignore_index=True).to_csv(tmp, index=False)
        os.replace(tmp, os.path.join(a.out, "macro_daily.csv"))
    now = datetime.now(timezone.utc)
    manifest = {
        "generated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_jst": now.astimezone(JST).strftime("%Y-%m-%d %H:%M JST"),
        "status": "ok" if not failed else ("partial" if frames else "failed"),
        "series_latest_date": latest,
        "failed": failed,
        "source": "FRED (fredgraph.csv, no API key)",
    }
    tmp = os.path.join(a.out, "macro_manifest.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    os.replace(tmp, os.path.join(a.out, "macro_manifest.json"))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    if failed and not frames:
        print("FREDの取得にすべて失敗しました。", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
