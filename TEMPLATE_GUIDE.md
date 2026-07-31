# テンプレートとして利用する方法

このFC東京版リポジトリをGitHubのTemplate Repositoryにすると、
他クラブ版を複製しやすくなります。

## GitHub設定

```text
Settings
→ General
→ Template repository をON
```

新しいクラブ版を作るときは、リポジトリ上部の
`Use this template`から新規リポジトリを作成します。

## 変更が必要な主なファイル

- `teams/fctokyo.json`
- `scraper.py`
- `updater.py`
- `data/ticket_sources.csv`
- `data/fallback_sales.csv`
- `data/manual_overrides.csv`
- `tests/test_parsers.py`
- `README.md`
- `SITE_INFO.md`

チーム名とURLだけの変更では安定して取得できません。
各クラブ公式サイトのHTML構造に合わせた解析処理が必要です。
