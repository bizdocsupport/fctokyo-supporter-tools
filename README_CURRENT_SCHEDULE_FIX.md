# FC東京公式・現行日程ページ対応パッチ v0.1

## 原因

現在のスクレイパーは旧FC東京公式ページを前提にしています。

旧想定:
`日付 -> HOME/AWAY -> 会場 -> ホーム -> VS -> アウェイ`

現行:
`日付 -> キックオフ -> ホーム -> VS -> アウェイ -> 会場`

現行ページには `HOME` / `AWAY` の文字がないため、
従来コードの `side_index` が毎試合 `None` となり、
最終的に試合が0件になります。

また、公式日程の現行URLは次です。

`https://www.fctokyo.co.jp/schedule`

## 修正

- 現行URLへ変更
- HOME/AWAY表記がなくてもホーム・アウェイをチーム位置から判定
- 現行ページの会場位置（アウェイチームの後）に対応
- 従来レイアウトも引き続き対応
- 終了済みのスコア形式にも対応
- これまでの東京V iframe / 鹿島SSL対応も維持

## 適用

この `scraper.py` を、実際にActionが走っているリポジトリ直下へ上書きしてください。

今回のスクリーンショットは
`club-ticket-navi-fctokyo`
のActionです。

公開サイト側の
`fctokyo-supporter-tools`
でも同じscraper.pyを使っている場合は、そちらにも同じ修正を入れてください。

コミット例:

`Support current FC Tokyo schedule layout`
