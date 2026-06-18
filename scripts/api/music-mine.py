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

# プリセット: ジャンル具体語のバリエーション（多様性確保用）
PRESETS = {
    "grateful-days": [
        "90s Japanese mixture rock, dreamy sampled acoustic guitar riff, heavy boom bap breakbeat, turntable scratches, warm analog bass, nostalgic, bittersweet, lo-fi 1990s production, vocal grit, natural human imperfections",
        "90s Japanese alternative hip-hop, organic trip-hop beat, acoustic guitar loop, melancholic vinyl scratch, lush strings, gospel-style female hook, smooth melodic male rap, nostalgic, street, raw 1990s recording feel, vinyl saturation",
        "90s Japanese mixture rock, distorted guitar riffs, boom bap drums, acoustic guitar arpeggio, deep bass, energetic, nostalgic, bittersweet, raw 1990s rock production, vocal grit",
        "90s Japanese dream-pop hip-hop, jangly acoustic guitar, laid-back trip-hop beat, vinyl crackle, airy female vocals, smooth male rap, nostalgic, ethereal, lo-fi warmth",
        "90s Japanese mixture rock, piano-led melancholy, boom bap breakbeat, cello strings, acoustic guitar, whispered male rap, soulful female vocal, bittersweet, cinematic, raw 1990s feel",
        "90s Japanese alternative rock, heavy bass groove, funk guitar riff, boom bap drums, turntable scratch, raspy male rap, angelic female hook, street, nostalgic, gritty analog warmth",
    ],
}

SCAT_LYRICS = """[Verse 1]
ららら　らーら　ららら　らー
ららら　らーら　ららら　らー

[Verse 3]
らーら　ららら　らーら　らら
らーら　ららら　らーら　らら

[Chorus]
ららら　らーら　ららら　らー
ららら　らーら　ららら　らー"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """コマンドライン引数をパースする."""
    parser = argparse.ArgumentParser(description="MiniMax music 直接生成（メロディマイニング用）")
    parser.add_argument("--prompt", help="プロンプト（--presetと排他）")
    parser.add_argument("--preset", choices=list(PRESETS.keys()), help="プリセット名")
    parser.add_argument("--count", type=int, default=1, help="生成数（プリセットから順/ランダム選択）")
    parser.add_argument("--scat", action="store_true", help="スキャット歌詞（メロディ抽出用）")
    parser.add_argument("--lyrics-file", help="歌詞ファイルパス")
    parser.add_argument("--outdir", default=str(DEFAULT_OUTDIR), help="出力ディレクトリ")
    parser.add_argument("--label", default="", help="ファイル名ラベル（preset名がデフォルト）")
    return parser.parse_args(argv)


def _generate(prompt: str, lyrics: str) -> tuple[bytes, float]:
    """MiniMax music_generation API を直接叩き、音声bytesと経過時間を返す.

    Args:
        prompt: 音楽プロンプト
        lyrics: 歌詞（構造タグ込み）

    Returns:
        (audio_bytes, elapsed_seconds)

    Raises:
        RuntimeError: APIエラー・タイムアウト
    """
    api_key = os.environ.get("MINIMAX_API_KEY", "")
    if not api_key:
        raise RuntimeError("MINIMAX_API_KEY not set in environment")
    body = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "lyrics": lyrics,
        "audio_setting": {"sample_rate": 44100, "bitrate": 256000, "format": "mp3"},
    }).encode()
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

    # 歌詞決定
    if args.lyrics_file:
        lyrics = Path(args.lyrics_file).read_text(encoding="utf-8")
    elif args.scat or (not args.prompt and not args.lyrics_file):
        lyrics = SCAT_LYRICS
    else:
        lyrics = SCAT_LYRICS  # デフォルトはスキャット（メロディ抽出）

    # プロンプト群決定
    if args.prompt:
        prompts = [args.prompt] * args.count
        label = args.label or "custom"
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
            audio_bytes, elapsed = _generate(prompt, lyrics)
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
                "file": fname, "prompt": prompt, "lyrics": lyrics,
                "duration_sec": dur, "elapsed_sec": round(elapsed, 1),
                "model": MODEL, "generated_at": ts,
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
