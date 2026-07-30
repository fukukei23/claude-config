"""impact-a データパーサ
- antipatterns.md: YAML区画抽出 + パース
- dangerous-ops.yaml: パース
"""
import re
from typing import Any

import yaml


def extract_yaml_block(text: str, marker: str) -> str:
    """指定マーカーで囲まれたYAML区画の中身を抽出。見つからなければ空文字。

    クロージングマーカーは `<!-- /marker-base -->` の短縮形式を許容する。
    例: 開始 `<!-- impact-mode: antipatterns:v1 -->` / 終了 `<!-- /impact-mode -->`
    """
    # 開始マーカーから "id" 部分（":" 以前）を取り出し、クロージング側でもそれを許容する
    base = marker.split(":", 1)[0].strip()
    open_pat = r"<!--\s*" + re.escape(marker) + r"\s*-->"
    close_pat = r"<!--\s*/" + re.escape(base) + r"\s*-->"
    pattern = re.compile(
        open_pat + r"\n```yaml\n(.*?)\n```\n" + close_pat,
        re.DOTALL,
    )
    m = pattern.search(text)
    return m.group(1) if m else ""


def parse_antipatterns_md(text: str) -> list[dict[str, Any]]:
    """antipatterns.md のYAML区画をパースしてリストで返す。"""
    yaml_text = extract_yaml_block(text, "impact-mode: antipatterns:v1")
    if not yaml_text:
        return []
    data = yaml.safe_load(yaml_text) or {}
    return list(data.get("antipatterns", []))


def parse_dangerous_ops_yaml(text: str) -> list[dict[str, Any]]:
    """dangerous-ops.yaml をパースして dangerous_ops リストを返す。

    frontmatter(1st YAML doc) + body(2nd YAML doc) の二段構成を許容。
    `dangerous_ops` キーを含むdoc を全走査して結合して返す。
    """
    found: list[dict[str, Any]] = []
    for doc in yaml.safe_load_all(text) or []:
        if not isinstance(doc, dict):
            continue
        if "dangerous_ops" in doc:
            found.extend(list(doc.get("dangerous_ops") or []))
    return found