#!/usr/bin/env python3
"""settings.json のシークレットをマスクして出力"""
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


def mask_value(v):
    """値がシークレットパターンにマッチしたらマスク"""
    if not isinstance(v, str) or len(v) < 15:
        return v
    for pat in SECRET_PATTERNS:
        if pat.search(v):
            return v[:6] + '***MASKED***'
    return v


def mask_secrets(obj):
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if k in SECRET_KEYS and isinstance(v, str) and len(v) > 4:
                result[k] = v[:4] + '***MASKED***'
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
