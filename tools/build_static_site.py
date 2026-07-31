from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DOCS_DATA = ROOT / "docs" / "data"
DOCS_DATA.mkdir(parents=True, exist_ok=True)


def read_csv(name: str) -> list[dict[str, str]]:
    path = DATA_DIR / name
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


payload = {
    "matches": read_csv("matches.csv"),
    "news": read_csv("ticket_news.csv"),
    "metadata": read_json(DATA_DIR / "metadata.json", {}),
    "team": read_json(ROOT / "teams" / "fctokyo.json", {}),
}

(DOCS_DATA / "ticket-data.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print(f"Built {DOCS_DATA / 'ticket-data.json'}")
print(f"Matches: {len(payload['matches'])}")
print(f"News: {len(payload['news'])}")
