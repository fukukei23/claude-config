# glm_rate_proxy 運用ガイド

## 概要
Claude Code CLIのAPIリクエストを中継し、使用率に応じてモデルを切り替えるローカルプロキシ。

## 通信経路

```
基本（安全）: Claude Code → Z.AI API（GLM）直接
プロキシ有効: Claude Code → localhost:8787 → GLM API → (429時) → MiniMax API
```

## 自動判定の仕組み

`~/.bashrc` の `claude()` 関数が起動時に自動判定：

| プロキシ状態 | ANTHROPIC_BASE_URL | 挙動 |
|---|---|---|
| 生きてる | `http://127.0.0.1:8787` | プロキシ経由（フォールバックあり） |
| 死んでる（再起動成功） | `http://127.0.0.1:8787` | 自動再起動 → プロキシ経由 |
| 死んでる（再起動失敗） | Z.AI直結（secrets.envの値） | GLM直結（フォールバックなし） |

## 手動操作

### Z.AI直結に完全に戻す手順

プロキシを完全に無効化してZ.AI直結に戻すには、**以下の2つ**を実行する：

```bash
# 1. プロキシプロセスを止める
pkill -f glm_rate_proxy

# 2. 次回 Claude Code 起動時に自動でZ.AI直結になる（.bashrc claude()が判定）
```

**変更不要なファイル**（触らなくていい）:
- `~/.secrets.env` — 既にZ.AI直結がデフォルト（`ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic`）
- `~/.claude/settings.json` — `apiBaseUrl: null` なので環境変数が使われる

**⚠️ 過去の罠**: settings.jsonの `apiBaseUrl` だけZ.AIに書き換えても、`ANTHROPIC_BASE_URL` 環境変数がproxyを指していると意味がない。環境変数が優先される。プロキシプロセス自体を止めることが重要。

**プロキシを永久に無効化する場合**（追加手順）:
```bash
# 上記に加えて、.bashrc の claude() 関数内の「glm_rate_proxy 自動判定」ブロックを削除
# これで起動時の自動再起動も止まる
```

### プロキシを有効化に戻す
```bash
# プロキシを起動するだけでOK（次回Claude Code起動時に自動でproxy経由になる）
source ~/.secrets.env
cd ~/.claude/scripts/glm-rate-proxy
PYTHONPATH=src nohup python3 -m glm_rate_proxy > /tmp/glm-proxy.log 2>&1 &
```

### プロキシの状態確認
```bash
curl http://127.0.0.1:8787/proxy/status
```

### プロキシを手動起動する
```bash
source ~/.secrets.env
cd ~/.claude/scripts/glm-rate-proxy
PYTHONPATH=src python3 -m glm_rate_proxy
```

### プロキシの状態確認
```bash
curl http://127.0.0.1:8787/proxy/status
```

### ログ確認
```bash
tail -20 /tmp/glm-proxy.log
```

## モデルルーティング

| モード | 使用率 | モデル | いつ |
|---|---|---|---|
| peak_block | peak_hours時間帯 | `fallback.model`（既定: MiniMax-M3） | 設定されたピーク時間帯 |
| normal | <80% | GLM-5.2 | 通常時 |
| economy | 80-95% | GLM-4.7 | 使用量が多い時 |
| emergency | 95%+ | GLM-4.7-Flash | 使用量限界付近 |
| fallback | 全滅時 | MiniMax-M2.7 | GLMが全モデル429の時 |

## ピーク時間帯（peak_hours）

`config/config.json` の `peak_hours` セクションで、**Z.AI（GLM）への呼出を遮断する時間帯**を定義する。

| 設定キー | 意味 | 既定値 |
|---|---|---|
| `enabled` | peak_hours機能の有効化 | `true` |
| `start_hour` | 開始時刻（24h表記・JST） | `15` |
| `end_hour` | 終了時刻（24h表記・JST・排他的） | `19` |
| `timezone_offset` | タイムゾーンオフセット | `9`（JST） |

**動作**: peak_hours時間帯中は、ModelRouterの `determine_mode()` が `peak_block` を返し、`route_model()` がフォールバック先（既定 `MiniMax-M3`）へ**強制切替**する。Z.AI（GLM）は呼ばれず、結果としてCoding Plan側のレートリミットを回避する。

**実装**: `src/glm_rate_proxy/model_router.py` の `_is_peak_hour()` が JST タイムゾーンで現在時刻を判定。`start_hour <= now_hour < end_hour` の条件。

**⚠️ 重要な制約**: peak_hours は **glm-rate-proxy を経由する呼出のみに効く**。`ANTHROPIC_BASE_URL` でZ.AI直エンドポイントを指定するクライアント（例: NexusCore の `GLM_API_BASE=https://api.z.ai/api/coding/paas/v4`）は proxy を経由しないため、peak_hours制御の対象外となる。この時間帯にZ.AI直呼出すると429多発を直接受ける（フォールバックなし）。

## 設定ファイル

| ファイル | 役割 |
|---|---|
| `~/.claude/scripts/glm-rate-proxy/config/config.json` | モデル・閾値・フォールバック設定 |
| `~/.secrets.env` | `ANTHROPIC_BASE_URL` のデフォルト（Z.AI直結） |
| `~/.bashrc` `claude()` | 起動時のプロキシ自動判定 |
| `/tmp/glm-proxy.log` | プロキシのログ |
| `/tmp/glm-rate-proxy-status.json` | 使用率・リクエスト数のステータス |

## 過去のインシデント

### 2026-05-20: 使用率99%固定化
- 原因: `proxy.py` で429後に `set_usage(99.0)` をハードコード
- 影響: 5時間制限リセット後もemergency modeが永続化 → 不要なMiniMax使用が続いた
- 修正: `update_from_headers(resp["headers"])` に変更（実際のヘッダー値で更新）
- **SSOT詳細**: [glm-rate-proxy修正とフォールバック復旧](../../projects/obsidian-ssot/01_DECISIONS/claude-code/2026-05-24_glm-rate-proxy修正とフォールバック復旧.md)
