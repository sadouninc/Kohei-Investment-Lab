# Investor DNA Engine

Issue: #55

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

## MVP Data Flow

```text
Trade Analysis (Trade Episodes)
        │
        ├── realized win/loss / PF / payoff
        ├── holding period
        └── return rate
                 │
Optional security price history
        │
        ├── post-exit 1/3/5/10/20d return
        └── days to post-exit peak
                 │
                 ▼
          Investor DNA Engine
                 │
        ├── compatibility score
        ├── confidence
        ├── mismatch cause
        └── strategy experiment
                 │
        ├── history.db
        └── GitHub Pages
```

## Explainability First

MVPでは不透明な機械学習を使いません。

Compatibility Scoreは現在、実現した取引の以下の要素から構成します。

- Historical Win Fit
- Profit Factor Fit
- Realized Return Fit

Scoreだけで判断せず、必ず `sample_count`、`confidence`、`primary_mismatch_code`、根拠値を併記します。

## Cause Policy

原因はデータが支持するときだけ付与します。

初期実装で扱う主な原因:

- `HOLDING_PERIOD_TOO_SHORT`
- `HOLDING_PERIOD_TOO_LONG`
- `EARLY_PROFIT_TAKING`
- `LATE_STOP`
- `UNKNOWN`

`UNKNOWN` は失敗ではありません。「現データでは原因未解明」という研究状態です。

今後、MFE/MAE、決算前後、板・分足、Market Phase、再エントリー履歴が蓄積した段階でCause Taxonomyを拡張します。

## Post-exit Analysis

任意の株価履歴を与えた場合、売却価格に対して以下を計測します。

- 1営業日後
- 3営業日後
- 5営業日後
- 10営業日後
- 20営業日後
- 20営業日以内のピークまでの日数

たとえば売却後5営業日リターンが継続的に大きくプラスで、ピーク到達が保有周期より遅い場合、`HOLDING_PERIOD_TOO_SHORT` または `EARLY_PROFIT_TAKING` の候補になります。

## History DB

Issue #53 の `history.db` に以下を追加します。

- `investor_dna_profiles`
- `security_behavior_profiles`
- `compatibility_assessments`
- `compatibility_factors`
- `strategy_experiments`

生の大量株価データは `analysis.db` に残し、説明可能な研究成果だけを `history.db` に保存します。

## CLI

Trade Analysisの公開JSONだけで実行:

```bash
python scripts/investor_dna.py
```

株価フォローアップを追加:

```bash
python scripts/investor_dna.py --prices-json data/local/investor-dna-prices.json
```

history.dbへ研究結果を保存:

```bash
python scripts/investor_dna.py --history-db data/database/history.db
```

## Pages

GitHub Pages:

```text
/research/investor-dna/
```

表示内容:

- 投資家全体の実取引プロファイル
- 相性が高い銘柄
- 利益化が難しい銘柄候補
- 銘柄別Compatibility Score / Confidence
- 原因コードと説明
- 売却後推移（価格履歴がある場合）
- Strategy Experiment候補

## Current Limitation

現時点でコミット済みTrade Analysisには実取引はありますが、全銘柄の売却後株価履歴は含まれていません。

したがって初回Pagesでは、実取引ベースの適合度は算出できますが、周期・早売り原因について証拠が不足する銘柄は `UNKNOWN` とします。

これは意図した挙動です。将来 `analysis.db` の株価履歴を接続すると、同じEngineが原因診断を深めます。
