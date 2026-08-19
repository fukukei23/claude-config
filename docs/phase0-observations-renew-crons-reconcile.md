# Phase 0 観測記録 — renew-crons reconcile（2026-08-20 02:23〜02:34）

## 実施内容

- 手動バックアップ: `~/.claude/scheduled_tasks.json.manual-bak-phase0`
- probe: `reconcile-phase0-probe`（id=b44829f1・one-shot・CronCreate(durable)で作成・観測後に削除済み）
- スキーマ観測: → `tests/fixtures/golden_master_entry.json`（A/B分類付き・C候補なし）
- 書き戻し観測: 30秒×20サンプル（10分02:23→02:33）。probeエントリへ `_phase0_probe: 'external-edit'` を外部注入し、CCが書き戻す（=マーカー消滅）か観測
  - シナリオ(a) idle: サンプル1〜7（3.5分）
  - シナリオ(b) 新規セッション起動: サンプル8〜9で `claude -p` サブプロセス起動（pong応答確認）
  - シナリオ(c) CC自身のcron操作: サンプル9→10の間で本セッションからCronCreate→CronDelete実行
  - ※specの「別cron発火」は任意時刻に強制できないため「CCのcron書込み操作」で代替（書き戻し経路の検証としては同等）

## 結果

| シナリオ | 書き戻し | 詳細 |
|---|---|---|
| (a) idle 3.5分 | **0回** | hash不変・マーカー保持 |
| (b) 新規CCセッション起動 | **0回** | hash不変・マーカー保持（セッション起動だけでは書き戻さない） |
| (c) CCのCronCreate→CronDelete | **1回** | 直後サンプルで marker=GONE・hash変化。**ただしprobeエントリ自体と全10件は保持** — CCは「メモリ状態でエントリを再構成」するが全ファイル盲目的上書きではない |

- スキーマ: top=`{"tasks":[...]}`・entry=`id/cron/prompt/recurring/lastFiredAt`(A) + `createdAt/createdBySessionId/createdByPid/createdByProcStart`(B)。**`durable`フィールドは存在しない**（Task 5 `_def_to_entry` の `durable: True` は書かない設計に訂正）
- 観測ログ: `/tmp/phase0_watch.log`（20サンプル全文）

## ゲート判定: **書き戻し1回 → セルフヒーリングで吸収可能と判定 → Phase 2続行**

根拠:
1. 書き戻しは「CC自身がcron操作をした時」のみ発生。移行後はrenew系でAIがCronCreateしなくなるためCC側書込みはレア（手動one-shot作成時のみ）
2. 書き戻しはエントリ単位の再構成で、CCが認識しているエントリを消すものではない（全消しでない）
3. 仮にreconcileの書込みが長寿命セッションのメモリ書き戻しで上書きされても、*/6hのcheck不一致→再applyで最大6時間で修復（spec成功条件3）
4. 現状（AI経由CronCreate・ID不整合で17件重複実績）より厳密に安全側

注意点（Task 7実装に反映）: 外部注入した**未知フィールドはCCのcron操作で落ちる**ため、`_phase0_probe` 的な外部マーカー運用は不可。desired状態の比較は「prompt+cron」で行い、未知フィールドの保持はbest effort（落ちてもreconcileが復元）。
