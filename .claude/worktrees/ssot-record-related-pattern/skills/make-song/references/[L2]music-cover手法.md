# music-cover 手法（曲調維持＋歌詞修正の公式解法）

> **「曲は良いが発音/歌詞だけ直したい」時の解法。** music-2.6の生成揺らぎを回避し、良い回を活かす。曹仁樊城v8で実証。

## なぜ必要か

music-2.6 は **非決定的**（同じprompt＋歌詞でも毎回違う結果・seed指定不可）:
- 良い回（v6）を再生成で再現できない
- 歌詞を直して再生成すると **曲調まで変わる**（曹仁v6→v7で曲調劣化の実例）

→ 良い曲を `music-cover` で参照し、**歌詞だけ直す**。

## 解法（2ステップ・直接API・MCP不可）

### Step 1: preprocess（無料）— cover_feature_id 取得

良い曲を base64 エンコードで POST:

```bash
# 音声ファイルをbase64化
AUDIO_B64=$(base64 -w0 good_version.mp3)

curl -X POST https://api.minimax.io/v1/music_cover_preprocess \
  -H "Authorization: Bearer $MINIMAX_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"music-cover\",\"audio_base64\":\"$AUDIO_B64\"}"
```

**結果:**
- `cover_feature_id`: 曲の音響特徴（**24h有効**）
- `structure_result`: 曲構造タイムスタンプ（intro/verse/chorus の秒数）
- `formatted_lyrics`: ASR歌詞（⚠️ 日本語ラップで精度低下・テロップ不適）

### Step 2: cover 生成（有料・$0.15/曲）— 修正歌詞を適用

```bash
curl -X POST https://api.minimax.io/v1/music_generation \
  -H "Authorization: Bearer $MINIMAX_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\":\"music-cover\",
    \"cover_feature_id\":\"<step1のID>\",
    \"lyrics\":\"<修正したひらがな歌詞>\"
  }"
```

## 実証データ（曹仁樊城・2026-06-14）

| 項目 | 値 |
|---|---|
| 参照元 | v6（172秒・Verse3回） |
| 生成結果 | v8 cover（**175秒・+3秒差のみ**） |
| 成果 | v6のビート/メロディ/構造を維持 + v7の正しい発音（は→わ等）を乗せた |
| 歌詞量 | 1058字（doc上限1000字だが余裕で通る） |

## 注意点

- **MCPから叩けない**（MCPはmusic-2.6固定・`server.py`行614）。`requests`/curl等の直接API必須
- APIキーは `~/.secrets.env` の `MINIMAX_API_KEY`（source経由・**値は出さない**）
- coverの歌詞上限はdoc上1000字だが、1058字でも通った（余裕あり）
- preprocess は音楽構造タイムスタンプも取得（動画同期にも再利用可）

## 活用場面

- 発音問題（は→わ等）を後から直したい時
- 良い曲調の生成を逃したくない時
- 同じメロディで歌詞バリエーションを作りたい時

## スキル内での位置付け（Phase 3 フォールバック）

```
Phase 3: 楽曲生成（music-2.6）
  → 🔴人間判断: 聴取
  → 発音問題あれば:
      良い回を即 preprocess 保存（cover_feature_id は24h有効）
      → 修正歌詞で cover 生成
      → 再聴取
```

> **重要**: どんなに発音ルールを守っても問題が出る場合がある。music-cover は**作詞プロセスの最終補強**。ただし直接API必須・MCP不可。

> 出典: `00_SYSTEM/AI生成メディア_ケイパビリティマップ.md` §1「★★★music-cover実用ノウハウ」
