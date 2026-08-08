# Canonical Portfolio State

このディレクトリは、Sado Investment Labの機械可読なPortfolio Stateを管理する。

## Authority

```text
直近VERIFIED Snapshot
+ Snapshot以降のSBI確定約定
= data/portfolio/current.json
```

`Current_Status.md`は表示先であり、Portfolioの一次SSoTにはしない。会話記憶や数量不明のMarkdownから数量を推測しない。

## Files

- `snapshots/*.json`: SBI等で照合済みのVERIFIED Snapshot
- `current.json`: 現在のCanonical Portfolio State

`current.json`は`VERIFIED`、`PROVISIONAL`、`MISMATCH`のいずれかを明示する。`MISMATCH`は差分を記録し、自動修正しない。

## Verification scope

初回の`VERIFIED` Snapshotは、SBIの保有証券一覧と信用建玉一覧で明示された国内上場株式を対象とする。
現行schemaでposition typeを一意に表現できない投資信託は、株式の`cash`へ推測変換せず対象外とする。

## Build

```text
python scripts/manage_portfolio_state.py
```

週次照合では、SBI由来の明示的なPosition Snapshotを渡す。

```text
python scripts/manage_portfolio_state.py \
  --verify-positions path/to/verified-positions.json \
  --verification-source sbi-2026-W32.csv \
  --verification-as-of 2026-08-08 \
  --promote-verified \
  --refresh-current-status Current_Status.md
```

取引履歴CSV、証券会社の認証情報、秘密情報はGitHubへ保存しない。
