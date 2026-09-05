"""G2一致保証テスト: review_policy.yaml ⇔ SKILL.md / review_lib.py の現行値一致。

spec: obsidian-ssot/docs/superpowers/specs/2026-09-04-レビュー統合スキルとlib共有ポリシー統一-design.md

- G1で抽出したYAML初期版が「両実装の現行値と完全一致」することを保証（spec §0.2）
- このリリースでは参照化しない（G3は次リリース）ため、両側の現値を**動的抽出**して
  YAMLと突合する（spec §3.6「YAMLから値リストを抽出→対象ファイル内の出現を検出」
  の動的生成方式・固定シグネチャgrepは使わない）
"""

import re
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
YAML_PATH = REPO_ROOT / "config" / "multi-llm-review" / "review_policy.yaml"
SKILL_PATH = REPO_ROOT / "skills" / "multi-llm-review" / "SKILL.md"
LIB_PATH = REPO_ROOT / "scripts" / "auto-dev" / "review_lib.py"

sys.path.insert(0, str(REPO_ROOT / "scripts" / "auto-dev"))
import review_lib  # noqa: E402  # noqa: E402


@pytest.fixture(scope="module")
def policy() -> dict:
    """YAML正本を読み込む（読込自体の失敗は fail-fast の第1検証）。"""
    return yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def skill_md() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def lib_src() -> str:
    return LIB_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# ファイル存在・frontmatter（V3a/V6相当）
# ---------------------------------------------------------------------------


def test_yaml_exists_and_parses(policy):
    """V3a: YAML欠損・parse不能なら即fail（正本の存在保証）。"""
    assert isinstance(policy, dict)


def test_yaml_required_top_keys(policy):
    """spec §3.2 の必須キー構造。未知キー（Strict対象）はG3でlib側に実装・
    この段階では必須キーの存在のみ保証する。"""
    for key in (
        "version",
        "last_updated",
        "vendors",
        "judge",
        "severity_enum",
        "severity_normalize",
        "output_schema",
        "silent_definition",
    ):
        assert key in policy, f"必須キー欠落: {key}"


def test_yaml_version_is_semver(policy):
    assert re.fullmatch(r"\d+\.\d+\.\d+", str(policy["version"])), (
        f"versionがSemVerでない: {policy['version']}"
    )


def test_yaml_last_updated_is_iso(policy):
    """V6: last_updatedはISO形式のみ（"yesterday"等はschema_violation相当）。"""
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(policy["last_updated"])), (
        f"last_updatedがISO形式でない: {policy['last_updated']}"
    )


# ---------------------------------------------------------------------------
# judge閾値（lib側・SKILL側の双方と一致）
# ---------------------------------------------------------------------------


def test_abort_vendor_threshold_matches_lib(lib_src, policy):
    """lib側はYAML judge.abort_vendor_threshold を参照する（G3参照化後契約）。

    旧契約（`len(ok_vendors) < N` の値抽出照合）はG3で廃止:
    libは値の複製を持たず、実行時にYAMLから読む。陽性=参照箇所の存在 +
    陰性=数値直書き0件で代替する。
    """
    assert 'judge"]["abort_vendor_threshold"' in lib_src, (
        "lib側にYAML judge.abort_vendor_threshold の参照が無い（過修正）"
    )
    assert re.search(r"len\(ok_vendors\) < \d", lib_src) is None, (
        "lib側にabort閾値の数値直書きが残っている"
    )


def test_critical_ng_threshold_matches_lib(lib_src, policy):
    """lib側はYAML judge.critical_ng_threshold を参照する（G3参照化後契約）。"""
    assert 'judge"]["critical_ng_threshold"' in lib_src, (
        "lib側にYAML judge.critical_ng_threshold の参照が無い（過修正）"
    )
    assert re.search(r"len\(criticals\) >= \d", lib_src) is None, (
        "lib側にng閾値の数値直書きが残っている"
    )


def test_abort_vendor_threshold_matches_skill(skill_md, policy):
    """SKILL.md側の縮退判定: 「M ≥ 2 で続行。M < 2 は中止」（L84付近）。"""
    ge = re.findall(r"M ≥ (\d+) で続行", skill_md)
    lt = re.findall(r"M < (\d+) は中止", skill_md)
    assert ge and lt, "SKILL.mdの縮退判定(M ≥ N で続行 / M < N は中止)が見つからない"
    thr = policy["judge"]["abort_vendor_threshold"]
    assert {int(x) for x in ge} == {int(x) for x in lt} == {thr}, (
        f"SKILL.md縮退判定{set(ge) | set(lt)} != YAML {thr}"
    )


def test_silent_policy_value_is_silent_definition_key(policy):
    """r6採用: silent_policyの値は silent_definition のキーと一致必須。"""
    assert policy["judge"]["silent_policy"] in policy["silent_definition"], (
        f"silent_policy '{policy['judge']['silent_policy']}' が silent_definition の"
        "キーに存在しない"
    )


# ---------------------------------------------------------------------------
# severity（enum・正規化マップ）
# ---------------------------------------------------------------------------


def test_severity_enum(policy, lib_src, skill_md):
    """enumは libプロンプト と SKILL.md正規化行 の双方に出現する。"""
    enum = set(policy["severity_enum"])
    assert enum == {"critical", "high", "med", "low"}
    assert enum.issubset(set(re.findall(r"critical/high/med/low", lib_src) and enum)), (
        "lib側プロンプトのseverity列挙とenumが不整合"
    )
    assert re.search(r"\{critical, high, med, low\}", skill_md), (
        "SKILL.mdの正規化後集合表記がenumと不一致"
    )


def _skill_normalize_map(skill_md: str) -> dict[str, str]:
    """SKILL.md「severity 正規化マップ」テーブルを動的パースする。

    行例: `| blocker / critical / P0 / 致命的 | critical |`
    """
    mapping: dict[str, str] = {}
    for line in skill_md.splitlines():
        m = re.match(r"^\| ([^|]+) \| (critical|high|med|low) \|$", line.strip())
        if not m:
            continue
        for raw in m.group(1).split("/"):
            word = raw.strip()
            if word:
                mapping[word] = m.group(2)
    return mapping


def test_severity_normalize_covers_skill_table(skill_md, policy):
    """SKILL.md正規化テーブルの全エントリがYAMLと一致。"""
    skill_map = _skill_normalize_map(skill_md)
    assert skill_map, "SKILL.md正規化テーブルが1件もパースできなかった"
    for key, value in skill_map.items():
        assert policy["severity_normalize"].get(key) == value, (
            f"severity_normalize[{key!r}]: SKILL.md={value} != "
            f"YAML={policy['severity_normalize'].get(key)}"
        )


def test_severity_normalize_covers_lib_map(policy):
    """lib正規化マップ（YAML由来・小文字キー）がYAMLと一致（G3参照化後契約）。"""
    expected = {str(k).lower(): v for k, v in policy["severity_normalize"].items()}
    assert review_lib._severity_map() == expected


# ---------------------------------------------------------------------------
# vendors（モデル一覧・トークン上限）
# ---------------------------------------------------------------------------


def test_minimax_models_match_lib(policy):
    """lib実行時のMiniMax候補がYAML由来で一致（G3参照化後契約）。"""
    assert review_lib._minimax_models() == list(
        policy["vendors"]["minimax"]["models"]
    )


def test_openrouter_models_match_lib(policy):
    """lib実行時のOpenRouter候補がYAML由来で一致（env未設定時）。"""
    assert review_lib._openrouter_models() == list(
        policy["vendors"]["openrouter"]["models"]
    )


def test_vendor_max_tokens_match_lib(lib_src, policy):
    """lib内にmax_tokens数値の直書き0件・YAML参照が有る（G3参照化後契約）。"""
    assert re.search(r'"max_tokens":\s*\d', lib_src) is None, (
        "lib側にmax_tokens数値直書きが残っている"
    )
    for ref in ('["vendors"]["minimax"]', '["max_tokens"]', '["vendors"]["openrouter"]'):
        assert ref in lib_src, f"lib側にYAML参照 '{ref}' が無い"


def test_gemini_generation_config_matches_lib(lib_src, policy):
    """libのgemini生成設定はYAML正本参照・数値直書き0件（G3参照化後契約）。"""
    assert re.search(r"maxOutputTokens=\d", lib_src) is None, (
        "lib側にmaxOutputTokens数値直書きが残っている"
    )
    for ref in ('["vendors"]["gemini"]', '["max_output_tokens"]', '["temperature"]'):
        assert ref in lib_src, f"lib側にYAML参照 '{ref}' が無い"


def test_gemini_models_come_from_skill(skill_md, policy):
    """SKILL.md側のGemini slug（URL形式 `models/<slug>:generateContent`）が
    YAMLのvendors.gemini.modelsに収録済み（G2時点は直書きが正・参照化はG3）。"""
    slugs = set(re.findall(r"models/([\w.\-]+):generateContent", skill_md))
    assert slugs, "SKILL.mdからgemini slugが見つからない"
    yaml_models = set(policy["vendors"]["gemini"]["models"])
    missing = slugs - yaml_models
    assert not missing, f"SKILL.mdのslugがYAML未収録: {missing}"


def test_openrouter_reasoning_disabled_matches_skill(skill_md, policy):
    """OpenRouterの reasoning 無効化（2026-08-21実測・5連敗対策）。"""
    assert policy["vendors"]["openrouter"]["reasoning_enabled"] is False
    assert re.search(r'"enabled":\s*false', skill_md), (
        "SKILL.mdにreasoning無効化指定が見つからない"
    )


# ---------------------------------------------------------------------------
# output_schema（libプロンプトのJSON契約）
# ---------------------------------------------------------------------------


def test_output_schema_fields_match_lib_prompt(lib_src, policy):
    required = policy["output_schema"]["required_fields"]
    assert set(required) == {"issue", "severity", "quote", "suggestion"}
    for field in required:
        assert f'"{field}"' in lib_src, (
            f"lib側プロンプト/パースに出力フィールド'{field}'が見つからない"
        )


def test_output_schema_items_max_matches_lib(lib_src, policy):
    """libプロンプトの件数上限はYAML output_schema.items_max 参照（G3参照化後）。"""
    assert re.search(r"最大\d+件", lib_src) is None, (
        "lib側に指摘件数上限の数値直書きが残っている"
    )
    for ref in ("output_schema", "items_max", "required_fields"):
        assert ref in lib_src, f"lib側にYAML参照 '{ref}' が無い"
