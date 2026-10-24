from __future__ import annotations

import csv
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "calendar_backend"
DOCS_DATA = ROOT / "docs" / "calendar" / "data"
DOCS_DATA.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = BACKEND / "calendar_config.json"
SAMPLE_PATH = BACKEND / "data" / "schedule_sample.csv"
U21_SCHEDULE_URL = "https://www.fctokyo.co.jp/team/u21/schedule/"

PUBLIC_COLUMNS = [
    "match_id", "team", "competition", "round", "status",
    "candidate_start", "candidate_end", "candidate_dates",
    "confirmed_date", "kickoff", "duration_minutes", "home_away",
    "opponent", "venue", "official_url", "ticket_url", "note", "enabled",
]


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def env_or_config(env_name: str, config: dict[str, Any], key: str) -> str:
    return str(os.getenv(env_name, "") or config.get(key, "") or "").strip()


def read_csv_text(text: str) -> list[dict[str, str]]:
    return [dict(row) for row in csv.DictReader(text.splitlines())]


def read_csv_file(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def load_remote(url: str) -> tuple[list[dict[str, Any]], str]:
    response = requests.get(
        url,
        timeout=25,
        headers={"User-Agent": "fctokyo.xyz-static-calendar/1.0"},
    )
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    body = response.text.lstrip()
    if "json" in content_type or body.startswith("{") or body.startswith("["):
        payload = response.json()
        if isinstance(payload, list):
            return payload, ""
        records = payload.get("data", payload.get("records", []))
        return list(records or []), str(payload.get("updated_at", "") or "")
    return read_csv_text(response.text), ""



def norm(value: str | None) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value or "")).strip()


def lines_from_html(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    for img in soup.find_all("img"):
        alt = norm(img.get("alt", ""))
        if alt:
            img.replace_with(f" {alt} ")
    lines = [norm(x) for x in soup.get_text("\n").splitlines()]
    return [x for x in lines if x]


def u21_stage_for_date(year: int, month: int, day: int) -> str:
    if year == 2027 and month == 4:
        return "U-21 Jリーグ プレーオフラウンド"
    if year == 2026 and (month in {11, 12} or (month == 10 and day >= 31)):
        return "U-21 Jリーグ 交流戦ラウンド"
    return "U-21 Jリーグ 東西リーグラウンド EAST"


def parse_u21_date(text: str) -> dict[str, Any] | None:
    date_pattern = re.compile(
        r"(?P<m>\d{1,2})月(?P<d>\d{1,2})日\((?P<w>[^)]+)\)"
    )
    matches = list(date_pattern.finditer(norm(text)))
    if not matches:
        return None

    dates: list[tuple[int, int, int, str]] = []
    for match in matches:
        month = int(match.group("m"))
        day = int(match.group("d"))
        year = 2026 if month >= 7 else 2027
        dates.append((year, month, day, match.group("w")))

    time_match = re.search(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)", norm(text))
    kickoff = (
        f"{int(time_match.group(1)):02d}:{time_match.group(2)}"
        if time_match
        else ""
    )

    first = dates[0]
    last = dates[-1]
    iso_dates = [f"{y:04d}-{m:02d}-{d:02d}" for y, m, d, _ in dates]
    display_dates = [f"{m}/{d}({w})" for _, m, d, w in dates]

    return {
        "dates": dates,
        "first": iso_dates[0],
        "last": iso_dates[-1],
        "candidate_dates": "・".join(display_dates),
        "kickoff": kickoff,
        "multiple": len(dates) > 1,
        "year": first[0],
        "month": first[1],
        "day": first[2],
    }


def _u21_team_token(value: str) -> bool:
    value = norm(value)
    return value == "未定" or value.startswith("U-21 ") or value.startswith("U-21")


def _u21_opponent(home: str, away: str) -> str:
    home_n = norm(home)
    away_n = norm(away)
    if "FC東京" in home_n:
        return away_n if away_n and away_n != "未定" else "対戦相手未定"
    if "FC東京" in away_n:
        return home_n if home_n and home_n != "未定" else "対戦相手未定"
    return "対戦相手未定"


def _u21_slug(value: str) -> str:
    mapping = {
        "東京ヴェルディ": "VERDY",
        "ジュビロ磐田": "IWATA",
        "川崎フロンターレ": "KAWASAKI",
        "浦和レッズ": "URAWA",
        "清水エスパルス": "SHIMIZU",
        "ガンバ大阪": "GAMBA",
        "ヴィッセル神戸": "KOBE",
        "V・ファーレン長崎": "NAGASAKI",
        "ファジアーノ岡山": "OKAYAMA",
        "名古屋グランパス": "NAGOYA",
    }
    clean = norm(value).replace("U-21", "").strip()
    for key, slug in mapping.items():
        if key in clean:
            return slug
    return "TBD"


def parse_u21_schedule_html(html: str) -> list[dict[str, str]]:
    lines = lines_from_html(html)
    date_re = re.compile(r"\d{1,2}月\d{1,2}日\([^)]+\)")
    round_re = re.compile(r"^第(?:\d+|1or2)節$")

    rows: list[dict[str, str]] = []
    i = 0
    while i < len(lines):
        date_line = norm(lines[i])
        if not date_re.search(date_line):
            i += 1
            continue

        date_info = parse_u21_date(date_line)
        if not date_info:
            i += 1
            continue

        side_index = next(
            (
                j for j in range(i + 1, min(i + 6, len(lines)))
                if norm(lines[j]).upper() in {"HOME", "AWAY"}
            ),
            None,
        )
        if side_index is None:
            i += 1
            continue

        next_date = next(
            (
                j for j in range(i + 1, len(lines))
                if date_re.search(norm(lines[j]))
            ),
            len(lines),
        )
        block = [norm(x) for x in lines[i:next_date] if norm(x)]

        round_name = ""
        for j in range(i - 1, max(-1, i - 6), -1):
            candidate = norm(lines[j])
            if round_re.fullmatch(candidate):
                round_name = candidate
                break

        side = norm(lines[side_index]).upper()
        venue = norm(lines[side_index + 1]) if side_index + 1 < next_date else ""

        home = ""
        away = ""
        try:
            vs_local = next(
                idx for idx, value in enumerate(block)
                if value.upper().rstrip(".") == "VS"
            )
            before = [value for value in block[:vs_local] if _u21_team_token(value)]
            after = [value for value in block[vs_local + 1:] if _u21_team_token(value)]
            if before:
                home = before[-1]
            if after:
                away = after[0]
        except StopIteration:
            # Completed matches have a score instead of VS.
            team_tokens = [value for value in block if _u21_team_token(value)]
            if len(team_tokens) >= 2:
                home, away = team_tokens[0], team_tokens[1]

        if not home and not away:
            i = next_date
            continue

        opponent = _u21_opponent(home, away)
        note = next(
            (
                value.replace("備考:", "").replace("備考：", "").strip()
                for value in block
                if value.startswith("備考:") or value.startswith("備考：")
            ),
            "",
        )

        year = int(date_info["year"])
        month = int(date_info["month"])
        day = int(date_info["day"])
        competition = u21_stage_for_date(year, month, day)

        if note and "場合" in note:
            status = "進出時"
        elif date_info["multiple"]:
            status = "候補日あり"
        else:
            status = "確定"

        if status == "確定":
            confirmed_date = date_info["first"]
            candidate_start = ""
            candidate_end = ""
            candidate_dates = ""
        else:
            confirmed_date = ""
            candidate_start = date_info["first"]
            candidate_end = date_info["last"]
            candidate_dates = date_info["candidate_dates"]

        opponent_slug = _u21_slug(opponent)
        match_id = f"U21-{date_info['first']}-{round_name or 'ROUND'}-{opponent_slug}"

        rows.append({
            "match_id": match_id,
            "team": "U21",
            "competition": competition,
            "round": round_name,
            "status": status,
            "candidate_start": candidate_start,
            "candidate_end": candidate_end,
            "candidate_dates": candidate_dates,
            "confirmed_date": confirmed_date,
            "kickoff": date_info["kickoff"] if status == "確定" else "",
            "duration_minutes": "120",
            "home_away": side,
            "opponent": opponent,
            "venue": "" if venue == "未定" else venue,
            "official_url": U21_SCHEDULE_URL,
            "ticket_url": "",
            "note": note or (
                "開催日時確定後、正式日時へ更新"
                if status == "候補日あり"
                else ""
            ),
            "enabled": "TRUE",
        })

        i = next_date

    unique: dict[str, dict[str, str]] = {}
    for row in rows:
        unique[row["match_id"]] = row
    return list(unique.values())


def load_official_u21() -> list[dict[str, str]]:
    response = requests.get(
        U21_SCHEDULE_URL,
        timeout=25,
        headers={"User-Agent": "fctokyo.xyz-static-calendar/1.1"},
    )
    response.raise_for_status()
    rows = parse_u21_schedule_html(response.text)
    if not rows:
        raise RuntimeError("FC東京U-21公式ページから日程を取得できませんでした。")
    return rows


def merge_u21(
    records: list[dict[str, Any]],
    u21_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    top_and_other = [
        row
        for row in records
        if str(row.get("team", "") or "").strip().upper() != "U21"
    ]
    return top_and_other + list(u21_rows)



def normalize(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for raw in records:
        row = {key: str(raw.get(key, "") or "").strip() for key in PUBLIC_COLUMNS}
        if row["enabled"].lower() in {"false", "0", "no", "off", "無効"}:
            continue
        row["display_start"] = row["confirmed_date"] or row["candidate_start"]
        result.append(row)
    result.sort(key=lambda row: (row.get("display_start") or "9999-12-31", row.get("team") or "", row.get("match_id") or ""))
    return result


def main() -> None:
    config = read_json(CONFIG_PATH, {})
    api_url = env_or_config("MASTER_API_URL", config, "master_api_url") or str(os.getenv("CALENDAR_MASTER_API_URL", "") or "").strip()
    top_id = env_or_config("TOP_CALENDAR_ID", config, "top_calendar_id")
    u21_id = env_or_config("U21_CALENDAR_ID", config, "u21_calendar_id")
    ticket_url = env_or_config("TICKET_URL", config, "ticket_url") or "/ticket/"

    records: list[dict[str, Any]] = []
    source = "同梱サンプル"
    source_updated_at = ""
    error = ""

    if api_url:
        try:
            records, source_updated_at = load_remote(api_url)
            source = "Googleスプレッドシート"
        except Exception as exc:  # Keep the public page available even if API is temporarily down.
            error = f"API取得失敗: {exc}"

    if not records:
        records = read_csv_file(SAMPLE_PATH) if SAMPLE_PATH.exists() else []
        if api_url and error:
            source = "API取得エラーのため同梱サンプル"

    u21_source = ""
    u21_error = ""
    try:
        official_u21 = load_official_u21()
        records = merge_u21(records, official_u21)
        u21_source = U21_SCHEDULE_URL
    except Exception as exc:
        u21_error = f"U-21公式取得失敗: {exc}"
        fallback_u21 = [
            row for row in (read_csv_file(SAMPLE_PATH) if SAMPLE_PATH.exists() else [])
            if str(row.get("team", "") or "").strip().upper() == "U21"
        ]
        if fallback_u21:
            records = merge_u21(records, fallback_u21)
            u21_source = "同梱U-21バックアップ"

    payload = {
        "schedule": normalize(records),
        "metadata": {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "source_updated_at": source_updated_at,
            "error": error,
            "u21_source": u21_source,
            "u21_error": u21_error,
        },
        "config": {
            "top_calendar_id": top_id,
            "u21_calendar_id": u21_id,
            "ticket_url": ticket_url,
        },
    }

    output = DOCS_DATA / "schedule-data.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Built {output}")
    print(f"Schedule: {len(payload['schedule'])}")
    print(f"Source: {source}")
    print(f"Top calendar ID: {'configured' if top_id else 'not configured'}")
    print(f"U-21 calendar ID: {'configured' if u21_id else 'not configured'}")
    print(f"U-21 source: {u21_source or 'not available'}")
    if error:
        print(error)
    if u21_error:
        print(u21_error)


if __name__ == "__main__":
    main()
