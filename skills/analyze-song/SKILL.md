---
name: analyze-song
description: 楽曲（YouTube/MP3）を音源から定量分析し、BPM/キー/コード進行/メロディ輪郭/音域/phrase_repetitionを抽出してfeatures.json＋五線譜PNG/PDF＋report.mdを出力するスキル。reverse-engineer-song（Gemini定性）とは完全独立・数値定量分析専用。ユーザーが「楽曲分析して」「曲を定量分析」「この曲のBPM/コード抽出」「名曲っぽさ分析」「analyze-song」と言った時、または /analyze-song を呼んだ時にトリガー。
---

# analyze-song（楽曲定量分析・Phase 1a）

## できること
音源（YouTube URL / ローカル MP3）から以下を数値抽出:
- BPM・テンポ信頼度（librosa）
- キー・スケール・信頼度（music21）
- コード進行（music21 chordify）
- メロディ音域（music21）
- phrase_repetition：前半/後半の音程同一性検出（Phase1aは固定長等分割・精度は1b改善）

## いつ使うか
- 自作曲の「名曲っぽさ」を数値で確認したい時
- 既存曲の構造を定量化して make-song の参照にしたい時
- reverse-engineer-song の定性分析を数値で裏付けたい時

## トリガーワード
「楽曲分析して」「曲を定量分析」「BPM/コード抽出」「名曲っぽさ分析」「analyze-song」「/analyze-song」

## 使い方（Phase 1a）
```bash
cd /home/yn4416/projects/claude-config/skills/analyze-song && \
/home/yn4416/projects/claude-config/.venv/bin/python scripts/analyze_song.py \
  <YouTube URL または MP3パス> \
  -o <出力ディレクトリ> \
  -t <曲名>
```
※ `scripts/analyze_song.py` は `from scripts import ...` で各モジュールを解決するため、cwd を `skills/analyze-song` にして実行すること。

## 出力（<出力ディレクトリ>/ 配下）
- `features.json` — 全特徴量（機械用）
- `score/full-1.png` `score/full.pdf` — 五線譜（人間用・MuseScore環境依存で省略の場合あり）
- `report.md` — サマリ＋工程ログ（人間用）

## Phase（本スキルは 1a のみ実装済み）
- 1a: 音源取得＋分析エンジン（librosa/basic_pitch/music21・Demucs無し）✅
- 1b: Demucs音源分離で精度UP（phrase_repetition/楽器構成/ヴォイス）・後日
- 2: 名曲特徴量DB構築（後日・別spec）
- 3: 照合エンジン＋make-song連携（後日・別spec）

## 既知の制限（Phase 1a）
- **BPM**: librosa推定限界で生成指定BPMと乖離する場合あり（yoen-v3_1は指定85→推定112）
- **phrase_repetition**: basic_pitch生MIDIのノイズで一致率が低くなる。メロディ単離（1b）で改善
- **楽譜PNG**: MuseScore AppImageがWSL環境依存でsegfaultする場合あり（features.jsonは正常生成）

## 前提知識（進行開始前に必ず読み込む）
- venv: `/home/yn4416/projects/claude-config/.venv`（変更禁止）
- MuseScore: `/home/yn4416/tools/MuseScore-Studio-4.7.3.AppImage`
- spec: `obsidian-ssot/docs/superpowers/specs/2026-06-19-analyze-song-design.md`
- plan: `obsidian-ssot/docs/superpowers/plans/2026-06-19-analyze-song-design.md`
