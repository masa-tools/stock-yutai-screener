"""
walkforward_connector.py  v9 Research (Phase6-5: Research評価層とWalk Forward実行の接続)
=========================================================================================
backtest.walkforward_runner.run_walkforward_runner() を呼び出し、その戻り値を
metrics_research.calculate_metrics_from_runner_result() へそのまま渡すだけの
薄い接続層（コネクタ）。

【責務】
  - run_walkforward_runner() の呼び出し（読み取り専用の利用。backtest配下の
    実装には一切手を加えない）
  - その戻り値（runner_result）を calculate_metrics_from_runner_result() に
    渡し、Research評価指標（total_return / calmar_ratio / sortino_ratio /
    time_underwater の4指標のみ）を取得する
  - runner_result と research_metrics をまとめて呼び出し元へ返す

【担当しないこと（DESIGN.md確定事項）】
  - Walk Forwardの計算ロジック自体（backtest.walkforward_runner等へ完全委譲。
    本モジュールは呼び出すだけで、計算・判定・集計は一切行わない）
  - win_rate・max_dd・risk_reward・平均利益・平均損失の算出・比較
    （Research評価層のスコープ外。必要な場合は
    backtest.walkforward_summary.build_metric_statistics() の既存値を
    別途参照すること）
  - 例外の握りつぶし。runner_result の summary=None・window_metricsなし・
    有効Windowなし等の場合、calculate_metrics_from_runner_result() が
    送出する ValueError を本モジュールは一切catchせず、そのまま
    呼び出し元へ伝播させる
  - SQLite保存・research_storage呼び出し・UI表示（streamlit等）
  - 既存モジュール（app.py, strategy_v8, scoring_config, ConfigManager,
    settings.json, research_settings.json）への接続

【v8.1 Stableへの影響について】
  backtest.walkforward_runner は読み取り専用でimportして呼び出すのみで、
  一切変更しない。app.py・strategy_v8.py・ConfigManager・settings.json等は
  本モジュールから一切参照しない。
"""

from typing import Any, Callable

from backtest.walkforward_runner import run_walkforward_runner
from evaluation.metrics_research import calculate_metrics_from_runner_result


def run_and_evaluate(
    code: str,
    strategy_fn: Callable[..., dict],
    strategy_name: str,
    period: str = "1y",
    **runner_kwargs: Any,
) -> dict:
    """
    run_walkforward_runner() を実行し、その戻り値からResearch評価指標
    （total_return / calmar_ratio / sortino_ratio / time_underwater）を
    算出する。

    Args:
        code: 対象銘柄コード（例: "7203"）。
        strategy_fn: run_walkforward_runner() へそのまま渡すスコアリング関数。
            本関数はこの引数の中身を一切解釈しない。
        strategy_name: レポート上の戦略識別子（例: "v9_rsi"）。
        period: yfinance期間文字列（例: "1y"）。
        **runner_kwargs: run_walkforward_runner() のその他の引数
            （splitter, date_col, score_col, components_col, run_id,
            dry_run, stability_config, health_check_config, ranking_config,
            trend_config, context, extensions, ai_context,
            fundamental_context, dividend_context, market_context等）を
            そのまま透過的に渡す。本関数はこれらの意味を一切解釈しない。

    Returns:
        dict: {
            "runner_result": run_walkforward_runner() の戻り値そのもの,
            "research_metrics": calculate_metrics_from_runner_result() の
                戻り値（total_return / calmar_ratio / sortino_ratio /
                time_underwater の4指標のみ）,
        }

    Raises:
        ValueError: calculate_metrics_from_runner_result() が送出する例外
            （summary=None・window_metricsなし・有効Windowなし等）を
            そのまま送出する。本関数では一切catchしない
            （呼び出し元が握りつぶさずに扱えるようにするため）。
    """
    runner_result = run_walkforward_runner(
        code=code,
        strategy_fn=strategy_fn,
        strategy_name=strategy_name,
        period=period,
        **runner_kwargs,
    )

    # calculate_metrics_from_runner_result() が送出する例外は、ここでは
    # 一切catchしない。呼び出し元がそのまま受け取れるようにするため。
    research_metrics = calculate_metrics_from_runner_result(runner_result)

    return {
        "runner_result": runner_result,
        "research_metrics": research_metrics,
    }
