"""guard-settings-write コアロジック（純粋関数・テスト対象）

spec: docs/superpowers/specs/2026-07-30-guard-settings-write-post-detection-design.md
"""
import glob
import hashlib
import json
import math
import os
import re
import shutil
import time

# 層1: 既知プロバイダ prefix 辞書（spec§4層ルール・層1）
# gitleaks 厳選ルールは Task 6 で拡張。まず基本辞書。
PREFIX_PATTERNS = [
    re.compile(r"^sk-"),                 # OpenAI
    re.compile(r"^sk_live_"),            # Stripe (gitleaks厳選)
    re.compile(r"^xox[abp]-"),           # Slack
    re.compile(r"^gh[pousr]_"),          # GitHub
    re.compile(r"^AKIA"),                # AWS
    re.compile(r"^AIza"),                # Google
    re.compile(r"^glpat-"),              # GitLab
    re.compile(r"^claude-"),             # Anthropic
    re.compile(r"^hf_"),                 # HuggingFace (gitleaks厳選)
    re.compile(r"^pplx-"),               # Perplexity (gitleaks厳選)
    re.compile(r"^vercel_token_"),       # Vercel (gitleaks厳選)
    re.compile(r"^eyJ"),                 # JWT (JSON Web Token)
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


def _shannon_entropy(value: str) -> float:
    """Shannon entropy (bits/char) — 有限サンプルの観測頻度から計算"""
    if not value:
        return 0.0
    freq = {}
    for ch in value:
        freq[ch] = freq.get(ch, 0) + 1
    n = len(value)
    return -sum((c / n) * math.log2(c / n) for c in freq.values())


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


# 層2.5: Shannon entropy 補完層（hex/base64-only TOKEN・案A: キー名AND）
HEX_ONLY_RE = re.compile(r"^[0-9a-fA-F]+$")
BASE64_ONLY_RE = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")
ENTROPY_MIN_LEN = 32
HEX_ENTROPY_THRESHOLD = 3.0    # truffleHog HEX_CHARS 標準
B64_ENTROPY_THRESHOLD = 4.5    # truffleHog BASE64_CHARS 標準


def layer25_entropy(key: str, value: str) -> bool:
    """層2.5: Shannon entropy による hex/base64-only TOKEN 補捉（案A: キー名AND）

    層2の文字種3種要件を満たさない hex-only TOKEN（文字種2種: 小文字+数字）を補完。
    entropy 単体では hex TOKEN(3.93) と git SHA(3.94) が不可分離のため、
    SECRET_KEY_RE(token|secret|api_key|webhook|password|auth) に一致するキー名の下の
    値に限定し「settings.json に secret 系キーで正当な hex を置く用法は存在しない」
    文脈的排除で誤報ゼロを達成。層3は独立経路（本層は scan_value_for_token 内で層1/2 とOR）。

    評価順序（性能・早期return）: len → キー名 → ${ENV} → entropy計算(O(n))。
    ※本関数は settings.json 走査専用。他hook再利用時は誤報を再評価すること。
    """
    if not value or len(value) < ENTROPY_MIN_LEN:
        return False
    if not SECRET_KEY_RE.search(key or ""):
        return False
    if STRICT_ENV_RE.match(value):      # ${ENV} 参照は許可
        return False
    if HEX_ONLY_RE.match(value) and _shannon_entropy(value) >= HEX_ENTROPY_THRESHOLD:
        return True
    if BASE64_ONLY_RE.match(value) and _shannon_entropy(value) >= B64_ENTROPY_THRESHOLD:
        return True
    return False


def scan_value_for_token(key: str, value: str) -> bool:
    """層4(単値): キー名無関係に層1+層2 を適用（キー名偽装対策の最終網）

    ツール呼出形式(Bash(curl -d TOKEN)等)の偽装TOKENは layer2_long が
    TOOL_SCHEMA_RE で全体を除外してしまうため、inner引数を分割再走査して捕捉(限界1是正)。
    ※残限界: inner引数が10字未満の短TOKEN偽装は layer1 len<10ガードで捕捉不可。
    """
    if not isinstance(value, str):
        return False
    if layer1_prefix(value) or layer2_long(value) or layer25_entropy(key, value):
        return True
    # 層4 最終網(偽装Bash捕捉): ツール呼出形式の場合、引数を個別に走査
    if TOOL_SCHEMA_RE.match(value):
        inner = value[value.find("(") + 1 : value.rfind(")")]
        for arg in inner.split():
            if layer1_prefix(arg) or layer2_long(arg) or layer25_entropy(key, arg):
                return True
    return False


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


# 監視対象 JSON パス（spec§監視対象・ホワイトリスト除外方式）
PERMISSIONS_SUBKEYS = ("allow", "deny", "ask", "default")
MCP_SUBKEYS = ("env", "headers", "args", "command", "url")
HOOKS_SUBKEYS = ("env", "command")


def _collect_str_values(node) -> list:
    """任意のJSONノードから文字列値を再帰収集"""
    out = []
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, dict):
        for v in node.values():
            out.extend(_collect_str_values(v))
    elif isinstance(node, list):
        for item in node:
            out.extend(_collect_str_values(item))
    return out


def extract_monitored_values(settings: dict) -> list:
    """監視対象パス配下の文字列値を全て抽出（未知フィールドも含む・ホワイトリスト除外）"""
    vals = []
    perms = settings.get("permissions", {})
    if isinstance(perms, dict):
        for sk in PERMISSIONS_SUBKEYS:
            if sk in perms:
                vals.extend(_collect_str_values(perms[sk]))
    if "env" in settings:
        vals.extend(_collect_str_values(settings["env"]))
    for mcp_name, mcp_cfg in settings.get("mcpServers", {}).items():
        if isinstance(mcp_cfg, dict):
            for sk in MCP_SUBKEYS:
                if sk in mcp_cfg:
                    vals.extend(_collect_str_values(mcp_cfg[sk]))
            # mcpCfg 内の未知 secret 系キーも層3/4で拾えるよう全値収集は scan_object に任せる
    for hook_event, hook_list in settings.get("hooks", {}).items():
        if isinstance(hook_list, list):
            for h in hook_list:
                if isinstance(h, dict):
                    for hh in h.get("hooks", []):
                        if isinstance(hh, dict):
                            for sk in HOOKS_SUBKEYS:
                                if sk in hh:
                                    vals.extend(_collect_str_values(hh[sk]))
    return vals


def has_new_token_value(old_vals: set, new_vals: set) -> bool:
    """意味的差分: 新規に出現した値が ${ENV}参照以外の実値か"""
    added = set(new_vals) - set(old_vals)
    for v in added:
        if not v:
            continue
        if STRICT_ENV_RE.match(v):  # ${ENV} 追加は許可
            continue
        # 新規実値の出現 = 発火条件（4層判定は extract→scan で別途適用）
        return True
    return False


def detect_token_write(before_path: str, after_path: str) -> str:
    """Post 検知メイン: before/after の settings.json を意味的差分 + 4層判定

    戻り値: "TOKEN_DETECTED" / "CLEAN" / "PARSE_ERROR"
    """
    try:
        with open(before_path) as f:
            before = json.load(f)
        with open(after_path) as f:
            after = json.load(f)
    except Exception:
        return "PARSE_ERROR"

    old_vals = set(extract_monitored_values(before))
    new_vals = set(extract_monitored_values(after))

    # 1. 意味的差分: 新規実値が出現したか
    if not has_new_token_value(old_vals, new_vals):
        return "CLEAN"

    # 2. 新規値に対して4層判定（層4 ブロードスキャンで after 全体を走査）
    if scan_object(after.get("permissions", {})) or \
       scan_object(after.get("env", {})) or \
       scan_object(after.get("mcpServers", {})) or \
       scan_object(after.get("hooks", {})):
        return "TOKEN_DETECTED"

    # 3. settings.local.json モード: 全値走査（spec§監視対象）
    if scan_object(after):
        return "TOKEN_DETECTED"

    return "CLEAN"


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_valid_json(path: str) -> bool:
    try:
        with open(path) as f:
            json.load(f)
        return True
    except Exception:
        return False


def restore_snapshot(backup_path: str, target_path: str) -> str:
    """復元 + フォールバック。成功条件: cp戻り値0 + サイズ一致 + JSON parse + sha256 AND

    戻り値: "RESTORED" / "FALLBACK_CHMOD400"
    ※ chmod 000 は使わない（CC本体DoS回避）→ chmod 400
    """
    backup_size = os.path.getsize(backup_path)
    backup_hash = _sha256(backup_path)
    backup_valid = _is_valid_json(backup_path)

    if not backup_valid:
        # バックアップが壊れている→復元不能→読取専用化で被害拡大防止
        os.chmod(target_path, 0o400)
        return "FALLBACK_CHMOD400"

    try:
        shutil.copy2(backup_path, target_path)  # cp -p 相当
    except Exception:
        os.chmod(target_path, 0o400)
        return "FALLBACK_CHMOD400"

    # 検証: サイズ + JSON parse + sha256
    if os.path.getsize(target_path) != backup_size:
        os.chmod(target_path, 0o400)
        return "FALLBACK_CHMOD400"
    if not _is_valid_json(target_path):
        os.chmod(target_path, 0o400)
        return "FALLBACK_CHMOD400"
    if _sha256(target_path) != backup_hash:
        os.chmod(target_path, 0o400)
        return "FALLBACK_CHMOD400"

    return "RESTORED"


def is_bypass_active(bypass_dir: str, ttl_seconds: int = 300) -> bool:
    """TTL付き bypass: ~/.claude/guard-bypass-<ts> が存在し期限内か

    期限切れファイルは削除（自動復帰）。bypass ファイルは空運用（TOKEN絶対書かない）。
    ※有効期限は**ファイル名埋め込みts**基準（mtime でなく）→ touch での期限延長攻撃無効
    ※bypass ファイルは作成時に chmod 0444 運用（書換防止・本関数は判定のみ）
    """
    now = int(time.time())
    active = False
    for path in glob.glob(os.path.join(bypass_dir, "guard-bypass-*")):
        try:
            ts = int(os.path.basename(path).rsplit("-", 1)[1])
        except (ValueError, IndexError):
            continue
        if now - ts <= ttl_seconds:
            active = True
            try:
                os.chmod(path, 0o444)  # 念のため読取専用化（内容書換防止）
            except OSError:
                pass
        else:
            try:
                os.remove(path)  # 期限切れは自動削除（ファイル名ts基準・mtime無関係）
            except OSError:
                pass
    return active


def write_log(log_path: str, event: str, detail: str, suspect_value: str = "") -> None:
    """JSON Lines ログ。TOKEN原値は絶対書かない・[REDACTED:hk:<sha256-prefix>] ハッシュ化

    100MB×10世代 gzip ローテーションは運用 logrotate に委譲（本関数は追記のみ）。
    ※spec 0444 乖離(2026-07-31 MiniMax M4採用): 追記型ログで 0444 にすると2回目以降書けない
      → 0600(所有者のみrw) で運用・spec意図(hook外改ざん防止・原値非混入)は 0600 で達成。
    """
    redacted = ""
    if suspect_value:
        h = hashlib.sha256(suspect_value.encode()).hexdigest()
        redacted = f"[REDACTED:hk:{h[:12]}]"  # sha256先頭12字のみ（原値復元不可）

    entry = {
        "ts": int(time.time()),
        "event": event,
        "detail": detail,
        "suspect": redacted,  # 原値は絶対入れない
    }
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    try:
        os.chmod(log_path, 0o600)  # 所有者のみrw・spec 0444→0600 乖離(上記docstring参照)
    except OSError:
        pass


# Pre: ネットワーク送信検知
NET_SEND_RE = re.compile(
    r"(curl|wget|nc\s+-|base64\s*\|.*(?:curl|wget)|https?://[a-z0-9.-]+\.[a-z]{2,})",
    re.IGNORECASE,
)
# settings.json を指す言及
SETTINGS_REF_RE = re.compile(r"settings\.json|settings\.local\.json", re.IGNORECASE)


def pre_detect_exfil_chain(cmd: str) -> bool:
    """Pre: 同一チェイン内に「settings.json 言及」+「ネットワーク送信」が両方存在でブロック

    spec L162準拠: settings.json 触る(読取/書込問わず) + 送信 = ブロック(安全側)。
    読取-only(jq/cat 単体)は送信なければ通す。
    ベストエフォート(動的生成・変数展開は完全網羅不可・spec既知限界)。
    ※plan の has_write(WRITE_OP_RE)実装は spec L162「jq...&&curl=ブロック」と矛盾のため廃止。
    """
    if not cmd:
        return False
    has_settings_ref = bool(SETTINGS_REF_RE.search(cmd))
    has_send = bool(NET_SEND_RE.search(cmd))
    return has_settings_ref and has_send
