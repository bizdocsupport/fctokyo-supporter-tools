from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from scraper import (
    FC_PRICE_URL,
    JST,
    extract_home_article_sales,
    fetch,
    fetch_fc_schedule,
    fetch_fc_ticket_news,
    find_csv_sale,
    find_home_ticket_article,
    inspect_away_sources,
    load_club_sources,
    load_fallback_sales,
    load_manual_overrides,
    make_session,
    parse_fc_price_sales,
    within_six_months,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MATCHES_PATH = DATA_DIR / "matches.csv"
NEWS_PATH = DATA_DIR / "ticket_news.csv"
METADATA_PATH = DATA_DIR / "metadata.json"

MATCH_COLUMNS = [
    "match_key", "season", "competition_group", "competition_name",
    "round_name", "kickoff", "date_text", "sort_date", "side",
    "home", "away", "opponent", "stadium", "match_url",
    "socio_at", "membership_at", "general_at", "ticket_source_url",
    "ticket_source_name", "ticket_note", "last_checked",
]
NEWS_COLUMNS = ["published_at", "title", "url", "fetched_at"]
Progress = Optional[Callable[[str, int, int], None]]


def _report(progress: Progress, message: str, done: int, total: int) -> None:
    print(message, flush=True)
    if progress:
        progress(message, done, total)


def _apply_sale_row(target: dict, row: dict, override: bool = False) -> None:
    for key in ("socio_at", "membership_at", "general_at"):
        if key in row:
            value = (row.get(key) or "").strip()
            if override or (value and not target.get(key)):
                target[key] = value or None
    if row.get("source_url") and (override or not target.get("ticket_source_url")):
        target["ticket_source_url"] = row["source_url"]
    if row.get("source_name") and (override or not target.get("ticket_source_name")):
        target["ticket_source_name"] = row["source_name"]
    if row.get("note") and (override or not target.get("ticket_note")):
        target["ticket_note"] = row["note"]


def _read_csv(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv_atomic(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name) or "" for name in fieldnames})
    temp_path.replace(path)


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def update_all(progress: Progress = None) -> dict:
    started = datetime.now(JST)
    session = make_session()
    errors: list[str] = []
    total_steps = 8

    _report(progress, "1/8 FC東京公式から全試合日程を取得しています", 0, total_steps)
    matches = fetch_fc_schedule(session)
    if not matches:
        raise RuntimeError("FC東京公式から試合日程を1件も取得できませんでした。既存公開データは変更しません。")

    _report(progress, f"2/8 チケットニュース一覧を取得しています（現在{len(matches)}試合）", 1, total_steps)
    try:
        news = fetch_fc_ticket_news(session, max_pages=6)
    except Exception as exc:
        errors.append(f"FC東京チケットニュース: {exc}")
        news = _read_csv(NEWS_PATH)

    _report(progress, "3/8 FC東京ホームゲームの発売日表を確認しています", 2, total_steps)
    try:
        price_html = fetch(session, FC_PRICE_URL)
        price_sales = parse_fc_price_sales(price_html, matches)
    except Exception as exc:
        price_sales = {}
        errors.append(f"FC東京発売日表: {exc}")

    _report(progress, "4/8 FC東京ホームゲームのチケット記事を確認しています", 3, total_steps)
    for match in matches:
        match.update({
            "socio_at": None,
            "membership_at": None,
            "general_at": None,
            "ticket_source_url": "",
            "ticket_source_name": "",
            "ticket_note": "",
        })
        if match["side"] != "HOME":
            continue
        article = find_home_ticket_article(match, news)
        if article:
            try:
                sales = extract_home_article_sales(fetch(session, article["url"]), match)
                _apply_sale_row(match, sales)
                match["ticket_source_url"] = article["url"]
                match["ticket_source_name"] = "FC東京チケットニュース"
            except Exception as exc:
                errors.append(f"{match['date_text']} {match['opponent']}戦記事: {exc}")
        if match["match_key"] in price_sales:
            _apply_sale_row(match, {
                **price_sales[match["match_key"]],
                "source_name": "FC東京 価格・席割図・発売日",
            })

    _report(progress, "5/8 半年以内のアウェイゲームの一般発売日を確認しています", 4, total_steps)
    sources = load_club_sources()
    away_targets = [match for match in matches if match["side"] == "AWAY" and within_six_months(match)]
    for index, match in enumerate(away_targets, 1):
        source = sources.get(match["home"])
        if not source or match["home"] == "未定":
            continue
        _report(
            progress,
            f"5/8 {match['home']} vs FC東京を確認中（{index}/{len(away_targets)}）",
            4,
            total_steps,
        )
        result = inspect_away_sources(session, match, source)
        _apply_sale_row(match, {
            "general_at": result.get("general_at"),
            "source_url": result.get("source_url"),
            "source_name": result.get("source_name"),
            "note": result.get("note"),
        })

    _report(progress, "6/8 補完値と手動補正を反映しています", 5, total_steps)
    fallback_rows = load_fallback_sales()
    override_rows = load_manual_overrides()
    for match in matches:
        fallback = find_csv_sale(match, fallback_rows)
        if fallback:
            verified = str(fallback.get("verified", "")).strip().lower() in ("1", "true", "yes")
            _apply_sale_row(match, fallback, override=verified)
        override = find_csv_sale(match, override_rows)
        if override:
            _apply_sale_row(match, override, override=True)

    now = datetime.now(JST).isoformat()
    for match in matches:
        match["last_checked"] = now

    _report(progress, "7/8 公開用CSVを書き出しています", 6, total_steps)
    match_rows = sorted(matches, key=lambda item: (item.get("sort_date", ""), item.get("competition_group", "")))
    news_rows = []
    for item in news:
        news_rows.append({
            "published_at": item.get("published_at", ""),
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "fetched_at": now,
        })
    news_rows.sort(key=lambda item: item.get("published_at", ""), reverse=True)

    _write_csv_atomic(MATCHES_PATH, MATCH_COLUMNS, match_rows)
    _write_csv_atomic(NEWS_PATH, NEWS_COLUMNS, news_rows)

    result = {
        "status": "success",
        "last_updated": now,
        "matches": len(match_rows),
        "news": len(news_rows),
        "away_checked": len(away_targets),
        "errors": errors,
        "started": started.isoformat(),
        "finished": datetime.now(JST).isoformat(),
    }
    _write_json_atomic(METADATA_PATH, result)
    _report(progress, "8/8 公開用データの更新が完了しました", 8, total_steps)
    return result


if __name__ == "__main__":
    try:
        output = update_all()
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False, indent=2))
        raise
    print(json.dumps(output, ensure_ascii=False, indent=2))
