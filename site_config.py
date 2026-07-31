from __future__ import annotations

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TEAM_CONFIG_PATH = BASE_DIR / "teams" / "fctokyo.json"


def get_team_config() -> dict:
    if not TEAM_CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"チーム設定ファイルがありません: {TEAM_CONFIG_PATH}"
        )
    try:
        return json.loads(TEAM_CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"チーム設定ファイルのJSON形式が不正です: {TEAM_CONFIG_PATH}"
        ) from exc
