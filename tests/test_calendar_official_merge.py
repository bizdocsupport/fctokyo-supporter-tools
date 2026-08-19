import unittest

from tools.build_calendar_data import (
    merge_official_top_matches,
    official_match_to_calendar_record,
)


class CalendarOfficialMergeTest(unittest.TestCase):
    def test_emperor_cup_confirmed_match(self):
        match = {
            "season": "2026/27",
            "competition_group": "天皇杯",
            "competition_name": "天皇杯",
            "round_name": "第2節",
            "kickoff": "2026-08-26T19:00:00+09:00",
            "date_text": "2026/08/26(水) 19:00",
            "sort_date": "2026-08-26T19:00:00+09:00",
            "side": "HOME",
            "opponent": "AC長野パルセイロ",
            "stadium": "味スタ",
            "match_url": "https://www.fctokyo.co.jp/match/schedule/",
        }
        row = official_match_to_calendar_record(match, "/ticket/")
        self.assertEqual(row["competition"], "天皇杯")
        self.assertEqual(row["confirmed_date"], "2026-08-26")
        self.assertEqual(row["kickoff"], "19:00")
        self.assertEqual(row["status"], "確定")
        self.assertEqual(row["source"], "FC東京公式")

    def test_candidate_dates_become_tentative_range(self):
        match = {
            "season": "2026/27",
            "competition_group": "Ｊ１リーグ",
            "competition_name": "Ｊ１リーグ",
            "round_name": "第23節",
            "kickoff": None,
            "date_text": "2027/02/27(土) or 2027/02/28(日) 時刻未定",
            "sort_date": "2027-02-27T00:00:00+09:00",
            "side": "AWAY",
            "opponent": "ジェフユナイテッド千葉",
            "stadium": "フクアリ",
            "match_url": "https://www.fctokyo.co.jp/match/schedule/",
        }
        row = official_match_to_calendar_record(match, "/ticket/")
        self.assertEqual(row["status"], "候補日あり")
        self.assertEqual(row["candidate_start"], "2027-02-27")
        self.assertEqual(row["candidate_end"], "2027-02-28")
        self.assertEqual(row["confirmed_date"], "")

    def test_single_date_without_kickoff_is_confirmed_date(self):
        match = {
            "season": "2026/27",
            "competition_group": "ＪリーグＹＢＣルヴァンカップ",
            "competition_name": "ＪリーグＹＢＣルヴァンカップ",
            "round_name": "2回戦",
            "kickoff": None,
            "date_text": "2026/09/29(火) 時刻未定",
            "sort_date": "2026-09-29T00:00:00+09:00",
            "side": "AWAY",
            "opponent": "未定",
            "stadium": "未定",
            "match_url": "https://www.fctokyo.co.jp/match/schedule/",
        }
        row = official_match_to_calendar_record(match, "/ticket/")
        self.assertEqual(row["status"], "確定")
        self.assertEqual(row["confirmed_date"], "2026-09-29")
        self.assertEqual(row["kickoff"], "")

    def test_existing_manual_match_id_is_preserved(self):
        master = [{
            "match_id": "TOP-2026-EMPEROR-02-NAGANO",
            "team": "TOP",
            "competition": "天皇杯",
            "round": "第2節",
            "status": "確定",
            "confirmed_date": "2026-08-26",
            "kickoff": "",
            "home_away": "HOME",
            "opponent": "AC長野パルセイロ",
            "venue": "味スタ",
            "ticket_url": "/ticket/",
            "note": "手入力メモ",
            "enabled": "1",
        }]
        official = [{
            "season": "2026/27",
            "competition_group": "天皇杯",
            "competition_name": "天皇杯",
            "round_name": "第2節",
            "kickoff": "2026-08-26T19:00:00+09:00",
            "date_text": "2026/08/26(水) 19:00",
            "sort_date": "2026-08-26T19:00:00+09:00",
            "side": "HOME",
            "opponent": "AC長野パルセイロ",
            "stadium": "味スタ",
            "match_url": "https://www.fctokyo.co.jp/match/schedule/",
        }]
        merged = merge_official_top_matches(master, official, "/ticket/")
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["match_id"], "TOP-2026-EMPEROR-02-NAGANO")
        self.assertEqual(merged[0]["kickoff"], "19:00")
        self.assertEqual(merged[0]["note"], "手入力メモ")

    def test_u21_rows_are_not_touched(self):
        master = [{
            "match_id": "U21-001",
            "team": "U21",
            "competition": "Jエリートリーグ",
            "round": "",
            "status": "確定",
            "confirmed_date": "2026-09-01",
            "kickoff": "18:00",
            "opponent": "相手",
            "enabled": "1",
        }]
        merged = merge_official_top_matches(master, [], "/ticket/")
        self.assertEqual(merged, master)


if __name__ == "__main__":
    unittest.main()
