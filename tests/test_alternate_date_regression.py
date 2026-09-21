import unittest
from scraper import parse_fc_schedule

class AlternateDateRegressionTest(unittest.TestCase):
    def test_schedule_or_date_split_lines(self):
        html = """
        <html><body><h2>Ｊ１リーグ</h2><h3>2027.05</h3>
        <div>第36節</div>
        <div><span>5月22日(土) or</span><span>5月23日(日)</span></div>
        <div>HOME</div><div>味スタ</div>
        <div>FC東京</div><div>VS</div><div>ガンバ大阪</div>
        </body></html>
        """
        match = parse_fc_schedule(html)[0]
        self.assertEqual(
            match["date_text"],
            "2027/05/22(土) or 2027/05/23(日) 時刻未定",
        )

if __name__ == "__main__":
    unittest.main()
