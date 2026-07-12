---
name: vision-analyze
description: >
  画像を理解（被写体・テキストOCR・構図・色・UI構造の分析）し、結果を構造化して返すスキル。CC CLI は GLM-5.2 等の vision 非対応モデルで稼働中のため画像を直接視認できず、主ルート Gemini 2.5 Flash（scripts/api/gemini_vision.py・無料枠）と副ルート 4_5v MCP（analyze_image・Readが返すCDN URL）の2経路で分析し、CCは結果の構造化・比較・保存に専任する。
  ユーザーが「画像見て」「この画像何が写ってる」「画像比較して」「スクショ見て」「画像分析して」「画像理解」「vision-analyze」と言った時、または /vision-analyze を呼んだ時にトリガー。
  ※画像生成（image generation）は対象外（make-song / video-prompt-spec / demo-site-sales参照）。ピクセル修正（花鈿除去等）は remove-huadian の役割。楽曲分析は analyze-song / reverse-engineer-song。
user-invocable: true
---

# vision-analyze — 画像理解スキル

## トリガーワード
「画像見て」「この画像何が写ってる」「画像比較して」「スクショ見て」「画像分析して」「画像理解」「/vision-analyze」

## 設計の核心
- **CCは画像を視認できない**（GLM-5.2 は vision 非対応）。分析は外部APIに委任。
- **CCの役割**: ①対象画像パス/CDN URLの特定 ②API呼び出し ③結果の構造化・比較・保存
- **モデル陳腐化耐性**: Gemini 候補は `config/gemini-models.json` から自動選択（半年後のモデル変更も設定書換で吸収）。429=バックオフ・403/404/5xx=次候補フォールバック・paid_ok で課金事故防止。

## 進行

### Phase 0: 対象画像の特定 🔴
- 会話文脈・ユーザー指定から画像パスを特定
- `Read` ツールで画像を読み込むと **CDN URL（base64非・軽量・Expires付き）** が返るので記録（Phase2 で使用）
- 複数画像の比較分析も対応（`--image` 複数指定）

### Phase 1: ルート1 — Gemini 2.5 Flash（主ルール）🟢
ローカル画像（`~/.claude/image-cache/` 配下のみ・sandbox）を直接 Gemini に渡す。

```bash
cd /home/yn4416/projects/claude-config
set -a; source ~/.secrets.env; set +a
.venv/bin/python scripts/api/gemini_vision.py --image "<path>" [--image "<path2>"] [--allow-paid]
```

- **Windows Desktop環境**: 上記は`.venv/bin/python`直接実行のためWSL-CLI環境専用。Windows Desktopでは`win-wsl-exec.sh`経由で実行（詳細は `analyze-song` SKILL.md の「Windows Desktop環境での実行」参照）
- 結果は JSON `{"status","summary","full_data","error"}`
- `status=ok` → `summary` を分析結果として読み込む
- `status=error` → Phase2（4_5v MCP フォールバック）へ
- `--allow-paid` は有料モデル（2.5-pro等）使用を許可（既定は無料枠のみ・課金事故防止）

### Phase 2: ルート2 — 4_5v MCP（副ルート・フォールバック）🟡
Phase1 が失敗した時、または CDN URL が手元にある時：
- `Read` が返した CDN URL を `mcp__4_5v_mcp__analyze_image` に渡す（`imageSource` = CDN URL・`prompt` = 分析指示）
- 4_5v の結果を構造化して提示

### フォールバック条件（Phase1 → Phase2 に切り替える条件）
- Gemini API エラー（429リトライ枯渇・500系・SDK import error・キーなし）
- Gemini レスポンス空（safety block）
- **モデル陳腐化警告**（全候補失敗・config/gemini-models.json 更新要）
- CDN URL の Expires がまだ有効なら Phase2 が使える

### Phase 3: 結果提示
- ルート1/2 の結果をユーザーに分かりやすく提示
- 比較分析の場合は表形式で整理
- 専門用語は平易な解説を併記（ユーザーが理解しないまま承認するのを防ぐ）

## 対象外（別スキル）
- 画像生成 → make-song / video-prompt-spec / demo-site-sales
- ピクセル修正（花鈿除去等） → remove-huadian
- 楽曲分析 → analyze-song / reverse-engineer-song

## 画像読込運用規約への準拠
本スキルは `Read` が返す **CDN URL（base64非・軽量）** 経由、または `image-cache/` 配下のローカルファイル直接入力で分析するため、「画像読込運用規約（32MBエラー対策）」の懸念は該当しない。ローカルファイルは `~/.claude/image-cache/` 配下のみ許可（sandbox・path traversal対策）。

## モデル陳腐化時の運用（半年〜1年後にモデルが変わったら）
1. 公式（[Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)）で無料枠を確認 → 正典 `30_RESEARCH/llm-models/models/gemini.md` を更新
2. `config/gemini-models.json` の candidates に新モデル追加・廃止モデル削除
3. `gemini-models-health.py --invalidate` で ListModels キャッシュ強制更新
4. `gemini-models-health.py --ping` で候補生存確認

## 関連
- 共通基盤: `lib/api_base.py`（resolve_gemini_model / run_api_with_fallback・5層の陳腐化耐性）
- 設定: `config/gemini-models.json`
- 正典: `30_RESEARCH/llm-models/models/gemini.md`
- 健診: `scripts/api/gemini-models-health.py`（月1 cron想定・層④⑤）
