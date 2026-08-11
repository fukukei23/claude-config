# evals/ — スキル評価キット

> スキルが「意図通り発火するか・期待の成果物を出すか・安全か・回帰しないか」を機械的に検証する評価ケース集。

## 命名規約（固定）

```
evals/<skill-name>/cases.md
```

- **`<skill-name>`** は `skills/<skill-name>/SKILL.md` と一致（例: `send-email`）
- **`cases.md`** 1ファイルに4観点をまとめる：
  1. **発火テスト (Trigger)** — 呼ばれる依頼 / 呼ばれない依頼（誤発火防止）
  2. **入出力テスト (Input → Output)** — 入力がブレても出力は一定か
  3. **安全テスト (Safety)** — 機密・認証・外部送信・権限判断（※send-email等の外部連携スキルで必須）
  4. **回帰テスト (Regression)** — SKILL.md 更新時に以前通っていたケースが壊れないか
- **判定基準** は「文章の雰囲気」でなく **存在・形式・必須項目・禁止項目** の4点で機械的に行う（`cases.md` 内に scorecard を明記）

## 運用

- 新規スキル追加時は `evals/<skill-name>/cases.md` をセットで作成すること（manifest drift にならないよう `.dir-manifest.json` の `evals` エントリは既に登録済み・ファイル追加のみでOK）
- パイロット第1号: `send-email`（2026-08-03・E案最小版）
- 評価キット導入の経緯: `obsidian-ssot/01_DECISIONS/claude-config/` 配下の該当記録を参照

## 関連

- 導入経緯・設計判断: `obsidian-ssot/01_DECISIONS/claude-config/2026-08-12_eval-kit-棚新設.md`（※ ssot-record で後刻記録）
- 親スキル定義: `skills/<skill-name>/SKILL.md`
