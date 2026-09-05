"""G3: review_policy.yaml 読込機構のテスト（spec §3.3-3.5・V3/V5/V6/V7対応）。

load_review_policy() / PolicyConfigError の契約を固定する。
YAML正本: claude-config/config/multi-llm-review/review_policy.yaml
spec: obsidian-ssot/docs/superpowers/specs/2026-09-04-レビュー統合スキルとlib共有ポリシー統一-design.md
"""
import json
import os
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import review_lib  # noqa: E402
from review_lib import PolicyConfigError, load_review_policy  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]  # claude-config
REAL_YAML = REPO_ROOT / "config/multi-llm-review/review_policy.yaml"
REAL_VERSION = "1.1.0"


def _policy_text(fn=None, version: str = REAL_VERSION) -> str:
    """正本YAMLを複利⽤し、fn で一部だけ書き換えたテキストを返す。"""
    data = yaml.safe_load(REAL_YAML.read_text(encoding="utf-8"))
    data["version"] = version
    if fn is not None:
        fn(data)
    return yaml.safe_dump(data, allow_unicode=True)


@pytest.fixture
def roots(tmp_path, monkeypatch):
    """ホワイトリストに正本repo root + tmp_path を許可した状態。"""
    monkeypatch.setattr(review_lib, "_ALLOWED_REPO_ROOTS", [REPO_ROOT, tmp_path])
    return tmp_path


# --- 正常系 ---


def test_load_real_policy_ok(capsys):
    """正本YAMLを正しいexpected_versionで読める。"""
    policy = load_review_policy(REAL_VERSION)
    assert policy["version"] == REAL_VERSION
    out = capsys.readouterr()
    # spec §3.3: 解決した実パスを必ずログ出力（監査性）
    assert str(REAL_YAML) in out.err


def test_patch_diff_warns_and_continues(roots, capsys):
    """patch差（1.1.0 → 1.1.1期待）は警告1行で継続（spec §3.4・OR採用）。"""
    policy = load_review_policy("1.1.1")
    assert policy["version"] == REAL_VERSION
    err = capsys.readouterr().err
    assert "警告" in err or "warning" in err.lower()


def test_force_local_allows_version_skip(roots, capsys):
    """force_local は version照合をスキップし警告付きで通す（spec §3.4）。"""
    policy = load_review_policy(None, force_local=True)
    assert policy["version"] == REAL_VERSION
    err = capsys.readouterr().err
    assert "警告" in err or "warning" in err.lower()


# --- version照合（V5） ---


def test_missing_expected_version_aborts(roots):
    """expected_version 省略は即abort・文言にRead失敗の可能性を併記（spec r6）。"""
    with pytest.raises(PolicyConfigError) as ei:
        load_review_policy(None)
    assert ei.value.error_type == "version_mismatch"
    assert "Read" in ei.value.message


def test_major_and_minor_diff_abort(roots):
    """major差・minor差はともにabort（spec §3.4）。"""
    for ver in ("0.9.0", "2.0.0", "1.2.0"):
        with pytest.raises(PolicyConfigError) as ei:
            load_review_policy(ver)
        assert ei.value.error_type == "version_mismatch", ver


# --- パス解決・ホワイトリスト（V4/V7） ---


def test_env_path_insecure_aborts_no_fallback(roots):
    """env指定がrepo外なら config_path_insecure で即abort・フォールバック禁止。"""
    outside = roots / ".." / "outside.yaml"
    outside.write_text(_policy_text(), encoding="utf-8")
    os.environ["MULTI_LLM_REVIEW_CONFIG_PATH"] = str(outside.resolve())
    try:
        with pytest.raises(PolicyConfigError) as ei:
            load_review_policy(REAL_VERSION)
        assert ei.value.error_type == "config_path_insecure"
    finally:
        os.environ.pop("MULTI_LLM_REVIEW_CONFIG_PATH", None)


def test_env_relative_path_rejected(roots):
    """相対パス指定は config_path_relative で拒否（spec §3.3・r5採用）。"""
    os.environ["MULTI_LLM_REVIEW_CONFIG_PATH"] = "config/relative.yaml"
    try:
        with pytest.raises(PolicyConfigError) as ei:
            load_review_policy(REAL_VERSION)
        assert ei.value.error_type == "config_path_relative"
    finally:
        os.environ.pop("MULTI_LLM_REVIEW_CONFIG_PATH", None)


def test_env_missing_file_is_config_not_found(roots):
    """env指定の実在しないパスは config_not_found（生tracebackを出さない・r6）。"""
    os.environ["MULTI_LLM_REVIEW_CONFIG_PATH"] = str(roots / "nope.yaml")
    try:
        with pytest.raises(PolicyConfigError) as ei:
            load_review_policy(REAL_VERSION)
        assert ei.value.error_type == "config_not_found"
    finally:
        os.environ.pop("MULTI_LLM_REVIEW_CONFIG_PATH", None)


def test_env_valid_path_loads(roots):
    """repo配下のenv指定パスは読める（正規経路）。"""
    p = roots / "policy_env.yaml"
    p.write_text(_policy_text(), encoding="utf-8")
    os.environ["MULTI_LLM_REVIEW_CONFIG_PATH"] = str(p)
    try:
        policy = load_review_policy(REAL_VERSION)
        assert policy["version"] == REAL_VERSION
    finally:
        os.environ.pop("MULTI_LLM_REVIEW_CONFIG_PATH", None)


# --- スキーマ検証・Strict（V3/V6） ---


def test_parse_error_on_invalid_yaml(roots):
    """不正形式YAMLは parse_error。"""
    p = roots / "broken.yaml"
    p.write_text("{broken: [", encoding="utf-8")
    os.environ["MULTI_LLM_REVIEW_CONFIG_PATH"] = str(p)
    try:
        with pytest.raises(PolicyConfigError) as ei:
            load_review_policy(REAL_VERSION)
        assert ei.value.error_type == "parse_error"
    finally:
        os.environ.pop("MULTI_LLM_REVIEW_CONFIG_PATH", None)


def test_unknown_top_key_is_strict_violation(roots):
    """未知トップレベルキーは schema_violation（Strict・r4採用）。"""
    p = roots / "unknown.yaml"
    p.write_text(_policy_text(lambda d: d.update(unknown_key=1)), encoding="utf-8")
    os.environ["MULTI_LLM_REVIEW_CONFIG_PATH"] = str(p)
    try:
        with pytest.raises(PolicyConfigError) as ei:
            load_review_policy(REAL_VERSION)
        assert ei.value.error_type == "schema_violation"
        assert "unknown_key" in ei.value.message
    finally:
        os.environ.pop("MULTI_LLM_REVIEW_CONFIG_PATH", None)


def test_unknown_nested_key_is_strict_violation(roots):
    """vendors 配下の未知キーも schema_violation（深部Strict）。"""
    def mutate(d):
        d["vendors"]["gemini"]["unknown_opt"] = 1

    p = roots / "unknown_nested.yaml"
    p.write_text(_policy_text(mutate), encoding="utf-8")
    os.environ["MULTI_LLM_REVIEW_CONFIG_PATH"] = str(p)
    try:
        with pytest.raises(PolicyConfigError) as ei:
            load_review_policy(REAL_VERSION)
        assert ei.value.error_type == "schema_violation"
    finally:
        os.environ.pop("MULTI_LLM_REVIEW_CONFIG_PATH", None)


def test_missing_required_key_version(roots):
    """version 欠落は schema_violation。"""
    p = roots / "noversion.yaml"
    p.write_text(_policy_text(lambda d: d.pop("version")), encoding="utf-8")
    os.environ["MULTI_LLM_REVIEW_CONFIG_PATH"] = str(p)
    try:
        with pytest.raises(PolicyConfigError) as ei:
            load_review_policy(REAL_VERSION)
        assert ei.value.error_type == "schema_violation"
    finally:
        os.environ.pop("MULTI_LLM_REVIEW_CONFIG_PATH", None)


def test_bad_last_updated_format(roots):
    """last_updated が ISO 形式以外は schema_violation（V6・r4採用）。"""
    p = roots / "baddate.yaml"
    p.write_text(
        _policy_text(lambda d: d.update(last_updated="yesterday")), encoding="utf-8"
    )
    os.environ["MULTI_LLM_REVIEW_CONFIG_PATH"] = str(p)
    try:
        with pytest.raises(PolicyConfigError) as ei:
            load_review_policy(REAL_VERSION)
        assert ei.value.error_type == "schema_violation"
    finally:
        os.environ.pop("MULTI_LLM_REVIEW_CONFIG_PATH", None)


def test_silent_policy_key_mismatch(roots):
    """silent_policy 値は silent_definition のキーと一致必須（spec r6）。"""
    def mutate(d):
        d["judge"]["silent_policy"] = "no_such_policy"

    p = roots / "silentmismatch.yaml"
    p.write_text(_policy_text(mutate), encoding="utf-8")
    os.environ["MULTI_LLM_REVIEW_CONFIG_PATH"] = str(p)
    try:
        with pytest.raises(PolicyConfigError) as ei:
            load_review_policy(REAL_VERSION)
        assert ei.value.error_type == "schema_violation"
    finally:
        os.environ.pop("MULTI_LLM_REVIEW_CONFIG_PATH", None)


def test_oversize_config_aborts(roots, monkeypatch):
    """サイズ上限超過はabort（V7・r4採用）。上限は定数で差し替え可能。"""
    monkeypatch.setattr(review_lib, "_MAX_CONFIG_BYTES", 10)
    p = roots / "big.yaml"
    p.write_text(_policy_text(), encoding="utf-8")
    os.environ["MULTI_LLM_REVIEW_CONFIG_PATH"] = str(p)
    try:
        with pytest.raises(PolicyConfigError) as ei:
            load_review_policy(REAL_VERSION)
        assert ei.value.error_type == "schema_violation"
    finally:
        os.environ.pop("MULTI_LLM_REVIEW_CONFIG_PATH", None)


def test_permission_error_normalized(roots):
    """読取権限なしは permission_error（生tracebackを出さない・r6）。"""
    if os.geteuid() == 0:
        pytest.skip("root では権限拒否にならない")
    p = roots / "noperm.yaml"
    p.write_text(_policy_text(), encoding="utf-8")
    p.chmod(0o000)
    os.environ["MULTI_LLM_REVIEW_CONFIG_PATH"] = str(p)
    try:
        with pytest.raises(PolicyConfigError) as ei:
            load_review_policy(REAL_VERSION)
        assert ei.value.error_type == "permission_error"
    finally:
        os.environ.pop("MULTI_LLM_REVIEW_CONFIG_PATH", None)
        p.chmod(0o644)


# --- エラーJSONL（spec §3.5） ---


def test_error_jsonl_record_written(roots, monkeypatch, tmp_path):
    """PolicyConfigError 時にエラーJSONLへ1行記録（4キー契約）。"""
    log = tmp_path / "policy_errors.jsonl"
    monkeypatch.setattr(review_lib, "_ERROR_LOG_PATH", log)
    p = roots / "broken2.yaml"
    p.write_text("{broken: [", encoding="utf-8")
    os.environ["MULTI_LLM_REVIEW_CONFIG_PATH"] = str(p)
    try:
        with pytest.raises(PolicyConfigError):
            load_review_policy(REAL_VERSION)
    finally:
        os.environ.pop("MULTI_LLM_REVIEW_CONFIG_PATH", None)
    lines = log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert set(rec) == {"timestamp", "error_type", "message", "config_path"}
    assert rec["error_type"] == "parse_error"
