# 終了済み試合 + 次の未開催試合の混在修正 v0.1

## GitHub Actions #109 の失敗原因

`Run parser tests` で以下が失敗しています。

```text
test_completed_match_does_not_mix_with_next_upcoming_match
AssertionError: 1 != 2
```

FC東京公式の試合一覧では、

終了済み:
```text
ガンバ大阪
0
-
2
FC東京
```

未開催:
```text
FC東京
VS
名古屋グランパス
```

のように表示形式が異なります。

旧パーサーは `VS` だけを試合の区切りとして探していたため、
終了済み試合から次の未開催試合の `VS` まで探索してしまい、
2試合を1試合として混ぜることがありました。

## 修正内容

- 次の試合の日付を越えて `VS` を探さない
- `2 - 0` 形式の終了済み試合も解析
- PK戦の `[ 5 - 4 ]` のような追加スコアも考慮
- 東京V iframe対応を維持
- 鹿島SSL回避対応を維持

## 反映

リポジトリ直下の `scraper.py` を上書きしてください。

`tests/test_completed_match_regression.py` は確認用なので、
追加しても追加しなくても構いません。

コミット例:

```text
Fix parsing of completed and upcoming matches
```

その後 GitHub Actions を再実行してください。
