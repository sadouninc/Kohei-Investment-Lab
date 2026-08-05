# Trade Analysis — 全期間集計仕様

## 目的

SQLiteで追跡できる最古の約定から最新の約定までを自動集計し、売買判断の改善へ利用する。

年月はコードへ固定しない。取引が存在する年・月だけを生成する。

## データフロー

```text
SBI約定CSV
  ↓ import_sbi_executions.py
executions（SQLite）
  ↓ build_closed_trades.py
closed_trades（FIFO決済ロット）
  ↓ build_trade_episodes.py
trade_episodes（建玉ゼロからゼロまで）
  ↓ generate_public_trade_dashboard.py
匿名集計JSON
  ↓ .github/pages/build_site.py
Trade Analysis
```

WebページがSQLiteを直接読むことはない。ビルド前に生成したJSONを正とする。

## 1取引の定義

統計上の1取引は `Trade Episode` とする。

同一銘柄、同一口座区分、同一売買方向について、建玉がゼロの状態から始まり、再びゼロへ戻るまでを一つにまとめる。分割買い、買い増し、部分決済を一つの投資判断として評価する。

- LONGとSHORTは分ける
- 現物と信用は分ける
- 未決済Episodeは `OPEN` として保持する
- 損益統計は `CLOSED` のEpisodeだけを対象とする
- 保有日数は営業日ではなく暦日

FIFO決済ロット数とTrade Episode数は、集計単位が異なるため一致しない。

## 全期間・年次・月次

対象期間は、決済済みTrade Episodeの最小開始日と最大決済日から決める。

年次・月次は決済日を基準に分類する。年次と月次の取引件数・損益合計が全期間値と一致することを自動テストする。

## 公開指数

個別損益や資産額を公開しないため、金額指標は指数化する。

```text
基準値 = 全期間の1取引あたり絶対損益平均
結果指数 = 対象損益 ÷ 基準値 × 100
```

同じJSON内の期間比較には利用できるが、実損益額へ換算するための情報は公開しない。

累積結果は決済済みEpisodeを月単位で合計して積み上げる。入出金、含み損益、配当を含まないため、証券口座の総資産推移ではない。

ドローダウンは、累積結果指数の過去最高値からの低下幅とする。

## データ品質

公開ページには次を表示する。

- 集計対象期間と最終更新日
- 読み込んだCSV数
- 有効約定レコード数
- 決済済み・未決済Episode数
- 対応不能約定数
- 銘柄名未解決件数
- 重複除外件数
- 対応付け方法

同一約定は、正規化した約定内容と同一内容の出現順から生成したfingerprintで重複登録を防ぐ。

`import_audit` 導入前に作られたDBは、過去の重複スキップ件数を保持していない。この場合は「既存DBには監査値なし」と表示する。次回以降のCSV取り込みでは、元レコード数、追加数、重複数、エラー数を記録する。

株式分割などの調整は元約定を書き換えない。将来、注記・調整マスタを追加して扱う。

## 再生成

```powershell
python scripts/import_sbi_executions.py `
  --input data/private/document.csv `
  --database data/database/investment_lab.sqlite

python scripts/build_closed_trades.py `
  --database data/database/investment_lab.sqlite

python scripts/build_trade_episodes.py `
  --database data/database/investment_lab.sqlite

python scripts/generate_public_trade_dashboard.py `
  --database data/database/investment_lab.sqlite `
  --output .github/pages/fixtures/trade-analysis-summary.json

python .github/pages/build_site.py
```

公開JSON生成時には禁止キー検査が実行される。元CSV、SQLite、銘柄名、証券コード、価格、数量、実損益、個別取引は公開しない。

## 既知の制約と次フェーズ

今回のPhase 1では、全期間、年次、月次、累積結果、ドローダウン、データ品質を実装する。

次の項目はIssue #24の後続Phaseとして扱う。

- 主テーマ・複数タグ・セクターマスタ
- 銘柄別の非公開分析と安全な公開表現
- 複合フィルター
- 損益分布と箱ひげ図
- 決算シーズン分類
- 外部株価データを利用する早売り・損切り遅れ分析

外部株価データは取得元、調整後株価、利用規約を確定するまで実装しない。

