from scraper import extract_away_general_sale

MATCH = {
    "sort_date": "2026-10-17T14:00:00+09:00",
}

IFRAME_HTML = """
<table>
  <tr>
    <th>節</th><th>試合日時</th><th>対戦相手(会場)</th>
    <th>会員割引販売</th><th>一般販売</th>
  </tr>
  <tr>
    <td>10</td>
    <td>10/17 (土) 14:00</td>
    <td>FC東京（味の素スタジアム）</td>
    <td>9/16 (水) ～</td>
    <td>9/18 (金) ～</td>
  </tr>
</table>
"""

PARENT_TEXT = "※販売開始初日の販売開始時間は、会員割引・一般販売ともに12:00～です。"

def test_verdy_iframe_date_only_with_parent_time_note():
    assert extract_away_general_sale(
        IFRAME_HTML,
        MATCH,
        supplemental_text=PARENT_TEXT,
    ) == "2026-09-18T12:00:00+09:00"
