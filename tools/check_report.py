#!/usr/bin/env python3
"""書き上がったレポートを、保存・配信の前に機械で点検する。

見るもの：見出しがひな形の順にそろっているか、表の行がそろっているか、「全件並べる」決まりが守られているか、
主な数字がデータ（data ブランチ）と合っているか、書いてはいけない言い方が無いか。
文の良し悪しや判断の中身は見ない（そこは書き手の仕事）。何も書き換えない。どこにも送らない。

使い方:
  python3 tools/check_report.py semis_daily  reports/daily/2026-11-09.md --data /home/claude/sd-data --mkt /home/claude/mkt_signals.json
  python3 tools/check_report.py semis_weekly reports/2026-11-06.md       --data /home/claude/sd-data
  python3 tools/check_report.py us_daily     reports/daily/20261109-DAILY.md   --data /home/claude/mkt
  python3 tools/check_report.py us_weekly    reports/weekly/20261106-WEEKLY.md --data /home/claude/mkt
  python3 tools/check_report.py delivery     /home/claude/delivery.txt --max 1200 --link <保管ページのURL>

出力：「不合格」（直してから配信する）と「注意」（読んで、必要なら直す）。不合格が無ければ終了コード 0。
補完版（題に「補完版」）は、ニュースなど補完で省く決まりの項目を自動で外す。
"""
import argparse
import csv
import json
import os
import re
import sys

FAIL, WARN = "不合格", "注意"


class Result:
    def __init__(self):
        self.items = []
        self.ok = 0

    def check(self, cond, where, msg, level=FAIL):
        if cond:
            self.ok += 1
        else:
            self.items.append((level, where, msg))
        return cond

    def fails(self):
        return [i for i in self.items if i[0] == FAIL]

    def report(self, title):
        f, w = self.fails(), [i for i in self.items if i[0] == WARN]
        print("%s：合格 %d 項目、不合格 %d 項目、注意 %d 項目" % (title, self.ok, len(f), len(w)))
        for level, where, msg in f + w:
            print("%s｜%s｜%s" % (level, where, msg))
        if not f:
            print("不合格はありません。")
        return 0 if not f else 1


# ---------------------------------------------------------------- text helpers
def norm(s):
    """数字を比べやすくする：全角の符号と桁区切りをそろえる。"""
    s = s.replace("−", "-").replace("－", "-").replace("＋", "+").replace("％", "%").replace("，", ",")
    return re.sub(r"(?<=\d),(?=\d{3})", "", s)


NUM = re.compile(r"(?<![A-Za-z0-9.])[-+]?\d+(?:\.\d+)?")


def numbers(text):
    out = []
    for m in NUM.finditer(norm(text)):
        try:
            out.append(float(m.group(0)))
        except ValueError:
            pass
    return out


def has_number(nums, v, extra_tol=0.0):
    """本文の数字の中に v（丸め方の違いを許す）があるか。符号は見ない（▲や「下落」で書くことがあるため）。"""
    if v is None:
        return True
    tol = max(0.06, abs(v) * 0.001) + extra_tol
    return any(abs(abs(n) - abs(v)) <= tol for n in nums)


class Doc:
    def __init__(self, text):
        self.text = text
        self.lines = text.split("\n")
        self.heads = []  # (line_index, level, title)
        fence = False
        for i, ln in enumerate(self.lines):
            if ln.lstrip().startswith("```"):
                fence = not fence
            if fence:
                continue
            m = re.match(r"^(#{1,6})\s+(.*\S)\s*$", ln)
            if m:
                self.heads.append((i, len(m.group(1)), m.group(2)))

    def find(self, pattern, start=0):
        """pattern（正規表現）で始まる見出しの位置（heads の番号）。無ければ None。"""
        for k in range(start, len(self.heads)):
            if re.match(pattern, self.heads[k][2]):
                return k
        return None

    def body(self, k, stop_level=None):
        """見出し k の本文（次の同格以上の見出しの手前まで）。"""
        i, level, _ = self.heads[k]
        stop = level if stop_level is None else stop_level
        end = len(self.lines)
        for j, lv, _t in self.heads[k + 1:]:
            if lv <= stop:
                end = j
                break
        return "\n".join(self.lines[i + 1:end])

    def block(self, k):
        """見出し k の直後から、次の見出し（どの段でも）の手前まで。"""
        return self.body(k, stop_level=6)

    def bullets(self, k, block=False):
        text = self.block(k) if block else self.body(k)
        return [ln for ln in text.split("\n") if re.match(r"^\s{0,1}[-*・]\s+\S", ln)]

    def tables(self, text=None):
        """表（区切り行 |---| を持つかたまり）の数。"""
        t = self.text if text is None else text
        return len(re.findall(r"^\s*\|?\s*:?-{3,}:?\s*\|", t, flags=re.M))


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def require_headings(doc, r, spec, where="見出し"):
    """spec: [(id, 正規表現, 必須か)]。順番どおりに並んでいるかを見て、id→heads の番号を返す。"""
    pos, last, last_id = {}, -1, None
    for sid, pat, required in spec:
        k = doc.find(pat)
        if k is None:
            if required:
                r.check(False, where, "見出しがありません：%s" % sid)
            continue
        r.ok += 1
        pos[sid] = k
        if k < last:
            r.check(False, where, "見出しの順番がひな形と違います：「%s」が「%s」より前にあります" % (sid, last_id))
        else:
            last, last_id = k, sid
    return pos


# ---------------------------------------------------------------- 半導体 日次
SEMI_ALIAS = {
    "^GSPC": ["S&P 500", "S&P500", "SPX", "^GSPC"], "^SOX": ["SOX"], "^VIX": ["VIX"], "^TNX": ["US10Y", "10年金利", "^TNX", "10年"],
    "USDJPY=X": ["USD/JPY", "ドル円", "USDJPY"], "KRW=X": ["USD/KRW", "ウォン", "KRW"],
    "000660.KS": ["SK hynix", "SKハイニックス", "000660"], "005930.KS": ["Samsung", "サムスン", "005930"],
    "285A.T": ["Kioxia", "キオクシア", "285A"], "2408.TW": ["Nanya", "南亜", "2408"], "2344.TW": ["Winbond", "華邦", "2344"],
    "SEMIS": ["半導体", "セクター", "SEMIS"], "S_score": ["Sスコア", "S スコア"], "D_score": ["Dスコア", "D スコア"],
    "TECHNICAL": ["TECHNICAL", "値動きの合計", "テクニカル"], "M_score": ["Mスコア", "M スコア"],
}
SEMI_DAILY_HEADS = [
    ("今日のひとこと", r"今日のひとこと", True), ("なぜその判断か", r"なぜその判断か", True), ("前日から変わった点", r"前日から変わった点", True),
    ("0. セクターの状態", r"0\.\s*セクターの状態", True), ("1. 本日のシグナル", r"1\.\s*本日のシグナル", True), ("2. 解釈", r"2\.\s*解釈", True),
    ("2b. 戻りの質", r"2b\.\s*戻りの質", True), ("3. 市場表", r"3\.\s*市場表", True), ("4. メモリー株", r"4\.\s*メモリー株", True),
    ("4b. セクター内の強弱と調整耐性", r"4b\.\s*セクター内の強弱", True), ("4c. 川下", r"4c\.\s*川下", True), ("5. 意識される水準", r"5\.\s*意識される水準", True),
    ("6. RS線", r"6\.\s*RS線", True), ("6b. 市場全体とテック内部", r"6b\.\s*市場全体とテック内部", True), ("7. 重要ニュース", r"7\.\s*重要ニュース", True),
    ("8. 今日・明日のイベント", r"8\.\s*(当時の)?今日・明日のイベント", True), ("9. 週次判定との整合", r"9\.\s*週次判定との整合", True),
    ("10. データ監査", r"10\.\s*データ監査", True), ("読み方", r"読み方", True),
]


def names_of(ticker):
    return SEMI_ALIAS.get(ticker, []) + [ticker]


def mentioned(text, ticker):
    return any(n in text for n in names_of(ticker))


def check_semis_daily(doc, r, a):
    backfill = "補完版" in "\n".join(doc.lines[:6])
    r.check(bool(doc.heads) and doc.heads[0][1] == 1 and "日次" in doc.heads[0][2], "題", "1行目が「# 半導体・メモリー定点観測｜日次 <基準日>（米国終値）」の形ではありません")
    pos = require_headings(doc, r, SEMI_DAILY_HEADS)
    sig = load_json(os.path.join(a.data, "daily_signals.json")) if a.data else None
    if a.data and sig is None:
        r.check(False, "データ", "daily_signals.json を読めません（--data の場所を確かめる）", WARN)
    as_of = (sig or {}).get("us_as_of")
    if as_of:
        r.check(as_of in doc.heads[0][2] if doc.heads else False, "題", "題の基準日がデータの us_as_of（%s）と違います" % as_of)

    k = pos.get("今日のひとこと")
    if k is not None:
        b = "\n".join(doc.bullets(k, block=True))
        for label in ("半導体", "メモリー", "行動の目安"):
            r.check(re.search(r"^\s*[-*・]\s*\**\s*%s[^：:\n]{0,60}[：:]" % label, b, flags=re.M) is not None, "今日のひとこと", "「%s：」の行がありません" % label)
    k = pos.get("なぜその判断か")
    if k is not None:
        n = len(doc.bullets(k, block=True))
        r.check(3 <= n <= 6, "なぜその判断か", "3〜5行の決まりに対して %d 行です" % n, WARN if n >= 3 else FAIL)
    k = pos.get("前日から変わった点")
    if k is not None:
        body = doc.block(k).strip()
        n = len(doc.bullets(k, block=True))
        r.check(bool(body), "前日から変わった点", "中身がありません（変化が無い日は「前日から状態の変化なし」の1行）")
        r.check(n <= 8, "前日から変わった点", "3〜6行の決まりに対して %d 行です" % n, WARN)

    k = pos.get("0. セクターの状態")
    if k is not None:
        body = doc.body(k)
        if "未取得" not in body[:200]:
            r.check("危険の目安" in body, "0節", "「危険の目安」がありません")
            r.check("底の目安" in body, "0節", "「底の目安」がありません")
            r.check("公式ステージ" in body or "公式" in body, "0節", "公式ステージの行（取れない日は「公式ステージ：取得できず」）がありません")
            sh = (sig or {}).get("sector_health") or {}
            if sh.get("risk_count") is not None:
                r.check(re.search(r"%s\s*/\s*3" % sh["risk_count"], norm(body)) is not None, "0節", "危険の目安のそろい数がデータ（%s/3）と合いません" % sh["risk_count"])
            if sh.get("washout_count") is not None:
                r.check(re.search(r"%s\s*/\s*3" % sh["washout_count"], norm(body)) is not None, "0節", "底の目安のそろい数がデータ（%s/3）と合いません" % sh["washout_count"])
            ph = (sh.get("washout_phase") or {}).get("ja")
            if ph and (sh.get("washout_phase") or {}).get("code") not in (None, "none"):
                parts = [x for x in re.split(r"[・／/、]", ph) if len(x) >= 2]
                r.check(any(x in body for x in parts), "0節", "底の局面（%s）が書かれていません" % ph)

    k = pos.get("1. 本日のシグナル")
    if k is not None and sig is not None:
        head, body = doc.heads[k][2], doc.body(k)
        signals = sig.get("signals") or []
        if not signals:
            r.check("検出なし" in body, "1節", "シグナルが0件の日は「検出なし」と書きます")
        else:
            counts = {}
            for s in signals:
                counts[s.get("severity")] = counts.get(s.get("severity"), 0) + 1
            for sev in ("high", "medium", "low"):
                if counts.get(sev):
                    m = re.search(r"%s\s*(\d+)\s*件" % sev, norm(head))
                    r.check(m is not None and int(m.group(1)) == counts[sev], "1節", "見出しの %s の件数がデータ（%d件）と合いません" % (sev, counts[sev]))
            missing = sorted({s.get("ticker") for s in signals if s.get("ticker") and not mentioned(body, s["ticker"])})
            r.check(not missing, "1節", "シグナルのある銘柄が載っていません（全件を並べる決まり）：%s" % "、".join(missing))

    table = {row.get("ticker"): row for row in (sig or {}).get("table") or []}

    def rows(sec_id, where, tickers, fields):
        k = pos.get(sec_id)
        if k is None:
            return
        body = doc.body(k)
        nums = numbers(body)
        for t in tickers:
            if not r.check(mentioned(body, t), where, "行がありません：%s" % names_of(t)[0]):
                continue
            row = table.get(t)
            if not row:
                continue
            for f in fields:
                v = row.get(f)
                if v is None:
                    continue
                ok = has_number(nums, v) or (t == "^TNX" and has_number(nums, v / 10.0))
                r.check(ok, where, "%s の %s がデータ（%s）と合う数字で見つかりません" % (names_of(t)[0], f, v), WARN)

    rows("3. 市場表", "3節", ["^GSPC", "QQQ", "^SOX", "SOXX", "SMH", "DRAM", "SOXL", "^VIX", "^TNX", "USDJPY=X", "KRW=X"], ["close", "ret_1d"])
    rows("4. メモリー株", "4節", ["MU", "SNDK", "SKHY", "WDC", "STX", "000660.KS", "005930.KS", "285A.T", "2408.TW", "2344.TW"], ["ret_1d"])
    k = pos.get("5. 意識される水準")
    if k is not None:
        body, wl = doc.body(k), (sig or {}).get("watch_levels") or {}
        nums = numbers(body)
        for t in ["^SOX", "SOXX", "SMH", "SOXL", "DRAM", "MU", "SNDK", "SKHY"]:
            if r.check(mentioned(body, t), "5節", "行がありません：%s" % names_of(t)[0]) and t in wl:
                r.check(has_number(nums, wl[t].get("close")), "5節", "%s の終値がデータ（%s）と合う数字で見つかりません" % (names_of(t)[0], wl[t].get("close")), WARN)

    k = pos.get("2b. 戻りの質")
    if k is not None:
        body = doc.body(k)
        r.check(bool(body.strip()), "2b節", "中身がありません（調整局面でない日・未取得の日も1行書きます）")
    k = pos.get("4c. 川下")
    if k is not None:
        body = doc.body(k)
        if "未取得" not in body:
            for t in ["CRWV", "NBIS", "IREN", "GLXY", "VRT"]:
                r.check(t in body, "4c節", "行がありません：%s" % t)
    k = pos.get("6. RS線")
    if k is not None:
        body = doc.body(k)
        for t in ["SOXX", "SMH", "DRAM", "NVDA", "TSM", "MU", "SNDK", "SKHY"]:
            r.check(t in body, "6節", "表に行がありません：%s" % t)
        r.check("RS線は強い銘柄を拾う道具" in body, "6節", "読み方の1行（「RS線は強い銘柄を拾う道具で…」）がありません")
    k = pos.get("6b. 市場全体とテック内部")
    if k is not None:
        body = doc.body(k)
        if "取得できず" not in body[:120]:
            r.check("テック内部" in body, "6b節", "「テック内部」の行がありません")
            if not backfill:
                r.check("買い戻しの燃料" in body, "6b節", "「買い戻しの燃料」の行がありません（取れない日は「買い戻しの燃料：未取得」）")
    k = pos.get("7. 重要ニュース")
    if k is not None:
        body = doc.body(k)
        if backfill:
            r.check("省略" in body, "7節", "補完版は「補完のため省略」と書きます")
        else:
            items = re.findall(r"^\s*(?:\d+[.．)]|[-*・])\s+\*{0,2}\S", body, flags=re.M)
            n_num = len(re.findall(r"^\s*\d+[.．)]\s+\S", body, flags=re.M))
            r.check(bool(body.strip()), "7節", "中身がありません")
            r.check(n_num <= 5, "7節", "最大5件の決まりに対して %d 件あります" % n_num)
            if items:
                r.check("http" in body or "出典" in body, "7節", "出典（URLと発表日）がありません")
    for sid, where in (("8. 今日・明日のイベント", "8節"), ("9. 週次判定との整合", "9節"), ("10. データ監査", "10節")):
        k = pos.get(sid)
        if k is not None:
            r.check(bool(doc.body(k).strip()), where, "中身がありません")
    k = pos.get("10. データ監査")
    if k is not None and as_of:
        r.check(as_of in doc.body(k) or as_of[5:].replace("-", "/") in doc.body(k), "10節", "基準日（%s）が書かれていません" % as_of, WARN)
    k = pos.get("読み方")
    if k is not None:
        body = doc.body(k)
        r.check(len(doc.bullets(k)) >= 3 or len(body.strip()) > 80, "読み方", "使った記号の説明がありません")
        r.check("高値比" in body and "終値でみた最高値" in body, "読み方", "決まりの1行（「高値比＝終値でみた最高値からの下落率。…」）がありません")

    common_wording(doc, r)
    n = len(doc.text)
    r.check(n <= 13000, "分量", "本文が %d 字あります（目安は約9,000字。変化の無い節を短縮形に）" % n, WARN)
    core = doc.text
    for sid in ("2b. 戻りの質", "8. 今日・明日のイベント"):
        if sid in pos:
            core = core.replace(doc.body(pos[sid]), "")
    r.check(doc.tables(core) <= 5, "分量", "表が %d 個あります（5つまで。2b節と8節の表は数えない）" % doc.tables(core), WARN)


def common_wording(doc, r):
    t = doc.text
    r.check("過去5回で外れなし" not in t and "だまし0%" not in norm(t), "言い方", "「過去5回で外れなし」「だまし0%」は書きません")
    m = re.search(r"普段の\s*[0-9.]+\s*倍", norm(t))
    r.check(m is None, "言い方", "倍率に基準がありません（「20日平均の○倍」「50日平均の○倍」と書く）：%s" % (m.group(0) if m else ""))
    for ln in doc.lines:
        if re.search(r"(買い|売り)シグナル", ln) and not re.search(r"ではな|としない|と書かな|ではありません|でなく", ln):
            r.check(False, "言い方", "「買いシグナル」「売りシグナル」と言い切っていないか確かめる：%s" % ln.strip()[:60], WARN)
            break
    for ln in doc.lines:
        s = ln.strip()
        if s.startswith(("-", "・")) and re.fullmatch(r"[-・]\s*[A-Z][A-Z0-9_]{0,5}\s*(が|＝|=|:|：)\s*[-−+]?\d+(\.\d+)?", s):
            r.check(False, "言い方", "記号だけで状態を言っている行があります（言葉を先に、記号は括弧）：%s" % s[:40], WARN)
            break


# ---------------------------------------------------------------- 配信の文
def check_delivery(text, r, a):
    body = text.strip()
    url_free = re.sub(r"https?://\S+", "", body)
    n = len(re.sub(r"\s", "", url_free))
    r.check(n <= a.max, "配信", "%d 字あります（上限 %d 字。全文は添付にあるので、判断に要るものだけに）" % (n, a.max))
    r.check(n >= 150, "配信", "短すぎます（%d 字）。冒頭ブロックと変わった点が入っているか確かめる" % n, WARN)
    if a.link:
        tail = "\n".join([ln for ln in body.split("\n") if ln.strip()][-2:])
        r.check(a.link in tail, "配信", "最後の行に保管ページのリンクがありません：%s" % a.link)
    r.check("今日のひとこと" in body or "ひとこと" in body or body.count("\n- ") + body.count("\n・") >= 3, "配信", "冒頭ブロック（今日のひとこと）が見当たりません", WARN)


KINDS = {"semis_daily": check_semis_daily}


def main():
    ap = argparse.ArgumentParser(description="レポートの点検（見出し・表の行・全件・数字・言い方）")
    ap.add_argument("kind", choices=sorted(KINDS) + ["delivery"])
    ap.add_argument("path")
    ap.add_argument("--data", help="data ブランチのクローンの場所")
    ap.add_argument("--mkt", help="market-data の signals.json（半導体のレポートで使う）")
    ap.add_argument("--max", type=int, default=1200, help="配信の文の上限（字）")
    ap.add_argument("--link", help="配信の最後の行に入れる保管ページのURL")
    a = ap.parse_args()
    try:
        with open(a.path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print("不合格｜ファイル｜読めません：%s" % e)
        return 1
    r = Result()
    if a.kind == "delivery":
        check_delivery(text, r, a)
        return r.report("配信の文の点検")
    KINDS[a.kind](Doc(text), r, a)
    return r.report("点検（%s）" % a.kind)


if __name__ == "__main__":
    sys.exit(main())
