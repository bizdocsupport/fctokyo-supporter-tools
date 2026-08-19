from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scraper import FC_SCHEDULE_URL, fetch_fc_schedule, make_session  # noqa: E402

BACKEND = ROOT / "calendar_backend"
DOCS_DATA = ROOT / "docs" / "calendar" / "data"
DOCS_DATA.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = BACKEND / "calendar_config.json"
SAMPLE_PATH = BACKEND / "data" / "schedule_sample.csv"

PUBLIC_COLUMNS = [
    "match_id", "team", "competition", "round", "status",
    "candidate_start", "candidate_end", "candidate_dates",
    "confirmed_date", "kickoff", "duration_minutes", "home_away",
    "opponent", "venue", "official_url", "ticket_url", "note", "enabled",
    # Googleスプレッドシートには存在しなくてもよい公開専用列。
    # Apps Script側がFC東京公式由来の行だけを識別するために使う。
    "source",
]

OFFICIAL_SOURCE = "FC東京公式"


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
        headers={"User-Agent": "fctokyo.xyz-static-calendar/1.1"},
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


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", "", text).strip().lower()


def _competition_key(value: Any) -> str:
    n = _norm(value)
    if "ルヴァン" in n or "levain" in n or "ybc" in n:
        return "levain"
    if "天皇杯" in n:
        return "emperor"
    if "j1" in n or "ｊ１" in str(value or "").lower():
        return "j1"
    if "プレシーズン" in n or "親善" in n:
        return "friendly"
    return n


def _date_year(row: dict[str, Any]) -> str:
    for key in ("confirmed_date", "candidate_start", "sort_date"):
        value = str(row.get(key, "") or "").strip()
        m = re.search(r"(20\d{2})", value)
        if m:
            return m.group(1)
    return ""


def _semantic_key(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        _norm(row.get("team") or "TOP"),
        _competition_key(row.get("competition") or row.get("competition_name") or row.get("competition_group")),
        _norm(row.get("round") or row.get("round_name")),
        _norm(row.get("opponent")),
        _date_year(row),
    )


def _date_opponent_key(row: dict[str, Any]) -> tuple[str, str, str]:
    date_value = str(
        row.get("confirmed_date")
        or row.get("candidate_start")
        or row.get("sort_date")
        or ""
    )
    m = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", date_value)
    date_key = f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""
    return (_norm(row.get("team") or "TOP"), date_key, _norm(row.get("opponent")))


def _auto_match_id(match: dict[str, Any]) -> str:
    identity = "|".join([
        str(match.get("season", "")),
        _competition_key(match.get("competition_name") or match.get("competition_group")),
        _norm(match.get("round_name")),
        _norm(match.get("opponent")),
        _norm(match.get("side")),
    ])
    digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:12].upper()
    return f"TOP-AUTO-{digest}"


def official_match_to_calendar_record(match: dict[str, Any], ticket_url: str) -> dict[str, str]:
    """scraper.parse_fc_scheduleの1試合をカレンダーマスター形式へ変換する。"""
    sort_dt = datetime.fromisoformat(str(match["sort_date"]))
    first_date = sort_dt.date().isoformat()
    kickoff_value = str(match.get("kickoff") or "").strip()
    date_text = str(match.get("date_text") or "").strip()

    confirmed_date = ""
    kickoff = ""
    candidate_start = ""
    candidate_end = ""
    candidate_dates = ""
    status = "確定"

    if kickoff_value:
        kickoff_dt = datetime.fromisoformat(kickoff_value)
        confirmed_date = kickoff_dt.date().isoformat()
        kickoff = kickoff_dt.strftime("%H:%M")
    else:
        candidates = re.findall(r"(20\d{2})/(\d{2})/(\d{2})", date_text)
        dates = [f"{y}-{m}-{d}" for y, m, d in candidates]
        if len(dates) >= 2:
            status = "候補日あり"
            candidate_start = dates[0]
            candidate_end = dates[-1]
            candidate_dates = " / ".join(dates)
        else:
            # 日付は決まっているがキックオフ時刻だけ未定のケース。
            confirmed_date = first_date

    return {
        "match_id": _auto_match_id(match),
        "team": "TOP",
        "competition": str(match.get("competition_name") or match.get("competition_group") or "").strip(),
        "round": str(match.get("round_name") or "").strip(),
        "status": status,
        "candidate_start": candidate_start,
        "candidate_end": candidate_end,
        "candidate_dates": candidate_dates,
        "confirmed_date": confirmed_date,
        "kickoff": kickoff,
        "duration_minutes": "120",
        "home_away": str(match.get("side") or "").strip().upper(),
        "opponent": str(match.get("opponent") or "未定").strip(),
        "venue": str(match.get("stadium") or "未定").strip(),
        "official_url": str(match.get("match_url") or FC_SCHEDULE_URL).strip(),
        "ticket_url": ticket_url,
        "note": "",
        "enabled": "1",
        "source": OFFICIAL_SOURCE,
    }


def merge_official_top_matches(
    master_records: list[dict[str, Any]],
    official_matches: list[dict[str, Any]],
    ticket_url: str,
) -> list[dict[str, Any]]:
    """スプレッドシートの既存行を優先しつつ、FC東京公式のTOP日程を自動補完・更新する。"""
    merged: list[dict[str, Any]] = [dict(row) for row in master_records]

    by_semantic: dict[tuple[str, str, str, str, str], int] = {}
    by_date_opponent: dict[tuple[str, str, str], int] = {}
    for idx, row in enumerate(merged):
        if _norm(row.get("team")) != "top":
            continue
        by_semantic.setdefault(_semantic_key(row), idx)
        by_date_opponent.setdefault(_date_opponent_key(row), idx)

    schedule_fields = [
        "team", "competition", "round", "status",
        "candidate_start", "candidate_end", "candidate_dates",
        "confirmed_date", "kickoff", "home_away", "opponent", "venue",
        "official_url", "source",
    ]

    for match in official_matches:
        incoming = official_match_to_calendar_record(match, ticket_url)
        idx = by_semantic.get(_semantic_key(incoming))
        if idx is None:
            idx = by_date_opponent.get(_date_opponent_key(incoming))

        if idx is None:
            merged.append(incoming)
            idx = len(merged) - 1
        else:
            current = merged[idx]
            # match_idは既存値を維持してGoogleカレンダーのイベントID紐付けを壊さない。
            for key in schedule_fields:
                current[key] = incoming[key]
            if not str(current.get("duration_minutes") or "").strip():
                current["duration_minutes"] = incoming["duration_minutes"]
            if not str(current.get("ticket_url") or "").strip():
                current["ticket_url"] = incoming["ticket_url"]
            if not str(current.get("enabled") or "").strip():
                current["enabled"] = "1"

        by_semantic[_semantic_key(merged[idx])] = idx
        by_date_opponent[_date_opponent_key(merged[idx])] = idx

    return merged


def normalize(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for raw in records:
        row = {key: str(raw.get(key, "") or "").strip() for key in PUBLIC_COLUMNS}
        if row["enabled"].lower() in {"false", "0", "no", "off", "無効"}:
            continue
        row["display_start"] = row["confirmed_date"] or row["candidate_start"]
        result.append(row)
    result.sort(key=lambda row: (
        row.get("display_start") or "9999-12-31",
        row.get("team") or "",
        row.get("match_id") or "",
    ))
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
    errors: list[str] = []

    if api_url:
        try:
            records, source_updated_at = load_remote(api_url)
            source = "Googleスプレッドシート"
        except Exception as exc:  # Keep the public page available even if API is temporarily down.
            errors.append(f"API取得失敗: {exc}")

    if not records:
        records = read_csv_file(SAMPLE_PATH) if SAMPLE_PATH.exists() else []
        if api_url and errors:
            source = "API取得エラーのため同梱サンプル"

    official_matches: list[dict[str, Any]] = []
    try:
        official_matches = fetch_fc_schedule(make_session())
        records = merge_official_top_matches(records, official_matches, ticket_url)
        source = f"{source} + FC東京公式"
    except Exception as exc:
        errors.append(f"FC東京公式日程取得失敗: {exc}")

    payload = {
        "schedule": normalize(records),
        "metadata": {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "source_updated_at": source_updated_at,
            "error": " / ".join(errors),
            "official_source_url": FC_SCHEDULE_URL,
            "official_match_count": len(official_matches),
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
    print(f"Official TOP matches: {len(official_matches)}")
    print(f"Source: {source}")
    print(f"Top calendar ID: {'configured' if top_id else 'not configured'}")
    print(f"U-21 calendar ID: {'configured' if u21_id else 'not configured'}")
    if errors:
        print(" / ".join(errors))


if __name__ == "__main__":
    main()
