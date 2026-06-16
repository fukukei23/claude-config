# 発音問題_MiniMax固有（Layer 2・MiniMax依存）

> 「日本語発音の正しさ」は `[L1]日本語歌詞技法.md`（AI非依存）。ここは **MiniMax が漢字を誤読する**固有問題とその解法。
> 出典: cyber-wa-song `発音ルール.md` / `music-cover手法.md`（実測: 曹仁v1-v8）

---

## 1. 問題の本質

MiniMax music-2.6 は:
- **漢字を誤読**する（樊城→まいふせつ・不屈→ふこつ）
- **造語を生成**する（まいれぬ・すがわだ 級の意味不明語）
- **ひらがな表記の母音列しか読めない**

→ 漢字歌詞をそのまま投げると発音崩壊。**ひらがな化が必須**。

## 2. ひらがな化フロー（日本語ボーカル時・必須）

1. **漢字で歌詞執筆**（意味明確・世界観の情景描写）
2. **ひらがな化**（`scripts/kanji_to_hiragana.py`・janome）:
   ```bash
   source ~/venv/janome/bin/activate
   python ~/.claude/skills/make-song/scripts/kanji_to_hiragana.py <歌詞ファイル>
   ```
3. **固有名詞マップ適用**: janome の限界を補正（般若/提灯/蓮華 等・必要に応じて拡充）
4. **助詞「は→わ」全適用**（`[L1]日本語歌詞技法.md` §2）
5. **漢字版併記**（ユーザー照合用・必須）
6. **1行ずつ音読**で造語・不自然表現スキャン

### ❌ 絶対禁止
- 造語を作らない
- 存在しない活用形（きたったのだ→正: きた）
- 慣用句の誤用（ねをひかれ→意味確認）
- 漢字をそのまま書く

## 3. music-cover ループ（聴取後の発音修正）

**「曲は良いが発音/歌詞だけ直したい」時の公式解法。**

### なぜ必要か
music-2.6 は**非決定的**（同じprompt+歌詞でも毎回違う結果・seed不可）。歌詞を直して再生成すると**曲調まで変わる**。
→ 良い曲を `music-cover` で参照し、**歌詞だけ直す**。

### Step 1: preprocess（無料）— cover_feature_id 取得
良い曲を base64 で POST:
```bash
AUDIO_B64=$(base64 -w0 good_version.mp3)
curl -X POST https://api.minimax.io/v1/music_cover_preprocess \
  -H "Authorization: Bearer $MINIMAX_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"music-cover\",\"audio_base64\":\"$AUDIO_B64\"}"
```
- `cover_feature_id`: 曲の音響特徴（**24h有効**）
- `structure_result`: 曲構造タイムスタンプ
- `formatted_lyrics`: ASR歌詞（⚠️ 日本語ラップで精度低下）

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

### 注意
- **MCPから叩けない**（MCPはmusic-2.6固定）。`requests`/curl 直接API必須
- APIキーは `~/.secrets.env` の `MINIMAX_API_KEY`（source経由・**値は出さない**）
- 歌詞上限はdoc上1000字だが1058字でも通った（余裕あり）

## 4. 音声転写（ZAI ASR）で検証 ※オプション

GLM-ASR-2512 で生成曲を文字起こしし、発音を客観確認:
- エンドポイント: `https://api.z.ai/api/paas/v4/audio/transcriptions`
- 認証: `Bearer $GLM_API_KEY`
- **モノラル16kHz必須**: `ffmpeg -y -i input.mp3 -ac 1 -ar 16000 out.mp3`
- 30秒以内・25MB以下
- ⚠️ 残高課題あり（`1113: Insufficient balance`）・チャージ必要

---

## Phase 3b/4 での使い方

- **Phase 3b**: 日本語ボーカルならひらがな化フロー（§2）を必ず実行
- **Phase 4**: 聴取後、発音問題あれば music-cover ループ（§3）で修正。良い回は即 preprocess 保存
