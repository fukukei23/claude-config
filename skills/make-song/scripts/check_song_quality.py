#!/usr/bin/env python3
"""
メロディ品質3軸チェッカー（Phase 1実装）

軸A: 音節密度（自動）
軸B: 中高音使用率（プロンプト評価のみ・Phase 2で自動）
軸C: 抑揚幅スコア（プロンプト評価のみ・Phase 2で自動）

使い方:
  python3 scripts/check_song_quality.py --bpm 98 --bars 8 歌詞.md

出力例:
  [Verse 1] 5.4音節/秒 ✅ 安全域
  [Verse 2] 5.8音節/秒 ✅ 安全域
  ...

対応形式:
  - 歌詞ブロックが ``` コードフェンス内の歌詞
  - Markdown見出し `### [Intro] 8小節` 形式
  - 構造タグのみ `[Intro]` 形式
  - `---` 以降はメタデータ扱いで打ち切り
"""

import argparse
import re
import sys
from pathlib import Path


def line_syllables(line: str) -> int:
    """行の音節数を概算（日本語は文字≒音節）"""
    line = line.strip()
    if not line:
        return 0
    # 句読点・記号・空白除外
    line = re.sub(r"[、。、「」『』()（）\[\]/…\s]", "", line)
    return len(line)


def check_syllable_density(lyrics_path: Path, bpm: int, default_bars: int = 8) -> dict:
    """軸A: 音節密度計算

    行ベースでセクションを抽出:
    - Markdown見出し行（# で始まる）も対象に含める（`### [Intro] 8小節` 形式）
    - コードフェンス ``` を尊重（歌詞が ``` ブロック内の場合は内容を抽出）
    - `---` 以降はメタデータ扱いで打ち切り
    """
    content = lyrics_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    # ヘッダー検出: `[Name] N小節` または `[Name]`（Markdown見出しの `#` 接頭辞許容）
    section_header_re = re.compile(
        r"^\s*(?:#{1,6}\s+)?\[(?P<name>\w+(?:\s+\d+)?|\w+:\w+)\]"
        r"(?:\s+(?P<bars>\d+)小節)?"
    )
    md_heading_re = re.compile(r"^\s*#{1,6}\s")
    code_fence_re = re.compile(r"^\s*```")
    table_or_list_re = re.compile(r"^\s*[|\-*]")

    section_default_bars = {
        "Intro": 8,
        "Verse": 16,
        "Verse 1": 16,
        "Verse 2": 8,
        "Verse 3": 16,
        "Chorus": 16,
        "Chorus:Final": 24,
        "Big Chorus": 24,
        "Break": 4,
        "Bridge": 8,
        "Outro": 8,
    }

    results: dict = {}
    current_section = None
    current_bars = default_bars
    current_lines: list = []
    in_code_fence = False
    in_metadata = False

    def _flush() -> None:
        nonlocal current_section, current_bars, current_lines
        if current_section and current_lines:
            total_syl = sum(line_syllables(line) for line in current_lines)
            section_seconds = current_bars * 60.0 / bpm * 4.0
            density = total_syl / section_seconds

            if density <= 8:
                verdict = "✅ 安全域"
            elif density <= 10:
                verdict = "⚠️ 警告域"
            else:
                verdict = "❌ 禁止域"

            results[current_section] = {
                "syllables": total_syl,
                "lines": len(current_lines),
                "bars": current_bars,
                "seconds": round(section_seconds, 2),
                "density": round(density, 2),
                "verdict": verdict,
            }
        current_section = None
        current_bars = default_bars
        current_lines = []

    for line in lines:
        stripped = line.strip()

        # --- はメタデータ境界
        if stripped == "---":
            in_metadata = True
            _flush()
            continue

        if in_metadata:
            continue

        # セクションヘッダー検出（コードフェンス外・`#` 接頭辞許容）
        m = section_header_re.match(line)
        if m and not in_code_fence:
            _flush()
            current_section = m.group("name")
            bars_str = m.group("bars")
            if bars_str:
                current_bars = int(bars_str)
            else:
                current_bars = section_default_bars.get(current_section, default_bars)
            continue

        # Markdown見出し行（セクションヘッダーでない）はスキップ
        if md_heading_re.match(line):
            continue

        # コードフェンス開始
        if code_fence_re.match(line) and not in_code_fence:
            in_code_fence = True
            continue

        # コードフェンス終了
        if code_fence_re.match(line) and in_code_fence:
            in_code_fence = False
            _flush()
            continue

        # コードフェンス内の歌詞行を収集
        if in_code_fence and current_section and stripped:
            current_lines.append(stripped)
            continue

        # 歌詞行の収集（コードフェンスなし）
        if current_section and stripped and not in_code_fence:
            if table_or_list_re.match(line):
                continue
            current_lines.append(stripped)

    _flush()
    return results


def print_results(results: dict, bpm: int) -> None:
    """結果を表示"""
    print(f"\n📊 音節密度チェック結果（BPM={bpm}）\n")
    print(f"{'セクション':<15} {'行数':>4} {'小節':>4} {'秒数':>6} {'音節':>5} {'密度':>5}  判定")
    print("-" * 70)

    has_warning = False
    has_forbidden = False

    for section_name, data in results.items():
        print(
            f"{section_name:<15} {data['lines']:>4} {data['bars']:>4} "
            f"{data['seconds']:>6.1f} {data['syllables']:>5} "
            f"{data['density']:>5.1f}  {data['verdict']}"
        )
        if "⚠️" in data["verdict"]:
            has_warning = True
        elif "❌" in data["verdict"]:
            has_forbidden = True

    print("\n" + "=" * 70)
    if has_forbidden:
        print("❌ 禁止域セクションあり → 歌詞短縮・改行必要")
        sys.exit(1)
    elif has_warning:
        print("⚠️ 警告域セクションあり → ユーザー判断（メロディックラップ許容か）")
        sys.exit(0)
    else:
        print("✅ 全セクション安全域 → 歌詞OK")
        sys.exit(0)


def print_phase1_note() -> None:
    """Phase 1の注意書き"""
    print("\n" + "=" * 70)
    print("📌 Phase 1 軸B・C（中高音使用率・抑揚幅）は自動評価未実装")
    print("   → プロンプト指示で予防制御してください:")
    print("   軸B: 「中高音域(A4以上)を主軸に歌う・低音ウィスパーに偏らない」")
    print("   軸C: 「メロディーの起伏を5音以上確保・サビで音程の跳躍」")
    print("   → 生成後、イヤホンで聴いて「ウィスパー低音偏り」「平板」と感じたら再生成")
    print("\n📌 Phase 2（1-2ヶ月後）に多次元スコアリング・自動評価を実装予定")
    print("   詳細: バックログ「音節密度ルール拡張設計(案A'合成案)」タスク")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="メロディ品質3軸チェッカー（Phase 1: 軸A音節密度のみ）"
    )
    parser.add_argument("lyrics_path", type=Path, help="歌詞ファイルのパス")
    parser.add_argument(
        "--bpm",
        type=int,
        required=True,
        help="BPM（必須・例: --bpm 98）",
    )
    parser.add_argument(
        "--bars",
        type=int,
        default=8,
        help="デフォルトの小節数（セクション固有値がない場合・default=8）",
    )

    args = parser.parse_args()

    if not args.lyrics_path.exists():
        print(f"❌ ファイルが見つかりません: {args.lyrics_path}", file=sys.stderr)
        sys.exit(2)

    results = check_syllable_density(args.lyrics_path, args.bpm, args.bars)
    if not results:
        print("⚠️ セクションが見つかりません ([Intro] 等のヘッダーが必要)", file=sys.stderr)
        sys.exit(2)

    print_results(results, args.bpm)
    print_phase1_note()


if __name__ == "__main__":
    main()