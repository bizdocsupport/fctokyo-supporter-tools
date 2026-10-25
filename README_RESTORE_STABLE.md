# build_calendar_data.py 安定版復元パッチ v0.1

今回の方針は「U-21自動スクレイピングをやめて、元の安定構成に戻す」です。

## 残すもの
- TOPチームのFC東京公式日程マージ
- Googleスプレッドシート/APIを日程マスターとして利用
- 既存TOP行のmatch_id / note / ticket_url維持

## やめるもの
- build_calendar_data.pyからのU-21公式ページ自動取得
- U-21公式データによる毎回の置換

U-21はGoogleスプレッドシート、または
calendar_backend/data/schedule_sample.csv
を更新する方式へ戻します。

## 反映するファイル

- tools/build_calendar_data.py
- calendar_backend/data/schedule_sample.csv

この2ファイルだけ上書きしてください。

既存のtestsフォルダは削除・変更不要です。
このパッチは、ユーザー提供の現時点最新ソースに入っている全テストを
実際に実行してから作成しています。

コミット例:

Restore stable calendar builder and use master U21 data
