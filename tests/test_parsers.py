import unittest
from scraper import parse_fc_schedule, extract_home_article_sales, parse_fc_price_sales, extract_away_general_sale

SCHEDULE = '''
<html><body><h2>Ｊ１リーグ</h2><h3>2026.08</h3>
<div>1</div><div>8月8日(土)</div><div>19:00</div><div>HOME</div><div>味スタ</div><div>FC東京</div><div>VS</div><div>FC町田ゼルビア</div>
<div>第2節</div><div>8月15日(土)</div><div>19:00</div><div>AWAY</div><div>ノエスタ</div><div>ヴィッセル神戸</div><div>VS</div><div>FC東京</div>
<h2>ＪリーグＹＢＣルヴァンカップ</h2><h3>2026.09</h3>
<div>2回戦</div><div>9月29日(火)</div><div>AWAY</div><div>未定</div><div>未定</div><div>VS</div><div>FC東京</div>
<h2>プレシーズンマッチ</h2><h3>2026.08</h3>
<div>8月1日(土) 19:00</div><div>HOME</div><div>MUFG国立</div><div>FC東京</div><div>VS</div><div>ボルシア ドルトムント</div>
</body></html>
'''

class ParserTests(unittest.TestCase):
    def test_schedule_all_competitions(self):
        matches = parse_fc_schedule(SCHEDULE)
        self.assertEqual(len(matches), 4)
        friendly = next(m for m in matches if m['competition_group'] == 'その他試合')
        home = next(m for m in matches if m['home'] == 'FC東京' and m['away'] == 'FC町田ゼルビア')
        away = next(m for m in matches if m['home'] == 'ヴィッセル神戸')
        cup = next(m for m in matches if m['competition_group'] == 'ＪリーグＹＢＣルヴァンカップ')
        self.assertEqual(home['side'], 'HOME')
        self.assertEqual(home['date_text'], '2026/08/08(土) 19:00')
        self.assertIn('T19:00:00', home['kickoff'])
        self.assertEqual(away['away'], 'FC東京')
        self.assertEqual(away['date_text'], '2026/08/15(土) 19:00')
        self.assertEqual(friendly['competition_group'], 'その他試合')
        self.assertEqual(cup['home'], '未定')
        self.assertIn('時刻未定', cup['date_text'])

    def test_schedule_or_date_same_line(self):
        html = """
        <html><body><h2>Ｊ１リーグ</h2><h3>2027.05</h3>
        <div>第35節</div><div>5月15日(土) or 5月16日(日)</div>
        <div>AWAY</div><div>未定</div><div>FC町田ゼルビア</div><div>VS</div><div>FC東京</div>
        </body></html>
        """
        match = parse_fc_schedule(html)[0]
        self.assertEqual(
            match['date_text'],
            '2027/05/15(土) or 2027/05/16(日) 時刻未定',
        )

    def test_schedule_or_date_split_lines(self):
        html = """
        <html><body><h2>Ｊ１リーグ</h2><h3>2027.05</h3>
        <div>第36節</div>
        <div><span>5月22日(土) or</span><span>5月23日(日)</span></div>
        <div>HOME</div><div>味スタ</div><div>FC東京</div><div>VS</div><div>ガンバ大阪</div>
        </body></html>
        """
        match = parse_fc_schedule(html)[0]
        self.assertEqual(
            match['date_text'],
            '2027/05/22(土) or 2027/05/23(日) 時刻未定',
        )

    def test_home_article_sales(self):
        match = next(m for m in parse_fc_schedule(SCHEDULE) if m['competition_group'] == 'その他試合')
        html = '<div>SOCIO先行販売期間：5/17(日)10:00～ OFFICIAL MEMBERSHIP先行販売期間：5/24(日)10:00～ 一般販売期間：6/5(金)12:00～</div>'
        result = extract_home_article_sales(html, match)
        self.assertIn('2026-05-17T10:00', result['socio_at'])
        self.assertIn('2026-05-24T10:00', result['membership_at'])
        self.assertIn('2026-06-05T12:00', result['general_at'])


    def test_home_article_english_on_sale_date(self):
        match = next(m for m in parse_fc_schedule(SCHEDULE) if m['home'] == 'FC東京' and m['away'] == 'FC町田ゼルビア')
        match['sort_date'] = '2026-09-06T19:30:00+09:00'
        html = """<div>
        9月6日(日) 京都戦 チケット販売について
        <h3>TICKETS FOR OVERSEAS</h3>
        <p>On-Sale Date: Monday, July 27th 10:00 JST</p>
        </div>"""
        result = extract_home_article_sales(html, match)
        self.assertIn('2026-07-27T10:00', result['general_at'])
        self.assertIn('On-Sale Date', result['note'])

    def test_japanese_general_sale_takes_priority_over_english(self):
        match = next(m for m in parse_fc_schedule(SCHEDULE) if m['home'] == 'FC東京' and m['away'] == 'FC町田ゼルビア')
        match['sort_date'] = '2026-09-06T19:30:00+09:00'
        html = """<div>
        一般販売期間：7/26(日)10:00～
        On-Sale Date: Monday, July 27th 10:00 JST
        </div>"""
        result = extract_home_article_sales(html, match)
        self.assertIn('2026-07-26T10:00', result['general_at'])
        self.assertNotIn('note', result)

    def test_price_sales(self):
        match = next(m for m in parse_fc_schedule(SCHEDULE) if m['away'] == 'FC町田ゼルビア')
        html = '<table><tr><td>1</td><td>08月08日（土）</td><td>FC町田ゼルビア</td><td>味の素スタジアム</td><td>07月11日（土）10:00～</td><td>07月12日（日）10:00～</td><td>07月13日（月）10:00～</td></tr></table>'
        result = parse_fc_price_sales(html, [match])[match['match_key']]
        self.assertIn('2026-07-11T10:00', result['socio_at'])
        self.assertIn('2026-07-13T10:00', result['general_at'])

    def test_gamba_away_general(self):
        match = next(m for m in parse_fc_schedule(SCHEDULE) if m['home'] == 'ヴィッセル神戸')
        match['sort_date'] = '2026-09-12T19:00:00+09:00'
        html = '<div>9.12(土) 19:00 ＠パナスタ vs. FC東京 FC1次先行販売 8.1(土)10:00 一般販売 8.8(土)10:00～</div>'
        value = extract_away_general_sale(html, match)
        self.assertIn('2026-08-08T10:00', value)

    def test_cerezo_table_general_column(self):
        match = next(m for m in parse_fc_schedule(SCHEDULE) if m['home'] == 'ヴィッセル神戸')
        match['sort_date'] = '2026-11-21T15:00:00+09:00'
        html = '''<table><tr><th>節</th><th>開催日</th><th>開始</th><th>対戦</th><th>先行</th><th>一般販売</th></tr>
        <tr><td>15</td><td>11/21(土)</td><td>15:00</td><td>FC東京</td><td>9/12(土) 11:00</td><td>9/17(木) 11:00</td></tr></table>'''
        value = extract_away_general_sale(html, match)
        self.assertIn('2026-09-17T11:00', value)

    def test_kobe_date_plus_global_time(self):
        match = next(m for m in parse_fc_schedule(SCHEDULE) if m['home'] == 'ヴィッセル神戸')
        html = '<div>8/15 19:00 FC東京 ノエスタ 一般：7/22（水）</div><p>販売開始時間はロイヤル、レギュラー、一般販売は10:00～</p>'
        value = extract_away_general_sale(html, match)
        self.assertIn('2026-07-22T10:00', value)

    def test_unpublished_does_not_pick_other_match(self):
        match = next(m for m in parse_fc_schedule(SCHEDULE) if m['home'] == 'ヴィッセル神戸')
        html = '<div>8/22 京都戦 一般販売 7/20 10:00</div>'
        self.assertIsNone(extract_away_general_sale(html, match))

if __name__ == '__main__':
    unittest.main()
