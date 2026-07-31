# FC TOKYO SUPPORTER TOOLS — Static migration v0.2

2つのStreamlitアプリを、`fctokyo.xyz`配下の静的サイトへ統合した版です。

## 公開構成

```text
https://fctokyo.xyz/
├─ ticket/    クラブチケットナビ
└─ calendar/  トップ＋U-21試合日程カレンダー
```

## 継続するバックエンド

- チケット：既存のPythonスクレイピング＋GitHub Actions
- カレンダー：Googleスプレッドシート＋Apps Script＋公開Googleカレンダー

Streamlitは画面表示から外れますが、カレンダー同期を行うApps Scriptはそのまま使用します。

## 初回設定

1. この内容を `bizdocsupport/club-ticket-navi-fctokyo` へ反映
2. GitHub Pagesを `main /docs` で公開
3. Repository Variablesへ以下を登録
   - `MASTER_API_URL`
   - `TOP_CALENDAR_ID`
   - `U21_CALENDAR_ID`
4. Actionsの `Update FC Tokyo public data` を手動実行
5. `https://fctokyo.xyz/calendar/` を確認

詳しくは以下を参照してください。

- `STATIC_MIGRATION_GUIDE.md`
- `CALENDAR_STATIC_MIGRATION_GUIDE.md`

## ローカル確認

```bash
python tools/build_static_site.py
python tools/build_calendar_data.py
python -m http.server 8000 --directory docs
```

- トップ：`http://localhost:8000/`
- チケット：`http://localhost:8000/ticket/`
- カレンダー：`http://localhost:8000/calendar/`
