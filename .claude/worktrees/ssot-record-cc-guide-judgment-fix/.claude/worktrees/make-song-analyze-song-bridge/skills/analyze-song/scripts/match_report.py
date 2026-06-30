"""照合結果からスコア + 改善ヒント（make-song 連携フォーマット）を生成する。"""


def build_report(ctx: dict) -> dict:
    """照合結果を受け make-song 連携レポートを構築する。

    Args:
        ctx: query/top/normalized_db/centroid/scores_detail を持つ辞書。

    Returns:
        score（top/centroid）と hints（改善ヒント文字列リスト）を持つ辞書。
    """
    top = ctx["top"]
    centroid = ctx["centroid"]
    scores_detail = ctx["scores_detail"]

    hints = []
    if top:
        best_id = top[0][0]
        best = scores_detail.get(best_id, {})
        # BPM ヒント
        if best.get("bpm") is not None and best["bpm"] < 0.6:
            hints.append(
                f"BPM: 最も近い名曲({best_id})とテンポ差が大きいです。"
                f"テンポを名曲の型(平均 {centroid.get('avg_bpm')})に寄せると類似度向上。"
            )
        elif best.get("bpm") is not None and best["bpm"] >= 0.8:
            hints.append("BPM: 名曲の型と近く、テンポ感は良好です。")
        # キーヒント
        if best.get("key") is not None and best["key"] < 0.6:
            hints.append("キー: 五度圏で遠いです。近接調への移調を検討してください。")
        # コードヒント
        if best.get("chord") is not None and best["chord"] < 0.4:
            hints.append(
                f"コード進行: 共有コード進行が少ないです。{best_id} の進行を参考にしてください。"
            )
        elif best.get("chord") is None:
            hints.append("コード進行: 比較データ不足で評価できません。")
    if not hints:
        hints.append("全軸で名曲の型に近い状態です。")

    return {
        "score": {
            "top": top,
            "centroid": centroid,
        },
        "hints": hints,
    }


def render_markdown(report: dict, query_meta: dict | None = None) -> str:
    """レポート辞書を report.md 形式の Markdown 文字列で出力する。

    Args:
        report: build_report の戻り値。
        query_meta: query 曲のメタ（title 等）。任意。

    Returns:
        Markdown 文字列。
    """
    title = (query_meta or {}).get("title", "(unknown)")
    lines = [f"# 名曲照合レポート: {title}", ""]
    lines.append("## 類似名曲ランキング")
    for sid, total in report["score"]["top"]:
        lines.append(f"- {sid}: {total:.3f}")
    c = report["score"]["centroid"]
    lines.append("")
    lines.append("## 重心（代表型）")
    lines.append(f"- 平均 BPM: {c.get('avg_bpm')}")
    lines.append(f"- 最頻キー(PC): {c.get('mode_key_pc')}")
    lines.append("")
    lines.append("## 改善ヒント")
    for h in report["hints"]:
        lines.append(f"- {h}")
    return "\n".join(lines) + "\n"


def build_make_song_input(
    ctx: dict, db_meta: dict, query_features: dict, query_id: str | None = None
) -> dict:
    """照合結果から make-song 連携用の構造化 dict を構築する。

    Args:
        ctx: match() の戻り値（top/centroid/scores_detail/normalized_db）。
        db_meta: _index.yaml の songs を id→meta 辞書化したもの。
        query_features: query 曲の features.json dict。
        query_id: query 曲のID（自分除外用・未設定可）。

    Returns:
        make_song_input.json の dict。
    """
    top = ctx["top"]
    centroid = ctx["centroid"]

    references = []
    rank = 0
    for sid, total in top:
        if query_id and sid == query_id:
            continue
        rank += 1
        entry: dict = {"rank": rank, "id": sid, "total": round(total, 3)}
        meta = db_meta.get(sid, {})
        for key in ("title", "artist", "genre"):
            if key in meta:
                entry[key] = meta[key]
        references.append(entry)

    genre_dist: dict = {}
    for r in references:
        g = r.get("genre")
        if g:
            genre_dist[g] = genre_dist.get(g, 0) + 1

    q_meta = query_features.get("meta", {})
    query_info: dict = {}
    if query_id:
        query_info["id"] = query_id
    if "title" in q_meta:
        query_info["title"] = q_meta["title"]
    tempo = query_features.get("tempo", {})
    if "bpm" in tempo:
        query_info["bpm"] = tempo["bpm"]
    key = query_features.get("key", {})
    if "key" in key:
        query_info["key"] = key["key"]
    vocals = query_features.get("vocals", {})
    if "gender_estimate" in vocals:
        query_info["gender_estimate"] = vocals["gender_estimate"]

    avg_bpm = centroid.get("avg_bpm")
    mode_key_pc = centroid.get("mode_key_pc")
    recommended: dict = {}
    if avg_bpm is not None:
        recommended["bpm"] = round(avg_bpm)
    if mode_key_pc is not None:
        recommended["key_pc"] = mode_key_pc

    return {
        "schema_version": 1,
        "query": query_info,
        "reference_songs": references,
        "centroid": {"avg_bpm": avg_bpm, "mode_key_pc": mode_key_pc},
        "recommended": recommended,
        "genre_distribution": genre_dist,
        "notes": build_report(ctx)["hints"],
    }
