from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
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

    payload = {
        "schedule": normalize(records),
        "metadata": {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "source_updated_at": source_updated_at,
            "error": error,
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
    if error:
        print(error)


if __name__ == "__main__":
    main()
