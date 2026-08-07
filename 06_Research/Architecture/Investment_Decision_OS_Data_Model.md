# Investment Decision OS Data Model

Issues: #49, #53

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

| Storage | Responsibility | Git |
|---|---|---|
| Markdown / YAML | 人間が管理する投資仮説、企業研究、Universe、ルール | 管理する |
| `master.db` | 銘柄、テーマ、Universe履歴、Framework/Model/Routine metadata | 管理する |
| `history.db` | Candidate、Decision、Portfolio/Capital、Outcome、Journal等の研究履歴 | 管理する |
| `analysis.db` | Tick/分足、板、特徴量、分析キャッシュ等の大容量・再生成可能データ | 管理しない |
| Generated JSON | GitHub Pages 表示用の生成物。SSoTではない | 必要な公開生成物のみ |
| Raw / Imported Data | SBI CSV、市場データ、外部取得データ | 原則管理しない |

### Research Asset Principle

Sado Investment Lab は通常のアプリケーションではなく研究リポジトリです。

そのためSQLiteを一律にGitから除外せず、**長期的な研究成果そのものを含むDBはGitで履歴管理**します。一方、巨大化しやすく再取得・再生成できるデータはローカル専用DBへ分離します。

```text
Markdown / YAML ───────┐
                       ├─> Research SSoT ─> Decision / Learning Engines ─> GitHub Pages
master.db / history.db ┘

analysis.db ─────────────> reproducible working data / high-volume analysis
```

## Database Layout

```text
data/database/
├── master.db    # Git-managed research master
├── history.db   # Git-managed research history
└── analysis.db  # local-only, gitignored

database/migrations/
├── master/
├── history/
└── analysis/
```

### `master.db` — Git-managed

保存対象:

- `decision_securities`
- `decision_themes`
- `decision_security_themes`
- `universe_membership`
- `model_versions`
- `routine_versions`
- `framework_metadata`

企業Markdownや `data/masters/stocks.json` を置き換えるものではなく、Decision OSから履歴参照するための正規化された研究マスターです。

Universe は `valid_from` / `valid_to` を保持し、後知恵で当時の監視対象を改変しない設計にします。

### `history.db` — Git-managed

保存対象:

- `portfolio_snapshots`
- `position_snapshots`
- `capital_snapshots`
- `signals`
- `market_states`
- `capital_policies`
- `candidates`
- `candidate_factors`
- `decisions`
- `decision_checks`
- `decision_trade_links`
- `outcomes`
- `missed_opportunities`
- `daily_reviews`

これはAIと人間の意思決定過程を蓄積する**研究履歴**です。

例えば半年後に次を検証できます。

- Candidate Score 90以上の1日・5日・20日後成績
- BUY候補を人間が見送ったケースの結果
- 決断遅延による価格差
- 余力不足による機会損失
- Morning Routine / Model Version別の精度

### `analysis.db` — Local only

保存対象:

- `market_observations`
- `security_observations`
- `order_book_snapshots`
- `intraday_features`
- `analysis_cache`

Tick、分足、板情報、特徴量などは巨大化しやすく、外部データから再生成可能です。そのためGitには保存しません。

必要な研究結果だけを `history.db` へ昇格させます。

```text
analysis.db
   ↓ analysis / aggregation
Signal / Market State / Candidate
   ↓
history.db
```

## Cross-database References

SQLiteファイルを分離したため、`history.db` から `master.db` のテーブルへSQLiteの外部キーは張りません。

例えば `history.db.candidates.security_code` は `master.db.decision_securities.security_code` への**論理参照**です。

アプリケーション層で参照整合性を検証し、必要に応じて `ATTACH DATABASE` を利用して横断クエリします。

この方針により、研究マスターと長期履歴を独立してGit管理できます。

## Migration

3DBすべてを初期化・更新:

```bash
python scripts/init_decision_os_db.py
```

個別DBのみ:

```bash
python scripts/init_decision_os_db.py --target master
python scripts/init_decision_os_db.py --target history
python scripts/init_decision_os_db.py --target analysis
```

任意ディレクトリで検証:

```bash
python scripts/init_decision_os_db.py --db-dir /tmp/decision-os
```

migrationはDBごとに独立して管理し、同じmigrationは一度しか適用されません。適用履歴は各DBの `schema_migrations` に保存します。

## Data Flow

```text
External / Raw Data
       │
       ▼
 analysis.db
 (market / intraday facts)
       │
       ▼
Analysis Engines
       │
       ├── Signal
       ├── Market State
       └── Candidate
              │
              ▼
          history.db
              │
master.db ────┤
              ▼
      Human Decision / Trade
              │
              ▼
        Outcome / Learning
              │
              ▼
         GitHub Pages
```

## Core / Trend Portfolio Readiness

Issue #50の Core / Trend 二層ポートフォリオに備え、`history.db.position_snapshots` は次を持ちます。

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

- `master.db` / `history.db` / `analysis.db` がそれぞれ必要テーブルを生成する
- migrationが冪等である
- Fact / Candidate / Human Decisionが別レイヤ・別DBとして保存できる
- 個別targetだけをmigrationできる

## Git Policy

Git管理する:

```text
data/database/master.db
data/database/history.db
```

Git管理しない:

```text
data/database/analysis.db
data/database/analysis.db-*
*.sqlite
*.sqlite3
その他の *.db
```

`master.db` と `history.db` はバイナリ差分を人間がレビューする対象ではありません。変更理由は同じcommit/PR内のMarkdown、migration、Journal、生成レポートで説明します。

DBが将来大きくなりGit運用に支障が出る場合は、Git LFS、期間分割、またはGit管理用の再現可能スナップショット方式を検討します。

## Next Steps

1. `data/masters/stocks.json` / Markdownから `master.db` へ同期する仕組みを作る
2. `Current_Status.md` → `history.db` portfolio / capital snapshot の変換方式を実装する
3. Universe Intelligence Engine が `history.db.candidates` を生成する契約を定義する
4. Capital Policy Engine が `history.db.capital_policies` を生成する契約を定義する
5. Trade Journalへ日次スナップショットを統合する
6. `analysis.db` から研究結果を `history.db` へ昇格するETLを設計する

## Guardrails

- 既存SBI取引データをmigrationで変更・削除しない
- 不明値を推測して埋めない。NULLを使用する
- 将来データを過去Candidate生成に混ぜない
- Generated JSONをSSoTにしない
- `analysis.db` の巨大データを誤ってGitへ追加しない
- Candidateは注文指示ではない
- 最終売買判断はHuman-in-the-loopを維持する
