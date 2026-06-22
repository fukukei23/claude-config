"""名曲照合エンジンのエントリポイント（DB読込→各層→Report出力を統括）。"""
import argparse
import json
from pathlib import Path

from scripts import aggregate, feature_scores as fs, match_report, preprocess

_DEFAULT_WEIGHTS = Path(__file__).parent / "weights.yaml"
_REQUIRED_AXES = ("bpm", "key", "chord", "range")


def _load_features(path: Path) -> dict:
    """features.json を読み込む。"""
    return json.loads(path.read_text(encoding="utf-8"))


def _load_db(db_dir: Path) -> dict:
    """DB ディレクトリから song_id→正規化ベクトル を構築する（必須軸欠損曲は除外）。"""
    norm_db = {}
    for feat_path in sorted(db_dir.glob("*/features.json")):
        song_id = feat_path.parent.name
        v = preprocess.preprocess(_load_features(feat_path))
        if v is not None:
            norm_db[song_id] = v
    return norm_db


def match(query_path: Path, db_dir: Path,
          weights_path: Path = _DEFAULT_WEIGHTS) -> dict:
    """query 曲を名曲DB と照合しレポートを返す。

    Args:
        query_path: query 曲の features.json パス。
        db_dir: 名曲DB ディレクトリ（<ID>/features.json を格納）。
        weights_path: weights.yaml パス。

    Returns:
        match_report.build_report 形式の辞書。

    Raises:
        ValueError: query の必須軸が欠損している場合。
    """
    cfg = aggregate.load_weights(weights_path)
    weights = cfg["weights"]
    k = cfg.get("k", 5)

    query_v = preprocess.preprocess(_load_features(query_path))
    if query_v is None:
        raise ValueError("query 曲の必須軸(BPM/key)が欠損しています")

    norm_db = _load_db(db_dir)
    if not norm_db:
        raise ValueError("有効な DB 曲がありません")

    results = []
    scores_detail = {}
    for song_id, db_v in norm_db.items():
        scores = {
            "bpm": fs.score_bpm(query_v, db_v),
            "key": fs.score_key(query_v, db_v),
            "chord": fs.score_chord(query_v, db_v),
            "range": fs.score_range(query_v, db_v),
        }
        scores_detail[song_id] = scores
        total = aggregate.weighted_total(scores, weights)
        results.append((song_id, total))

    top = aggregate.rank(results, k)
    centr = aggregate.centroid(top, norm_db)
    return match_report.build_report({
        "query": query_v,
        "top": top,
        "normalized_db": norm_db,
        "centroid": centr,
        "scores_detail": scores_detail,
    })


def main(query_path: str, db_dir: str, out_path: str | None = None) -> Path:
    """CLI エントリ: 照合し report.md を書き出す。

    Args:
        query_path: query features.json のパス文字列。
        db_dir: 名曲DB ディレクトリのパス文字列。
        out_path: 出力 report.md パス（省略時は query と同階層）。

    Returns:
        曫き出した report.md のパス。
    """
    rep = match(Path(query_path), Path(db_dir))
    query_meta = _load_features(Path(query_path)).get("meta", {})
    md = match_report.render_markdown(rep, query_meta)
    out = Path(out_path) if out_path else Path(query_path).parent / "match_report.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(f"保存完了: {out}")
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="名曲照合エンジン: query features.json を名曲DBと照合し report.md を出力",
    )
    parser.add_argument("query_path", help="query 曲の features.json パス")
    parser.add_argument(
        "db_dir", help="名曲DB ディレクトリのパス（<ID>/features.json を格納）"
    )
    parser.add_argument(
        "-o", "--out", default=None, help="出力 report.md パス（省略時は query と同階層）"
    )
    args = parser.parse_args()
    main(args.query_path, args.db_dir, args.out)
