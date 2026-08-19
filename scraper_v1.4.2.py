from __future__ import annotations

import csv
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Callable, Iterable, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from dateutil.relativedelta import relativedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_DIR = Path(__file__).resolve().parent
JST = timezone(timedelta(hours=9))
FC_SCHEDULE_URL = "https://www.fctokyo.co.jp/match/schedule/"
FC_TICKET_NEWS_URL = "https://www.fctokyo.co.jp/news/?slug=ticket"
FC_PRICE_URL = "https://www.fctokyo.co.jp/ticket/price/"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FC-Tokyo-Ticket-List/2.0"}

TEAM_ALIASES = {
    "水戸ホーリーホック": ["水戸ホーリーホック", "水戸"],
    "鹿島アントラーズ": ["鹿島アントラーズ", "鹿島"],
    "浦和レッズ": ["浦和レッズ", "浦和"],
    "ジェフユナイテッド千葉": ["ジェフユナイテッド千葉", "ジェフユナイテッド市原・千葉", "千葉"],
    "柏レイソル": ["柏レイソル", "柏"],
    "FC東京": ["FC東京", "FC TOKYO"],
    "東京ヴェルディ": ["東京ヴェルディ", "東京V", "東京Ｖ"],
    "FC町田ゼルビア": ["FC町田ゼルビア", "町田"],
    "川崎フロンターレ": ["川崎フロンターレ", "川崎F", "川崎Ｆ"],
    "横浜F・マリノス": ["横浜F・マリノス", "横浜FM", "横浜ＦＭ"],
    "清水エスパルス": ["清水エスパルス", "清水"],
    "名古屋グランパス": ["名古屋グランパス", "名古屋"],
    "京都サンガF.C.": ["京都サンガF.C.", "京都サンガFC", "京都"],
    "ガンバ大阪": ["ガンバ大阪", "G大阪", "Ｇ大阪"],
    "セレッソ大阪": ["セレッソ大阪", "C大阪", "Ｃ大阪"],
    "ヴィッセル神戸": ["ヴィッセル神戸", "神戸"],
    "ファジアーノ岡山": ["ファジアーノ岡山", "岡山"],
    "サンフレッチェ広島": ["サンフレッチェ広島", "広島"],
    "アビスパ福岡": ["アビスパ福岡", "福岡"],
    "V・ファーレン長崎": ["V・ファーレン長崎", "Ｖ・ファーレン長崎", "長崎"],
    "ボルシア ドルトムント": ["ボルシア ドルトムント", "ボルシア・ドルトムント", "ドルトムント"],
    "未定": ["未定"],
}


def norm(value: str | None) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value or "")).strip()


def compact(value: str | None) -> str:
    return norm(value).replace(" ", "")


def normalize_team(value: str) -> str:
    target = compact(value).replace(".C.", "C").replace(".C", "C")
    for canonical, aliases in TEAM_ALIASES.items():
        for alias in aliases:
            a = compact(alias).replace(".C.", "C").replace(".C", "C")
            if target == a:
                return canonical
    return norm(value)


def aliases_for(team: str) -> list[str]:
    return [norm(x) for x in TEAM_ALIASES.get(team, [team])]


def make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(UA)
    return session


def fetch(session: requests.Session, url: str, timeout: int = 25) -> str:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def soup_with_image_alt(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    for img in soup.find_all("img"):
        alt = norm(img.get("alt", ""))
        if alt:
            img.replace_with(f" {alt} ")
    return soup


def lines_from_html(html: str) -> tuple[BeautifulSoup, list[str]]:
    soup = soup_with_image_alt(html)
    lines = [norm(x) for x in soup.get_text("\n").splitlines()]
    return soup, [x for x in lines if x]


def competition_group(name: str) -> str:
    n = norm(name)
    if "YBC" in n and "ルヴァン" in n:
        return "ＪリーグＹＢＣルヴァンカップ"
    if "天皇杯" in n:
        return "天皇杯"
    if "J1リーグ" in n or "明治安田J1" in n:
        return "Ｊ１リーグ"
    return "その他試合"


def _looks_like_competition(line: str, heading_titles: set[str]) -> bool:
    n = norm(line)
    known = ("J1リーグ", "JリーグYBCルヴァンカップ", "天皇杯", "プレシーズンマッチ", "国際親善試合")
    return n in heading_titles or any(k in n for k in known)


def _has_year_month_soon(lines: list[str], index: int) -> bool:
    return any(re.fullmatch(r"20\d{2}\.\d{2}", lines[j]) for j in range(index + 1, min(index + 7, len(lines))))


def _parse_match_date(line: str, year_hint: int) -> Optional[dict]:
    n = norm(line)
    pattern = re.compile(
        r"(?P<m1>\d{1,2})月(?P<d1>\d{1,2})日\((?P<w1>[^)]+)\)"
        r"(?:\s*or\s*(?P<m2>\d{1,2})月(?P<d2>\d{1,2})日\((?P<w2>[^)]+)\))?"
        r"(?:\s*(?P<time>\d{1,2}:\d{2}))?",
        re.I,
    )
    m = pattern.search(n)
    if not m:
        return None
    m1, d1 = int(m.group("m1")), int(m.group("d1"))
    w1 = m.group("w1")
    m2 = int(m.group("m2")) if m.group("m2") else None
    d2 = int(m.group("d2")) if m.group("d2") else None
    w2 = m.group("w2") if m.group("w2") else None
    time_text = m.group("time")
    first = datetime(year_hint, m1, d1, tzinfo=JST)
    if time_text:
        h, mi = map(int, time_text.split(":"))
        first = first.replace(hour=h, minute=mi)
    date_text = f"{year_hint:04d}/{m1:02d}/{d1:02d}({w1})"
    if m2 and d2:
        date_text += f" or {year_hint:04d}/{m2:02d}/{d2:02d}({w2})"
    date_text += f" {time_text}" if time_text else " 時刻未定"
    return {
        "sort_date": first.isoformat(),
        "kickoff": first.isoformat() if time_text else None,
        "date_text": date_text,
        "month": m1,
        "day": d1,
        "time": time_text,
    }


def _apply_neighbor_kickoff(date_info: dict, lines: list[str], start: int, end: int) -> dict:
    """日付とキックオフ時刻が別行の場合に、HOME/AWAY表示までの時刻を補完する。"""
    if date_info.get("time"):
        return date_info
    time_pattern = re.compile(r"^(?:KICK\s*OFF\s*)?(\d{1,2}:\d{2})(?:\s*KICK\s*OFF)?$", re.I)
    for j in range(start, end):
        m = time_pattern.fullmatch(norm(lines[j]))
        if not m:
            continue
        time_text = m.group(1)
        hour, minute = map(int, time_text.split(":"))
        base = datetime.fromisoformat(date_info["sort_date"]).replace(hour=hour, minute=minute)
        updated = dict(date_info)
        updated["time"] = time_text
        updated["sort_date"] = base.isoformat()
        updated["kickoff"] = base.isoformat()
        updated["date_text"] = re.sub(r"\s+時刻未定$", f" {time_text}", updated["date_text"])
        return updated
    return date_info


def _find_round(lines: list[str], date_index: int, comp_group: str) -> str:
    for j in range(date_index - 1, max(-1, date_index - 6), -1):
        value = norm(lines[j])
        if re.fullmatch(r"20\d{2}\.\d{2}", value):
            break
        if re.fullmatch(r"\d+", value) and comp_group == "Ｊ１リーグ":
            return f"第{value}節"
        if re.search(r"(?:第?\d+節|\d+回戦|ラウンド|準々決勝|準決勝|決勝)", value):
            return value
    return ""


def parse_fc_schedule(html: str) -> list[dict]:
    soup, lines = lines_from_html(html)
    heading_titles = {norm(h.get_text(" ", strip=True)) for h in soup.find_all(["h2", "h3"])}
    current_comp = None
    current_group = None
    current_year = None
    results: list[dict] = []

    i = 0
    while i < len(lines):
        line = norm(lines[i])
        if _looks_like_competition(line, heading_titles) and _has_year_month_soon(lines, i):
            current_comp = line
            current_group = competition_group(line)
            i += 1
            continue

        ym = re.fullmatch(r"(20\d{2})\.(\d{2})", line)
        if ym and current_comp:
            current_year = int(ym.group(1))
            i += 1
            continue

        if not current_comp or current_year is None:
            i += 1
            continue

        # 公式サイトでは候補日が同一行の場合と、HTML要素の都合で
        # 「5月15日(土) or」「5月16日(日)」のように分割される場合がある。
        # 日付を含む行から最大4行を連結し、or以降の第2候補日と別行の時刻も解析する。
        if not re.search(r"\d{1,2}月\d{1,2}日\([^)]+\)", line):
            i += 1
            continue
        date_scope = " ".join(lines[i:min(i + 4, len(lines))])
        date_info = _parse_match_date(date_scope, current_year)
        if not date_info:
            i += 1
            continue

        side_index = next(
            (j for j in range(i + 1, min(i + 12, len(lines))) if norm(lines[j]).upper() in ("HOME", "AWAY")),
            None,
        )
        if side_index is None:
            i += 1
            continue
        date_info = _apply_neighbor_kickoff(date_info, lines, i + 1, side_index)
        side = norm(lines[side_index]).upper()

        # 1試合分の範囲を次の「節/回戦」等までに限定する。
        # 終了済み試合は中央表記が VS ではなく「2 - 2」のようなスコアになるため、
        # 次試合の VS まで探索すると日付・会場と対戦相手が混線してしまう。
        block_end = min(side_index + 24, len(lines))
        boundary_pattern = re.compile(r"^(?:第?\d+節|\d+回戦|ラウンド.*|準々決勝|準決勝|決勝)$")
        for j in range(side_index + 1, block_end):
            value = norm(lines[j])
            if boundary_pattern.fullmatch(value):
                block_end = j
                break
            if re.fullmatch(r"20\d{2}\.\d{2}", value):
                block_end = j
                break
            if _looks_like_competition(value, heading_titles) and _has_year_month_soon(lines, j):
                block_end = j
                break

        vs_index = next(
            (j for j in range(side_index + 1, block_end) if norm(lines[j]).upper().rstrip(".") == "VS"),
            None,
        )

        if vs_index is not None and vs_index - 1 > side_index and vs_index + 1 < block_end:
            home_index = vs_index - 1
            away_index = vs_index + 1
        else:
            # 終了済み試合: 「HOME/AWAY, 会場, ホーム, 得点, -, 得点, アウェイ」
            # のスコア区切りを同一試合ブロック内だけで探す。
            score_dash = next(
                (j for j in range(side_index + 2, block_end - 1)
                 if norm(lines[j]) in ("-", "－", "–", "—")
                 and re.fullmatch(r"\d+", norm(lines[j - 1]))
                 and re.fullmatch(r"\d+", norm(lines[j + 1]))),
                None,
            )
            if score_dash is None or score_dash - 2 <= side_index or score_dash + 2 >= block_end:
                i += 1
                continue
            home_index = score_dash - 2
            away_index = score_dash + 2

        home = normalize_team(lines[home_index])
        away = normalize_team(lines[away_index])
        if home == away or "FC東京" not in (home, away):
            i += 1
            continue

        stadium_values = [norm(x) for x in lines[side_index + 1:home_index] if norm(x)]
        stadium = stadium_values[0] if stadium_values else "未定"
        round_name = _find_round(lines, i, current_group)
        opponent = away if home == "FC東京" else home
        match_key = "|".join([
            "2026/27", current_group, current_comp, round_name,
            date_info["date_text"], home, away,
        ])
        results.append({
            "match_key": match_key,
            "season": "2026/27",
            "competition_group": current_group,
            "competition_name": current_comp,
            "round_name": round_name,
            "kickoff": date_info["kickoff"],
            "date_text": date_info["date_text"],
            "sort_date": date_info["sort_date"],
            "side": side,
            "home": home,
            "away": away,
            "opponent": opponent,
            "stadium": stadium,
            "match_url": FC_SCHEDULE_URL,
        })
        i = max(home_index, away_index) + 1

    unique = {}
    for item in results:
        unique[item["match_key"]] = item
    return sorted(unique.values(), key=lambda x: x["sort_date"])


def fetch_fc_schedule(session: requests.Session) -> list[dict]:
    return parse_fc_schedule(fetch(session, FC_SCHEDULE_URL))


def _clean_news_title(raw: str) -> str:
    text = norm(raw)
    text = re.sub(r"\s+20\d{2}/\d{1,2}/\d{1,2}\s+チケット\s*$", "", text)
    return text


def fetch_fc_ticket_news(session: requests.Session, max_pages: int = 6) -> list[dict]:
    found: dict[str, dict] = {}
    empty_pages = 0
    for page in range(1, max_pages + 1):
        url = FC_TICKET_NEWS_URL if page == 1 else f"{FC_TICKET_NEWS_URL}&page={page}"
        html = fetch(session, url)
        soup = soup_with_image_alt(html)
        new_count = 0
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"])
            if "/news/details/" not in href:
                continue
            title = _clean_news_title(a.get_text(" ", strip=True))
            if not title:
                continue
            parent_text = norm(a.parent.get_text(" ", strip=True) if a.parent else title)
            published = None
            dm = re.search(r"(20\d{2})/(\d{1,2})/(\d{1,2})", parent_text)
            if dm:
                published = f"{int(dm.group(1)):04d}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
            if href not in found:
                found[href] = {"url": href, "title": title, "published_at": published}
                new_count += 1
        empty_pages = empty_pages + 1 if new_count == 0 else 0
        if empty_pages >= 2:
            break
        time.sleep(0.15)
    return sorted(found.values(), key=lambda x: x.get("published_at") or "", reverse=True)


def _date_variants(match: dict) -> list[str]:
    dt = datetime.fromisoformat(match["sort_date"])
    return [f"{dt.month}/{dt.day}", f"{dt.month}月{dt.day}日", f"{dt.month:02d}/{dt.day:02d}"]


def find_home_ticket_article(match: dict, news: list[dict]) -> Optional[dict]:
    variants = _date_variants(match)
    opponent_aliases = aliases_for(match["opponent"])
    candidates = []
    for item in news:
        title = norm(item["title"])
        if not any(v in title for v in variants):
            continue
        score = 100
        if any(alias in title for alias in opponent_aliases):
            score += 40
        if "チケット販売" in title or "チケット" in title:
            score += 20
        if match["competition_group"] == "ＪリーグＹＢＣルヴァンカップ" and ("ルヴァン" in title or "ラウンド" in title):
            score += 15
        if match["competition_group"] == "その他試合" and ("親善" in title or match["opponent"] in title):
            score += 15
        candidates.append((score, item))
    return max(candidates, key=lambda x: x[0])[1] if candidates else None


def _sale_year(match_date: datetime, sale_month: int) -> int:
    year = match_date.year
    if match_date.month <= 3 and sale_month >= 9:
        year -= 1
    elif sale_month > match_date.month + 7:
        year -= 1
    return year


def _iso_sale(match: dict, month: int, day: int, hour: int, minute: int) -> Optional[str]:
    match_date = datetime.fromisoformat(match["sort_date"])
    try:
        return datetime(_sale_year(match_date, month), month, day, hour, minute, tzinfo=JST).isoformat()
    except ValueError:
        return None


def _extract_label_sale(text: str, match: dict, label_patterns: list[str]) -> Optional[str]:
    n = norm(text)
    date_pattern = r"(\d{1,2})\s*(?:/|\.|月)\s*(\d{1,2})(?:日)?(?:\([^)]+\))?\s*(\d{1,2})\s*[:時]\s*(\d{2})"
    for label in label_patterns:
        pattern = re.compile(rf"(?:{label})[^。\n]{{0,130}}?{date_pattern}", re.I)
        for m in pattern.finditer(n):
            month, day, hour, minute = map(int, m.groups()[-4:])
            value = _iso_sale(match, month, day, hour, minute)
            if value:
                return value
    return None


ENGLISH_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def _extract_english_on_sale_date(text: str, match: dict) -> Optional[str]:
    """英語案内の ``On-Sale Date`` を一般発売日時として取得する。

    FC東京の記事では、日本語の販売スケジュールが画像だけでも、記事下部の
    海外向け案内に ``On-Sale Date: Monday, July 27th 10:00 JST`` のような
    テキストが掲載される場合がある。
    """
    n = norm(text)
    month_names = "|".join(name.title() for name in ENGLISH_MONTHS)
    weekday = r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
    pattern = re.compile(
        rf"On[\s-]*Sale\s+Date\s*[:：]?\s*"
        rf"(?:{weekday}\s*,?\s*)?"
        rf"(?P<month>{month_names})\s+"
        rf"(?P<day>\d{{1,2}})(?:st|nd|rd|th)?"
        rf"(?:\s*,?\s*(?P<year>20\d{{2}}))?"
        rf"\s+(?:at\s+)?(?P<hour>\d{{1,2}}):(?P<minute>\d{{2}})"
        rf"(?:\s*(?:JST|Japan\s+Standard\s+Time))?",
        re.I,
    )
    match_result = pattern.search(n)
    if not match_result:
        return None

    month = ENGLISH_MONTHS[match_result.group("month").lower()]
    day = int(match_result.group("day"))
    hour = int(match_result.group("hour"))
    minute = int(match_result.group("minute"))
    match_date = datetime.fromisoformat(match["sort_date"])
    year = int(match_result.group("year")) if match_result.group("year") else _sale_year(match_date, month)
    try:
        return datetime(year, month, day, hour, minute, tzinfo=JST).isoformat()
    except ValueError:
        return None


def extract_home_article_sales(html: str, match: dict) -> dict:
    soup = soup_with_image_alt(html)
    text = norm(soup.get_text(" ", strip=True))
    socio_at = _extract_label_sale(
        text,
        match,
        [r"SOCIO(?:先々行|先行)?販売(?:期間)?", r"SOCIOのみなさま"],
    )
    membership_at = _extract_label_sale(
        text,
        match,
        [r"OFFICIAL\s*MEMBERSHIP(?:先行)?販売(?:期間)?", r"OFFICIAL\s*MEMBERSHIPのみなさま"],
    )
    general_at = _extract_label_sale(
        text,
        match,
        [r"一般販売(?:期間)?", r"一般のみなさま"],
    )
    english_general_at = None
    if not general_at:
        english_general_at = _extract_english_on_sale_date(text, match)
        general_at = english_general_at

    result = {
        "socio_at": socio_at,
        "membership_at": membership_at,
        "general_at": general_at,
    }
    if english_general_at:
        result["note"] = "記事内の英語案内（On-Sale Date）から一般発売日時を取得"
    return result


def _extract_md_time_tokens(text: str, match: dict) -> list[str]:
    n = norm(text)
    pattern = re.compile(r"(\d{1,2})\s*(?:/|\.|月)\s*(\d{1,2})(?:日)?(?:\([^)]+\))?\s*(\d{1,2})\s*[:時]\s*(\d{2})")
    values = []
    for m in pattern.finditer(n):
        value = _iso_sale(match, *map(int, m.groups()))
        if value and value not in values:
            values.append(value)
    return values


def parse_fc_price_sales(html: str, matches: list[dict]) -> dict[str, dict]:
    soup = soup_with_image_alt(html)
    full_text = norm(soup.get_text(" ", strip=True))
    rows = [norm(tr.get_text(" ", strip=True)) for tr in soup.find_all("tr")]
    outputs: dict[str, dict] = {}
    for match in matches:
        if match["side"] != "HOME":
            continue
        aliases = aliases_for(match["opponent"])
        dt = datetime.fromisoformat(match["sort_date"])
        match_variants = [f"{dt.month:02d}月{dt.day:02d}日", f"{dt.month}月{dt.day}日"]
        candidates = [row for row in rows if any(a in row for a in aliases) and any(v in row for v in match_variants)]
        if not candidates:
            positions = [full_text.find(a) for a in aliases if full_text.find(a) >= 0]
            for pos in positions:
                local = full_text[max(0, pos - 120):pos + 450]
                if any(v in local for v in match_variants):
                    candidates.append(local)
                    break
        for candidate in candidates:
            tokens = _extract_md_time_tokens(candidate, match)
            if len(tokens) >= 3:
                outputs[match["match_key"]] = {
                    "socio_at": tokens[0],
                    "membership_at": tokens[1],
                    "general_at": tokens[2],
                    "source_url": FC_PRICE_URL,
                }
                break
    return outputs


def load_club_sources() -> dict[str, dict]:
    path = BASE_DIR / "data" / "club_sources.csv"
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {row["club"]: row for row in csv.DictReader(f)}


def load_fallback_sales() -> list[dict]:
    path = BASE_DIR / "data" / "fallback_sales.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_manual_overrides() -> list[dict]:
    path = BASE_DIR / "data" / "manual_overrides.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _match_csv_row(match: dict, row: dict) -> bool:
    dt = datetime.fromisoformat(match["sort_date"])
    date_key = f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d}"
    return (
        (not row.get("competition_group") or row.get("competition_group") == match["competition_group"])
        and (not row.get("match_date") or row.get("match_date") == date_key)
        and (not row.get("home") or row.get("home") == match["home"])
        and (not row.get("away") or row.get("away") == match["away"])
    )


def find_csv_sale(match: dict, rows: list[dict]) -> Optional[dict]:
    for row in rows:
        if _match_csv_row(match, row):
            return row
    return None


def _match_date_markers(match: dict) -> list[str]:
    dt = datetime.fromisoformat(match["sort_date"])
    return [
        f"{dt.month}/{dt.day}", f"{dt.month:02d}/{dt.day:02d}",
        f"{dt.month}.{dt.day}", f"{dt.month:02d}.{dt.day:02d}",
        f"{dt.month}月{dt.day}日", f"{dt.month:02d}月{dt.day:02d}日",
    ]


def _extract_general_from_scope(scope: str, full_text: str, match: dict) -> Optional[str]:
    n = norm(scope)
    if "情報掲載までお待ち" in n or re.search(r"一般(?:販売|発売)?\s*未定", n):
        return None
    patterns = [
        r"一般(?:販売|発売)?(?:開始)?\s*[:：]?\s*(\d{1,2})\s*(?:/|\.|月)\s*(\d{1,2})(?:日)?(?:\([^)]+\))?\s*(\d{1,2})\s*[:時]\s*(\d{2})",
    ]
    for pattern in patterns:
        m = re.search(pattern, n, re.I)
        if m:
            return _iso_sale(match, *map(int, m.groups()))

    date_only = re.search(
        r"一般(?:販売|発売)?(?:開始)?\s*[:：]?\s*(\d{1,2})\s*(?:/|\.|月)\s*(\d{1,2})(?:日)?(?:\([^)]+\))?",
        n,
        re.I,
    )
    if date_only:
        hour, minute = None, None
        time_patterns = [
            r"一般販売(?:は|の販売開始時間は)?[^。]{0,35}?(\d{1,2}):(\d{2})",
            r"一般(?:販売)?[^。]{0,20}?(\d{1,2})時(\d{2})分",
            r"ロイヤル[^。]{0,80}?一般販売は(\d{1,2}):(\d{2})",
        ]
        combined = norm(n + " " + full_text)
        for p in time_patterns:
            tm = re.search(p, combined)
            if tm:
                hour, minute = map(int, tm.groups())
                break
        if hour is not None:
            month, day = map(int, date_only.groups())
            return _iso_sale(match, month, day, hour, minute)
    return None


def _extract_structured_table_general(soup: BeautifulSoup, match: dict) -> Optional[str]:
    """販売表の「一般」列、または対象試合行の最後の販売日時を取得する。"""
    aliases = aliases_for("FC東京")
    markers = _match_date_markers(match)
    match_dt = datetime.fromisoformat(match["sort_date"])

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        general_index = None
        for tr in rows[:3]:
            headers = [norm(c.get_text(" ", strip=True)) for c in tr.find_all(["th", "td"])]
            for idx, header in enumerate(headers):
                if "一般" in header and ("販売" in header or "発売" in header or header == "一般"):
                    general_index = idx
                    break
            if general_index is not None:
                break

        for tr in rows:
            cells = [norm(c.get_text(" ", strip=True)) for c in tr.find_all(["th", "td"])]
            row_text = norm(" ".join(cells))
            if not any(alias in row_text for alias in aliases):
                continue
            if not any(marker in row_text for marker in markers):
                continue

            if general_index is not None and general_index < len(cells):
                values = _extract_md_time_tokens(cells[general_index], match)
                if values:
                    return values[0]

            values = _extract_md_time_tokens(row_text, match)
            before_match = [v for v in values if datetime.fromisoformat(v) < match_dt]
            if before_match:
                return max(before_match, key=datetime.fromisoformat)
    return None


def extract_away_general_sale(html: str, match: dict) -> Optional[str]:
    soup, lines = lines_from_html(html)
    structured = _extract_structured_table_general(soup, match)
    if structured:
        return structured
    full_text = norm(" ".join(lines))
    fc_aliases = [norm(x) for x in aliases_for("FC東京")]
    markers = _match_date_markers(match)
    windows = []
    for idx, line in enumerate(lines):
        if any(alias in norm(line) for alias in fc_aliases):
            window = " ".join(lines[max(0, idx - 18): min(len(lines), idx + 42)])
            normalized_window = norm(window)
            marker_hits = sum(1 for marker in markers if marker in normalized_window)
            # 別試合の発売日を拾わないため、対象試合日を含むブロックだけを解析する。
            if marker_hits == 0:
                continue
            score = 20 + marker_hits * 20
            if "一般" in window:
                score += 20
            windows.append((score, window))
    for _, window in sorted(windows, reverse=True):
        value = _extract_general_from_scope(window, full_text, match)
        if value:
            return value
    return None


def within_six_months(match: dict, today: Optional[date] = None) -> bool:
    today = today or date.today()
    match_date = datetime.fromisoformat(match["sort_date"]).date()
    return today <= match_date <= today + relativedelta(months=6)


def inspect_away_sources(session: requests.Session, match: dict, source: dict) -> dict:
    urls = []
    for key, label in (("schedule_url", "対戦クラブ公式日程"), ("ticket_url", "対戦クラブ公式チケット")):
        url = (source.get(key) or "").strip()
        if url and url not in [x[0] for x in urls]:
            urls.append((url, label))
    errors = []
    for url, label in urls:
        try:
            html = fetch(session, url)
            general = extract_away_general_sale(html, match)
            if general:
                return {
                    "general_at": general,
                    "source_url": url,
                    "source_name": label,
                    "note": "対戦相手FC東京の試合ブロックから一般発売日時を取得",
                }
        except Exception as exc:
            errors.append(f"{label}: {exc}")
    return {
        "general_at": None,
        "source_url": urls[-1][0] if urls else "",
        "source_name": urls[-1][1] if urls else "",
        "note": " / ".join(errors) if errors else "一般発売日時は未発表または抽出できませんでした",
    }
