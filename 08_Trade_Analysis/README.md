# Trade Analysis

## 目的

SBI証券の実売買データを再現可能な形で取り込み、売買傾向、保有期間、勝ち負けの
パターンからSado Frameworkを検証・改善するための基盤です。

## 非公開データ方針

元CSV、SQLite、個別取引、損益・資産額を含む生成レポートは公開GitHubへ登録しません。
CSVは`data/private/`、DBは`data/database/`、生成物は`data/generated/`に置きます。
各ディレクトリは`.gitignore`で保護されています。

## 実行順

リポジトリのルートで次の順に実行します。

```powershell
python scripts/import_sbi_executions.py `
  --input data/private/document.csv `
  --database data/database/investment_lab.sqlite

python scripts/build_closed_trades.py `
  --database data/database/investment_lab.sqlite

python scripts/generate_trade_reports.py `
  --database data/database/investment_lab.sqlite `
  --output data/generated
```

macOS/LinuxではPowerShellの継続記号を`\`に置き換えてください。各スクリプトの詳細は
`--help`で確認できます。

## 損益とFIFO

確定損益はSBI記載の信用決済損益を優先します。FIFO計算は建玉指定、株式分割、諸経費を
完全には再現できないため、保有期間と売買傾向の推定に利用します。取得期間より前の
建玉や期間末の未決済建玉は、未対応約定としてDBへ記録されます。

## 出力

`data/generated/`へ以下を生成します。

- `Trading_Statistics.md`
- `closed_trades.csv`
- `by_security.csv`

これらは個人データを含むためコミットしないでください。

