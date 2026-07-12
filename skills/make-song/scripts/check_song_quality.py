#!/usr/bin/env python3
"""
メロディ品質3軸チェッカー（Phase 1実装）

軸A: 音節密度（自動）
軸B: 中高音使用率スコア（自動・簡易版）
軸C: 抑揚幅スコア（自動・簡易版）

使い方:
  python3 scripts/check_song_quality.py --bpm 98 --bars 8 歌詞.md

判定ロジック（Phase 1・歌詞文字列ベース）:
  軸B: サビセクションで力強い母音・破裂音行・上行語彙の存在を加点
  軸C: セクション内の音節数ばらつき・強母音の交替頻度を加点

Phase 2（1-2ヶ月後）に実測オーディオ解析版へ拡張予定:
  軸B: librosa等を用いたスペクトル重心 > A4周波数での時間比率
  軸C: 音高推定(pYIN/piptrack)による音程差分散

詳細: バックログ「音節密度ルール拡張設計(案A'合成案)」タスク

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
import statistics
import sys
from pathlib import Path


# ========================================
# 軸B/軸C 用 定数
# ========================================

# 破裂音（パ・バ・タ・ダ行）：中高音的な発声を促す音
PLOSIVE_RE = re.compile(r"[パバタダパパラバ][ァィゥェォー]?|[pbtd]")
# 強母音（あ・い・う・え・お）：中高音域を出しやすい母音
STRONG_VOWELS = "あいうえお"
STRONG_VOWEL_RE = re.compile(f"[{STRONG_VOWELS}]")
# 低音ウィスパー語彙（ネガティブ指標）
WHISPER_WORDS = ("囁く", "伏せる", "眠る", "そっと", "静かに", "息を殺す", "影が揺れる")
# 中高音語彙（ポジティブ指標・命令形・力強い動詞）
MID_HIGH_WORDS = (
    "張れ", "跳べ", "鳴らせ", "叩け", "叫べ", "歌え", "立て", "見せろ",
    "信じろ", "抱いて行け", "来い", "出ろ", "声を揃え", "足踏み",
    "火種", "太鼓", "胸", "声", "朝日", "心",
)

# 推奨3軸総合判定の閾値
MID_HIGH_THRESHOLD = 50  # 軸B: 50以上で「中高音OK」
PITCH_RANGE_THRESHOLD = 40  # 軸C: 40以上で「抑揚OK」

# セクション分類と重み付け
SECTION_WEIGHTS = {
    # サビ系: 軸B/C が高得点であるべき
    "Chorus": 1.0,
    "Chorus:Final": 1.0,
    "Big Chorus": 1.2,
    # Verse系: 中庸
    "Verse": 0.7,
    "Verse 1": 0.7,
    "Verse 2": 0.7,
    "Verse 3": 0.7,
    "Verse 4": 0.7,
    # 低重要セクション: Intro/Break/Outro/Bridge
    "Intro": 0.5,
    "Break": 0.5,
    "Bridge": 0.6,
    "Outro": 0.5,
}


def classify_section(section_name: str) -> str:
    """セクション名を sabi / verse / low の3カテゴリに分類。

    サビ系: Chorus, Big Chorus, Chorus:Final
    Verse系: Verse 1-4, A, B, C（汎用）
    低重要: Intro, Break, Bridge, Outro
    """
    if any(k in section_name for k in ("Chorus", "サビ", "sabi")):
        return "sabi"
    if any(k in section_name for k in ("Verse", "A:", "B:", "C:", "メロ")):
        return "verse"
    return "low"


def _kanji_to_hiragana_simple(text: str) -> str:
    """漢字をひらがなに変換する簡易版（janome依存なし）。

    Phase 1では主要語彙のみ対応。複雑な読み方は正規表現でカバーできない。
    未対応の漢字はそのまま残る（強母音カウント対象から外れる）。
    """
    hira_map = {
        "胸を張れ": "むねをはれ",
        "胸": "むね", "張れ": "はれ",
        "朝日": "あさひ", "出": "で",
        "足踏み鳴らせ": "あしふみならせ",
        "足踏み": "あしふみ", "鳴らせ": "ならせ",
        "声を揃え": "こえをそろえ",
        "声を": "こえを", "揃え": "そろえ",
        "信じて": "しんじて",
        "漏れそうな": "もれそうな", "漏れそう": "もれそう",
        "火種を抱いて行け": "ひだねをだいていけ",
        "火種": "ひだね", "抱いて行け": "だいていけ",
        "祭礼前夜": "さいれいぜんや",
        "自分の輪郭": "じぶんのりんかく",
        "確かめに来い": "たしかめにこい",
        "誰もが見てる": "だれもみてる",
        "自分の太鼓": "じぶんのおおづつ",
    }
    # 長い順に置換（複合語優先）
    for kanji, hira in sorted(hira_map.items(), key=lambda x: -len(x[0])):
        text = text.replace(kanji, hira)
    return text


def _line_syllables_simple(line: str) -> int:
    """文字数ベースの簡易音節数カウント（行ベース）"""
    line = re.sub(r"[、。、「」『』()（）\[\]/…\s]", "", line)
    return len(line)


def calc_mid_high_score(section_name: str, lines: list[str]) -> float:
    """軸B: 中高音使用率スコア（0.0-100.0）を計算。

    判定要素:
      + 破裂音（パ・バ・タ・ダ行）の有無（1点/行）
      + 強母音（あ・い・う・え・お）の使用率（10%目標）
      + 中高音語彙（「張れ」「鳴らせ」型）の有無（5点/語）
      - 低音ウィスパー語彙（「囁く」「眠る」「そっと」型）の存在（-10点/語）

    重み付け: セクションタイプ別（サビ1.0, Verse0.7, Intro/Break0.5）
    """
    if not lines or not any(line.strip() for line in lines):
        return 0.0

    raw_score = 0.0
    total_chars = 0
    strong_vowel_count = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # 漢字→ひらがな変換（語彙マッチング用）
        hira = _kanji_to_hiragana_simple(stripped)
        total_chars += len(hira)

        # 破裂音加点（行ごと）
        if PLOSIVE_RE.search(hira):
            raw_score += 5.0

        # 中高音語彙加点（漢字混じりでもマッチするよう両方で確認）
        for word in MID_HIGH_WORDS:
            if word in stripped or word in hira:
                raw_score += 8.0

        # ウィスパー語彙減点
        for word in WHISPER_WORDS:
            if word in stripped or word in hira:
                raw_score -= 10.0

        strong_vowel_count += len(STRONG_VOWEL_RE.findall(hira))

    # 強母音使用率ボーナス（10%以上で満点加点）
    if total_chars > 0:
        vowel_ratio = strong_vowel_count / total_chars
        raw_score += min(vowel_ratio * 200, 20.0)  # 最大20点

    # セクション重み
    weight = SECTION_WEIGHTS.get(section_name, 0.5)
    weighted = raw_score * weight

    # 0-100に収める
    return max(0.0, min(100.0, weighted))


def calc_pitch_range_score(section_name: str, lines: list[str]) -> float:
    """軸C: 抑揚幅スコア（0.0-100.0）を計算。

    判定要素:
      + 行の音節数ばらつき（標準偏差が大きいほど高音程跳躍を期待）
      + 強母音（あ・い・う・え・お）の**行ごとの遷移回数**（隣接行で変われば加点）
      + 強母音の種類数（多いほど加点・最大5種で満点20点）

    平板メロ判定: 全行の音節数が同じ±2以内 → 低評価

    重み付け: セクションタイプ別（サビ高、Intro低）
    """
    valid_lines = [l.strip() for l in lines if l.strip()]
    if not valid_lines:
        return 0.0

    # 漢字→ひらがな変換（強母音カウント用）
    hira_lines = [_kanji_to_hiragana_simple(l) for l in valid_lines]
    syllables_per_line = [_line_syllables_simple(l) for l in valid_lines]
    n_lines = len(valid_lines)

    raw_score = 0.0

    # 音節数ばらつき（標準偏差ベース・標準偏差1毎に10点・最大40点）
    if n_lines >= 2:
        stdev = statistics.stdev(syllables_per_line)
        raw_score += min(stdev * 10.0, 40.0)

    # 強母音の種類数（多いほど加点・最大5種で満点20点）
    distinct_vowels = set()
    for line in hira_lines:
        distinct_vowels.update(STRONG_VOWEL_RE.findall(line))
    raw_score += min(len(distinct_vowels) * 4.0, 20.0)

    # 強母音の行ごとの遷移（隣接行で強母音セットが変化すれば加点・最大20点）
    prev_vowels = None
    transitions = 0
    for line in hira_lines:
        curr_vowels = set(STRONG_VOWEL_RE.findall(line))
        if prev_vowels is not None and curr_vowels != prev_vowels:
            transitions += 1
        prev_vowels = curr_vowels
    raw_score += min(transitions * 5.0, 20.0)

    # 行数ボーナス（サビは最低4行あるべき）
    if n_lines >= 4:
        raw_score += 10.0

    # 平板メロ減点: 音節数の最小/最大差が2以下で減点
    if n_lines >= 3:
        spread = max(syllables_per_line) - min(syllables_per_line)
        if spread <= 2:
            raw_score -= 15.0

    # セクション重み
    weight = SECTION_WEIGHTS.get(section_name, 0.5)
    weighted = raw_score * weight

    return max(0.0, min(100.0, weighted))


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

            # 軸B/軸C スコア計算（Phase 1 追加）
            mid_high_score = calc_mid_high_score(current_section, current_lines)
            pitch_range_score = calc_pitch_range_score(current_section, current_lines)

            # 総合判定（3軸のうち最低値で判定）
            axes = [
                ("A密度", density, density <= 8, density <= 10),
                ("B中高音", mid_high_score, mid_high_score >= MID_HIGH_THRESHOLD, mid_high_score >= 30),
                ("C抑揚", pitch_range_score, pitch_range_score >= PITCH_RANGE_THRESHOLD, pitch_range_score >= 20),
            ]
            axis_results = {}
            for name, val, ok_pass, ok_warn in axes:
                if name == "A密度":
                    axis_results[name] = {
                        "score": round(val, 2),
                        "verdict": "✅" if ok_pass else ("⚠️" if ok_warn else "❌"),
                    }
                else:
                    axis_results[name] = {
                        "score": round(val, 2),
                        "verdict": "✅" if ok_pass else ("⚠️" if ok_warn else "❌"),
                    }

            # 総合: ❌1つでもあれば❌、⚠️1つ以上なら⚠️、全部✅なら✅
            verdicts = [ar["verdict"] for ar in axis_results.values()]
            if "❌" in verdicts:
                overall = "❌ 禁止"
            elif "⚠️" in verdicts:
                overall = "⚠️ 警告"
            else:
                overall = "✅ 安全"

            results[current_section] = {
                "syllables": total_syl,
                "lines": len(current_lines),
                "bars": current_bars,
                "seconds": round(section_seconds, 2),
                "density": round(density, 2),
                "verdict": verdict,
                "mid_high_score": round(mid_high_score, 2),
                "pitch_range_score": round(pitch_range_score, 2),
                "axes": axis_results,
                "overall": overall,
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
            # 最初の見出し行が出たらメタデータ境界を抜ける（歌詞セクション開始）
            # 例: 歌詞ファイルでは `---GMIV設定---` 後の `## 歌詞` で復帰
            if md_heading_re.match(line):
                in_metadata = False
                # この見出し行は次のブロックで処理されるためここではcontinueしない
            else:
                continue

        # セクションヘッダー検出（コードフェンス外・`#` 接頭辞許容）
        # Markdown見出し行（### [Intro] 8小節形式）はセクションヘッダーとして処理
        m = section_header_re.match(line)
        if m:
            _flush()
            current_section = m.group("name")
            bars_str = m.group("bars")
            if bars_str:
                current_bars = int(bars_str)
            else:
                current_bars = section_default_bars.get(current_section, default_bars)
            continue

        # Markdown見出し行（セクションヘッダーでない）はスキップ
        # コードフェンス内の場合はスキップ不要（コードフェンス検出で扱う）
        if md_heading_re.match(line) and not code_fence_re.match(line):
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