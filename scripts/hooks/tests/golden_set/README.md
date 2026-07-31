# impactモード ゴールデンセット（6件fixture）

> 📅 2026-07-31 作成 · セッション 3c16→cacbe
> spec: [obsidian-ssot/docs/superpowers/specs/2026-07-30-multi-llm-review-impact-mode-design.md](obsidian-ssot/docs/superpowers/specs/2026-07-30-multi-llm-review-impact-mode-design.md) §5.2
> 改訂案: [obsidian-ssot/docs/superpowers/reviews/2026-07-31_impact-golden-set-fixture-design/revised_proposal.md](obsidian-ssot/docs/superpowers/reviews/2026-07-31_impact-golden-set-fixture-design/revised_proposal.md)
> review: [obsidian-ssot/docs/superpowers/reviews/2026-07-31_impact-golden-set-fixture-design/review_log.md](obsidian-ssot/docs/superpowers/reviews/2026-07-31_impact-golden-set-fixture-design/review_log.md)（Gemini+MiniMax 14件・採用14/却下0）

## 6件一覧

| ID | 事案 | category | axis | 層a期待 | 役割 |
|---|---|---|---|---|---|
| F1 | #7 Battle Festa | safety-net-change | serial | True(DOP-001) | 真陽性の正例 |
| F2a | #8 再現 | safety-net-change | serial | True(**偽陽性**) | 層a過剰検知の再現 |
| F2b | #8 改善後 | safety-net-change | layer_b_only | False(目標) | 偽陽性の層b是正 |
| F3 | #9 候補c | (層a外) | layer_b_only | False(**情報理論的**) | ★モード崩壊反証（層a永遠不可能） |
| F4 | 想定・schema | schema-change | serial | False(カタログギャップ) | category偏り解消 |
| F5 | 想定・DELETE | data-mutation | serial | True(DOP-004) | 副作用連鎖 |

## 各fixtureの5面スキーマ（YAML）

1. `diff` — 層a入力用 git diff（unified=0・`parse_unified_zero_diff` が `+` 行のみ抽出）
2. `layer_a_expected` — 層a検証用期待値（matched/category/dangerous_op_match/antipattern_id/matched_keywords）
3. `layer_b_context` — 層bプロンプト入力（**必須4フィールド**: diff/intent/domain_context/non_public・M9）
4. `layer_b_expected` — 層b検証用期待値（future_keywords[required(1.0)/permitted(0.5)]・future_scenarios[5W1H+影響対象+規模]・persona_coverage[根拠1行+各2回以上]・論点D/M5）
5. `axis` — serial / layer_b_only

## 管理原則（M8・spec§5.2 G3）

- **ゴールデンセット = 期待値の固定データ**・**antipatterns.md = 過去失敗カタログ**・参照は**一方通行**（antipatterns.md→fixture は参照するが逆はしない）
- ゴールデンセット ≠ antipatterns.md（独立管理）
- 層aテスト・層b検証スクリプトともに**絶対パス参照**

## 層aマッチ方式（設計上の制約・git_diff.py）

- `match_keywords`: **大文字小文字無視の部分一致**（`k_lower in line_lower`）
- trigger_keywords 10語: `BLACKLIST/blocklist/denylist/exclude/excluded/threshold/disabled/skip/enabled/filter`
- F3/F4 は上記10語の部分文字列が diff 行に入らないよう厳格回避済み
- DOP-001〜005 は `re.search`（正規表現）・詳細は `dangerous-ops.yaml`

## 次ステップ（E''進め方）

- **ステップ2**: detector.py に6件を流し 再現率/適合率・F2a 偽陽性再現・F2b ギャップ記録
- **ステップ3**: 層b最小実装（P1+Future Logic Check・API直叩きスクリプト1本）
- **ステップ4**: 定量Go/No-Go（変種生成 n=15-25・LLM-as-a-Judge・Precision/Recall）
- **ステップ5**: 撤退条件（6件中3件で層b≤層a → abort）
