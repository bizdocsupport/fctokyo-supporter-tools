import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "tools" / "build_calendar_data.py"
spec = importlib.util.spec_from_file_location("build_calendar_data", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class CalendarOfficialMergeTest(unittest.TestCase):
    def test_candidate_dates_become_tentative_range(self):
        official = [{
            "competition_name": "J1リーグ",
            "round_name": "第20節",
            "date_text": "2027/05/22(土) or 2027/05/23(日) 時刻未定",
            "kickoff": "",
            "sort_date": "2027-05-22T23:59:00+09:00",
            "side": "HOME",
            "home": "FC東京",
            "away": "浦和レッズ",
            "opponent": "浦和レッズ",
            "stadium": "味スタ",
            "match_url": "https://example.com/match",
        }]
        merged = mod.merge_official_top_matches([], official)
        row = merged[0]
        self.assertEqual(row["status"], "候補日あり")
        self.assertEqual(row["candidate_start"], "2027-05-22")
        self.assertEqual(row["candidate_end"], "2027-05-23")
        self.assertEqual(row["confirmed_date"], "")

    def test_emperor_cup_confirmed_match(self):
        official = [{
            "competition_name": "天皇杯",
            "round_name": "3回戦",
            "date_text": "2026/10/07(水) 19:00",
            "kickoff": "2026-10-07T19:00:00+09:00",
            "side": "HOME",
            "home": "FC東京",
            "away": "湘南ベルマーレ",
            "opponent": "湘南ベルマーレ",
            "stadium": "レモンＳ",
            "match_url": "https://example.com/emperor",
        }]
        row = mod.merge_official_top_matches([], official)[0]
        self.assertEqual(row["competition"], "天皇杯")
        self.assertEqual(row["confirmed_date"], "2026-10-07")
        self.assertEqual(row["kickoff"], "19:00")

    def test_existing_manual_match_id_is_preserved(self):
        master = [{
            "match_id": "MANUAL-TOP-001",
            "team": "TOP",
            "competition": "J1リーグ",
            "round": "第8節",
            "status": "確定",
            "confirmed_date": "2026-09-19",
            "home_away": "HOME",
            "opponent": "名古屋グランパス",
            "ticket_url": "https://example.com/ticket",
            "enabled": "TRUE",
        }]
        official = [{
            "competition_name": "J1リーグ",
            "round_name": "第8節",
            "date_text": "2026/09/19(土) 19:00",
            "kickoff": "2026-09-19T19:00:00+09:00",
            "side": "HOME",
            "opponent": "名古屋グランパス",
            "stadium": "MUFG国立",
            "match_url": "https://example.com/official",
        }]
        row = mod.merge_official_top_matches(master, official)[0]
        self.assertEqual(row["match_id"], "MANUAL-TOP-001")
        self.assertEqual(row["ticket_url"], "https://example.com/ticket")

    def test_single_date_without_kickoff_is_confirmed_date(self):
        official = [{
            "competition_name": "J1リーグ",
            "round_name": "第21節",
            "date_text": "2027/05/30(日) 時刻未定",
            "kickoff": "",
            "sort_date": "2027-05-30T23:59:00+09:00",
            "side": "AWAY",
            "opponent": "川崎フロンターレ",
            "stadium": "未定",
        }]
        row = mod.merge_official_top_matches([], official)[0]
        self.assertEqual(row["confirmed_date"], "2027-05-30")
        self.assertEqual(row["kickoff"], "")
        self.assertEqual(row["candidate_start"], "")

    def test_u21_rows_are_not_touched(self):
        u21 = {
            "match_id": "U21-1",
            "team": "U21",
            "opponent": "U-21 ガンバ大阪",
            "confirmed_date": "2026-11-01",
        }
        official = [{
            "competition_name": "J1リーグ",
            "round_name": "第8節",
            "date_text": "2026/09/19(土) 19:00",
            "kickoff": "2026-09-19T19:00:00+09:00",
            "side": "HOME",
            "opponent": "名古屋グランパス",
        }]
        merged = mod.merge_official_top_matches([u21], official)
        self.assertIn(u21, merged)

if __name__ == "__main__":
    unittest.main()
