# 試合日程カレンダーの静的サイト移植

カレンダー画面は `docs/calendar/` に統合済みです。
公開後のURLは次の想定です。

```text
https://fctokyo.xyz/calendar/
```

## Streamlit Secretsから移す3項目

現在のStreamlit Community Cloudに設定している以下を、GitHubリポジトリのVariablesへ登録します。

```text
MASTER_API_URL
TOP_CALENDAR_ID
U21_CALENDAR_ID
```

GitHubでの場所：

```text
Settings
→ Secrets and variables
→ Actions
→ Variables
→ New repository variable
```

### MASTER_API_URL

Apps Scriptをウェブアプリとして公開した `/exec` のURLです。
GitHub ActionsがこのURLから日程を取得し、静的JSONへ変換します。

### TOP_CALENDAR_ID / U21_CALENDAR_ID

Googleカレンダーの「設定と共有」→「カレンダーの統合」に表示されるカレンダーIDです。
これらは公開カレンダーの登録リンクとiCal URLの生成に使います。

## データ更新の流れ

```text
Googleスプレッドシート
  ↓ Apps Script JSON API
GitHub Actions（1日2回）
  ↓ tools/build_calendar_data.py
docs/calendar/data/schedule-data.json
  ↓
fctokyo.xyz/calendar/
```

Apps ScriptによるGoogleカレンダー自体の同期は、従来どおり継続します。
静的サイトは公開画面だけをStreamlitから置き換えます。

## ローカル設定

GitHub Variablesを設定する前にローカル確認する場合は、
`calendar_backend/calendar_config.json`へ値を記載してから実行します。

```bash
python tools/build_calendar_data.py
python -m http.server 8000 --directory docs
```

ブラウザで次を開きます。

```text
http://localhost:8000/calendar/
```

## Variables未設定時

同梱の `schedule_sample.csv` を表示します。
トップチームのサンプルは無効行のため、U-21の日程のみ表示される場合があります。
Googleカレンダー追加ボタンは無効になります。
