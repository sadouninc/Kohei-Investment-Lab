# ダイヘン（6622）

> **Sado投資レポート — 既存研究のCompany昇格版**
>
> Version 0.1  
> Sado Investment Lab  
> Updated: 2026-08-08

---

## AIサマリー

ダイヘンは、すでにTrade Journal内で投資アイデアとして研究・記録されていた銘柄である。

今回のCompanyページは新しい分析をゼロから作るものではなく、**2026-08-04のTrade Journalに保存済みのダイヘン研究を、provenanceを維持したままCompaniesへ昇格する**ことを目的とする。

当時の中心テーマは、決算期待で株価が先行して上昇した場合の扱いと、好決算でも市場期待を下回れば材料出尽くしになり得るというリスク管理だった。

現時点で元記録に存在しない財務数値、最新PER、最新需給、事業別評価などは推測で追加しない。

---

## 1. Research Provenance

このページの初期内容は次の既存記録から昇格した。

- Source: `01_Portfolio/Transactions/2026-08.md`
- Source date: `2026-08-04`
- Source section: `Investment Ideas / ダイヘン`
- Published mapping: PR #16 `Fix Trade Journal content mapping and daily structure`
- Promotion issue: #114

PR #16では、2026-08-04のTrade Journalについて `Investment Ideas / ダイヘン・テラドローン` がPublished版へ正しく表示されることが実装・テストされている。

このCompanyページでは、その既存研究を別物として書き直さず、Company Researchから参照できる形へ移す。

---

## 2. 既存Investment Idea — 2026-08-04

2026-08-04時点のTrade Journalには、ダイヘンについて次の判断材料が記録されている。

- 決算期待で株価が大きく上昇した場合、決算前売却を検討
- 当時の記録では100株保有のため、半分だけ売却することはできない
- 15,800円付近まで上昇した場合、期待がかなり織り込まれたと判断する案
- 好決算でも市場期待以下なら材料出尽くしになるリスク
- 企業の長期評価と、決算を跨ぐかどうかは分けて考える

**15,800円は2026-08-04時点の検討条件であり、現在の目標株価・売買指示ではない。**

---

## 3. 当時のMarket Context

同日のTrade Journalでは、市場について次のように記録されていた。

- 市場全体は全面的に強い状態ではなかった
- AI、ロボティクス、国産AI、インフラ関連へ資金が戻り始めている印象
- 大きく上昇した銘柄では利益確定を優先する判断も必要
- 決算期待で大きく上昇した場合は、決算を跨がず利益確定する選択肢を持つ

ダイヘンのInvestment Ideaは、この市場認識の中で記録されたものである。

---

## 4. Fact / Interpretation / Hypothesis

### Fact — 当時の記録

- 2026-08-04のTrade JournalにダイヘンのInvestment Ideaが存在する
- 当時の記録では100株保有とされている
- 決算前の上昇と決算跨ぎの判断が検討対象だった

### Interpretation — 当時の判断

- 株価が決算期待で大きく上昇すると、良い決算でも期待との差によって売られる可能性がある
- 企業の長期評価と、短期の決算イベントを跨ぐ判断は分けるべきである

### Hypothesis / Scenario — 当時の案

- 15,800円付近まで上昇した場合は、期待の織り込みが進んだ可能性を考える
- 決算前売却を選択肢として検討する

これらは2026-08-04時点の投資仮説であり、現在の価格・保有状況・決算情報へ自動的に引き継がない。

---

## 5. Research Status / Missing Data

この初期Companyページは、既存研究を失わずPagesへ昇格することを優先している。

以下は元Trade Journalだけでは確認できないため、**未補完**とする。

- 最新の事業構成・セグメント別収益
- 最新決算数値
- 最新PER・その他バリュエーション
- 最新の信用需給・出来高・相対強度
- 定量化された競争優位
- Earnings Reactionの過去サンプル統計
- Personal Compatibility Score

不足値をAIで推測して埋めない。追加調査を行う場合も、既存研究と新規情報のprovenanceを分けて記録する。

---

## 6. 今後の接続先

このページを起点として、既存Issueの成果を将来統合できるようにする。

- #36 AI Company Card
- #43 Earnings Reaction Model
- #44 Companies Comparison Dashboard
- #45 Personal Stock Compatibility
- #47 Investment Decision OS Architecture

特に #43 では、ダイヘンが「決算前期待・上昇と決算後反応」の初期検証ケースとして想定されているため、将来は当時のInvestment Ideaと実際の決算後反応を分離して検証できる構造にする。

---

## 7. 更新原則

- 既存Trade Journalの内容を消さず、Company側からprovenanceを辿れるようにする
- 事実・解釈・仮説を分離する
- 過去の売買条件を現在の推奨へ読み替えない
- 最新データを追加する場合は基準日と出所を明示する
- #43 / #44 / #45 等のCanonicalロジックが整った場合は重複計算せず、その成果を参照する

---

担当: ♦️ソラ  
種別: Implementation / Company Research Promotion  
Related: #114, PR #16
