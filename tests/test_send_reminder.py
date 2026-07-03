import contextlib
import io
import os
import sys
import unittest
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import send_reminder as sr  # noqa: E402


# 样例事件：字段与 data.json 完全一致
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


class TestTimezone(unittest.TestCase):
    def test_est_in_winter(self):
        self.assertEqual(sr.us_eastern_offset(date(2026, 1, 15)), -5)

    def test_edt_in_summer(self):
        self.assertEqual(sr.us_eastern_offset(date(2026, 7, 15)), -4)

    def test_nth_weekday_second_sunday_march_2026(self):
        # 2026 年 3 月第 2 个周日 = 3 月 8 日
        self.assertEqual(sr._nth_weekday(2026, 3, 6, 2), date(2026, 3, 8))


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
        self.assertEqual(sr.beijing_from_et("2026-01-09", 8, 30), datetime(2026, 1, 9, 21, 30))

    def test_fomc_summer_next_day(self):
        # 夏令时 EDT：2:00pm ET + 12h = 次日 02:00 北京
        self.assertEqual(sr.beijing_from_et("2026-07-29", 14, 0), datetime(2026, 7, 30, 2, 0))


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


class TestMainNoEvents(unittest.TestCase):
    def test_no_events_prints_and_returns(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            sr.main(["--dry-run", "--date", "2099-01-01"])
        self.assertIn("无事件", out.getvalue())


if __name__ == "__main__":
    unittest.main()
