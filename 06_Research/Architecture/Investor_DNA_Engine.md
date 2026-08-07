# Investor DNA Engine

Issues: #55, #57

## Purpose

Investor DNA Engine は「この銘柄は自分に合う／合わない」を固定的な性格ラベルとして扱いません。

```text
Poor result
  ↓
Cause decomposition
  ↓
Measured mismatch
  ↓
Testable adaptation
  ↓
Re-test
  ↓
Learning
```

方向予測が正しくても利益化できない場合、保有周期・損失許容・利確・再エントリー・市場局面などのどこにミスマッチがあるかを実取引から説明可能にします。

Issue #57 ではさらに、**本来の投資能力（Native DNA）と、現在それを実行できる環境（Environment）を分離**します。

```text
Market Opportunity
      ×
Native Investor DNA
      ×
Current Environment
      ×
Capital Feasibility
      ↓
Personal Executable Strategy
```

投資スタイルが変化したとき、能力低下と決めつけず、仕事・通信・監視頻度などの外部制約による Style Drift を検証します。

## Data Flow

```text
Trade Analysis (Trade Episodes)
        │
        ├── realized win/loss / PF / payoff
        ├── holding period
        ├── LONG / SHORT
        └── return rate
                 │
Environment Profiles
        │
        ├── market-open availability
        ├── check interval
        ├── network reliability
        ├── reaction capability
        └── pre-market analysis availability
                 │
Optional security price history
        │
        ├── post-exit 1/3/5/10/20d return
        └── days to post-exit peak
                 │
                 ▼
          Investor DNA Engine
                 │
        ├── Native DNA
        ├── Compatibility Score
        ├── Environment Fit
        ├── Style Drift
        ├── Lifetime Profit Contribution
        ├── Tail-risk warning
        └── Daily DNA Fit interface
                 │
        ├── history.db
        └── GitHub Pages
```

## Explainability First

不透明な機械学習から始めません。すべてのScoreは要素・サンプル数・Confidence・根拠を併記します。

Compatibility Score v0.1:

- Historical Win Fit
- Profit Factor Fit
- Realized Return Fit

Environment Fit v0.2 は能力評価ではありません。現在その能力を実行できる条件の評価で、以下を明示的な重みで合成します。

- market-open monitoring: 25%
- morning execution availability: 20%
- network reliability: 15%
- fast reaction capability: 20%
- pre-market analysis availability: 10%
- expected check interval: 10%

HIGH / MEDIUM / LOW は 90 / 60 / 25 の運用スコアへ写像します。この変換はモデルバージョンで管理し、後から実績で校正します。

## Native DNA vs Environment

Native DNA は現在の制約から独立して、過去実績で再現した強みを保存します。

初期実装で実データから安全に算出できるもの:

- short-horizon repeatability
- repeated-security execution
- LONG / SHORT別実績
- win rate / PF / payoff

高ボラ適性・上昇トレンド適性など、市場価格特徴量が必要な項目はP/Lだけから推測しません。価格履歴が接続されるまで `UNKNOWN` 相当として扱います。

## Environment Profiles

`data/config/investor-environments.json` に、公開可能な一般化済み運用条件を期間別で保存します。

個別の勤務先名・具体的な場所は公開データへ保存しません。

現時点の2期間:

- frequent intraday access: 寄付き監視と短い定期チェックが可能だった期間
- limited intraday access: 寄付き実行・通信・即応性が制約される現在期間

Style Drift はこの境界で実取引の保有期間・PF・LONG/SHORT損益などを比較します。

## Lifetime Profit Contribution

勝率だけでなく、実際の資産形成への寄与を銘柄別に測定します。

主な指標:

- lifetime realized P/L
- positive profit contribution share
- trade count
- win rate
- PF / payoff
- largest win / loss
- gross profit / loss
- top-1 loss / gross profit
- loss concentration
- LONG / SHORT P/L

研究ラベル:

- `HERO`: 大きな利益寄与と十分な再現性
- `COMPATIBLE`: 高い実績適合度
- `NORMAL`: 明確な強弱未確定
- `CHALLENGE`: 累積損失または大きなテールリスク
- `RESEARCH`: サンプル不足

これらは売買許可ではなく研究用分類です。

## Tail Risk / Danger Pattern

高勝率でも一度の巨大損失で利益が消えるケースを明示的に検出します。

初期パターン:

`TAIL_LOSS_DESTROYS_SMALL_WINS`

判定候補:

- win rate が高いのに PF < 1
- 最大損失が gross profit の50%以上
- 最大損失が総損失の大部分を占める
- LONG / SHORTの損益差が大きい

この警告により「勝率90%だから相性が良い」という誤った単純化を防ぎます。

## Cause Policy

原因はデータが支持するときだけ付与します。

- `HOLDING_PERIOD_TOO_SHORT`
- `HOLDING_PERIOD_TOO_LONG`
- `EARLY_PROFIT_TAKING`
- `LATE_STOP`
- `UNKNOWN`

`UNKNOWN` は「現データでは原因未解明」という研究状態です。

## Post-exit Analysis

任意の株価履歴を与えた場合、売却価格に対して1/3/5/10/20営業日後と、20営業日以内のピークまでの日数を計測します。

たとえば売却後5営業日リターンが継続的に大きくプラスで、ピーク到達が保有周期より遅い場合、`HOLDING_PERIOD_TOO_SHORT` または `EARLY_PROFIT_TAKING` の候補になります。

## Daily DNA Fit Interface

Candidate Engineとロジックを重複させず、候補JSONを受け取れる接続口を用意します。

```text
Market Score         40%
DNA Fit              35%
Environment Fit      25%
Capital Fit          optional
Execution Difficulty penalty
        ↓
Final Personal Fit
```

Market Scoreが高くても、連続監視を必要とするセットアップならCurrent EnvironmentによってPersonal Fitを下げられます。

## History DB

Issue #53 の `history.db` に保存します。

#55:

- `investor_dna_profiles`
- `security_behavior_profiles`
- `compatibility_assessments`
- `compatibility_factors`
- `strategy_experiments`

#57:

- `investor_environment_profiles`
- `investor_style_periods`
- `environment_fit_assessments`
- `security_lifetime_contributions`
- `theme_lifetime_contributions`
- `risk_pattern_assessments`
- `daily_dna_fit_assessments`

生の大量株価・分足・板データは `analysis.db` に残し、説明可能な研究成果だけをGit管理の `history.db` に保存します。

## CLI

Investor DNA v2:

```bash
python scripts/investor_dna_v2.py
```

株価フォローアップ:

```bash
python scripts/investor_dna_v2.py --prices-json data/local/investor-dna-prices.json
```

Candidate接続:

```bash
python scripts/investor_dna_v2.py --candidates-json data/local/dna-candidates.json
```

history.dbへ研究結果を保存する場合は、先にmigrationを適用します。

```bash
python scripts/init_decision_os_db.py --target history
python scripts/investor_dna_v2.py --history-db data/database/history.db
```

## Pages

GitHub Pages:

```text
/research/investor-dna/
```

表示内容:

- Native DNA
- Current Environment Fit
- Style Drift
- Lifetime Profit Contribution
- Hero / Challenge Stocks
- Tail-risk / Danger Patterns
- 相性ランキングと原因
- Daily DNA Fit（候補入力がある場合）

## Current Limitations

- 全銘柄の売却後株価履歴はまだ常時接続されていません。
- 高ボラ・上昇トレンド適性は価格特徴量なしでは推測しません。
- Environment Fitは透明な初期ヒューリスティックであり、今後の実績で校正します。
- Theme contribution はTrade Analysisにテーマ情報が存在する場合だけ算出します。
- `UNKNOWN` を推測で埋めません。
