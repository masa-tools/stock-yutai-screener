"""
research/evaluation/strategy_comparison.py  (Phase8: Walk Forward比較検証)
============================================================================
複数戦略を同一条件（code / period / runner_kwargs）で
walkforward_connector.run_and_evaluate() へ順次渡し、結果を
比較用リストとして集約する薄いオーケストレーション層。

【責務】
  - 複数戦略を同一条件で実行するループ制御のみ
  - 戦略単位でValueErrorを捕捉し、1戦略の失敗が他戦略の比較を
    妨げないようにする（握りつぶさず、結果に含めて返す）

【担当しないこと】
  - Walk Forwardの計算ロジック（run_and_evaluate()へ完全委譲）
  - 採用基準の判定（V9_RESEARCH_ARCHITECTURE.md §12の判定自体は
    呼び出し元 or 別モジュールの責務とする）
  - UI表示（walkforward_result_view.py側の責務）

【未確認事項（重要・要修正の可能性あり）】
  runner_result内でwin_rate・max_ddが実際にどのキーに格納されているかは
  backtest/walkforward_summary.py未確認のため特定できていない。
  本実装では runner_result["summary"]["metric_statistics"] という
  想定パスで試行的に取得する。このパスが誤っている場合、
  win_rate/max_ddはNoneとして扱われる（例外は出さない設計）。
  実際のキー構造判明後、このパスの修正が必要。
"""

from typing import Any, Callable

from evaluation.walkforward_connector import run_and_evaluate


def run_comparison(
    code: str,
    strategies: list[tuple[Callable[..., dict], str]],
    period: str = "1y",
    **runner_kwargs: Any,
) -> list[dict]:
    """
    複数戦略を同一条件で実行し、比較用の結果リストを返す。

    Args:
        code: 対象銘柄コード。
        strategies: (strategy_fn, strategy_name) のタプルのリスト。
        period: 全戦略共通のyfinance期間文字列（同一条件比較のため固定）。
        **runner_kwargs: 全戦略共通で渡すrun_walkforward_runner()の引数。
            戦略ごとに変えず、呼び出し元で固定した値を渡すこと
            （固定しないと「同一条件比較」が成立しない）。

    Returns:
        list[dict]: strategies引数の順序を保持した結果リスト。各要素は
            {"strategy_name", "research_metrics", "win_rate", "max_dd", "error"}。
    """
    results = []

    for strategy_fn, strategy_name in strategies:
        try:
            r = run_and_evaluate(
                code=code,
                strategy_fn=strategy_fn,
                strategy_name=strategy_name,
                period=period,
                **runner_kwargs,
            )
        except ValueError as e:
            results.append({
                "strategy_name": strategy_name,
                "research_metrics": None,
                "win_rate": None,
                "max_dd": None,
                "error": str(e),
            })
            continue

        # 【未確認パス】判明次第、修正が必要
        summary = r.get("runner_result", {}).get("summary", {}) or {}
        metric_stats = summary.get("metric_statistics", {}) or {}

        results.append({
            "strategy_name": strategy_name,
            "research_metrics": r.get("research_metrics"),
            "win_rate": metric_stats.get("win_rate"),
            "max_dd": metric_stats.get("max_dd"),
            "error": None,
        })

    return results
