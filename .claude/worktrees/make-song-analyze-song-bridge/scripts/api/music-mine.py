#!/usr/bin/env python3
"""MiniMax music_generation 直接API（curl/urllib・MCP非経由）でメロディを生成・保存する.

MCP music_generation は300秒タイムアウトするが、直接APIは~40秒で完了する
（MCPラッパーのオーバーヘッドが原因・API自体は高速）。
Cron定期生成（メロディマイニング）の中核。

Usage:
    # 単一曲（プロンプト指定）
    music-mine.py --prompt "90s Japanese mixture rock, ..."
    # プリセットからランダム1曲
    music-mine.py --preset grateful-days --count 3
    # スキャット（メロディ抽出用）か歌詞指定か
    music-mine.py --preset grateful-days --scat
    music-mine.py --preset grateful-days --lyrics-file path/to/lyrics.txt

成果物: <outdir>/<timestamp>_<preset>.mp3 + .meta.json（プロンプト・歌詞・duration記録）
"""
import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

DEFAULT_OUTDIR = Path.home() / "projects/make-song-guide/songs/melody-mining"
MODEL = "music-2.6"
API_URL = "https://api.minimax.io/v1/music_generation"

# プリセット: 2020年代の売れてるジャンル（ボーカル曲・日本語ボーカル前提）
# 各ジャンル2バリエーション・計16（variedで全ローテーション）
# 根拠: SoundCloud/Billboard 2026 + TikTok蔓延（01_DECISIONS/ai-music/2026-06-19_music-mine-プリセット見直し-売れるジャンル候補.md）
PRESETS = {
    "modern-pop": [
        "modern dance pop, catchy synth hook, punchy drums, bright production, clear female vocal, upbeat, radio-friendly, 2020s mainstream pop, polished, vocal grit",
        "modern pop, tropical influences, smooth bass, glossy production, breathy female vocal, infectious melody, chart-topping, contemporary, natural warmth",
    ],
    "hiphop-trap": [
        "modern trap, deep 808 bass, rolling hi-hats, dark synth pads, punchy male rap, aggressive flow, contemporary hip-hop, hard-hitting, Billboard chart style",
        "melodic trap, atmospheric pads, auto-tuned male vocal, 808s, skittering hi-hats, emotional, modern rap, mainstream hit, vocal grit",
    ],
    "kpop": [
        "K-pop, powerful EDM drop, punchy drums, mixed group vocals, catchy hook, high energy, polished production, dance breakdown, global hit style",
        "K-pop, lush synth layers, emotional female vocal, dramatic build, anthemic chorus, sophisticated production, modern mainstream, polished",
    ],
    "afrobeats": [
        "afrobeats, silky guitar, groovy percussion, warm bass, smooth male vocal, infectious rhythm, danceable, West African pop, global crossover",
        "afrobeats-pop fusion, sweet melody, shaker percussion, female vocal, breezy, romantic, contemporary African pop, crossover hit",
    ],
    "latin-reggaeton": [
        "reggaeton, dembow beat, perreo rhythm, punchy synth, male vocal, danceable, Latin urban, global hit, energetic, club-ready",
        "Latin pop, tropical beat, romantic melody, smooth male vocal, acoustic guitar accents, danceable, crossover hit, polished",
    ],
    "pop-edm": [
        "pop-EDM, festival drop, euphoric synth lead, four-on-the-floor, female vocal, anthemic, build-up, mainstage energy, club crossover",
        "future bass pop, chopped vocals, warm synth chords, trap drums, dreamy female vocal, emotional drop, modern electronic pop",
    ],
    "hyperpop": [
        "hyperpop, distorted bass, pitched-up vocals, glitchy synths, maximalist, bubblegum melodies, chaotic energy, internet-native, Gen-Z",
        "hyperpop, bubblegum bass, auto-tuned female vocal, bright synths, frantic tempo, surreal, playful, TikTok viral",
    ],
    "alt-rnb": [
        "alt R&B, atmospheric synths, slow trap beat, breathy male vocal, moody, nocturnal, introspective, modern R&B, The Weeknd style",
        "alt R&B, velvety female vocal, warm bass, minimalist beat, sensual, late-night, sophisticated, contemporary R&B",
    ],
}


def _varied_pool() -> list[str]:
    """全プリセットのバリエーションをフラット化して返す（variedモード用）."""
    pool = []
    for prompts in PRESETS.values():
        pool.extend(prompts)
    return pool


def _pick_varied(count: int) -> tuple[list[str], str]:
    """時間ベースで全バリエーションからcount件をローテーション選択する.

    毎時切り替わり（同一時刻内の重複回避）。Cron毎回独立プロセスでも
    タイムスタンプで再現可能な選択になる。
    """
    pool = _varied_pool()
    base = int(time.time() // 3600)  # 現在の「時」のインデックス
    prompts = [pool[(base + i) % len(pool)] for i in range(count)]
    return prompts, "varied"

SCAT_LYRICS = """[Verse 1]
ららら　らーら　ららら　らー
ららら　らーら　ららら　らー

[Verse 3]
らーら　ららら　らーら　らら
らーら　ららら　らーら　らら

[Chorus]
ららら　らーら　ららら　らー
ららら　らーら　ららら　らー"""


def _apply_bpm_key(prompt: str, bpm: int | None, key: str | None) -> str:
    """BPM/Key をプロンプト先頭に埋め込む（Music 2.6 公式仕様）.

    Music 2.6 は bpm/key の独立リクエストフィールドを持たず、prompt 文字列内の
    "<key>, <bpm> BPM, ..." 形式で指定すると 99% 精度で出力に反映される。
    両方 None のときは prompt をそのまま返す（後方互換）。

    Args:
        prompt: 元の音楽プロンプト
        bpm: BPM（None時は付加しない）
        key: キー（None時は付加しない）

    Returns:
        BPM/Key 前置き付きプロンプト
    """
    parts: list[str] = []
    if key:
        parts.append(key)
    if bpm:
        parts.append(f"{bpm} BPM")
    if not parts:
        return prompt
    return ", ".join(parts) + ", " + prompt


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """コマンドライン引数をパースする."""
    parser = argparse.ArgumentParser(description="MiniMax music 直接生成（メロディマイニング用）")
    parser.add_argument("--prompt", help="プロンプト（--presetと排他）")
    parser.add_argument("--preset", choices=list(PRESETS.keys()) + ["varied"], help="プリセット名（varied=全ジャンル時間ローテーション）")
    parser.add_argument("--count", type=int, default=1, help="生成数（プリセットから順/ランダム選択）")
    parser.add_argument("--lyrics-file", help="歌詞ファイルパス")
    parser.add_argument("--outdir", default=str(DEFAULT_OUTDIR), help="出力ディレクトリ")
    parser.add_argument("--label", default="", help="ファイル名ラベル（preset名がデフォルト）")
    # 歌詞ソース排他: スキャット vs 自動生成（--lyrics-file は main 側で別途排他チェック）
    lyrics_group = parser.add_mutually_exclusive_group()
    lyrics_group.add_argument("--scat", action="store_true", help="スキャット歌詞（メロディ抽出用）")
    lyrics_group.add_argument(
        "--auto-lyrics", action="store_true",
        help="lyrics_optimizer有効化（promptから歌詞自動生成・Music 2.6）")
    # Music 2.6 新機能: BPM/Key（独立フィールドではなく prompt 埋め込み方式）
    parser.add_argument("--bpm", type=int, help="BPM指定（prompt先頭に埋め込み・99%%精度で反映）")
    parser.add_argument("--key", help="キー指定（例: 'E minor'・prompt先頭に埋め込み）")
    return parser.parse_args(argv)


def _generate(prompt: str, lyrics: str, auto_lyrics: bool = False) -> tuple[bytes, float]:
    """MiniMax music_generation API を直接叩き、音声bytesと経過時間を返す.

    Args:
        prompt: 音楽プロンプト（BPM/Key 埋め込み済み）
        lyrics: 歌詞（構造タグ込み）・auto_lyrics=True 時は無視され空文字でよい
        auto_lyrics: True 時は lyrics_optimizer を有効化し lyrics フィールドを送信しない

    Returns:
        (audio_bytes, elapsed_seconds)

    Raises:
        RuntimeError: APIエラー・タイムアウト
    """
    api_key = os.environ.get("MINIMAX_API_KEY", "")
    if not api_key:
        raise RuntimeError("MINIMAX_API_KEY not set in environment")
    body_dict: dict = {
        "model": MODEL,
        "prompt": prompt,
        "audio_setting": {"sample_rate": 44100, "bitrate": 256000, "format": "mp3"},
    }
    if auto_lyrics:
        # lyrics_optimizer: prompt から歌詞を自動生成（lyrics フィールドは送信しない）
        body_dict["lyrics_optimizer"] = True
    else:
        body_dict["lyrics"] = lyrics
    body = json.dumps(body_dict).encode()
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
    )
    t0 = time.time()
    resp = urllib.request.urlopen(req, timeout=600).read()
    elapsed = time.time() - t0
    data = json.loads(resp)
    if data.get("base_resp", {}).get("status_code", 0) != 0:
        raise RuntimeError(f"API error: {data.get('base_resp')}")
    audio_hex = data["data"]["audio"]
    # hex デコード（ID3ヘッダ確認）
    audio_bytes = bytes.fromhex(audio_hex)
    return audio_bytes, elapsed


import urllib.request  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    """エントリポイント。指定数のメロディを生成・保存する."""
    args = parse_args(argv)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # --auto-lyrics と --lyrics-file の矛盾チェック（両方指定は不可）
    if args.auto_lyrics and args.lyrics_file:
        print("error: --auto-lyrics and --lyrics-file are mutually exclusive", file=sys.stderr)
        return 1

    # 歌詞決定
    if args.auto_lyrics:
        lyrics = ""  # lyrics_optimizer に任せるため空（APIには送信しない）
    elif args.lyrics_file:
        lyrics = Path(args.lyrics_file).read_text(encoding="utf-8")
    elif args.scat or (not args.prompt and not args.lyrics_file):
        lyrics = SCAT_LYRICS
    else:
        lyrics = SCAT_LYRICS  # デフォルトはスキャット（メロディ抽出）

    # プロンプト群決定
    if args.prompt:
        prompts = [args.prompt] * args.count
        label = args.label or "custom"
    elif args.preset == "varied":
        prompts, label = _pick_varied(args.count)
        label = args.label or label
    elif args.preset:
        pool = PRESETS[args.preset]
        # count が pool 超なら循環
        prompts = [pool[i % len(pool)] for i in range(args.count)]
        label = args.label or args.preset
    else:
        print("error: --prompt or --preset required", file=sys.stderr)
        return 1

    ts = time.strftime("%Y%m%d_%H%M%S")
    results = []
    for i, prompt in enumerate(prompts):
        try:
            effective_prompt = _apply_bpm_key(prompt, args.bpm, args.key)
            audio_bytes, elapsed = _generate(effective_prompt, lyrics, auto_lyrics=args.auto_lyrics)
            fname = f"{ts}_{label}_{i+1}.mp3"
            fpath = outdir / fname
            fpath.write_bytes(audio_bytes)
            # duration 測定（ffprobe optional）
            dur = ""
            try:
                import subprocess
                dur = subprocess.check_output(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "csv=p=0", str(fpath)],
                    stderr=subprocess.DEVNULL,
                ).decode().strip()
            except Exception:
                pass
            meta = {
                "file": fname, "prompt": effective_prompt, "lyrics": lyrics,
                "duration_sec": dur, "elapsed_sec": round(elapsed, 1),
                "model": MODEL, "generated_at": ts,
                "bpm": args.bpm, "key": args.key, "auto_lyrics": args.auto_lyrics,
            }
            (fpath.with_suffix(".meta.json")).write_text(
                json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            results.append({"file": fname, "duration": dur, "elapsed": round(elapsed, 1)})
            print(f"OK [{i+1}/{len(prompts)}] {fname} ({dur}s, {elapsed:.1f}s生成)")
            # レート制限回避: 連続生成は少し間を空ける
            if i < len(prompts) - 1:
                time.sleep(5)
        except Exception as exc:  # noqa: BLE001
            print(f"NG [{i+1}/{len(prompts)}] {type(exc).__name__}: {exc}", file=sys.stderr)
            results.append({"file": None, "error": str(exc)})

    # サマリー
    summary_path = outdir / f"{ts}_{label}_summary.json"
    summary_path.write_text(
        json.dumps({"batch": ts, "label": label, "results": results},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    ok = sum(1 for r in results if r.get("file"))
    print(f"\n完了: {ok}/{len(prompts)}曲成功・サマリー: {summary_path}")
    return 0 if ok == len(prompts) else 1


if __name__ == "__main__":
    sys.exit(main())
