# FC東京 試合日程カレンダー v0.1.0

FC東京トップチームとFC東京U-21の試合日程を、公開Googleカレンダーとして配信する初版です。

## 初版のポイント

- トップチーム用とU-21用の公開Googleカレンダーを分けて配信
- 日時未確定の試合は、候補期間を終日イベント1件で登録
- 日時確定後は、同じ `calendar_event_id` のイベントを正式日時へ更新
- Googleスプレッドシートを日程マスターとして使用
- シート編集時と6時間ごとにApps Scriptで自動同期
- Streamlit画面からGoogleカレンダー登録
- Appleカレンダー・Outlook向けのiCal URLも表示
- 既存のFC東京チケット発売日ナビへリンク
- Streamlit表示データもGoogleスプレッドシートから取得可能

---

# 構成

```text
Googleスプレッドシート（日程マスター）
       │
       ├─ Apps Script ──→ 公開Googleカレンダー
       │                    ├─ FC東京トップ
       │                    └─ FC東京U-21
       │
       └─ Apps Script JSON API ──→ Streamlit登録画面
                                     └─ チケット発売日ナビへのリンク
```

---

# 1. 公開Googleカレンダーを2つ作る

Googleカレンダーで次の2つを新規作成します。

1. `FC東京｜トップチーム試合日程（非公式）`
2. `FC東京｜U-21試合日程（非公式）`

各カレンダーの「設定と共有」で、一般公開を有効にします。

次に「カレンダーの統合」にある **カレンダーID** を控えます。

---

# 2. Googleスプレッドシートを作る

新しいGoogleスプレッドシートを作ります。

メニューから、

`拡張機能 → Apps Script`

を開きます。

同梱の以下を設定します。

- `gas/Code.gs` の内容をApps Scriptへ貼り付け
- Apps Scriptのプロジェクト設定でタイムゾーンを `Asia/Tokyo`

`gas/appsscript.json` は参考用です。通常はApps Script画面でマニフェストを表示して置き換えます。

---

# 3. スクリプトプロパティを設定する

Apps Scriptの左側にある歯車アイコン「プロジェクトの設定」を開きます。

「スクリプト プロパティ」に次を追加します。

| プロパティ | 値 |
|---|---|
| `TOP_CALENDAR_ID` | トップチーム用カレンダーID |
| `U21_CALENDAR_ID` | U-21用カレンダーID |
| `TICKET_APP_URL` | `https://club-ticket-navi-fctokyo-test.streamlit.app/` |

---

# 4. 日程マスターを作る

Apps Scriptで `setupMasterSheet` を1回実行します。

初回のみGoogleの権限確認が表示されます。

スプレッドシートに戻ると、`schedule` シートが作成されます。

サンプルには、添付画像をもとにしたFC東京U-21の確定日程・候補期間を入れています。

トップチームのサンプル行は `enabled=FALSE` です。実際の日程に置き換えてから `TRUE` にしてください。

---

# 5. カレンダーへ初回同期する

Apps Scriptで `syncAllCalendars` を実行します。

または、スプレッドシートを再読み込み後、

`FC東京カレンダー → カレンダーへ同期`

を選びます。

同期に成功すると、以下の列が自動入力されます。

- `calendar_event_id`
- `last_synced`
- `sync_result`

`calendar_event_id` は削除しないでください。同じ予定を更新するためのキーです。

---

# 6. 自動同期を設定する

スプレッドシートのメニューから、

`FC東京カレンダー → 自動同期を設定`

を選びます。

次の2種類が作成されます。

- `schedule` シートのセル編集時
- 6時間ごとの保険同期

---

# 7. Apps ScriptをJSON APIとして公開する

Apps Script画面で、

`デプロイ → 新しいデプロイ → ウェブアプリ`

を選びます。

設定例：

- 次のユーザーとして実行：自分
- アクセスできるユーザー：全員

デプロイ後の `/exec` URLを控えます。

このURLがStreamlitの `MASTER_API_URL` です。

---

# 8. Streamlitを設定する

`.streamlit/secrets.toml.example` を参考に、Streamlit Community CloudのSecretsへ設定します。

```toml
MASTER_API_URL = "https://script.google.com/macros/s/xxxxxxxx/exec"
TOP_CALENDAR_ID = "xxxxxxxx@group.calendar.google.com"
U21_CALENDAR_ID = "yyyyyyyy@group.calendar.google.com"
TICKET_APP_URL = "https://club-ticket-navi-fctokyo-test.streamlit.app/"
```

ローカルで確認するときは、

`.streamlit/secrets.toml.example`

を

`.streamlit/secrets.toml`

へコピーして値を設定します。

---

# 9. Streamlitへ公開する

GitHubリポジトリへ以下をアップロードします。

- `app.py`
- `requirements.txt`
- `data/`
- `.streamlit/config.toml`

Streamlit Community Cloudで `app.py` を指定してデプロイします。

---

# 未確定日程を確定日へ変更する例

変更前：

| 列 | 値 |
|---|---|
| status | 候補日あり |
| candidate_start | 2027-02-27 |
| candidate_end | 2027-03-01 |
| candidate_dates | 2/27(土)・2/28(日)・3/1(月) |
| confirmed_date | 空欄 |
| kickoff | 空欄 |

この状態では、2/27〜3/1の終日イベントを1件登録します。

2/28 14:00に決まった場合：

| 列 | 値 |
|---|---|
| status | 確定 |
| confirmed_date | 2027-02-28 |
| kickoff | 14:00 |

`calendar_event_id` はそのまま残します。

自動同期後、候補期間のイベントが同じ予定IDのまま2/28 14:00の試合予定へ変わります。

候補日を3件作って2件削除する方式ではありません。

---

# scheduleシートの主な列

| 列 | 内容 |
|---|---|
| match_id | 試合を一意に識別する固定ID |
| team | `TOP` または `U21` |
| status | `確定`、`候補日あり`、`進出時`など |
| candidate_start | 候補期間の開始日 |
| candidate_end | 候補期間の終了日 |
| candidate_dates | 画面・説明欄に表示する候補日一覧 |
| confirmed_date | 確定した試合日 |
| kickoff | キックオフ時刻 |
| duration_minutes | 予定時間。初期値120分 |
| calendar_event_id | GoogleカレンダーのイベントID。自動入力 |
| enabled | `TRUE` の行だけ同期・公開 |

---

# チケット発売日ナビとの連携

## 初版

カレンダーアプリから、既存のチケット発売日ナビへリンクします。

```text
https://club-ticket-navi-fctokyo-test.streamlit.app/
```

## 次の段階

既存チケットナビのデータには `match_key` があります。

カレンダーマスターの `match_id` を、チケットナビの `match_key` と同じ値にすると、将来的に次の連携ができます。

- 試合予定の説明欄へ、その試合のチケット発売日時を自動追記
- カレンダーアプリの日程カードへ発売日を表示
- チケット発売日も別イベントとしてカレンダー登録
- 試合日程変更時にチケット情報との紐付けを維持

初版では無理に統合せず、まず同じID体系にしておくのがおすすめです。

---

# 既存チケットナビ側へリンクを追加する例

`docs/TICKET_APP_LINK_PATCH.md` を参照してください。

---

# 注意事項

- FC東京公式サービスではありません。
- チーム名、エンブレム、ロゴ画像などの利用には注意してください。
- 初版の画面はクラブカラーを参考にしていますが、公式ロゴ・エンブレムは同梱していません。
- 日程・会場・時刻は必ず公式発表を確認してください。
- Google Workspace管理アカウントでは一般公開が禁止されている場合があります。
