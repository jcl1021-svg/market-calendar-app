# 邮件提醒 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在日历事件前一天北京时间中午 12:00，自动发一封提醒邮件到用户 Gmail。

**Architecture:** 新增一个 GitHub Actions 每日定时任务（04:00 UTC = 北京 12:00），跑纯 Python 标准库脚本 `scripts/send_reminder.py`：读现成 `data.json`，筛出"明天"的事件，拼中文邮件，走 Gmail SMTP 发出。无事件则不发。加 keepalive 动作防 GitHub 60 天自动禁用。

**Tech Stack:** Python 3（仅标准库：`smtplib` / `email` / `datetime` / `argparse` / `json` / `re`），`unittest`（stdlib，不引入新依赖），GitHub Actions。keepalive 用内联 git 空提交实现（原第三方 action `gautamkrishnar/keepalive-workflow` 已被 GitHub 因 TOS 封禁，不可用）。

**设计文档：** `docs/superpowers/specs/2026-07-03-email-reminders-design.md`

**提交约定：** 本计划**不含任何 git 提交步骤**。全部任务完成、用户验收后，由用户自行提交（格式 `2026.MM.DD-增加邮件提醒`）。

---

## 文件结构

- **Create** `scripts/send_reminder.py` — 提醒脚本（纯函数 + SMTP 发送 + CLI）。唯一职责：把"某日的事件列表"变成一封邮件并（可选）发出。
- **Create** `tests/test_send_reminder.py` — `unittest` 单元测试，覆盖全部纯函数与无事件路径。
- **Create** `.github/workflows/reminder.yml` — 每日定时触发 + keepalive。
- **不改** `data.json` / `app.js` / `index.html` / `fetch_data.py`（提醒只读数据，不碰网页与生成器）。

`send_reminder.py` 函数清单（后续任务逐个实现）：
`_nth_weekday` · `us_eastern_offset` · `parse_et_time` · `beijing_from_et` · `chinese_part` · `subject_label` · `body_line` · `select_events` · `build_subject` · `build_body` · `load_events` · `send_email` · `main`

模块级常量：
```python
WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]  # 对应 date.weekday()：周一=0
CAL_URL = "https://jcl1021-svg.github.io/market-calendar-app/"
SUBJECT_LABELS = {
    "Non-Farm Employment Change": "非农",
    "CPI | Consumer Price Index": "CPI",
    "FOMC Statement": "FOMC",
}
```

---

## Task 1: 建脚本骨架与时区换算（EDT/EST → 北京）

**Files:**
- Create: `scripts/send_reminder.py`
- Create: `tests/test_send_reminder.py`

- [ ] **Step 1: 写 `send_reminder.py` 骨架 + 时区函数**

创建 `scripts/send_reminder.py`，写入：

```python
#!/usr/bin/env python3
"""事件前一天发提醒邮件：读 data.json，筛出目标日事件，拼中文邮件并发送。

用法：
  python3 scripts/send_reminder.py                 # 目标=UTC 明天，发信（需 Gmail 凭证）
  python3 scripts/send_reminder.py --dry-run       # 只打印不发
  python3 scripts/send_reminder.py --dry-run --date 2026-07-29  # 指定目标日
"""

import argparse
import json
import os
import re
import smtplib
import ssl
from datetime import date, datetime, timedelta
from email.message import EmailMessage

WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]  # date.weekday()：周一=0
CAL_URL = "https://jcl1021-svg.github.io/market-calendar-app/"
SUBJECT_LABELS = {
    "Non-Farm Employment Change": "非农",
    "CPI | Consumer Price Index": "CPI",
    "FOMC Statement": "FOMC",
}


def _nth_weekday(year, month, weekday, n):
    """返回某年某月第 n 个 weekday（周一=0…周日=6）的日期。"""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def us_eastern_offset(d):
    """d 当天的美东 UTC 偏移：夏令时 -4（EDT），否则 -5（EST）。

    夏令时区间 = 3 月第 2 个周日 至 11 月第 1 个周日。事件都在工作日，
    绝不会落在切换当天（周日），故按天粒度判断即可。
    """
    dst_start = _nth_weekday(d.year, 3, 6, 2)   # 3 月第 2 个周日
    dst_end = _nth_weekday(d.year, 11, 6, 1)    # 11 月第 1 个周日
    return -4 if dst_start <= d < dst_end else -5
```

- [ ] **Step 2: 写失败测试**

创建 `tests/test_send_reminder.py`，写入：

```python
import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import send_reminder as sr  # noqa: E402


class TestTimezone(unittest.TestCase):
    def test_est_in_winter(self):
        self.assertEqual(sr.us_eastern_offset(date(2026, 1, 15)), -5)

    def test_edt_in_summer(self):
        self.assertEqual(sr.us_eastern_offset(date(2026, 7, 15)), -4)

    def test_nth_weekday_second_sunday_march_2026(self):
        # 2026 年 3 月第 2 个周日 = 3 月 8 日
        self.assertEqual(sr._nth_weekday(2026, 3, 6, 2), date(2026, 3, 8))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: 跑测试确认通过**

Run: `python3 -m unittest discover -s tests -v`
Expected: 3 个测试 PASS（函数已在 Step 1 写好）。

---

## Task 2: 解析 ET 时间 + 换算北京时间

**Files:**
- Modify: `scripts/send_reminder.py`（追加函数）
- Modify: `tests/test_send_reminder.py`（追加测试类）

- [ ] **Step 1: 追加 `parse_et_time` 与 `beijing_from_et`**

在 `send_reminder.py` 的 `us_eastern_offset` 之后追加：

```python
def parse_et_time(time_str):
    """"8:30am ET" -> (8, 30)；"2:00pm ET" -> (14, 0)；无时钟时间（"" / "提前收盘"）-> None。"""
    m = re.match(r"\s*(\d{1,2}):(\d{2})\s*(am|pm)", time_str or "", re.I)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2)), m.group(3).lower()
    if ap == "pm" and h != 12:
        h += 12
    elif ap == "am" and h == 12:
        h = 0
    return h, mi


def beijing_from_et(date_iso, h, mi):
    """把某美东日期的 ET 时钟时间换成北京时间（naive datetime，可能滚到次日）。"""
    d = date.fromisoformat(date_iso)
    delta = 8 - us_eastern_offset(d)  # EDT->12h，EST->13h
    return datetime(d.year, d.month, d.day, h, mi) + timedelta(hours=delta)
```

- [ ] **Step 2: 追加失败测试**

在 `tests/test_send_reminder.py` 末尾（`if __name__` 之前）追加：

```python
class TestTimeParse(unittest.TestCase):
    def test_parse_am(self):
        self.assertEqual(sr.parse_et_time("8:30am ET"), (8, 30))

    def test_parse_pm(self):
        self.assertEqual(sr.parse_et_time("2:00pm ET"), (14, 0))

    def test_parse_none(self):
        self.assertIsNone(sr.parse_et_time("提前收盘"))
        self.assertIsNone(sr.parse_et_time(""))


class TestBeijing(unittest.TestCase):
    def test_economic_winter_same_day(self):
        # 冬令时 EST：8:30am ET + 13h = 当天 21:30 北京
        from datetime import datetime as dt
        self.assertEqual(sr.beijing_from_et("2026-01-09", 8, 30), dt(2026, 1, 9, 21, 30))

    def test_fomc_summer_next_day(self):
        # 夏令时 EDT：2:00pm ET + 12h = 次日 02:00 北京
        from datetime import datetime as dt
        self.assertEqual(sr.beijing_from_et("2026-07-29", 14, 0), dt(2026, 7, 30, 2, 0))
```

- [ ] **Step 3: 跑测试确认通过**

Run: `python3 -m unittest discover -s tests -v`
Expected: 全部 PASS（新增 5 个）。

---

## Task 3: 文本处理（中文说明 / 主题标签 / 正文行）

**Files:**
- Modify: `scripts/send_reminder.py`（追加函数）
- Modify: `tests/test_send_reminder.py`（追加测试类）

- [ ] **Step 1: 追加 `chinese_part` / `subject_label` / `body_line`**

在 `beijing_from_et` 之后追加：

```python
def chinese_part(desc):
    """desc 形如 "01/09/2026 at 8:30am ET. 美国非农…" 或 "01/01/2026. 元旦…"，
    去掉开头的美国日期/时间前缀，只留中文说明。"""
    parts = desc.split(". ", 1)
    return parts[1] if len(parts) == 2 else desc


def subject_label(ev):
    """主题里的简短标签：非农/CPI/FOMC 用中文缩写，假期用英文名+休市标记。"""
    base = SUBJECT_LABELS.get(ev["name"], ev.get("title") or ev["name"])
    if ev["type"] == "holiday":
        return base + "（休市）"
    if ev["type"] == "early_close":
        return base + "（提前收盘）"
    return base


def body_line(ev):
    """正文里单个事件的多行文本。"""
    title = ev.get("title") or ev["name"]
    zh = chinese_part(ev["desc"])
    if ev["type"] == "holiday":
        return f"• {title} — 全天休市\n  {zh}"
    if ev["type"] == "early_close":
        return f"• {title} — 提前收盘\n  {zh}"
    hm = parse_et_time(ev.get("time", ""))
    if hm:
        bj = beijing_from_et(ev["date"], *hm)
        return f"• {title}\n  美东 {ev['time']}（北京 {bj:%m/%d} 约 {bj:%H:%M}）\n  {zh}"
    return f"• {title}\n  {zh}"
```

- [ ] **Step 2: 追加失败测试**

在测试文件末尾追加。样例事件放在测试类里，字段与 `data.json` 完全一致：

```python
NFP = {
    "date": "2026-01-09", "name": "Non-Farm Employment Change",
    "title": "Non-Farm Employment Change", "time": "8:30am ET", "type": "economic",
    "desc": "01/09/2026 at 8:30am ET. 美国非农就业数据发布, 市场高波动事件.",
}
FOMC = {
    "date": "2026-07-29", "name": "FOMC Statement",
    "title": "FOMC Statement", "time": "2:00pm ET", "type": "economic",
    "desc": "07/29/2026 at 2:00pm ET. 联邦公开市场委员会 (FOMC) 利率决议与政策声明.",
}
XMAS = {
    "date": "2026-12-25", "name": "Christmas Day",
    "title": "Christmas Day", "time": "", "type": "holiday",
    "desc": "12/25/2026. 圣诞节, 美股与股指期货全天休市.",
}
JULY4 = {
    "date": "2026-07-03", "name": "Independence Day",
    "title": "Independence Day", "time": "提前收盘", "type": "early_close",
    "desc": "07/03/2026. 独立日, 股指期货提前收盘 (约 13:00 ET).",
}


class TestText(unittest.TestCase):
    def test_chinese_part_economic(self):
        self.assertEqual(sr.chinese_part(NFP["desc"]), "美国非农就业数据发布, 市场高波动事件.")

    def test_chinese_part_holiday(self):
        self.assertEqual(sr.chinese_part(XMAS["desc"]), "圣诞节, 美股与股指期货全天休市.")

    def test_subject_label_economic(self):
        self.assertEqual(sr.subject_label(NFP), "非农")
        self.assertEqual(sr.subject_label(FOMC), "FOMC")

    def test_subject_label_holiday(self):
        self.assertEqual(sr.subject_label(XMAS), "Christmas Day（休市）")

    def test_subject_label_early(self):
        self.assertEqual(sr.subject_label(JULY4), "Independence Day（提前收盘）")

    def test_body_line_economic(self):
        line = sr.body_line(NFP)
        self.assertIn("• Non-Farm Employment Change", line)
        self.assertIn("美东 8:30am ET（北京 01/09 约 21:30）", line)
        self.assertIn("美国非农就业数据发布, 市场高波动事件.", line)

    def test_body_line_holiday(self):
        self.assertEqual(
            sr.body_line(XMAS),
            "• Christmas Day — 全天休市\n  圣诞节, 美股与股指期货全天休市.",
        )

    def test_body_line_early(self):
        self.assertEqual(
            sr.body_line(JULY4),
            "• Independence Day — 提前收盘\n  独立日, 股指期货提前收盘 (约 13:00 ET).",
        )
```

- [ ] **Step 3: 跑测试确认通过**

Run: `python3 -m unittest discover -s tests -v`
Expected: 全部 PASS。

---

## Task 4: 组装主题与正文 + 选事件

**Files:**
- Modify: `scripts/send_reminder.py`（追加函数）
- Modify: `tests/test_send_reminder.py`（追加测试类）

- [ ] **Step 1: 追加 `select_events` / `build_subject` / `build_body`**

在 `body_line` 之后追加：

```python
def select_events(events, target_iso):
    """筛出日期等于 target_iso 的事件，保持原顺序。"""
    return [e for e in events if e["date"] == target_iso]


def build_subject(events, target):
    """target 为 date 对象。"""
    labels = "、".join(subject_label(e) for e in events)
    return f"【美盘日历】明天 {target:%m/%d}（周{WEEKDAY_CN[target.weekday()]}）：{labels}"


def build_body(events):
    lines = "\n\n".join(body_line(e) for e in events)
    return f"明天有以下美盘事件：\n\n{lines}\n\n日历：{CAL_URL}"
```

- [ ] **Step 2: 追加失败测试**

在测试文件末尾追加：

```python
class TestAssemble(unittest.TestCase):
    def test_select_events(self):
        got = sr.select_events([NFP, FOMC, XMAS], "2026-07-29")
        self.assertEqual(got, [FOMC])

    def test_build_subject_single(self):
        self.assertEqual(
            sr.build_subject([NFP], date(2026, 1, 9)),
            "【美盘日历】明天 01/09（周五）：非农",
        )

    def test_build_subject_multi(self):
        self.assertEqual(
            sr.build_subject([NFP, FOMC], date(2026, 7, 29)),
            "【美盘日历】明天 07/29（周三）：非农、FOMC",
        )

    def test_build_body(self):
        body = sr.build_body([XMAS])
        self.assertTrue(body.startswith("明天有以下美盘事件：\n\n"))
        self.assertIn("• Christmas Day — 全天休市", body)
        self.assertTrue(body.endswith(f"日历：{sr.CAL_URL}"))
```

- [ ] **Step 3: 跑测试确认通过**

Run: `python3 -m unittest discover -s tests -v`
Expected: 全部 PASS。

---

## Task 5: 读数据 + SMTP 发送 + CLI 入口

**Files:**
- Modify: `scripts/send_reminder.py`（追加 `_load_dotenv` / `load_events` / `send_email` / `main` + `__main__`）
- Modify: `tests/test_send_reminder.py`（追加"无事件"冒烟测试）

- [ ] **Step 1: 追加数据读取、发信、主流程**

在 `build_body` 之后追加：

```python
def _load_dotenv():
    """本地跑真实发送时，从项目根 .env 读 GMAIL_* （已被 .gitignore 忽略）。"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, ".env")
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def load_events():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "data.json"), encoding="utf-8") as f:
        return json.load(f)["events"]


def send_email(subject, body):
    address = (os.environ.get("GMAIL_ADDRESS") or "").strip()          # 发件账号
    # 应用专用密码：Google 显示带空格，去掉空格更稳（正常应为 16 个英文小写字母）
    password = (os.environ.get("GMAIL_APP_PASSWORD") or "").replace(" ", "").strip()
    recipient = (os.environ.get("MAIL_TO") or "").strip() or address   # 收件地址；缺省则发给自己
    if not address or not password:
        raise RuntimeError("缺少 GMAIL_ADDRESS / GMAIL_APP_PASSWORD 环境变量")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = address
    msg["To"] = recipient
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(address, password)
        s.send_message(msg)


def main(argv=None):
    _load_dotenv()
    ap = argparse.ArgumentParser(description="发美盘事件提醒邮件")
    ap.add_argument("--dry-run", action="store_true", help="只打印邮件，不发送")
    ap.add_argument("--date", help="目标日期 YYYY-MM-DD（默认 = UTC 明天）")
    args = ap.parse_args(argv)

    target = (date.fromisoformat(args.date) if args.date
              else date.today() + timedelta(days=1))
    events = select_events(load_events(), target.isoformat())

    if not events:
        print(f"{target.isoformat()} 无事件，不发送。")
        return

    subject = build_subject(events, target)
    body = build_body(events)

    if args.dry_run:
        print("=== DRY RUN ===")
        print("Subject:", subject)
        print(body)
        return

    send_email(subject, body)
    print(f"已发送提醒：{subject}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 追加"无事件"冒烟测试**

用一个远期、`data.json` 里必然没有的日期，验证读数据 + 选事件 + 主流程的"不发送"分支，不依赖具体数据内容。在测试文件末尾追加：

```python
import contextlib
import io


class TestMainNoEvents(unittest.TestCase):
    def test_no_events_prints_and_returns(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            sr.main(["--dry-run", "--date", "2099-01-01"])
        self.assertIn("无事件", out.getvalue())
```

- [ ] **Step 3: 跑全部测试确认通过**

Run: `python3 -m unittest discover -s tests -v`
Expected: 全部 PASS。

- [ ] **Step 4: 手动 dry-run 核对真实数据的一条**

Run: `python3 scripts/send_reminder.py --dry-run --date 2026-07-29`
Expected: 打印
```
=== DRY RUN ===
Subject: 【美盘日历】明天 07/29（周三）：FOMC

明天有以下美盘事件：

• FOMC Statement
  美东 2:00pm ET（北京 07/30 约 02:00）
  联邦公开市场委员会 (FOMC) 利率决议与政策声明.

日历：https://jcl1021-svg.github.io/market-calendar-app/
```
人工确认主题、北京时间、中文说明、网址都对。

- [ ] **Step 5: 手动 dry-run 核对一个假期日**

Run: `python3 scripts/send_reminder.py --dry-run --date 2026-12-25`
Expected: 主题含 `Christmas Day（休市）`，正文含 `• Christmas Day — 全天休市`。

---

## Task 6: GitHub Actions 定时任务 + keepalive

**Files:**
- Create: `.github/workflows/reminder.yml`

- [ ] **Step 1: 写 workflow**

创建 `.github/workflows/reminder.yml`，写入：

```yaml
name: Daily market reminder

on:
  schedule:
    - cron: "0 4 * * *"   # 04:00 UTC = 北京 12:00（提前一天中午）
  workflow_dispatch:      # 允许在 Actions 页手动触发（测试用）
    inputs:
      date:
        description: "手动测试：目标日期 YYYY-MM-DD（留空=正常按明天）"
        required: false
        default: ""

permissions:
  contents: write         # keepalive 做空提交需要写权限

jobs:
  remind:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Send reminder
        env:
          GMAIL_ADDRESS: ${{ secrets.GMAIL_ADDRESS }}        # 发件小号
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
          MAIL_TO: ${{ secrets.MAIL_TO }}                     # 收件主邮箱
          TARGET_DATE: ${{ github.event.inputs.date }}       # 手动测试指定日期；定时触发时为空
        run: |
          if [ -n "$TARGET_DATE" ]; then
            python3 scripts/send_reminder.py --date "$TARGET_DATE"
          else
            python3 scripts/send_reminder.py
          fi
      - name: Keepalive (防 60 天自动禁用)
        run: |
          # 最后一次提交超过 50 天则做一次空提交，刷新 GitHub 的 60 天计时器
          days=$(( ( $(date +%s) - $(git log -1 --format=%ct) ) / 86400 ))
          echo "距上次提交 ${days} 天"
          if [ "$days" -ge 50 ]; then
            git config user.name "github-actions[bot]"
            git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
            git commit --allow-empty -m "chore: keepalive $(date +%F)"
            git push
          else
            echo "无需 keepalive"
          fi
```

- [ ] **Step 2: 本地校验 YAML 语法**

Run: `python3 -c "import yaml, sys; yaml.safe_load(open('.github/workflows/reminder.yml')); print('YAML OK')"`
Expected: 打印 `YAML OK`（若无 `yaml` 模块则跳过此步，语法在 GitHub 上会校验）。

- [ ] **Step 3: 确认目标日期逻辑（说明，无需执行）**

Runner 默认时区 UTC；cron 于 04:00 UTC 触发，此刻北京为当天 12:00，故 `date.today()+1` 正是"明天（北京）"。GitHub 定时可能延迟数小时——只要不跨 UTC 午夜就不影响目标日；跨午夜属极端罕见，用户已接受该残余风险。

---

## Task 7: 用户一次性配置（人工，不可自动化）

> 这些步骤涉及登录用户的 Google 与 GitHub 账号，须由**用户在网页后台**完成；执行者在此**暂停并把步骤交给用户**，不要尝试代做。

- [ ] **Step 1: 生成 Gmail 应用专用密码**
  1. Google 账号需已开**两步验证**。
  2. 打开 https://myaccount.google.com/apppasswords ，为"邮件"生成一个 16 位应用专用密码，复制备用。

- [ ] **Step 2: 在 GitHub 仓库加三个 Secret**
  仓库 `Settings → Secrets and variables → Actions → New repository secret`，分别新建：
  - `GMAIL_ADDRESS` = 新注册的发件小号地址（如 `xxx@gmail.com`）
  - `GMAIL_APP_PASSWORD` = 该小号生成的 16 位应用专用密码
  - `MAIL_TO` = `jcl1021@gmail.com`（收件的主邮箱）

- [ ] **Step 3: 手动触发真发信验证（测的是 GitHub 真实路径）**
  推送后，在仓库 `Actions → Daily market reminder → Run workflow`：
  - **date 填一个有事件的日期**（如 `2026-07-14`）→ 用 GitHub Secret、在 runner 上真发一封到主邮箱，核对收件箱（含垃圾箱）。这一步验证 Secret 填对没、runner 能否连 Gmail、投递是否进箱。
  - date 留空 → 走正常逻辑（对"明天"发），明天无事件则显示"无事件，不发送"。

---

## 完成后

全部任务通过、用户验收后，由**用户自行提交**（勿自动提交）：
```
git add .
git commit -m "2026.07.03-增加事件邮件提醒"
```
（`.env` 已被 `.gitignore` 忽略，不会误传。）
