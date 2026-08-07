# Investment Decision OS Data Model

Issue: #49

## Purpose

Investment Decision OS の観測、分析、候補抽出、人間判断、売買、結果、学習を、後から再現・検証できる形で保存するためのデータモデルです。

最重要原則は次の分離です。

```text
FACT / OBSERVATION
        ↓
DERIVED FEATURE / MODEL OUTPUT
        ↓
AI SUGGESTION
        ↓
HUMAN DECISION
        ↓
EXECUTION
        ↓
OUTCOME
        ↓
REVIEW / LEARNING
```

事実と推測、人間判断とAI提案を同じレコードへ混在させません。

## Storage Responsibilities

| Storage | Responsibility |
|---|---|
| Markdown / YAML | 人間が管理する投資仮説、企業研究、Universe、ルール |
| SQLite | 時刻付き観測、分析結果、候補、判断、資金状態、結果履歴 |
| Generated JSON | GitHub Pages 表示用の生成物。SSoTではない |
| Raw / Imported Data | SBI CSV、市場データ、外部取得データ |

SQLite本体は `data/database/` 配下に置き、Gitへコミットしません。スキーマ変更は `database/migrations/` で管理します。

## Migration

初期化または更新:

```bash
python scripts/init_decision_os_db.py
```

任意DBで確認する場合:

```bash
python scripts/init_decision_os_db.py --db /tmp/investment.db
```

同じmigrationは一度しか適用されません。適用履歴は `schema_migrations` に保存します。

## Core Domains

### Reference / Knowledge Link

- `decision_securities`
- `decision_themes`
- `decision_security_themes`
- `universe_membership`

既存の企業Markdownや `data/masters/stocks.json` を置き換えるものではありません。Decision OS 内で履歴参照するための正規化層です。

Universe は `valid_from` / `valid_to` を保持し、後知恵で当時の監視対象を改変しない設計にします。

### Observation — Facts Only

- `market_observations`
- `security_observations`
- `portfolio_snapshots`
- `position_snapshots`
- `capital_snapshots`

価格、出来高、保有状態、買付余力など、その時点で観測された事実だけを保存します。

`Current_Status.md` が現在保有状況の人間可読SSoTである運用は維持し、構造化DBは履歴スナップショットとして利用します。

### Analysis / Model Output

- `signals`
- `market_states`
- `capital_policies`
- `candidates`
- `candidate_factors`

例:

```text
Observation
富士通 1分足終値 3,674円

Model Output
Momentum weakening

Candidate
Today Score 92 / BUY_CANDIDATE
```

これらを同じ事実テーブルに書き込みません。

### Human Decision

- `decisions`
- `decision_checks`

AI提案と人間判断を別カラムで保存します。

例:

```text
AI Suggestion: BUY_CANDIDATE
Human Decision: WATCH
Reason: 板・歩み値確認まで待つ
```

これにより、モデルと人間のどちらに改善余地があったかを後から検証できます。

### Execution Link

- `decision_trade_links`

既存SBI取引テーブルを作り直さず、Decision OSの判断と既存Trade IDを紐付けます。

### Outcome / Learning

- `outcomes`
- `missed_opportunities`
- `daily_reviews`
- `model_versions`
- `routine_versions`

CandidateやDecisionは後から書き換えず、評価結果を `outcomes` に追加します。

これにより、次の分析を可能にします。

- Candidate Score 90以上の1日・5日・20日後成績
- BUY候補を人間が見送ったケースの結果
- 決断遅延による価格差
- 余力不足による機会損失
- Morning Routine / Model Version別の精度

## Core / Trend Portfolio Readiness

Issue #50の Core / Trend 二層ポートフォリオに備え、`position_snapshots` は次を持ちます。

- `portfolio_role`: `CORE` / `TREND`
- `capital_bucket`

`capital_policies` は以下も保持します。

- `core_target_ratio`
- `trend_target_ratio`
- `target_cash_ratio_min/max`

市場環境に応じて余力とCore/Trend配分を変化させられるようにします。

## Model Versioning

分析結果には `model_name` と `model_version` を保存します。

ルール変更前後の結果を混ぜず、例えば次を比較可能にします。

```text
candidate-engine v0.1
candidate-engine v0.2
```

## Tests

```bash
python -m unittest tests/test_decision_os_schema.py
```

最低限、以下を検証します。

- migrationが必要テーブルを生成する
- migrationが冪等である
- Observation / Candidate / Human Decisionを別レイヤとして保存できる

## Next Steps

1. 既存SQLiteスキーマを監査し、同義テーブルが存在する場合は統合方針を決定する
2. `Current_Status.md` → portfolio / capital snapshot の変換方式を設計する
3. Universe Intelligence Engine が `candidates` を生成する契約を定義する
4. Capital Policy Engine が `capital_policies` を生成する契約を定義する
5. Trade Journalへ日次スナップショットを統合する

## Guardrails

- 既存SBI取引データをmigrationで変更・削除しない
- 不明値を推測して埋めない。NULLを使用する
- 将来データを過去Candidate生成に混ぜない
- Generated JSONをSSoTにしない
- Candidateは注文指示ではない
- 最終売買判断はHuman-in-the-loopを維持する
