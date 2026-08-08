# ニュースと検証結果

このディレクトリにニュースと検証結果を保存します。

## AI Key Person Watch

AI主要人物の重要ニュース差分は、月次Markdownへ追記します。既存ログは`AI_Key_Person/`、新規ログの標準保存先は`AI_Key_Person_Watch/`です。Pages生成処理は移行期間中、両方を読み取ります。

```markdown
## YYYY-MM-DD HH:MM JST

### 人物名 / テーマ

- 関連企業・テーマ: ...
- 何が変わったか: ...
- 投資上の意味: ...
- Source: 媒体・日付 — https://example.com/
```

「追加情報なし」は保存しません。ニュース全文ではなく、前回から変化した投資判断上の要点だけを記録します。
