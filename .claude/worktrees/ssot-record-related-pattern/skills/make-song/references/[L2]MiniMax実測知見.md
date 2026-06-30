# MiniMax実測知見（Layer 2・MiniMax固有・信頼度: 中=実測だが回数限定）

> AI が変わったら `[META]ポータビリティチェックリスト.md` で再検証。ここは MiniMax(music-2.6) 固有。
> 出典: SSOT `2026-06-14_曲構成と小節BPM計算.md` / `2026-06-14_ZAI転写API解明...md` §3.1

---

## 1. APIパラメータの決定的結論

- **duration/BPM指定 param は API にも MCP にも存在しない**（100%確定）
- MCP payload は5項目のみ: `model / prompt / lyrics / audio_setting / output_format`
- 残るレバーは **`prompt` ＋ `lyrics` の構造タグ のみ**
- 価格は長さ非依存: **$0.15/曲**（1分でも5分でも同額）

## 2. 圧縮挙動（理論と実測の乖離・核心）

**AI は設計値の60-70%にしか届かない**（Verse3回構造を2Verse分に圧縮する傾向）。

| 検証 | 歌詞量 | 理論小節 | 実測duration | 到達率 |
|---|---|---|---|---|
| 曹仁v1 | ~500字 | (設計なし) | 109秒 | − |
| 曹仁v2 | ~1100字 | 136 | 154秒 | **62%** |
| 曹仁v3 | +間奏タグ3回 | − | 181秒 | +27秒延長 |

## 3. 長尺化ベストプラクティス（公式テンプレ準拠）

1. **`[Verse 1][Verse 2][Verse 3]` 番号付き**（`[Verse]`のみは圧縮される）
2. **`(掛け声)` 括弧バックボーカル**（歌詞量増＋演出）
3. **各Verse完全差別化**（類似圧縮回避）
4. **`[Break]` でVerse間区切り**（構造認識強化）

## 4. 無意味な手法（検証済み）

- prompt に `"4 minutes"` 明示 → ❌ 無効（曹仁v3実証）
- `"exact BPM 130"` 明示 → ❓ 効果不明

### 実務目安（BPMと自然な曲長）
| BPM帯 | 自然な曲長 | 目安小節数 |
|---|---|---|
| 70-90（ゆったり） | 4分半-5分 | 113-130小節 |
| 90-110（標準） | 4分-4分半 | 100-120小節 |
| 120-140（速い） | 3分半-4分 | 90-110小節 |
| 140+（高速） | 3分-3分半 | 75-95小節 |

**教訓**: 目標曲長を固定せず、BPMに合った自然な長さを受け入れる。無理に伸ばすと息切れ。

### ショート尺の曲長コントロール（設計小節数逆算）
目標秒数を狙う場合、duration param は存在しないため歌詞量（小節数）で間接制御する。

**計算式**: `設計小節数 = 目標秒数 ÷ (240 / BPM) × 1.4`
（1.4 = 圧縮率60-70%への補正・§2参照）

**ショート尺の目安（BPM85）**:
| 目標 | 設計小節 | 構成例 |
|---|---|---|
| 70秒 | ~35 | Intro4 Verse8 Pre4 Chorus8 Inter8 Outro3 |
| 90秒 | ~45 | Intro4 Verse8 Pre4 Chorus8 Inter8 Verse2-8 Outro3 |

**圧縮回避（必須・§3参照）**:
- `[Verse 1][Verse 2]` 番号付き（`[Verse]`のみは圧縮される）
- 各セクション歌詞**4行+**（少ないと短縮される）
- `[Break]` 区切りで構造認識強化
- `"N seconds/min"` 明示は無効（実証済）

## 5. 高音質標準値（必須）

```
model: music-2.6
audio_setting: { sample_rate: 44100, bitrate: 256000, format: mp3 }
```
（デフォルト32k/128kbpsは低音質・必ず上書き）

## 6. 声質プロファイル固定（核心課題・MiniMax制約）

**問題**: `voice_id` は music_generation に**渡せない**（voice_design/clone は TTS 専用）。曲間の声色完全固定は保証されない。

**現実解（3層）:**
1. **声質プロファイル固定化**: 全曲共通の声質ブロックを毎回同一文字列で `prompt` に挿入
   ```
   Vocals: 20s female alto, breathy delivery with warm chest resonance, ethereal clarity
   ```
2. **変更するのはスタイル部分のみ**: core vocal identity を維持しつつ style 切替
3. **期待値調整**: 「だいたい同じ声」まではいくが「同一人物と100%認識」は保証外

## 7. 括弧 (text) 記法（実証済・v10男女デュオ）

```
(female lead vocal) / (male rap feature verse) / (backing vocal) / (ad-lib)
```
backing/response/ad-lib として広く実証。男女デュオで `(F)(M)` 切替も有効。
> ※ 明文定義はdocにないが公式例で実証。

## 8. 歌詞タグ14種（公式）＋ 禁止組み合わせ

公式タグ: `[Intro][Verse][Pre Chorus][Chorus][Interlude][Bridge][Outro][Post Chorus][Transition][Break][Hook][Build Up][Inst][Solo]`

⚠️ **music側スペース区切り**（`[Pre Chorus]`）/ **lyrics側ハイフン**（`[Pre-Chorus]`）。混同注意。

**禁止組み合わせ（`2013` エラー）:**
- cover で `audio_url` + `audio_base64` 両方
- `cover_feature_id` + `audio_url` 同時
- `stream:true` で `output_format:url`
- `music-cover` で `lyrics_optimizer:true`（music-2.6 専用）

## 9. MiniMax 得意/苦手ジャンル（実測で拡充）

| 得意（実証） | 苦手/要注意（実測で確認） |
|---|---|
| 和楽器（三味線/琴/尺八） | （制作ごとに蓄積・空欄可） |
| Lo-Fi Hip Hop | |
| 日本語ボーカル（ひらがななら） | |

> この表は制作ごとに `[L2]失敗パターンカタログ.md` と連動して育成。

---

## Phase 2b/4 での使い方

- **Phase 2b**: 構造設計の理論値に**圧縮率補正**（60-70%）を適用
- **Phase 3a**: 声質プロファイル固定＋括弧記法をプロンプトに組込
- **Phase 4**: 生成後、高音質設定で出力・圧縮率を実測確認
