#!/usr/bin/env python3
"""settings.json のシークレットをマスクして出力

⚠️ マスクは値を一切残さない（2026-08-22 修正）。
以前は `v[:4]`（キー名一致）/ `v[:6]`（パターン一致）で**先頭数文字を残して**おり、
その結果 claude-config/settings.example.json に 5 箇所の先頭4文字が git 追跡され
GitHub へ push されていた（2026-08-14 に決めた方針「生値の git 混入経路遮断」に反する）。
キーの種類が特定できる情報を残す利点より、方針違反のコストが上回るため完全マスクにした。
"""
import json, sys, re

src = sys.argv[1]
dst = sys.argv[2]

with open(src) as f:
    data = json.load(f)

# キー名で判定するシークレット（env系）
SECRET_KEYS = {
    'ANTHROPIC_AUTH_TOKEN',
    'BRAVE_API_KEY',
    'MINIMAX_API_KEY',
    'GLM_API_KEY',
    'GITHUB_PERSONAL_ACCESS_TOKEN',
    'DISCORD_TOKEN',
}

# 値のパターンで判定するシークレット（permissions.allow等に埋め込まれたtoken）
SECRET_PATTERNS = [
    re.compile(r'MTI[a-zA-Z0-9]{20,}'),            # Discord Bot Token
    re.compile(r'ghp_[a-zA-Z0-9]{30,}'),            # GitHub PAT
    re.compile(r'github_pat_[a-zA-Z0-9_]{30,}'),    # GitHub fine-grained PAT
    re.compile(r'sk-[a-zA-Z0-9]{30,}'),             # OpenAI/API key style
    re.compile(r'BSAW[a-zA-Z0-9]{20,}'),            # Brave API key
    re.compile(r'97c1[a-zA-Z0-9]{20,}'),            # ZAI/GLM API key
    re.compile(r'TOKEN=\s*\S{20,}'),                # TOKEN=... pattern
]


MASK = '***MASKED***'


def mask_value(v):
    """値がシークレットパターンにマッチしたらマスク"""
    if not isinstance(v, str) or len(v) < 15:
        return v
    for pat in SECRET_PATTERNS:
        if pat.search(v):
            return MASK
    return v


def mask_secrets(obj):
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if k in SECRET_KEYS and isinstance(v, str) and len(v) > 4:
                result[k] = MASK
            else:
                result[k] = mask_secrets(v)
        return result
    elif isinstance(obj, list):
        return [mask_secrets(mask_value(item) if isinstance(item, str) else item) for item in obj]
    elif isinstance(obj, str):
        return mask_value(obj)
    return obj


data = mask_secrets(data)

with open(dst, 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')
