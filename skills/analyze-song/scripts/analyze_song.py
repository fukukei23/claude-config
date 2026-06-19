"""analyze-song メインパイプライン（CLI エントリポイント）。

エラー中央管理: 各ステップの成功/失敗/所要時間を _log に蓄積し features.json に埋め込む。
止まるのが基本・楽譜だけは諦めても良い。
"""
import argparse
import json
import time
from datetime import date
from pathlib import Path

from scripts import (
    features,
    midi_extract,
    report,
    score_render,
    source_fetch,
    tempo_key,
)


def _timed(label: str, func, log: list):
    """ステップを計時して log に追記。失敗時は例外をそのまま上げる。"""
    start = time.time()
    try:
        result = func()
        log.append({"step": label, "status": "ok", "sec": round(time.time() - start, 2)})
        return result
    except Exception:  # noqa: BLE001
        log.append({"step": label, "status": "fail", "sec": round(time.time() - start, 2)})
        raise


def run_pipeline(source: str, workdir: Path, title: str = "(unknown)") -> dict:
    """1曲の解析パイプラインを実行し features.json/report.md を生成する。

    Args:
        source: YouTube URL またはローカル MP3 パス。
        workdir: 出力ディレクトリ（analysis/）。
        title: 曲名。

    Returns:
        features 辞書。
    """
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    log: list = []

    audio = _timed("source_fetch", lambda: source_fetch.fetch_source(source, workdir), log)
    tempo = _timed("tempo_key", lambda: tempo_key.analyze_tempo(str(audio)), log)
    midi = _timed("midi_extract", lambda: midi_extract.extract_midi(str(audio), workdir), log)
    feat = _timed("features", lambda: features.analyze_features(str(midi)), log)

    # 楽譜だけは失敗を許容（スキップ）
    score_result = None
    start = time.time()
    try:
        score_result = score_render.render_score(str(midi), workdir)
        log.append({"step": "score_render", "status": "ok" if score_result else "skip",
                    "sec": round(time.time() - start, 2)})
    except Exception as exc:  # noqa: BLE001
        log.append({"step": "score_render", "status": "skip",
                    "reason": str(exc), "sec": round(time.time() - start, 2)})

    features_json = {
        "meta": {
            "title": title,
            "source": "youtube" if source.startswith("http") else "local",
            "source_url": source if source.startswith("http") else None,
            "duration_sec": tempo["duration_sec"],
            "analyzed_at": date.today().isoformat(),
            "phase": "1a",
        },
        "tempo": tempo["tempo"],
        "key": feat["key"],
        "chords": feat["chords"],
        "melody": feat["melody"],
        "structure": feat["structure"],
        "score": score_result,
        "_log": log,
    }
    (workdir / "features.json").write_text(
        json.dumps(features_json, ensure_ascii=False, indent=2)
    )
    report.generate_report(workdir)
    return features_json


def main():
    """CLI エントリポイント。"""
    parser = argparse.ArgumentParser(description="楽曲定量分析（Phase 1a）")
    parser.add_argument("source", help="YouTube URL またはローカル MP3 パス")
    parser.add_argument("-o", "--output", required=True, help="出力ディレクトリ")
    parser.add_argument("-t", "--title", default="(unknown)", help="曲名")
    args = parser.parse_args()
    run_pipeline(args.source, Path(args.output), title=args.title)


if __name__ == "__main__":
    main()
