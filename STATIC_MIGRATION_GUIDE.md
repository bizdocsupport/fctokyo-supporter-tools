# fctokyo.xyz 静的サイト移植ガイド

## この版の構成

```text
docs/
├ index.html               fctokyo.xyz のトップ
├ CNAME                    fctokyo.xyz
├ assets/site.css
├ data/ticket-data.json    自動生成される表示データ
└ ticket/
  ├ index.html             チケットナビ
  └ app.js
```

既存のPython処理は残しています。

```text
scraper.py → updater.py → data/*.csv
                          ↓
              tools/build_static_site.py
                          ↓
              docs/data/ticket-data.json
```

Streamlitは画面表示に使わず、GitHub Actionsによる情報収集だけ継続します。

## ローカル確認

リポジトリ直下で次を実行します。

```bash
python tools/build_static_site.py
python -m http.server 8000 --directory docs
```

ブラウザで次を開きます。

```text
http://localhost:8000/
http://localhost:8000/ticket/
```

`docs/index.html`を直接ダブルクリックすると、ブラウザの制約によりJSONを読み込めないため、必ずローカルサーバーで確認してください。

## GitHub Pagesの設定

1. この版をGitHubの`main`ブランチへ上書きまたはマージ
2. GitHubのリポジトリで`Settings`を開く
3. `Pages`を開く
4. Sourceを`Deploy from a branch`
5. Branchを`main`、Folderを`/docs`
6. 保存

`docs/CNAME`には`fctokyo.xyz`を設定済みです。

## お名前.comのDNS

GitHub Pagesに表示された案内に従い、Web用のDNSレコードを設定します。ネームサーバーを丸ごと変更するのではなく、既存のメール設定がある場合はMX・TXTを維持してください。

## 自動更新

既存の`.github/workflows/update-data.yml`へ次を追加済みです。

```text
python updater.py
python tools/build_static_site.py
```

更新されたCSVと`docs/data/ticket-data.json`が同時にコミットされ、GitHub Pagesへ反映されます。

## カレンダーアプリ

トップページの「試合日程カレンダー」は、現在のStreamlitアプリへリンクしています。
カレンダー側のリポジトリを移植後、リンクを`calendar/`へ変更します。
