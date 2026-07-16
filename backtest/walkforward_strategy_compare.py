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

【戻り値構造について（RC監査 H-1対応）】
    run_id / status / warnings をトップレベルへ追加し、Walk Forward
    ファミリー（Runner/Pipeline/Benchmark/Summary/Context）と同じ
    構造上の一貫性を持たせている。
      - run_id: この比較実行全体を識別するID。Runnerと同じ生成方式
        （未指定時は uuid.uuid4()）。各戦略のRunner呼び出しへも
        同じrun_idを伝播させ、「1回のStrategy Compare実行」に属する
        すべてのRunnerResultが同一run_idで紐付くようにしている
        （Runner内部でPipeline/Benchmark/Summary/Contextが同一run_idを
        共有するのと同じ思想）。
      - status: SUCCESS / PARTIAL_SUCCESS / FAILED というRunnerと同じ
        3値のみを用いる。新しい状態は追加しない。判定基準は
        「戦略の実行結果という既存の値の集約」であり、新しい財務・
        投資判断ロジックではない（Runner自身がStage状態を集約して
        自らのstatusを決めるのと同じ性質の配線ロジック）。
      - warnings: 現時点では常に空リストだが、将来Runner側と同様に
        警告を追加できるよう構造上の受け皿として保持する。
"""

from __future__ import annotations

import uuid
from typing import Any, Callable, Mapping, Optional

from backtest.walkforward_runner import run_walkforward_runner

__all__ = [
    "STRATEGY_COMPARE_SCHEMA_VERSION",
    "run_walkforward_strategy_compare",
]

#: このモジュールの戻り値スキーマのバージョン。
STRATEGY_COMPARE_SCHEMA_VERSION = "1.0"


def _determine_compare_status(results: Mapping[str, Any], errors: list[dict[str, str]]) -> str:
    """
    複数戦略の実行結果から、比較全体としてのstatusを集約する。

    新しい評価ロジックではなく、各戦略のRunnerResultが既に持っている
    "status"値（Runner自身が算出済み）と、本モジュールが記録した
    実行失敗（errors）という既存情報の単純な集約のみを行う。

    Args:
        results: 実行に成功した戦略のRunnerResultのマッピング
            （{戦略名: RunnerResult}）。
        errors: 実行に失敗した戦略のエラー記録のリスト。

    Returns:
        "SUCCESS" | "PARTIAL_SUCCESS" | "FAILED"
        （Runnerと同じ3値のみ。新しい状態は導入しない）
    """
    if not results:
        return "FAILED"
    if errors:
        return "PARTIAL_SUCCESS"
    if all(r.get("status") == "SUCCESS" for r in results.values()):
        return "SUCCESS"
    return "PARTIAL_SUCCESS"


def run_walkforward_strategy_compare(
    code: str,
    strategies: Mapping[str, Callable[..., Mapping[str, Any]]],
    period: str = "1y",
    run_id: Optional[str] = None,
    **runner_kwargs: Any,
) -> dict[str, Any]:
    """複数戦略について run_walkforward_runner() を順に呼び出し、結果を束ねる。

    Args:
        code: 対象銘柄コード。
        strategies: {戦略名: strategy_fn} のマッピング
            （例: {"v8": compute_score_at_v8, "v9": compute_score_at_v9}）。
        period: 全戦略共通で使うyfinance期間文字列。
        run_id: この比較実行全体を一意に識別する予約フィールド。
            省略時はUUID4を新規生成する（Runnerと同じ方式）。
            解決されたrun_idは、各戦略のrun_walkforward_runner()呼び出しへ
            同じ値として伝播される。
        **runner_kwargs: run_walkforward_runner() へそのまま渡す追加引数
            （splitter/date_col/score_col/components_col/dry_run/context/
            extensions等）。strategy_name/run_idは自動設定されるため
            指定不要（run_idを渡したい場合は本関数の明示引数を使うこと）。

    Returns:
        {
            "strategy_compare_schema_version": "1.0",
            "run_id": "...",
            "status": "SUCCESS" | "PARTIAL_SUCCESS" | "FAILED",
            "warnings": [],
            "errors": [{"strategy": 戦略名, "message": str}, ...],
            "code": code,
            "period": period,
            "strategies": {戦略名: run_walkforward_runner()の戻り値, ...},
        }
        1つの戦略の実行が失敗しても他の戦略の実行は継続する。失敗した
        戦略は"strategies"に含まれず、"errors"に記録される。
    """
    resolved_run_id = run_id if run_id is not None else str(uuid.uuid4())

    results: dict[str, Any] = {}
    errors: list[dict[str, str]] = []

    for strategy_name, strategy_fn in strategies.items():
        try:
            results[strategy_name] = run_walkforward_runner(
                code=code,
                strategy_fn=strategy_fn,
                strategy_name=strategy_name,
                period=period,
                run_id=resolved_run_id,
                **runner_kwargs,
            )
        except Exception as exc:  # noqa: BLE001 - 1戦略の失敗で他戦略を止めないため意図的に捕捉する
            errors.append({"strategy": strategy_name, "message": f"{type(exc).__name__}: {exc}"})

    return {
        "strategy_compare_schema_version": STRATEGY_COMPARE_SCHEMA_VERSION,
        "run_id": resolved_run_id,
        "status": _determine_compare_status(results, errors),
        "warnings": [],
        "errors": errors,
        "code": code,
        "period": period,
        "strategies": results,
    }
