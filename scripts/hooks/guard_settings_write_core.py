"""guard-settings-write コアロジック（純粋関数・テスト対象）

spec: docs/superpowers/specs/2026-07-30-guard-settings-write-post-detection-design.md
"""
import re

# 層1: 既知プロバイダ prefix 辞書（spec§4層ルール・層1）
# gitleaks 厳選ルールは Task 6 で拡張。まず基本辞書。
PREFIX_PATTERNS = [
    re.compile(r"^sk-"),                 # OpenAI
    re.compile(r"^xox[abp]-"),           # Slack
    re.compile(r"^gh[pousr]_"),          # GitHub PAT/secret
    re.compile(r"^AKIA"),                # AWS access key
    re.compile(r"^AIza"),                # Google API key
    re.compile(r"^glpat-"),              # GitLab
    re.compile(r"^claude-"),             # Anthropic
]

# 層2: 除外パターン（誤検知抑制）
# ※除外は「文字列全体が該当フォーマット」の場合のみ（部分一致は除外しない・偽装バイパス対策）
URL_RE = re.compile(r"^https?://\S+$")     # 完全一致限定
PATH_RE = re.compile(r"^/\S+$|^\~/\S+$")   # 完全なUnixパス/homeパスのみ
TOOL_SCHEMA_RE = re.compile(r"^(Bash|Read|Edit|Write|MultiEdit|Grep|Glob|WebFetch)\([^)]*\)$")  # 完全なツール呼出形式のみ


def layer1_prefix(value: str) -> bool:
    """層1: 既知プロバイダ prefix 辞書に一致するか

    len<10 ガード: prefix 単独('sk-'等)の誤検知防止・spec短TOKEN境界(31/30/29字)準拠。
    Task6 で gitleaks厳選ルール(プロバイダ別の正確な長さ/文字種)へ昇華。
    """
    if not value or len(value) < 10:
        return False
    return any(p.match(value) for p in PREFIX_PATTERNS)


def _char_class_count(value: str) -> int:
    """英大文字・英小文字・数字・記号のうち何種類含むか"""
    classes = 0
    if re.search(r"[A-Z]", value):
        classes += 1
    if re.search(r"[a-z]", value):
        classes += 1
    if re.search(r"[0-9]", value):
        classes += 1
    if re.search(r"[^A-Za-z0-9\s]", value):
        classes += 1
    return classes


def layer2_long(value: str) -> bool:
    """層2: 長文字列32字+文字種混在(3種以上)+URL/パス/ツール呼出除外"""
    if not value or len(value) < 32:
        return False
    if URL_RE.search(value) or PATH_RE.search(value) or TOOL_SCHEMA_RE.match(value):
        return False
    return _char_class_count(value) >= 3


# 層3: シークレット系キー名 + ${ENV} 厳密判定
SECRET_KEY_RE = re.compile(r"(token|secret|api[_-]?key|webhook|password|auth)", re.IGNORECASE)
STRICT_ENV_RE = re.compile(r"^\$\{[A-Z_][A-Z0-9_]*\}$")  # ${VAR} のみ許可・${VAR:-x}/${sk-..}は拒否


def layer3_keyname(key: str, value: str) -> bool:
    """層3: キー名がsecret系 を含み、値が厳密な${ENV}参照でない"""
    if not value:
        return False
    if not SECRET_KEY_RE.search(key or ""):
        return False
    return not STRICT_ENV_RE.match(value)


def scan_value_for_token(key: str, value: str) -> bool:
    """層4(単値): キー名無関係に層1+層2 を適用（キー名偽装対策の最終網）"""
    if not isinstance(value, str):
        return False
    return layer1_prefix(value) or layer2_long(value)


def scan_object(obj) -> bool:
    """層4(全体): JSONツリー全値を再帰走査し scan_value_for_token 適用"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str):
                if scan_value_for_token(k, v):
                    return True
            elif scan_object(v):
                return True
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, str):
                if scan_value_for_token("", item):
                    return True
            elif scan_object(item):
                return True
    return False
