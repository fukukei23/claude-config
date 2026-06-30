"""features.json から人間向け report.md（サマリ＋工程ログ）を生成する。"""
import json
from pathlib import Path


def generate_report(workdir: Path) -> Path:
    """workdir/features.json を読み report.md を書き出す。

    Args:
        workdir: features.json が入った作業ディレクトリ。

    Returns:
        workdir/report.md のパス。
    """
    features = json.loads((workdir / "features.json").read_text())
    meta = features.get("meta", {})
    tempo = features.get("tempo", {})
    key = features.get("key", {})
    chords = features.get("chords", {})
    melody = features.get("melody", {})
    pr = melody.get("phrase_repetition", {})
    vocals = features.get("vocals", {})
    inst = features.get("instrumentation", {})
    log = features.get("_log", [])

    lines = [
        f"# 楽曲分析レポート: {meta.get('title', '(unknown)')}",
        "",
        f"- ソース: {meta.get('source', '?')} / Phase: {meta.get('phase', '?')}",
        f"- BPM: {tempo.get('bpm', '?')} (信頼度 {tempo.get('bpm_confidence', '?')})",
        f"- キー: {key.get('key', '?')} {key.get('scale', '?')} (信頼度 {key.get('confidence', '?')})",
        f"- 音域: {melody.get('range_low', '?')} 〜 {melody.get('range_high', '?')} "
        f"({melody.get('range_semitones', '?')}半音)",
        "",
        "## ヴォイス",
        f"- 音域: {vocals.get('range_low', '?')} 〜 {vocals.get('range_high', '?')}",
        f"- 推定: {vocals.get('gender_estimate', '?')} / 声域: {vocals.get('timbre', '?')}",
        "",
        "## 楽器構成",
        f"- パート: {', '.join(inst.get('parts', [])) or '?'}",
        f"- 推定楽器: {', '.join(inst.get('instruments_detected', [])) or '?'}",
        "",
        "## コード進行",
        " -> ".join(chords.get("progression", [])),
        "",
        "## phrase_repetition（同一性検出）",
    ]
    if pr.get("detected"):
        for pair in pr.get("pairs", []):
            lines.append(
                f"- {pair.get('section_a')} vs {pair.get('section_b')}: "
                f"{pair.get('match')}/{pair.get('total')} 音一致"
            )
    else:
        lines.append("- 検出なし")

    lines += ["", "## 工程ログ"]
    for entry in log:
        status = entry.get("status", "?")
        extra = f" ({entry.get('reason')})" if entry.get("reason") else ""
        lines.append(f"- {entry.get('step', '?')}: {status}{extra} [{entry.get('sec', '?')}s]")

    out = workdir / "report.md"
    out.write_text("\n".join(lines))
    return out
