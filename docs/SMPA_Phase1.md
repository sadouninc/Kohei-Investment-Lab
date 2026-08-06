# Sado Market Phase Analyzer — Phase 1

## 目的

AI半導体エコシステムの候補40銘柄を事業分類だけで決めつけず、実際の日次リターンから相関、自動クラスタ、統計上の先行・遅行候補を調べる。

## データ

- MVPプロバイダー：Yahoo Finance（`yfinance`）
- ティッカー：銘柄コード + `.T`
- 保存値：日付、四本値、調整後終値、出来高
- 期間：初回2年、以後差分更新
- 欠損日：前方補完しない
- 更新失敗：既存CSVを保持し、ワークフローを失敗として終了する

利用時はデータ提供元の規約を確認する。将来は `PriceProvider` を実装することでJ-Quants等へ交換できる。

## 実行

```text
python -m pip install -r requirements-market-phase.txt
python -m scripts.market_phase.fetch_prices --years 2 --continue-on-error
python -m scripts.market_phase.pipeline
python -m unittest tests.test_market_phase -v
```

## 分析定義

- 正規化価格：`adjusted_close / first_valid_adjusted_close * 100`
- 日次リターン：調整後終値の対数リターン
- 相関：PearsonおよびSpearman。標本数20未満は評価しない
- 相関距離：`1 - Pearson correlation`
- クラスタ：相関距離の平均連結による階層的統合
- 先行・遅行：-10～+10営業日のラグ相関最大値
- 周期性基礎：上昇・下落連続日数

相関は同じ周期や因果関係を意味しない。ラグ相関は「統計上の候補」であり、サンプル外期間で再検証する。

## 公開ページ

`/research/market-phase/ai-semiconductor/`

期間と事業上の仮分類を切り替えられる正規化チャート、相関ヒートマップ、自動クラスタ、相関ペア、先行・遅行候補、データ品質を表示する。

## 自動更新

平日18:15 JSTに価格を差分更新する。手動実行にも対応する。価格CSVが変化した場合だけコミットし、既存のPagesワークフローが公開ページを再生成する。

## 既知の制約

- クラスタ数6はPhase 1の表示候補であり、正式指数の構成ではない
- 新規上場銘柄は取得期間が短い
- 価格データの訂正や配信遅延があり得る
- 正式なSado AI半導体指数、売買シグナル、資金移動分析は対象外
