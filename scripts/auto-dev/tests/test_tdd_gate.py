"""tdd_gate.py のテスト（D″案第一段階C層・4条件blockゲート）。"""
import subprocess
from pathlib import Path

import tdd_gate


# ===== 純関数: コードファイル判定 =====


def test_is_code_file_py拡張子はTrue():
    assert tdd_gate.is_code_file("src/app.py") is True


def test_is_code_file_ts系拡張子はTrue():
    assert tdd_gate.is_code_file("web/index.tsx") is True


def test_is_code_file_mdとjsonはFalse():
    assert tdd_gate.is_code_file("docs/README.md") is False
    assert tdd_gate.is_code_file("config/settings.json") is False


# ===== 純関数: テスト関数カウント（AST） =====


def test_count_test_functions_関数とメソッドを数える():
    src = """
def test_a():
    assert 1 == 1

def helper():
    return 2

class TestFoo:
    def test_b(self):
        assert 2 == 2

    def setup(self):
        pass
"""
    assert tdd_gate.count_test_functions(src) == 2


def test_count_test_functions_空ソースは0():
    assert tdd_gate.count_test_functions("") == 0


def test_count_test_functions_パース失敗は0():
    assert tdd_gate.count_test_functions("def broken(:") == 0


# ===== 純関数: 空アサーション検出（質検査） =====


def test_has_substantive_assertion_変数比較はTrue():
    src = """
def test_x():
    result = add(1, 2)
    assert result == 3
"""
    assert tdd_gate.has_substantive_assertion(src) is True


def test_has_substantive_assertion_assert_TrueのみはFalse():
    src = """
def test_x():
    assert True
"""
    assert tdd_gate.has_substantive_assertion(src) is False


def test_has_substantive_assertion_定数のみ比較はFalse():
    src = """
def test_x():
    assert 1 == 1
"""
    assert tdd_gate.has_substantive_assertion(src) is False


def test_has_substantive_assertion_assertion無しはFalse():
    src = """
def test_x():
    print("hello")
"""
    assert tdd_gate.has_substantive_assertion(src) is False


# ===== 純関数: モック含有検出（KPI・警告のみ） =====


def test_mock_import_count_検出():
    src = """
from unittest import mock

def test_x():
    m = mock.MagicMock()
"""
    assert tdd_gate.mock_import_count(src) == 1


def test_mock_import_count_非モックは0():
    src = """
import json

def test_x():
    assert json.dumps({"a": 1})
"""
    assert tdd_gate.mock_import_count(src) == 0


# ===== 純関数: pytest green件数パース =====


def test_parse_green_count_passed形式():
    assert tdd_gate.parse_green_count("5 passed in 0.1s") == 5


def test_parse_green_count_失敗混在はNone():
    assert tdd_gate.parse_green_count("3 passed, 1 failed in 0.1s") is None


def test_parse_green_count_マッチなしはNone():
    assert tdd_gate.parse_green_count("no tests ran") is None


# ===== 純関数: テスト区分パース =====


def test_extract_test_category_新規追加():
    assert tdd_gate.extract_test_category("テスト区分: 新規追加") == "新規追加"


def test_extract_test_category_対象外():
    assert tdd_gate.extract_test_category("- テスト区分: 対象外") == "対象外"


def test_extract_test_category_宣言なしはNone():
    assert tdd_gate.extract_test_category("# 計画\n本文のみ") is None


def test_extract_test_category_無効値はNone():
    assert tdd_gate.extract_test_category("テスト区分: 不明") is None


# ===== 純関数: F層テスト方針パース =====


def test_parse_test_policy_選択肢と理由():
    text = "3 該当なし: ドキュメント追記のみのためテスト不要"
    result = tdd_gate.parse_test_policy(text)
    assert result["choice"] == 3
    assert len(result["reason"]) >= 20


def test_parse_test_policy_理由短すぎはNone():
    text = "3 該当なし: 短い"
    assert tdd_gate.parse_test_policy(text) is None


def test_parse_test_policy_選択肢1と2は理由不要():
    assert tdd_gate.parse_test_policy("1")["choice"] == 1
    assert tdd_gate.parse_test_policy("2 既存テストで網羅")["choice"] == 2


def test_parse_test_policy_無効入力はNone():
    assert tdd_gate.parse_test_policy("9") is None
    assert tdd_gate.parse_test_policy("") is None


# ===== 純関数: A層 plan.md 検証 =====


def test_validate_plan_ACと区分ありはok():
    plan = "# 計画\n## 受け入れ条件\n- pytest全緑 (exit code 0)\n\nテスト区分: 新規追加\n"
    result = tdd_gate.validate_plan(plan)
    assert result["ok"] is True
    assert result["reasons"] == []


def test_validate_plan_AC欄なしはng():
    plan = "# 計画\nテスト区分: 新規追加\n"
    result = tdd_gate.validate_plan(plan)
    assert result["ok"] is False


def test_validate_plan_区分宣言なしはng():
    plan = "# 計画\n## 受け入れ条件\n- pytest全緑\n"
    result = tdd_gate.validate_plan(plan)
    assert result["ok"] is False
    assert any("テスト区分" in r for r in result["reasons"])


def test_validate_plan_coverage100はng():
    plan = (
        "# 計画\n## 受け入れ条件\n- coverage 100%達成\n"
        "テスト区分: 新規追加\n"
    )
    result = tdd_gate.validate_plan(plan)
    assert result["ok"] is False
    assert any("coverage" in r for r in result["reasons"])


# ===== allowlist判定 =====


def test_repo_in_allowlist_パス一致():
    config = {"test_gate_repos": [{"name": "NexusCore", "path": "/r/nexus"}]}
    assert tdd_gate.repo_in_allowlist("/r/nexus", config) is True


def test_repo_in_allowlist_不在はFalse():
    config = {"test_gate_repos": [{"name": "NexusCore", "path": "/r/nexus"}]}
    assert tdd_gate.repo_in_allowlist("/r/other", config) is False


def test_repo_in_allowlist_設定なしはFalse():
    assert tdd_gate.repo_in_allowlist("/r/nexus", {}) is False


# ===== git diff 統合（tmpリポジトリで実測） =====


def _make_git_repo(tmp_path: Path) -> Path:
    """テスト用gitリポジトリを作り (before, after) のHEADを返える。"""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
         "--allow-empty", "-m", "init"],
        cwd=repo, check=True,
    )
    return repo


def _commit_file(repo: Path, path: str, content: str) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", path], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
         "-m", f"add {path}"],
        cwd=repo, check=True,
    )


def test_diff_test_delta_新規テスト追加はdelta_1(tmp_path):
    repo = _make_git_repo(tmp_path)
    before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    _commit_file(repo, "tests/test_new.py", "def test_a():\n    assert 1 == 1\n")
    result = tdd_gate.diff_test_delta(repo, before, "HEAD")
    assert result["new_functions"] >= 1
    assert result["existing_changed"] is False


def test_diff_test_delta_実装のみ変更はdelta_0(tmp_path):
    repo = _make_git_repo(tmp_path)
    before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    _commit_file(repo, "src/app.py", "def add(a, b):\n    return a + b\n")
    result = tdd_gate.diff_test_delta(repo, before, "HEAD")
    assert result["new_functions"] == 0
    assert result["existing_changed"] is False


def test_diff_test_delta_既存テスト書換はexisting_changed(tmp_path):
    repo = _make_git_repo(tmp_path)
    _commit_file(repo, "tests/test_a.py", "def test_a():\n    assert 1 == 1\n")
    before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    _commit_file(repo, "tests/test_a.py", "def test_a():\n    assert 2 == 2\n")
    result = tdd_gate.diff_test_delta(repo, before, "HEAD")
    assert result["existing_changed"] is True


def test_diff_test_delta_空アサーションのみはsubstantive_0(tmp_path):
    repo = _make_git_repo(tmp_path)
    before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    _commit_file(repo, "tests/test_dummy.py", "def test_x():\n    assert True\n")
    result = tdd_gate.diff_test_delta(repo, before, "HEAD")
    assert result["new_functions"] == 1  # 関数としては存在
    assert result["new_substantive"] == 0  # 中身のあるassertionは0


# ===== ゲート統合判定 evaluate_gate =====


def test_evaluate_gate_allowlist外はskipで合格():
    result = tdd_gate.evaluate_gate(
        repo="/r/other",
        delta={"new_functions": 0, "new_substantive": 0, "existing_changed": False,
               "code_files_changed": []},
        category="新規追加",
        pytest_log=None,
        allowlisted=False,
    )
    assert result["passed"] is True
    assert result["skipped"] is True


def test_evaluate_gate_対象外宣言でコード変更なしは合格():
    result = tdd_gate.evaluate_gate(
        repo="/r/nexus",
        delta={"new_functions": 0, "new_substantive": 0, "existing_changed": False,
               "code_files_changed": []},
        category="対象外",
        pytest_log=None,
        allowlisted=True,
    )
    assert result["passed"] is True


def test_evaluate_gate_対象外宣言でもコード変更ありはblock():
    result = tdd_gate.evaluate_gate(
        repo="/r/nexus",
        delta={"new_functions": 0, "new_substantive": 0, "existing_changed": False,
               "code_files_changed": ["src/app.py"]},
        category="対象外",
        pytest_log=None,
        allowlisted=True,
    )
    assert result["passed"] is False
    assert any("対象外" in r for r in result["reasons"])


def test_evaluate_gate_新規追加宣言でテスト無しはblock():
    result = tdd_gate.evaluate_gate(
        repo="/r/nexus",
        delta={"new_functions": 0, "new_substantive": 0, "existing_changed": False,
               "code_files_changed": ["src/app.py"]},
        category="新規追加",
        pytest_log=None,
        allowlisted=True,
    )
    assert result["passed"] is False


def test_evaluate_gate_テストありpytest証跡なしはblock():
    result = tdd_gate.evaluate_gate(
        repo="/r/nexus",
        delta={"new_functions": 2, "new_substantive": 2, "existing_changed": False,
               "code_files_changed": ["src/app.py", "tests/test_x.py"]},
        category="新規追加",
        pytest_log=None,
        allowlisted=True,
    )
    assert result["passed"] is False
    assert any("pytest" in r for r in result["reasons"])


def test_evaluate_gate_テストあり証跡ありは合格():
    log = {"rc": 0, "green_count": 5, "log_path": "/tmp/x.log"}
    result = tdd_gate.evaluate_gate(
        repo="/r/nexus",
        delta={"new_functions": 2, "new_substantive": 2, "existing_changed": False,
               "code_files_changed": ["src/app.py", "tests/test_x.py"]},
        category="新規追加",
        pytest_log=log,
        allowlisted=True,
    )
    assert result["passed"] is True


def test_evaluate_gate_空アサーションのみの新規テストはblock():
    log = {"rc": 0, "green_count": 5, "log_path": "/tmp/x.log"}
    result = tdd_gate.evaluate_gate(
        repo="/r/nexus",
        delta={"new_functions": 1, "new_substantive": 0, "existing_changed": False,
               "code_files_changed": ["tests/test_dummy.py"]},
        category="新規追加",
        pytest_log=log,
        allowlisted=True,
    )
    assert result["passed"] is False
    assert any("空アサーション" in r for r in result["reasons"])


def test_evaluate_gate_既存テスト修正宣言でAST差分ありは合格():
    log = {"rc": 0, "green_count": 5, "log_path": "/tmp/x.log"}
    result = tdd_gate.evaluate_gate(
        repo="/r/nexus",
        delta={"new_functions": 0, "new_substantive": 0, "existing_changed": True,
               "code_files_changed": ["tests/test_a.py"]},
        category="既存修正",
        pytest_log=log,
        allowlisted=True,
    )
    assert result["passed"] is True


def test_evaluate_gate_モック含有率高は警告のみで合格():
    log = {"rc": 0, "green_count": 5, "log_path": "/tmp/x.log"}
    result = tdd_gate.evaluate_gate(
        repo="/r/nexus",
        delta={"new_functions": 2, "new_substantive": 2, "existing_changed": False,
               "code_files_changed": ["src/app.py"], "mock_count": 2},
        category="新規追加",
        pytest_log=log,
        allowlisted=True,
    )
    assert result["passed"] is True
    assert any("モック含有率" in r for r in result["warnings"])


def test_extract_test_category_with_bold_decoration():
    """2026-09-01 Q5実発: LLMが**太字**装飾を付けてもテスト区分を抽出できる。"""
    from tdd_gate import extract_test_category
    assert extract_test_category("テスト区分: **新規追加**（既存への小幅修正を伴う）") == "新規追加"
    assert extract_test_category("テスト区分:**既存修正**") == "既存修正"
    assert extract_test_category("テスト区分: 対象外") == "対象外"
