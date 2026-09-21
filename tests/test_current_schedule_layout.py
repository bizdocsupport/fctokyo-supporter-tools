import unittest
from scraper import parse_fc_schedule

CURRENT_HTML = """
<html><body>
<h3>明治安田J1百年構想リーグ</h3>
<h4>2026.09</h4>
<div>第8節</div>
<div>9月19日(土)</div>
<div>19:00</div>
<div>FC東京</div>
<div>VS</div>
<img alt="名古屋グランパス">
<div>ゲームインフォメーション</div>
<div>MUFG国立</div>
<div>DAZN</div>

<div>第9節</div>
<div>9月29日(火)</div>
<div>19:00</div>
<div>愛媛FC</div>
<div>VS</div>
<img alt="FC東京">
<div>ニンスタ</div>
<div>DAZN</div>
</body></html>
"""

OLD_HTML = """
<html><body>
<h3>明治安田J1リーグ</h3>
<h4>2026.10</h4>
<div>第9節</div>
<div>10月10日(土) 15:00</div>
<div>HOME</div>
<div>味スタ</div>
<div>FC東京</div>
<div>VS</div>
<div>浦和レッズ</div>
</body></html>
"""

COMPLETED_HTML = """
<html><body>
<h3>明治安田J1百年構想リーグ</h3>
<h4>2026.09</h4>
<div>第7節</div>
<div>9月12日(土)</div>
<div>19:00</div>
<div>ガンバ大阪</div>
<div>0</div>
<div>-</div>
<div>2</div>
<div>FC東京</div>
<div>パナスタ</div>
<div>DAZN</div>

<div>第8節</div>
<div>9月19日(土)</div>
<div>19:00</div>
<div>FC東京</div>
<div>VS</div>
<div>名古屋グランパス</div>
<div>MUFG国立</div>
</body></html>
"""

class CurrentScheduleParserTests(unittest.TestCase):
    def test_current_layout_without_home_away_labels(self):
        matches = parse_fc_schedule(CURRENT_HTML)
        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0]["side"], "HOME")
        self.assertEqual(matches[0]["opponent"], "名古屋グランパス")
        self.assertEqual(matches[0]["stadium"], "MUFG国立")
        self.assertEqual(matches[0]["kickoff"], "2026-09-19T19:00:00+09:00")
        self.assertEqual(matches[1]["side"], "AWAY")
        self.assertEqual(matches[1]["opponent"], "愛媛FC")
        self.assertEqual(matches[1]["stadium"], "ニンスタ")

    def test_old_layout_still_supported(self):
        matches = parse_fc_schedule(OLD_HTML)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["side"], "HOME")
        self.assertEqual(matches[0]["stadium"], "味スタ")

    def test_completed_match_does_not_mix_with_next_match(self):
        matches = parse_fc_schedule(COMPLETED_HTML)
        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0]["home"], "ガンバ大阪")
        self.assertEqual(matches[0]["away"], "FC東京")
        self.assertEqual(matches[0]["stadium"], "パナスタ")
        self.assertEqual(matches[1]["home"], "FC東京")
        self.assertEqual(matches[1]["away"], "名古屋グランパス")

if __name__ == "__main__":
    unittest.main()
