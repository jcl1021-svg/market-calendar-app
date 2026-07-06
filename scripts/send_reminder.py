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
    "PCE | Core PCE Price Index": "PCE",
    "FOMC Statement": "FOMC",
    "Roll Week": "换月周",
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


def _load_dotenv():
    """本地跑真实发送时，从项目根 .env 读 GMAIL_* （已被 .gitignore 忽略）。"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
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
