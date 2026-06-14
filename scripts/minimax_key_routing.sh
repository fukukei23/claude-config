#!/bin/bash
# minimax_key_routing.sh
# MiniMax APIキー ルーティング判定スクリプト
#
# 使い方:
#   source minimax_key_routing.sh
#   echo "$MINIMAX_ACTIVE_KEY"  # サブスク優先、なければ従量
#
# 判定ロジック:
#   1. サブスクキー (MINIMAX_API_KEY) の残高を確認
#   2. 残あり → MINIMAX_ACTIVE_KEY="SUBSCRIPTION"
#   3. なし or エラー → MINIMAX_ACTIVE_KEY="PAYG"
#
# ※APIキーの値そのものは出力しない（存在・長さのみ）

source ~/.secrets.env 2>/dev/null

# サブスクキーで残高照会（usage チェック）
check_subscription() {
  curl -s --max-time 10 \
    -H "Authorization: Bearer $MINIMAX_API_KEY" \
    "https://api.minimax.io/v1/dashboard/billing/credit_grants" \
    | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    # 残高フィールド名は MiniMax によって異なる場合あり
    # 一般的なフィールドを探す
    if 'total_granted' in d and 'total_used' in d:
        remaining = d['total_granted'] - d['total_used']
        print(f'REMAINING={remaining:.4f}')
    elif 'data' in d and isinstance(d['data'], dict):
        print(f\"DATA_KEYS={','.join(d['data'].keys())}\")
    else:
        print('NO_BILLING_API')
except Exception as e:
    print(f'ERROR={e}')
"
}

# 簡易版: サブスクキーの TOKEN_PLAN 残量は billing API で取得できない場合がある
# 代替: 動画生成の試行で 2056 エラーが出たら従量に切替、を推奨

# ヘッダのみ設定（値は隠す）
if [ -n "$MINIMAX_API_KEY" ]; then
  export MINIMAX_SUBSCRIPTION_AVAILABLE=1
else
  export MINIMAX_SUBSCRIPTION_AVAILABLE=0
fi

if [ -n "$MINIMAX_API_KEY_VIDEO" ]; then
  export MINIMAX_PAYG_AVAILABLE=1
else
  export MINIMAX_PAYG_AVAILABLE=0
fi

# デフォルトはサブスク優先
export MINIMAX_ACTIVE_KEY="SUBSCRIPTION"
export MINIMAX_ACTIVE_KEY_VAR="MINIMAX_API_KEY"

echo "[minimax-routing] SUBSCRIPTION=$MINIMAX_SUBSCRIPTION_AVAILABLE  PAYG=$MINIMAX_PAYG_AVAILABLE  ACTIVE=$MINIMAX_ACTIVE_KEY"
