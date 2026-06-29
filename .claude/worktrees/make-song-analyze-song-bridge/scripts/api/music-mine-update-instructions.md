# music-mine.py 更新指示書（Music 2.6新機能対応）

## 背景
`~/projects/claude-config/scripts/api/music-mine.py` はMiniMax Music 2.6を使用しているが、
モデル自体は最新（2026-04-10リリース）なものの、Music 2.6で追加された新パラメータを
使っていない。以下の対応を行うこと。

## 対象ファイル
`~/projects/claude-config/scripts/api/music-mine.py`

## 変更内容

### 1. BPM / Key 指定パラメータの追加
- `_generate()` のリクエストボディに `bpm` と `key`（任意・省略可）を追加できるようにする
- CLI引数 `--bpm` `--key` を追加（未指定時は省略してAPIにモデル任せにする）
- 参考: Music 2.6はBPM/key指定時99%以上の精度で出力に反映される

```python
body_dict = {
    "model": MODEL,
    "prompt": prompt,
    "lyrics": lyrics,
    "audio_setting": {"sample_rate": 44100, "bitrate": 256000, "format": "mp3"},
}
if bpm:
    body_dict["bpm"] = bpm
if key:
    body_dict["key"] = key
body = json.dumps(body_dict).encode()
```

### 2. lyrics_optimizer オプションの追加
- 現在は `--scat` でダミーのスキャット歌詞（らーら…）を固定で使っている
- 新規オプション `--auto-lyrics` を追加し、有効時は `lyrics_optimizer: true` をリクエストに含め、
  `lyrics` フィールドを省略する（プロンプトから自動生成させる）
- `--scat` と `--auto-lyrics` は排他（argparseで `mutually_exclusive_group` を使う）

```python
if auto_lyrics:
    body_dict["lyrics_optimizer"] = True
    # lyrics フィールドは送らない
else:
    body_dict["lyrics"] = lyrics
```

### 3. 長尺生成オプション（任意）
- Music 2.6は最大6分まで生成可能（旧版は短尺固定だった可能性）
- `--duration` または既存の `audio_setting` 周りでAPI仕様を確認し、
  指定可能なら `--max-duration` 引数を追加（**事前にAPI公式ドキュメントで
  パラメータ名を確認すること** — 推測で実装しない）

### 4. AI Cover モード（任意・優先度低）
- 既存曲のメロディを保持して別ジャンルに変換する新機能
- 今回のメロディマイニング運用とは目的が異なるため、対応は別タスクとして見送り可
- 必要なら別スクリプト（`music-cover.py`等）として切り出す方が筋が良い

## 注意事項
- **推測で実装しない**: 各パラメータの正式名・型・制約は
  https://platform.minimax.io/docs/api-reference/music-generation
  を直接確認してから実装すること（このドキュメントの引用情報は参考レベル）
- 既存の `--preset varied --count N --scat --label hourly` という
  Cron実行コマンド（1時間毎）は後方互換を保つこと（デフォルト動作は変えない）
- BPM/key/auto-lyricsはすべて**オプトイン**（明示指定時のみ有効）にする
- 変更後は `bash ~/projects/claude-config/scripts/api/music-mine.py --preset varied --count 1 --scat --label test` で
  既存動作が壊れていないことを確認してから、新オプションの動作確認を行う

## 完了後
- SSOT記録: `01_DECISIONS/ai-music/YYYY-MM-DD_music-mine-Music2.6新機能対応.md` を作成
- 日記更新（記録ルールに従う）
