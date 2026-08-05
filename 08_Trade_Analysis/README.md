# Trade Analysis

SBI証券の約定履歴から、売買の再現性と改善点を検証するための分析基盤です。

## プライバシー方針

次の情報は公開リポジトリへコミットしません。

- SBI証券から取得した元CSV
- SQLiteデータベース
- 個別約定、銘柄名、証券コード
- 実際の価格、数量、損益額、資産額
- 口座を特定できる情報
- 個人用の生成レポート

これらは `.gitignore` で保護された `data/private/`、`data/database/`、
`data/generated/` の中だけで扱います。公開用JSONには、匿名化した集計値と
金額を含まない指数だけを出力します。

## 分析単位

### 約定

証券会社CSVの1行に相当する最小単位です。

### 決済ロット

FIFOで一つの買いと売りを対応付けた単位です。

### Trade Episode

同一銘柄・口座区分・売買方向について、建玉がゼロの状態から始まり、
再びゼロへ戻るまでを一つの取引として集約します。分割買い、部分決済、
買い増しを一つの投資判断として検証するための標準単位です。

現物と信用、LONGとSHORTは混在させません。未決済のエピソードは
`OPEN` として保存しますが、確定損益の統計からは除外します。

## 実行手順

リポジトリのルートで次の順に実行します。

```powershell
python scripts/import_sbi_executions.py `
  --input data/private/document.csv `
  --database data/database/investment_lab.sqlite

python scripts/build_closed_trades.py `
  --database data/database/investment_lab.sqlite

python scripts/build_trade_episodes.py `
  --database data/database/investment_lab.sqlite

python scripts/generate_trade_reports.py `
  --database data/database/investment_lab.sqlite `
  --output data/generated

python scripts/generate_advanced_trade_reports.py `
  --database data/database/investment_lab.sqlite `
  --output data/generated

python scripts/generate_public_trade_dashboard.py `
  --database data/database/investment_lab.sqlite `
  --output data/generated/public/trade-analysis-summary.json
```

各スクリプトの引数は `--help` で確認できます。

## 生成物

個人用の `data/generated/` には、次のファイルを生成します。

- `Trading_Statistics.md`
- `Advanced_Trading_Statistics.md`
- `closed_trades.csv`
- `trade_episodes.csv`
- `by_security.csv`
- `public/trade-analysis-summary.json`

すべてGit管理対象外です。公開サイトのビルドでは、ローカルに匿名集計JSONが
存在すればそれを利用し、GitHub Actionsでは匿名のテスト用集計を利用します。

## 公開ダッシュボード

`/trade-analysis/` では、次の集計だけを公開します。

- 取引数、勝率、PF、ペイオフレシオ
- 金額を除いた期待値指数
- 平均・中央値の保有日数
- 最大連勝・連敗
- 保有期間別、曜日別、LONG/SHORT別、現物/信用別の集計
- 利益集中度と上位取引除外後PF

個別の売買を逆算できる情報は公開しません。

## 投資改善メモ

`Improvement_Notes.md` は、集計結果を次の投資判断へつなげるための公開用Markdownです。

- `Today's Lesson`: その日の学び
- `AI先生コメント`: 判断過程の評価と改善案
- `Next Action`: 次回の売買で確認する行動
- `Framework Candidate`: Frameworkへ昇格を検討する教訓
- `Today's Score`: 成績ではなく判断過程の自己評価

Pages生成時にTrade Analysisへ組み込まれます。公開ダッシュボードのプライバシー方針に合わせ、銘柄名、証券コード、価格、数量、実損益額は記載しません。

## 全期間集計

分析期間は年月を固定せず、SQLiteに存在する決済済みTrade Episodeの全期間から自動生成します。

- 全期間サマリー
- 年別パフォーマンス
- 月別パフォーマンス
- 累積結果指数
- ドローダウン指数
- データ品質

詳しい定義、再生成手順、既知の制約は
[`docs/Trade_Analysis_All_Period.md`](../docs/Trade_Analysis_All_Period.md)
を参照してください。

## 計算上の注意

既存DBとの互換性のためSQLiteの金額列は `REAL` を維持しています。Trade
Episodeの計算時は文字列表現から `Decimal` へ変換し、浮動小数点誤差の影響を
抑えています。実データでは、証券会社が示す確定損益との照合も継続します。

この仕組みは投資判断を自動化するものではありません。結果だけでなく、
どの保有期間・方向・市場局面で判断の再現性が高いかを検証するために使います。

