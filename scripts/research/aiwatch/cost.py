"""cost — コスト記録 + 週$20キャップ判定。

MiniMax dev API料金: $0.30/M入力tok・$1.20/M出力tok。
正常運用は$0.02/週程度・$20キャップは暴走(API key漏洩/無限ループ)保険。
"""
import json
from pathlib import Path

COST_FILE = Path("/home/yn4416/projects/obsidian-ssot/00_SYSTEM/stats/aiwatch-cost.json")
WEEKLY_CAP_USD = 20.0
INPUT_RATE = 0.30 / 1_000_000  # $/tok
OUTPUT_RATE = 1.20 / 1_000_000  # $/tok


def estimate_usd(tokens_in: int, tokens_out: int) -> float:
    """トークン数からコスト推定(USD)。"""
    return round(tokens_in * INPUT_RATE + tokens_out * OUTPUT_RATE, 6)


def weekly_cap_exceeded(week_usd: float, cap: float = WEEKLY_CAP_USD) -> bool:
    """週コストがキャップ超過か(暴走検知)。"""
    return week_usd > cap


def record_usage(
    tokens_in: int,
    tokens_out: int,
    count: int,
    eval_methods: dict,
    cost_file: Path = COST_FILE,
    week_label: str = "",
) -> dict:
    """使用量をcost.jsonに追記。戻り値: 当週コストdict。"""
    usd = estimate_usd(tokens_in, tokens_out)
    record = {
        "week": week_label,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "usd": usd,
        "count": count,
        "eval_methods": eval_methods,
        "cap_usd": WEEKLY_CAP_USD,
        "cap_pct": round((usd / WEEKLY_CAP_USD) * 100, 4),
        "cap_exceeded": weekly_cap_exceeded(usd),
    }
    try:
        cost_file.parent.mkdir(parents=True, exist_ok=True)
        history: list = []
        if cost_file.exists():
            history = json.loads(cost_file.read_text(encoding="utf-8"))
            if not isinstance(history, list):
                history = []
        history.append(record)
        cost_file.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return record
