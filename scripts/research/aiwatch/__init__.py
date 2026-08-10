"""aiwatch — GitHub Trending AIリポ週次収集→環境特化評価→ガイド生成パイプライン。

5ユニット構成:
- collector: Trending取得 + gh CLI累計★
- env_profiler: SSOT→環境プロファイル
- rule_scorer: ルール★採点(フォールバック)
- evaluator: MiniMax API評価(Phase2)
- lifecycle: 状態機械(pending/archived/declined/evaluated)
- guide_generator: source MD→convert.py→HTML
- cost: コスト記録 + 週$20キャップ
- safety: gh認証/HTML sanity
"""
