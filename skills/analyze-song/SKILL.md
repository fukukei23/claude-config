---
name: analyze-song
description: 楽曲（YouTube/MP3）を音源から定量分析し、BPM/キー/コード進行/メロディ輪郭/音域/phrase_repetitionを抽出してfeatures.json＋五線譜PNG/PDF＋report.mdを出力するスキル。reverse-engineer-song（Gemini定性）とは完全独立・数値定量分析専用。ユーザーが「楽曲分析して」「曲を定量分析」「この曲のBPM/コード抽出」「名曲っぽさ分析」「analyze-song」と言った時、または /analyze-song を呼んだ時にトリガー。
---

# analyze-song（楽曲定量分析・Phase 1b）

## できること
音源（YouTube URL / ローカル MP3）から以下を数値抽出:
- BPM・テンポ信頼度（librosa）
- キー・スケール・信頼度（music21）
- コード進行（music21 chordify）
- メロディ音域（music21）
- phrase_repetition：前半/後半の音程同一性検出（vocals.mid 単離で高精度化）
- vocals 音域・性別推定・声域（ボーカルMIDI音域ベース・median MIDI で male/female 判定）
- instrumentation 楽器構成（4 stem の音響特徴量で楽器カテゴリ推定）
- （Phase2）名曲特徴量DB登録: analyze-song 結果を features.json として名曲DB（reference/名曲DB/）へ蓄積・_index.yaml で一覧管理

## いつ使うか
- 自作曲の「名曲っぽさ」を数値で確認したい時
- 既存曲の構造を定量化して make-song の参照にしたい時
- reverse-engineer-song の定性分析を数値で裏付けたい時

## トリガーワード
「楽曲分析して」「曲を定量分析」「BPM/コード抽出」「名曲っぽさ分析」「analyze-song」「/analyze-song」

## 使い方（Phase 1b）
```bash
cd /home/yn4416/projects/claude-config/skills/analyze-song && \
/home/yn4416/projects/claude-config/.venv/bin/python scripts/analyze_song.py \
  <YouTube URL または MP3パス> \
  -o <出力ディレクトリ> \
  -t <曲名>
```
※ `scripts/analyze_song.py` は `from scripts import ...` で各モジュールを解決するため、cwd を `skills/analyze-song` にして実行すること。

## 使い方（Phase 2・名曲DB登録）
```bash
cd /home/yn4416/projects/claude-config/skills/analyze-song && \
/home/yn4416/projects/claude-config/.venv/bin/python -m scripts.register_song \
  <曲ID(JPOP-001等)> <YouTube URL または MP3パス> \
  --title <曲名> --artist <アーティスト> \
  --genre {JPOP,ROCK,HIPHOP,WAFU,WORLD} \
  --commercial-rank {million,oricon1,billboard_top10,long_seller} \
  --era {1970s,1980s,1990s,2000s,2010s,2020s} --selection-reason <選定理由>
```
- features.json → SSOT（`reference/名曲DB/<曲ID>/`）・音源MP3/PNG/stems → ローカル（`~/Music/名曲DB_raw/<曲ID>/`）に**配置分離**（著作権安全・音源は公開側に置かない）
- `_index.yaml` に冪等でエントリ追記（同曲ID再登録は上書き・重複なし）
- 曲ID 命名: `<GENRE>-<3桁>`（JPOP-001/HIPHOP-010/WAFU-099）

## 出力（<出力ディレクトリ>/ 配下）
- `features.json` — 全特徴量（機械用）
- `score/full-1.png` `score/full.pdf` — 五線譜（人間用・MuseScore環境依存で省略の場合あり）
- `report.md` — サマリ＋工程ログ（人間用）

## Phase（1a/1b/2 実装済み）
- 1a: 音源取得＋分析エンジン（librosa/basic_pitch/music21・Demucs無し）✅
- 1b: Demucs音源分離で精度UP（drums BPM・vocals/accompaniment別MIDI・phrase/音域改善）✅
- 2: 名曲特徴量DB（features.json蓄積＋_index.yaml・登録パイプライン実装済・初期選曲は別途）✅
- 3: 照合エンジン＋make-song連携（後日・別spec）

## 既知の制限（Phase 1b）
- **BPM**: drums stem推定で実曲精度UP（Stayin' Alive 104→103.36）。AI生成ドラムonset特殊音源は外れ値あり（yoen-v3_1: 85指定→112推定）
- **phrase_repetition**: vocals.mid 単離で改善済み
- **楽譜PNG**: libpipewire-0.3-0 導入で headless WSL2 のセグフォ解消（PNG/PDF生成可能）
- **vocals 性別推定**: ピッチ中央値のヒューリスティック（median MIDI ≤A3=male/超=female）。falsetto 判定不可（MIDI単体・倍音構造必要）
- **instrumentation**: 楽器カテゴリ推定のみ（具象名=エレキピアノ等は Phase2+）。stem名+音響特徴量ハイブリッド
- **Phase2 名曲DB**: 登録パイプライン実装済・初期選曲(20-30曲)は未着手（`reference/名曲DB/_candidates.yaml` で管理予定）・Phase3照合エンジン未実装

## 前提知識（進行開始前に必ず読み込む）
- venv: `/home/yn4416/projects/claude-config/.venv`（変更禁止）
- MuseScore: `/home/yn4416/tools/MuseScore-Studio-4.7.3.AppImage`
- spec: `obsidian-ssot/docs/superpowers/specs/2026-06-19-analyze-song-design.md`
- plan: `obsidian-ssot/docs/superpowers/plans/2026-06-19-analyze-song-design.md`
- Phase2 spec: `obsidian-ssot/docs/superpowers/specs/2026-06-21-analyze-song-phase2-famous-songs-db-design.md`
- Phase2 plan: `obsidian-ssot/docs/superpowers/plans/2026-06-21-analyze-song-phase2-famous-songs-db.md`
