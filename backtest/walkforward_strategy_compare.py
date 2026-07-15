"""backtest/walkforward_strategy_compare.py (Walk Forward 戦略評価ツール Phase2)
====================================================================
複数の戦略について walkforward_runner.run_walkforward_runner() を
繰り返し呼び出し、結果を束ねるだけの薄いラッパー。

責務:
    「Runnerを複数回呼ぶだけ」。新しい評価・判定ロジックは一切実装しない。
    1つの戦略の実行が失敗しても、他の戦略の実行には影響を与えない
    （戦略ごとに独立してtry/exceptする）。

    walkforward_runner.py（計算・Stage実行の実体）には一切変更を加えない。
    本モジュールはRunnerのさらに外側に立つ、もう一段上のオーケストレーション
    層であり、walkforward_pipeline.pyが3関数を直列実行するのと同じ
    「配線のみ」というパターンを、Runner単位で踏襲している。
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from backtest.walkforward_runner import run_walkforward_runner

__all__ = [
    "STRATEGY_COMPARE_SCHEMA_VERSION",
    "run_walkforward_strategy_compare",
]

#: このモジュールの戻り値スキーマのバージョン。
STRATEGY_COMPARE_SCHEMA_VERSION = "1.0"


def run_walkforward_strategy_compare(
    code: str,
    strategies: Mapping[str, Callable[..., Mapping[str, Any]]],
    period: str = "1y",
    **runner_kwargs: Any,
) -> dict[str, Any]:
    """複数戦略について run_walkforward_runner() を順に呼び出し、結果を束ねる。

    Args:
        code: 対象銘柄コード。
        strategies: {戦略名: strategy_fn} のマッピング
            （例: {"v8": compute_score_at_v8, "v9": compute_score_at_v9}）。
        period: 全戦略共通で使うyfinance期間文字列。
        **runner_kwargs: run_walkforward_runner() へそのまま渡す追加引数
            （splitter/date_col/score_col/components_col/run_id/dry_run等）。
            strategy_name は各戦略名から自動的に設定されるため指定不要。

    Returns:
        {
            "strategy_compare_schema_version": "1.0",
            "code": code,
            "period": period,
            "strategies": {戦略名: run_walkforward_runner()の戻り値, ...},
            "errors": [{"strategy": 戦略名, "message": str}, ...],
        }
        1つの戦略の実行が失敗しても他の戦略の実行は継続する。失敗した
        戦略は"strategies"に含まれず、"errors"に記録される。
    """
    results: dict[str, Any] = {}
    errors: list[dict[str, str]] = []

    for strategy_name, strategy_fn in strategies.items():
        try:
            results[strategy_name] = run_walkforward_runner(
                code=code,
                strategy_fn=strategy_fn,
                strategy_name=strategy_name,
                period=period,
                **runner_kwargs,
            )
        except Exception as exc:  # noqa: BLE001 - 1戦略の失敗で他戦略を止めないため意図的に捕捉する
            errors.append({"strategy": strategy_name, "message": f"{type(exc).__name__}: {exc}"})

    return {
        "strategy_compare_schema_version": STRATEGY_COMPARE_SCHEMA_VERSION,
        "code": code,
        "period": period,
        "strategies": results,
        "errors": errors,
    }
