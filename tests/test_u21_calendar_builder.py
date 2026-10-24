import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "tools" / "build_calendar_data.py"
spec = importlib.util.spec_from_file_location("build_calendar_data", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

HTML = """
<html><body>
<div>第5節</div>
<div>10月17日(土) 16:00</div>
<div>HOME</div>
<div>江東区夢の島競技場</div>
<div>U-21 FC東京</div>
<div>3</div><div>-</div><div>1</div>
<div>U-21 清水エスパルス</div>

<div>第1節</div>
<div>11月1日(日) 19:00</div>
<div>HOME</div>
<div>味の素スタジアム</div>
<div>U-21 FC東京</div>
<div>VS</div>
<div>U-21 ガンバ大阪</div>

<div>第3節</div>
<div>11月29日(日) 10:30</div>
<div>HOME</div>
<div>武蔵野陸上競技場</div>
<div>U-21 FC東京</div>
<div>VS</div>
<div>U-21 V・ファーレン長崎</div>

<div>第8節</div>
<div>2月27日(土) or 2月28日(日) or 3月1日(月)</div>
<div>HOME</div>
<div>未定</div>
<div>U-21 FC東京</div>
<div>VS</div>
<div>U-21 浦和レッズ</div>

<div>第1節</div>
<div>4月3日(土) or 4月4日(日)</div>
<div>HOME</div>
<div>未定</div>
<div>未定</div>
<div>VS</div>
<div>未定</div>
<div>備考： 東リーグラウンドにおいて2位もしくは6位となった場合は実施いたしません。</div>
</body></html>
"""

class U21CalendarParserTests(unittest.TestCase):
    def test_official_schedule_rows(self):
        rows = mod.parse_u21_schedule_html(HTML)
        self.assertEqual(len(rows), 5)

        self.assertEqual(rows[0]["opponent"], "U-21 清水エスパルス")

        gamba = rows[1]
        self.assertEqual(gamba["confirmed_date"], "2026-11-01")
        self.assertEqual(gamba["kickoff"], "19:00")
        self.assertEqual(gamba["opponent"], "U-21 ガンバ大阪")
        self.assertEqual(gamba["venue"], "味の素スタジアム")
        self.assertEqual(gamba["competition"], "U-21 Jリーグ 交流戦ラウンド")

        nagasaki = rows[2]
        self.assertEqual(nagasaki["kickoff"], "10:30")

        urawa = rows[3]
        self.assertEqual(urawa["candidate_start"], "2027-02-27")
        self.assertEqual(urawa["candidate_end"], "2027-03-01")
        self.assertEqual(urawa["status"], "候補日あり")

        playoff = rows[4]
        self.assertEqual(playoff["status"], "進出時")
        self.assertEqual(playoff["opponent"], "対戦相手未定")

    def test_merge_replaces_old_u21_only(self):
        master = [
            {"match_id": "TOP-1", "team": "TOP"},
            {"match_id": "OLD-U21", "team": "U21"},
        ]
        new_rows = [{"match_id": "NEW-U21", "team": "U21"}]
        merged = mod.merge_u21(master, new_rows)
        self.assertEqual([row["match_id"] for row in merged], ["TOP-1", "NEW-U21"])

if __name__ == "__main__":
    unittest.main()
