"""長期検証用：tickers_history.txt の銘柄を Yahoo から最長（period=max）で取得し、縦持ちの csv.gz に保存する。
close＝分割調整済み・配当非調整、adj_close＝配当込み。失敗銘柄は manifest に残す。"""
import json, sys, time
from datetime import datetime, timezone
import pandas as pd, yfinance as yf

tick_path, out_dir = sys.argv[1], sys.argv[2]
tickers = list(dict.fromkeys(l.split("#")[0].strip().upper() for l in open(tick_path, encoding="utf-8") if l.split("#")[0].strip()))
FIELDS = {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Adj Close": "adj_close", "Volume": "volume"}
frames, failed = [], []
for i in range(0, len(tickers), 20):
    batch = tickers[i:i + 20]
    for attempt in range(3):
        try:
            df = yf.download(batch, period="max", interval="1d", auto_adjust=False, actions=False, group_by="ticker", threads=True, progress=False)
            break
        except Exception as e:
            print("retry", attempt, e, file=sys.stderr); time.sleep(20)
    else:
        failed += batch; continue
    for t in batch:
        try:
            sub = df[t] if isinstance(df.columns, pd.MultiIndex) else df
        except KeyError:
            failed.append(t); continue
        sub = sub.rename(columns=FIELDS).dropna(subset=["close"])
        if sub.empty:
            failed.append(t); continue
        sub = sub.reset_index().rename(columns={"Date": "date"})
        sub["ticker"] = t
        frames.append(sub[["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]])
    time.sleep(2)
out = pd.concat(frames, ignore_index=True)
out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
out = out.sort_values(["ticker", "date"])
out.to_csv(f"{out_dir}/prices_max.csv.gz", index=False, compression="gzip")
first = out.groupby("ticker")["date"].min().to_dict()
man = {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "yfinance_version": yf.__version__,
       "tickers_ok": sorted(first), "tickers_failed": failed, "first_date": first, "last_date": out["date"].max(), "rows": int(len(out))}
json.dump(man, open(f"{out_dir}/manifest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(json.dumps({"ok": len(first), "failed": failed, "rows": len(out), "last": out["date"].max()}, ensure_ascii=False))
