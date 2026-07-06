#!/usr/bin/env python3
"""生成 data.json：非农 / CPI / FOMC / CME(ES/NQ)假期。

数据源（均为权威源，互相独立，某个失败不影响其余）：
  - FOMC       : 美联储官网 FOMC 日历页（解析会议日）
  - 非农 / CPI : FRED API（圣路易斯联储，记录 BLS 官方发布日）——需环境变量 FRED_API_KEY
  - CME 假期   : 脚本内手工核准的 CME_HOLIDAYS 显式表（逐年逐条交叉核对，见下方注释）

用法：
  FRED_API_KEY=xxxx python3 scripts/fetch_data.py
  # 可选：YEARS=2026,2027 指定生成年份（默认当年 + 次年）
"""

import datetime
import json
import os
import re
import ssl
import sys
import urllib.request

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSL_CTX = ssl.create_default_context()

_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149 Safari/537.36"}
MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}


def http_get(url):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, context=_SSL_CTX, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


def _nth_weekday(year, month, weekday, n):
    """某年某月第 n 个 weekday（周一=0…周日=6）的日期。"""
    first = datetime.date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + datetime.timedelta(days=offset + 7 * (n - 1))


# ---------------------------------------------------------------- FOMC
def fetch_fomc(years):
    """从美联储日历页解析各年 FOMC 会议，声明日 = 会议第二天 14:00 ET。"""
    html = http_get("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm")
    events = []
    for year in years:
        i = html.find(f"{year} FOMC Meetings")
        if i < 0:
            continue
        # 该年区块到下一年区块为止
        nxt = html.find("FOMC Meetings", i + 10)
        seg = html[i:nxt if nxt > 0 else i + 6000]
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", seg))
        # 匹配 "January 27-28" 或跨月 "January 31-February 1"
        pat = re.compile(
            r"(" + "|".join(MONTHS) + r")\s+(\d{1,2})-(?:(" + "|".join(MONTHS) + r")\s+)?(\d{1,2})")
        for m in pat.finditer(text):
            m1, d1, m2, d2 = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
            end_month = MONTHS[m2] if m2 else MONTHS[m1]
            date = datetime.date(year, end_month, d2)
            events.append({
                "date": date.isoformat(),
                "name": "FOMC Statement",
                "title": "FOMC Statement",
                "time": "2:00pm ET",
                "type": "economic",
                "desc": f"{date:%m/%d/%Y} at 2:00pm ET. 联邦公开市场委员会 (FOMC) 利率决议与政策声明.",
            })
    return events


# ---------------------------------------------------------------- FRED (非农 / CPI)
def _fred(path, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    return json.loads(http_get(f"https://api.stlouisfed.org/fred/{path}?{q}"))


def _release_id_for(series_id, key):
    data = _fred("series/release", series_id=series_id, api_key=key, file_type="json")
    return data["releases"][0]["id"]


def _release_dates(release_id, key, years):
    data = _fred("release/dates", release_id=release_id, api_key=key, file_type="json",
                 include_release_dates_with_no_data="true",
                 realtime_start=f"{min(years)}-01-01", realtime_end=f"{max(years)}-12-31",
                 limit="1000")
    out = []
    for d in data.get("release_dates", []):
        y = int(d["date"][:4])
        if y in years:
            out.append(d["date"])
    return sorted(set(out))


def fetch_bls(years, key):
    """非农（Employment Situation）+ CPI 发布日，来自 FRED（BLS 官方记录），8:30am ET。"""
    events = []
    specs = [
        ("PAYEMS", "Non-Farm Employment Change", "美国非农就业数据发布, 市场高波动事件.", "economic"),
        ("CPIAUCSL", "CPI | Consumer Price Index", "美国消费者物价指数 (CPI) 发布.", "economic"),
        ("PCEPILFE", "PCE | Core PCE Price Index", "核心 PCE 物价指数, 美联储首选通胀指标, 早盘或放量.", "pce"),
    ]
    for series_id, name, zh, etype in specs:
        rid = _release_id_for(series_id, key)
        for ds in _release_dates(rid, key, years):
            events.append({
                "date": ds, "name": name, "title": name, "time": "8:30am ET", "type": etype,
                "desc": f"{datetime.date.fromisoformat(ds):%m/%d/%Y} at 8:30am ET. {zh}",
            })
    return events


# ---------------------------------------------------------------- CME 假期
# CME Globex 股指期货（ES/NQ）假期表：逐年逐条核对的确定清单（非推算）。
# 官网封锁抓取、社区库有遗漏（漏 Juneteenth），故采用核准过的显式表。
# kind: "full" = 全天休市；"early" = 提前收盘（约 13:00 ET）。
# 每年刷新时在此新增下一年并核对。
CME_HOLIDAYS = {
    # (日期, 中文名, 英文名, kind)
    2026: [
        ("2026-01-01", "元旦", "New Year's Day", "full"),
        ("2026-01-19", "马丁·路德·金纪念日", "Martin Luther King Jr. Day", "early"),
        ("2026-02-16", "总统日", "Presidents' Day", "early"),
        ("2026-04-03", "耶稣受难日", "Good Friday", "full"),
        ("2026-05-25", "阵亡将士纪念日", "Memorial Day", "early"),
        ("2026-06-19", "六月节", "Juneteenth", "early"),
        ("2026-07-03", "独立日", "Independence Day", "early"),
        ("2026-09-07", "劳动节", "Labor Day", "early"),
        ("2026-11-26", "感恩节", "Thanksgiving Day", "early"),
        ("2026-11-27", "黑色星期五", "Black Friday", "early"),
        ("2026-12-24", "平安夜", "Christmas Eve", "early"),
        ("2026-12-25", "圣诞节", "Christmas Day", "full"),
    ],
}


def fetch_cme(years):
    """CME Globex 股指（ES/NQ）全休日 + 提前收盘日，来自核准过的显式表。"""
    events = []
    for year in years:
        table = CME_HOLIDAYS.get(year)
        if table is None:
            raise RuntimeError(f"{year} 的 CME 假期表未核对，请更新 CME_HOLIDAYS")
        for ds, zh, en, kind in table:
            d = datetime.date.fromisoformat(ds)
            if kind == "full":
                events.append({
                    "date": ds, "name": en, "title": en, "time": "", "type": "holiday",
                    "desc": f"{d:%m/%d/%Y}. {zh}, 美股与股指期货全天休市.",
                })
            else:
                events.append({
                    "date": ds, "name": en, "title": en, "time": "提前收盘", "type": "early_close",
                    "desc": f"{d:%m/%d/%Y}. {zh}, 股指期货提前收盘 (约 13:00 ET).",
                })
    return events


# ---------------------------------------------------------------- ES/NQ 换月周
def fetch_contract_roll(years):
    """ES/NQ 季度合约换月周锚点 = 到期月(3/6/9/12)第三个周五所在周的周一。

    这是"换月周·开始盯量"的提醒，不是精确执行日：实际成交量向次月转移是
    渐进过程（机构先动持仓、日内散户约到期前一周才跟上），应以次月成交量
    超过近月为准再切。故只标一个锚点周一，说明里提示按盘面量确认。
    """
    events = []
    for year in years:
        for month in (3, 6, 9, 12):
            monday = _nth_weekday(year, month, 4, 3) - datetime.timedelta(days=4)
            events.append({
                "date": monday.isoformat(),
                "name": "Roll Week",
                "title": "Roll Week",
                "time": "",
                "type": "roll",
                "desc": f"{monday:%m/%d/%Y}. ES/NQ 换合约周. "
                        f"以次月成交量超过近月为准再切.",
            })
    return events


# ---------------------------------------------------------------- main
def _load_dotenv():
    """读取项目根目录下 .env（仅本地用，已被 .gitignore 忽略）。"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, ".env")
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def main():
    _load_dotenv()
    years_env = os.environ.get("YEARS")
    if years_env:
        years = [int(y) for y in years_env.split(",")]
    else:
        # 默认只生成已核对 CME 假期表的年份（见 CME_HOLIDAYS）
        years = [datetime.date.today().year]
    years = sorted(set(years))

    key = os.environ.get("FRED_API_KEY")
    events = []

    for label, fn in [
        ("FOMC", lambda: fetch_fomc(years)),
        ("CME", lambda: fetch_cme(years)),
        ("Roll", lambda: fetch_contract_roll(years)),
        ("BLS(FRED)", lambda: fetch_bls(years, key) if key else _need_key()),
    ]:
        try:
            got = fn()
            events += got
            print(f"[ok] {label}: {len(got)} 条", file=sys.stderr)
        except Exception as e:
            print(f"[FAIL] {label}: {e}", file=sys.stderr)

    events.sort(key=lambda e: (e["date"], e["name"]))

    problems = sanity_check(events, years)
    if problems:
        print("⚠️ 离线体检发现问题：", file=sys.stderr)
        for p in problems:
            print("   -", p, file=sys.stderr)
    else:
        print(f"离线体检通过（{len(events)} 条）", file=sys.stderr)

    out = {"generated": datetime.date.today().isoformat(),
           "years": years, "events": events}
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "data.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"写入 {path}：{len(events)} 条事件，年份 {years}", file=sys.stderr)


def _need_key():
    raise RuntimeError("未设置 FRED_API_KEY，跳过非农/CPI")


def sanity_check(events, years):
    """离线体检：不联网，只查会真出问题的几种情况，绝不误报。"""
    from collections import Counter
    problems = []

    # 1) 数量：每年非农/CPI 应各 12、FOMC 应 8（源抓取失败=0 则跳过不报）
    for y in years:
        cnt = Counter()
        for e in events:
            if not e["date"].startswith(str(y)):
                continue
            if e["name"].startswith("Non-Farm"):
                cnt["非农"] += 1
            elif e["name"].startswith("CPI"):
                cnt["CPI"] += 1
            elif e["name"] == "FOMC Statement":
                cnt["FOMC"] += 1
            elif e["name"] == "Roll Week":
                cnt["换月周"] += 1
        for k, expect in (("非农", 12), ("CPI", 12), ("FOMC", 8), ("换月周", 4)):
            if cnt[k] and cnt[k] != expect:
                problems.append(f"{y} 年 {k} 数量异常：{cnt[k]}（应为 {expect}）")

    # 2) 周末：所有事件都应落在工作日
    for e in events:
        if datetime.date.fromisoformat(e["date"]).weekday() >= 5:
            problems.append(f'{e["date"]} {e["name"]} 落在周末')

    # 3) 重复：同一天同一事件出现多次
    for key, n in Counter((e["date"], e["name"]) for e in events).items():
        if n > 1:
            problems.append(f"重复事件：{key[0]} {key[1]} ×{n}")

    # 4) 年份越界
    for e in events:
        if int(e["date"][:4]) not in years:
            problems.append(f'{e["date"]} {e["name"]} 超出年份范围 {years}')

    return problems


if __name__ == "__main__":
    main()
