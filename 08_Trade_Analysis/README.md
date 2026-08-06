# Trade Analysis

SBI証券の約定履歴から、売買の再現性と改善点を検証するための分析基盤です。

## プライバシー方針

元CSVとSQLiteは公開リポジトリへコミットしません。ビルド前にローカルで
個人情報を除外し、投資分析に必要な銘柄、数量、価格、損益を含む公開JSONへ
変換します。

公開しない情報は、口座番号、支店番号、ログインID、パスワード、APIキー、
住所、電話番号、メールアドレス、元CSVのパス、取込フィンガープリントです。

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

`public/trade-analysis-summary.json` だけをGit管理し、Pagesの正本として
利用します。それ以外の生成物、元CSV、SQLiteはGit管理対象外です。

## 公開ダッシュボード

`/trade-analysis/` では、次の投資データを公開します。

- 銘柄名・証券コード
- 売買日・現物／信用・買い／空売り
- 数量・平均取得価格・平均決済価格
- 実現損益・利益率・保有期間
- 全期間、年次、月次、銘柄、テーマ、売買区分、保有期間、曜日の集計

口座番号、ログインID、パスワード、APIキー、住所、電話番号、メールアドレス、
元CSVのファイルパス、取込フィンガープリントは公開しません。

この方針は、見た目上の匿名化よりも、後から正確に投資判断を検証できることを
優先するものです。

## 投資改善メモ

`Improvement_Notes.md` は、集計結果を次の投資判断へつなげるための公開用Markdownです。

- `Today's Lesson`: その日の学び
- `AI先生コメント`: 判断過程の評価と改善案
- `Next Action`: 次回の売買で確認する行動
- `Framework Candidate`: Frameworkへ昇格を検討する教訓
- `Today's Score`: 成績ではなく判断過程の自己評価

Pages生成時にTrade Analysisへ組み込まれます。個人情報を含めず、分析に必要な
銘柄名、証券コード、価格、数量、実損益額は記載できます。

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

