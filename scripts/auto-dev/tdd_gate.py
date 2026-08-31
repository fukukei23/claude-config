#!/usr/bin/env python3
"""C層テストゲート（D″案第一段階）: テスト無し完了を機械的にblockする。

4条件:
  1. テスト関数/ケース数の差分>=1 または 既存テストのAST差分あり
     （空アサーション `assert True` 等は substative 数に数えない）
  2. pytest 生ログの提出（green件数の実測）
  3. repo種別allowlist（configの手動フラグ・機械判定）
  4. warnでなくblock（失敗時 exit 1 = run-task.sh が VERIFY を NG 化）

モック含有率はKPI（警告のみ・blockしない）。
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

# B層相当の列挙条件（第一段階はPython/TS系・対象外宣言の整合検証にも使用）
CODE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx"}
TEST_CATEGORIES = ("新規追加", "既存修正", "対象外")
# テストファイル判定: test_*.py / *_test.py / tests(s)_ ディレクトリ配下
_TEST_BASE_RE = re.compile(r"^test_|^test$|_test$|^test\b")
GREEN_RE = re.compile(r"(\d+)\s+passed")
CATEGORY_RE = re.compile(r"テスト区分[:：]\s*\**\s*(新規追加|既存修正|対象外)")  # **太字**装飾許容（2026-09-01 Q5実発: LLMが装飾付き出力し機械検証誤NG）
COVERAGE_100_RE = re.compile(r"coverage[^0-9]{0,6}100", re.IGNORECASE)


def is_code_file(path: str) -> bool:
    """パスがコードファイル（*.py|*.ts系）か否かを機械判定する。

    Args:
        path: repo相対パス（git diff --name-one 形式）。

    Returns:
        コードファイルなら True。
    """
    return Path(path).suffix in CODE_SUFFIXES


def is_test_file(path: str) -> bool:
    """パスがテストファイルか否かを機械判定する。

    Args:
        path: repo相対パス。

    Returns:
        test_*.py / *_test.py / tests/ 配下のファイルなら True。
    """
    p = Path(path)
    if p.suffix not in CODE_SUFFIXES:
        return False
    if _TEST_BASE_RE.search(p.name):
        return True
    return any(part in ("tests", "test", "__tests__") for part in p.parts[:-1])


def _parse(source: str) -> ast.Module | None:
    """ソースをASTにパースする（失敗時 None）。"""
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def count_test_functions(source: str) -> int:
    """AST で test_ で始まる関数/メソッドの数を数える。

    Args:
        source: Pythonソース全文。

    Returns:
        テスト関数・メソッドの合計数（パース失敗時 0）。
    """
    tree = _parse(source)
    if tree is None:
        return 0
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    )


def _assert_is_substantive(node: ast.Assert) -> bool:
    """assert 文が変数参照を含む実質的な検証か判定する。"""
    return any(isinstance(n, ast.Name) for n in ast.walk(node.test))


def has_substantive_assertion(source: str) -> bool:
    """ソース内に実質的な assert（assert True・定数のみ比較を除く）があるか。

    Args:
        source: Pythonソース全文。

    Returns:
        変数参照を1つでも含む assert があれば True。
    """
    tree = _parse(source)
    if tree is None:
        return False
    return any(
        _assert_is_substantive(n) for n in ast.walk(tree) if isinstance(n, ast.Assert)
    )


def count_substantive_test_functions(source: str) -> int:
    """実質的なassertionを含むテスト関数のみを数える（空アサーション除外）。"""
    tree = _parse(source)
    if tree is None:
        return 0
    count = 0
    for node in ast.walk(tree):
        if not (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        ):
            continue
        has_assert = any(
            isinstance(n, ast.Assert) for n in ast.walk(node)
        )
        if has_assert and any(
            isinstance(n, ast.Assert) and _assert_is_substantive(n)
            for n in ast.walk(node)
        ):
            count += 1
    return count


def mock_import_count(source: str) -> int:
    """mock / MagicMock の import 文数を数える（KPI用）。"""
    tree = _parse(source)
    if tree is None:
        return 0
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "unittest.mock":
                count += 1
            elif node.module == "unittest" and any(
                alias.name in ("mock", "MagicMock", "patch") for alias in node.names
            ):
                count += 1
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "mock" or alias.name.startswith("unittest.mock"):
                    count += 1
    return count


def parse_green_count(text: str) -> int | None:
    """pytest 出力から green（passed）件数を抽出する。

    Args:
        text: pytest の生出力。

    Returns:
        passed 件数。failed/error 混在やマッチなしは None（信用できない）。
    """
    if "failed" in text or "error" in text.lower():
        return None
    m = GREEN_RE.search(text)
    return int(m.group(1)) if m else None


def extract_test_category(text: str) -> str | None:
    """文書（plan.md等）からテスト区分宣言を抽出する。

    Args:
        text: plan.md 等の全文。

    Returns:
        "新規追加" / "既存修正" / "対象外" のいずれか。宣言なし・無効値は None。
    """
    m = CATEGORY_RE.search(text)
    return m.group(1) if m else None


def parse_test_policy(text: str) -> dict | None:
    """F層テスト方針入力をパースする。

    選択肢: 1=テスト追加必要 / 2=既存テストで網羅 / 3=該当なし（理由20字以上必須）。

    Args:
        text: 起票時の入力文字列（例: "3 該当なし: ドキュメント追記のみのため"）。

    Returns:
        {"choice": 1|2|3, "reason": str}。無効入力・理由不足は None。
    """
    m = re.match(r"^\s*([123])\s*(.*)$", text or "")
    if not m:
        return None
    choice = int(m.group(1))
    reason = m.group(2).strip()
    if choice == 3 and len(reason) < 20:
        return None
    return {"choice": choice, "reason": reason}


def validate_plan(plan: str) -> dict:
    """A層: plan.md の機械検証（AC欄・テスト区分・coverage100%禁止）。

    Args:
        plan: plan.md の全文。

    Returns:
        {"ok": bool, "reasons": [str, ...]}。
    """
    reasons: list[str] = []
    if "受け入れ条件" not in plan:
        reasons.append("受け入れ条件(AC)欄なし（必須）")
    category = extract_test_category(plan)
    if category is None:
        reasons.append("テスト区分宣言なし（新規追加/既存修正/対象外 のいずれか必須）")
    if COVERAGE_100_RE.search(plan):
        reasons.append("coverage=100% は禁止（既存値±5pt以内で設定せよ）")
    return {"ok": not reasons, "reasons": reasons}


def repo_in_allowlist(repo_path: str, config: dict) -> bool:
    """repoがテストゲートallowlist（コード系repo手動フラグ）に含まれるか。

    Args:
        repo_path: リポジトリ絶対パス。
        config: auto-loop-config.yaml の内容。

    Returns:
        allowlist に含まれれば True。
    """
    entries = config.get("test_gate_repos") or []
    for entry in entries:
        if isinstance(entry, dict):
            if entry.get("path") == repo_path or entry.get("name") == repo_path:
                return True
        elif entry == repo_path:
            return True
    return False


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """repo 内で git を実行する（text mode）。"""
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=False
    )


def _blob_at(repo: Path, rev: str, path: str) -> str | None:
    """指定リビジョンのファイル内容を返す（不在・失敗時 None）。"""
    result = _git(repo, "show", f"{rev}:{path}")
    if result.returncode != 0:
        return None
    return result.stdout


def diff_test_delta(repo: Path, before: str, after: str) -> dict:
    """before..after の差分からテスト増減・AST差分を機械抽出する。

    Args:
        repo: リポジトリパス。
        before: 比較元リビジョン（実装前HEAD）。
        after: 比較先リビジョン（通常 HEAD）。

    Returns:
        {"new_functions": int, "new_substantive": int, "existing_changed": bool,
         "code_files_changed": [str], "mock_count": int}
    """
    repo = Path(repo)
    changed = [
        line
        for line in _git(repo, "diff", "--name-only", before, after)
        .stdout.splitlines()
        if line.strip()
    ]
    code_files = [f for f in changed if is_code_file(f)]
    test_files = [f for f in changed if is_test_file(f)]

    old_total = new_total = old_sub = new_sub = mock_total = 0
    existing_changed = False
    for tf in test_files:
        old_src = _blob_at(repo, before, tf)
        new_src = _blob_at(repo, after, tf)
        old_n = count_test_functions(old_src) if old_src is not None else 0
        new_n = count_test_functions(new_src) if new_src is not None else 0
        old_total += old_n
        new_total += new_n
        old_sub += (
            count_substantive_test_functions(old_src) if old_src is not None else 0
        )
        new_sub += (
            count_substantive_test_functions(new_src) if new_src is not None else 0
        )
        if new_src is not None:
            mock_total += mock_import_count(new_src)
        if old_src is not None and new_src is not None:
            old_tree = _parse(old_src)
            new_tree = _parse(new_src)
            if old_tree is not None and new_tree is not None:
                if ast.dump(old_tree) != ast.dump(new_tree):
                    existing_changed = True

    return {
        "new_functions": max(new_total - old_total, 0),
        "new_substantive": max(new_sub - old_sub, 0),
        "existing_changed": existing_changed,
        "code_files_changed": code_files,
        "mock_count": mock_total,
    }


def evaluate_gate(
    repo: str,
    delta: dict,
    category: str | None,
    pytest_log: dict | None,
    allowlisted: bool,
) -> dict:
    """4条件を統合判定する（純粋関数・UIから切り離す）。

    Args:
        repo: リポジトリパス（ログ出力用）。
        delta: diff_test_delta の結果。
        category: テスト区分（None は宣言なし）。
        pytest_log: {"rc", "green_count", "log_path"} または None（未提出）。
        allowlisted: repoがallowlist内か。

    Returns:
        {"passed": bool, "skipped": bool, "reasons": [...], "warnings": [...]}。
    """
    if not allowlisted:
        return {
            "passed": True,
            "skipped": True,
            "reasons": ["allowlist外・ゲートskip（コード系repoのみ有効）"],
            "warnings": [],
        }

    reasons: list[str] = []
    warnings: list[str] = []

    if category is None:
        reasons.append("テスト区分宣言なし（A層で事前宣言必須）")
    elif category == "対象外":
        if delta.get("code_files_changed"):
            reasons.append(
                f"テスト区分『対象外』だがコードファイル変更あり: "
                f"{delta['code_files_changed'][:3]}"
            )
    else:
        has_test_change = delta.get("new_substantive", 0) >= 1 or delta.get(
            "existing_changed", False
        )
        if not has_test_change:
            if delta.get("new_functions", 0) >= 1:
                reasons.append(
                    "新規テストが空アサーションのみ（assert True等は不成立）"
                )
            else:
                reasons.append(
                    "テスト関数の追加/修正なし（新規>=1 または既存テストAST差分が必要）"
                )
        if has_test_change:
            if pytest_log is None:
                reasons.append("pytest生ログ未提出（green件数の実測証跡必須）")
            elif pytest_log.get("rc") != 0:
                reasons.append(f"pytest失敗(rc={pytest_log.get('rc')})")
            elif pytest_log.get("green_count") is None:
                reasons.append("pytest green件数パース不能（生ログを確認）")

    new_funcs = delta.get("new_functions", 0)
    mock_count = delta.get("mock_count", 0)
    if new_funcs and mock_count / new_funcs > 0.5:
        warnings.append(
            f"モック含有率高: 新規テスト{new_funcs}件中{mock_count}件がmock利用"
        )

    return {
        "passed": not reasons,
        "skipped": False,
        "reasons": reasons,
        "warnings": warnings,
    }


def run_pytest(repo: Path, log_path: Path) -> dict | None:
    """repo 内で pytest を実行し生ログを保存する。

    Args:
        repo: リポジトリパス。
        log_path: 生ログの保存先（pytest.log）。

    Returns:
        {"rc": int, "green_count": int|None, "log_path": str}。
        pytest 起動自体に失敗した時は None。
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=570,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        sys.stderr.write(f"[test_gate] pytest起動失敗: {e}\n")
        return None
    output = result.stdout + result.stderr
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(output, encoding="utf-8")
    return {
        "rc": result.returncode,
        "green_count": parse_green_count(output),
        "log_path": str(log_path),
    }


def load_config(path: Path) -> dict:
    """auto-loop-config.yaml を読む（無ければ空 dict）。"""
    if not path.exists():
        return {}
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def cmd_gate(args: argparse.Namespace) -> int:
    """CLI: ゲート本体（run-task.sh から呼ばれる）。"""
    task_dir = Path(args.task_dir)
    repo = Path(args.repo)
    config = load_config(Path(args.config))
    try:
        category = args.category
        if category is None:
            plan = task_dir / "plan.md"
            category = (
                extract_test_category(plan.read_text(encoding="utf-8"))
                if plan.exists()
                else None
            )
        delta = diff_test_delta(repo, args.before, args.after)
        pytest_log = run_pytest(repo, task_dir / "logs" / "pytest.log")
        result = evaluate_gate(
            repo=str(repo),
            delta=delta,
            category=category,
            pytest_log=pytest_log,
            allowlisted=repo_in_allowlist(str(repo), config),
        )
        result["delta"] = delta
        result["pytest"] = pytest_log
    except Exception as e:  # ゲート内部エラーもblock（例外巻き込み防止）
        result = {
            "passed": False,
            "skipped": False,
            "reasons": [f"ゲート内部エラー: {e}"],
            "warnings": [],
        }
    out = task_dir / "gate-result.json"
    task_dir.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["passed"] else 1


def cmd_validate_plan(args: argparse.Namespace) -> int:
    """CLI: plan.md のA層機械検証。"""
    plan = Path(args.plan).read_text(encoding="utf-8")
    result = validate_plan(plan)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


def cmd_parse_policy(args: argparse.Namespace) -> int:
    """CLI: F層テスト方針入力のパース（approve.py から呼ばれる）。"""
    result = parse_test_policy(args.text)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result is not None else 1


def main(argv: list[str] | None = None) -> int:
    """エントリポイント。"""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_gate = sub.add_parser("gate", help="4条件blockゲート本体")
    p_gate.add_argument("--repo", required=True)
    p_gate.add_argument("--before", required=True)
    p_gate.add_argument("--after", default="HEAD")
    p_gate.add_argument("--task-dir", required=True)
    p_gate.add_argument("--category", default=None)
    p_gate.add_argument(
        "--config",
        default=str(Path(__file__).parent / "auto-loop-config.yaml"),
    )
    p_gate.set_defaults(func=cmd_gate)

    p_plan = sub.add_parser("validate-plan", help="plan.mdのA層機械検証")
    p_plan.add_argument("--plan", required=True)
    p_plan.set_defaults(func=cmd_validate_plan)

    p_policy = sub.add_parser("parse-policy", help="F層テスト方針パース")
    p_policy.add_argument("text")
    p_policy.set_defaults(func=cmd_parse_policy)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
