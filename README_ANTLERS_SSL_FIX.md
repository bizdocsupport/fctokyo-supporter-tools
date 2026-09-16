# 鹿島アントラーズ公式サイト SSL エラー回避パッチ v0.1

## 今回のエラー

GitHub Actions の `Run scraper` で次のエラーが発生しています。

```text
requests.exceptions.SSLError
SSLCertVerificationError
www.antlers.co.jp
unable to get local issuer certificate
```

東京Vの販売日程取得処理ではなく、
鹿島アントラーズ公式サイトのSSL証明書検証で全体処理が停止しています。

## 修正内容

通常は従来どおりSSL証明書を検証します。

ただし `antlers.co.jp` / `*.antlers.co.jp` で
`SSLError` が発生した場合だけ、証明書検証を無効にして1回再試行します。

他ドメインには影響しません。

東京V iframe対応も含んだ scraper.py をベースにしているため、
前回の東京V修正は残っています。

## 反映方法

リポジトリ直下の `scraper.py` を、このパッチの `scraper.py` で上書きしてください。

コミット例:

```text
Handle Antlers SSL certificate error
```

その後、

`Actions` → `Update FC Tokyo public data` → `Run workflow`

で再実行してください。
