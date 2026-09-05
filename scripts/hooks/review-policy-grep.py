#!/usr/bin/env python3
"""review_policy.yaml 直書き検出grep（G3・spec §3.6 動的生成方式・r4/r5採用）。

YAML正本から値リストを抽出し、対象ファイル（SKILL.md / review_lib.py）内の
出現を検出する。固定シグネチャgrepは使わない。

検出方式（spec §3.6 偽陽性対策・r5/r5b）:
- モデルslug・MCPツール名など長い値 → 単独リテラル検索
- 数値・短い値（閾値・トークン上限・temperature）→ **キー名との複合マッチ**
  （例: ``max_tokens=8000`` / ``abort_vendor_threshold: 2``）
- 自然言語記述・severity_normalize の語（blocker 等）は spec 上 対象外
- ``vendors.openrouter.pick_script`` は記録用キー（手順コマンド内の正当出現が
  あるため対象外・G1乖離4の記録どおり機械参照はしない）

Usage:
    python3 review-policy-grep.py --yaml <yaml> --target <file>
Exit: 0 = 直書きあり（検出）/ 1 = なし（clean）
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml


def _leaf_pairs(data: object, path: str = "") -> list[tuple[str, str]]:
    """YAMLを (パス, 葉の値文字列) のリストへ平坦化する。"""
    pairs: list[tuple[str, str]] = []
    if isinstance(data, dict):
        for k, v in data.items():
            pairs.extend(_leaf_pairs(v, f"{path}{k}."))
    elif isinstance(data, list):
        for v in data:
            pairs.extend(_leaf_pairs(v, path))
    else:
        pairs.append((path, str(data)))
    return pairs


# 複合マッチ（キー名+値）で検査する葉キー（数値・短い値・spec偽陽性対策）
_COMPOUND_KEYS = {
    "max_tokens",
    "max_output_tokens",
    "items_max",
    "abort_vendor_threshold",
    "critical_ng_threshold",
    "temperature",
}
# 対象外キー（spec上の除外・理由はdocstring）
_EXCLUDED_KEYS = {"pick_script", "last_updated", "version", "reasoning_enabled"}
# 対象外パス（severity語・フィールド名等の一般語はspec「単独grep禁止」により
# 構造テスト（G2一致テストの実行時突合）に切り分ける・自然言語は複合マッチ不能）
_EXCLUDED_PATHS = ("severity_enum.", "severity_normalize.", "output_schema.required_fields.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--yaml", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()

    policy = yaml.safe_load(Path(args.yaml).read_text(encoding="utf-8"))
    target = Path(args.target).read_text(encoding="utf-8")

    findings: list[str] = []
    for path, value in _leaf_pairs(policy):
        leaf = path.rstrip(".").split(".")[-1]
        if leaf in _EXCLUDED_KEYS:
            continue
        if any(path.startswith(p) for p in _EXCLUDED_PATHS):
            continue
        if not value:
            continue
        if leaf in _COMPOUND_KEYS:
            # キー名+値の複合マッチ（数値単独grep禁止・r5採用）
            pat = re.compile(
                rf"{re.escape(leaf)}\s*[\"']?\s*[=:]\s*[\"']?{re.escape(value)}\b"
            )
            for m in pat.finditer(target):
                line_no = target.count("\n", 0, m.start()) + 1
                findings.append(f"{Path(args.target).name}:{line_no}: 複合直書き {leaf}={value}")
        elif len(value) > 3:  # 3文字以下は単独grep禁止（spec r5採用）
            for m in re.finditer(re.escape(value), target):
                line_no = target.count("\n", 0, m.start()) + 1
                findings.append(
                    f"{Path(args.target).name}:{line_no}: 単独直書き [{path}] {value}"
                )

    if findings:
        print(f"直書き検出 {len(findings)}件:")
        for f in findings:
            print(f"  {f}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
