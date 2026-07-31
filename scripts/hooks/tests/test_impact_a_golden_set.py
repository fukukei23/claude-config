"""impact-a ゴールデンセット検証（E''進め方ステップ2・spec§5.2）

6件fixture の層a期待値(matched)を detect_from_state で検証し、
Recall/Precision/Accuracy を測定する。detector.py 本体は変更しない
（現状の層a検知性能を測るのがステップ2の目的・本体を変えると測定意味が消失）。

axis=layer_b_only の F2b は改善目標KPI（現状 matched=True の偽陽性・目標 False）のため
条件付き xfail で「想定通りのギャップ」として記録する。
"""
import sys
from pathlib import Path

import pytest
import yaml

HOOKS_DIR = Path.home() / ".claude" / "scripts" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

from impact_a.detector import detect_from_state  # type: ignore  # noqa: E402
from impact_a.parser import parse_antipatterns_md, parse_dangerous_ops_yaml  # type: ignore  # noqa: E402

GOLDEN_DIR = Path.home() / "projects" / "claude-config" / "scripts" / "hooks" / "tests" / "golden_set"
SSOT = Path.home() / "projects" / "obsidian-ssot" / "00_SYSTEM"


def _load_golden_set() -> list[dict]:
    """golden_set/F*.yaml を全件ロード（絶対パス参照・README 管理原則）。"""
    cases = [yaml.safe_load(f.read_text()) for f in sorted(GOLDEN_DIR.glob("F*.yaml"))]
    assert cases, f"ゴールデンセットfixtureが見つかりません: {GOLDEN_DIR}"
    return cases


GOLDEN_CASES = _load_golden_set()


@pytest.fixture(scope="module")
def antipatterns() -> list[dict]:
    return parse_antipatterns_md((SSOT / "impact-antipatterns.md").read_text())


@pytest.fixture(scope="module")
def dangerous_ops() -> list[dict]:
    return parse_dangerous_ops_yaml((SSOT / "dangerous-ops.yaml").read_text())


def _detect(case: dict, antipatterns: list[dict], dangerous_ops: list[dict]) -> dict:
    return detect_from_state(case["diff"], antipatterns, dangerous_ops)


# F2b は axis=layer_b_only の改善目標KPI（現状偽陽性・層bで是正目標）
def _is_expected_gap(case: dict) -> bool:
    return case.get("axis") == "layer_b_only" and case["id"] == "F2b"


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c["id"] for c in GOLDEN_CASES])
def test_layer_a_matched(case: dict, antipatterns: list[dict], dangerous_ops: list[dict]) -> None:
    """各fixture の layer_a_expected.matched を detect_from_state の結果で検証。"""
    res = _detect(case, antipatterns, dangerous_ops)
    exp = case["layer_a_expected"]
    # F2b: 現状 matched=True（偽陽性）で exp=False のギャップは想定通り → xfail で記録
    if _is_expected_gap(case) and res["matched"] is True and exp["matched"] is False:
        pytest.xfail(
            "F2b 改善目標KPI: 現状 matched=True（偽陽性・trigger 'enabled'/'skip' 部分一致）・"
            "目標 False（層bで『安全』と是正）"
        )
    assert res["matched"] == exp["matched"], (
        f"{case['id']}: exp.matched={exp['matched']} got={res['matched']} "
        f"kw={res['matched_keywords']} dop={res['dangerous_op_match']}"
    )


def test_f2a_false_positive_reproduced(
    antipatterns: list[dict], dangerous_ops: list[dict]
) -> None:
    """F2a: 層aの偽陽性を再現し、原因(trigger 'filter' の汎用語マッチ)まで検証。"""
    case = next(c for c in GOLDEN_CASES if c["id"] == "F2a")
    res = _detect(case, antipatterns, dangerous_ops)
    assert res["matched"] is True, "F2a は現状 detector の偽陽性(matched=True)を再現するはず"
    kws_lower = [k.lower() for k in res["matched_keywords"]]
    assert "filter" in kws_lower, (
        f"偽陽性の原因は trigger 'filter' 部分一致・got kw={res['matched_keywords']}"
    )


def test_layer_a_metrics(
    antipatterns: list[dict], dangerous_ops: list[dict], capsys: pytest.CaptureFixture[str]
) -> None:
    """6件で Recall/Precision/Accuracy を算出し、不変条件を検証 + 詳細レポートを stdout 出力。

    golden の layer_a_expected.matched を正解とした層aの分類性能:
      TP=exp(T)&got(T) / FN=exp(T)&got(F) / FP=exp(F)&got(T) / TN=exp(F)&got(F)
    """
    tp = fp = fn = tn = 0
    rows: list[tuple] = []
    for case in GOLDEN_CASES:
        res = _detect(case, antipatterns, dangerous_ops)
        exp_m: bool = case["layer_a_expected"]["matched"]
        got_m: bool = res["matched"]
        if exp_m and got_m:
            kind, tp = "TP", tp + 1
        elif exp_m and not got_m:
            kind, fn = "FN", fn + 1
        elif (not exp_m) and got_m:
            kind, fp = "FP", fp + 1
        else:
            kind, tn = "TN", tn + 1
        rows.append(
            (case["id"], exp_m, got_m, kind, res["matched_keywords"], res["dangerous_op_match"])
        )

    recall = tp / (tp + fn) if (tp + fn) else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    accuracy = (tp + tn) / len(GOLDEN_CASES)

    # 不変条件（E''ステップ2時点）: 真陽性 F1/F2a/F5 は層aが必ず検知する
    assert recall == 1.0, f"Recall={recall:.3f} (TP={tp}, FN={fn}): 真陽性を取りこぼしてはいけない"

    lines = [
        "[impact-a golden set metrics]",
        f"  TP={tp} FN={fn} FP={fp} TN={tn} (n={len(GOLDEN_CASES)})",
        f"  Recall={recall:.3f} Precision={precision:.3f} Accuracy={accuracy:.3f}",
        "  per-case:",
    ]
    for fid, exp_m, got_m, kind, kws, dop in rows:
        lines.append(f"    {fid}: exp={exp_m} got={got_m} [{kind}] kw={kws} dop={dop}")
    print("\n" + "\n".join(lines))
