# FC東京公式日程取得 修正版 v0.3

## #122 の原因

GitHub Actions は以下の状態です。

- Run parser tests: 成功
- Update ticket data: 失敗
- エラー: FC東京公式から試合日程を1件も取得できない

前版で取得先を `/schedule` に変更していましたが、
現在の最新試合が表示される公式ページは

`https://www.fctokyo.co.jp/match/schedule/`

です。

さらに、ライブページの表示構造が月別アーカイブ形式と異なる場合に備え、
見出しに依存しないフォールバック解析を追加しました。

## v0.3

- メインURLを `/match/schedule/` に戻す
- `/schedule` はフォールバックURLとして残す
- 従来パーサーが0件ならライブ試合カード形式で再解析
- HOME/AWAY + 日付 + VS/スコア + FC東京を条件に抽出
- 東京V iframe対応維持
- 鹿島SSL対応維持
- 候補日2行対応維持
- 終了済み試合対応維持

## 反映

`fctokyo-supporter-tools` リポジトリ直下の `scraper.py` を上書き。

コミット例:

`Fix live FC Tokyo schedule source`

その後 `Update FC Tokyo public data` を再実行してください。
