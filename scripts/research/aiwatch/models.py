"""aiwatch データモデル(dataclass)。"""
from dataclasses import dataclass
from enum import Enum


class LifecycleState(Enum):
    """ライフサイクル状態。"""

    PENDING = "pending"
    ARCHIVED = "archived"
    DECLINED = "declined"
    EVALUATED = "evaluated"


@dataclass
class RepoStats:
    """Trending収集+gh CLI★取得済みのリポジトリ統計。"""

    name: str  # owner/repo
    url: str
    description: str
    stars_today: int
    stars_total: int  # -1 = N/A(gh失敗)
    growth_rate: float  # stars_today / stars_total(0.0=計算不能)
    tag: str  # 初見/2週連続/定着


@dataclass
class EvaluatedRepo:
    """評価済みリポジトリ(ルール★ or LLM評価)。"""

    repo: RepoStats
    fit_star: int  # 1-5 環境適合度
    eval_text: str  # おすすめ文
    eval_method: str  # "llm"|"rule_fallback"|"human"


@dataclass
class EnvProfile:
    """ユーザのCC環境プロファイル(LLM評価プロンプトに埋込む)。"""

    mcp_active: list  # 稼働中MCPサーバー名
    mcp_disabled: list  # 無効化履歴MCP
    projects: list  # アクティブプロジェクト名
    skill_categories: list  # スキルカテゴリ
    past_decisions: list  # 過去判断サマリ(コスト/MCP削減等)
    fetched_at: str  # YYYY-MM-DD
