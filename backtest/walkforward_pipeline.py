"""backtest/walkforward_pipeline.py (v9研究開発ブランチ Walk Forward Pipeline)
====================================================================
walkforward.py → walkforward_decision.py → walkforward_evaluation.py を
順番に呼び出すだけの統合オーケストレーター。

責務:
    「Walk Forward → Decision → Validation → Report」をワンコールで
    実行できるようにするための配線のみを担う。本モジュール自身は
    Decision・Confidence・Rating・Statistics・Benchmark・Validation・
    Reportの計算を一切行わない。walkforward.py（期間分割＋バックテスト
    実行）・walkforward_decision.py（Decision列の付与）・
    walkforward_evaluation.py（Decision Validation／Decision Reportの
    適用）とは責務を重複させず、それらの「呼び出し順序の固定化」に
    のみ責任を持つ。splitter引数はwalkforward.pyへ透過的に渡すのみ
    で、Window方式には依存しない。

    トップレベルの errors / warnings は、各段階の呼び出し自体が例外を
    送出した場合（＝パイプライン全体を継続できない致命的な失敗）のみを
    記録する。個々のValidationウィンドウ単位のエラーは、
    walkforward_decision.py・walkforward_evaluation.pyが既に
    windows[].error として保持しているため、本モジュールで重複して
    集計・再記録はしない。

    JSON構造の詳細は backtest.types（WalkForwardPipelineResult・
    StageErrorEntry等）を参照。"windows"キーは正常時は
    WalkForwardEvaluationResult相当、途中失敗時は{"windows": [...]}
    という縮退構造になるため、単一の厳密な型ではなくMapping[str, Any]
    として扱っている（backtest.types内のコメント参照）。

Public API:
    run_walkforward_pipeline
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Mapping, Optional

from backtest.walkforward import run_walkforward_validation, WindowSplitter, StrategyFn
from backtest.walkforward_decision import run_walkforward_decision_validation
from backtest.walkforward_evaluation import run_walkforward_evaluation
from backtest.types import StageErrorEntry, WalkForwardPipelineResult

__all__ = [
    "WALKFORWARD_PIPELINE_VERSION",
    "run_walkforward_pipeline",
]

#: このパイプライン全体の戻り値スキーマのバージョン。
WALKFORWARD_PIPELINE_VERSION = "1.0"

#: 他モジュール（walkforward_schema_version等）との命名規則統一のために追加した
#: エイリアスキー名。WALKFORWARD_PIPELINE_VERSIONと常に同じ値を持つ。
#: 【重要】既存の"pipeline_version"キーは後方互換のため削除・変更しない。
#: 新規の消費者はこちらのキー名を参照することを推奨する。
PIPELINE_SCHEMA_VERSION_KEY = "pipeline_schema_version"

#: パイプラインの各ステージを識別する名称
#: （errors/warnings の "stage" フィールドで使用する）。
_STAGE_WALKFORWARD = "walkforward"
_STAGE_WALKFORWARD_DECISION = "walkforward_decision"
_STAGE_WALKFORWARD_EVALUATION = "walkforward_evaluation"


def run_walkforward_pipeline(
    code: str,
    strategy_fn: StrategyFn,
    strategy_name: str,
    period: str = "1y",
    splitter: Optional[WindowSplitter] = None,
    date_col: str = "date",
    score_col: str = "total",
    components_col: str = "components",
    run_id: Optional[str] = None,
    extensions: Optional[Mapping[str, object]] = None,
) -> WalkForwardPipelineResult:
    """Walk Forward検証パイプライン全体（Validation生成→Decision付与→
    Decision Validation/Report適用）をワンコールで実行する統合エントリ
    ポイント。

    以下の既存関数を、各段階の戻り値をそのまま次の段階の入力として
    渡す形で順に呼び出すだけであり、本関数自身は計算・判定・集計
    ロジックを一切実装しない。
        1. walkforward.run_walkforward_validation()
        2. walkforward_decision.run_walkforward_decision_validation()
        3. walkforward_evaluation.run_walkforward_evaluation()

    Args:
        code: 対象銘柄コード（例: "7203"）。
        strategy_fn: backtest_runner.run_backtest() へ最終的に渡される
            スコアリング関数。
        strategy_name: レポート上の戦略識別子（例: "v9"）。
        period: yfinance期間文字列（例: "1y"）。
        splitter: 期間分割方式。中身は解釈せずwalkforward.pyへ
            そのまま渡す（Window方式に依存しない）。
        date_col: res_dfの判定日列名。
        score_col: スコア列名。
        components_col: components列名。
        run_id: この実行全体を一意に識別する予約フィールド。省略時は
            UUID4を新規生成する。
        extensions: 将来のFundamental分析・配当分析・AIコメント等の
            追加ステップを見据えた予約引数。現時点では解釈・実行を
            行わず、指定された場合のみ戻り値の"extensions"キーへ
            そのまま格納する。

    Returns:
        WalkForwardPipelineResult（backtest.types参照）。いずれかの
        段階で例外が発生した場合、その段階以降の呼び出しは行わず、
        "errors" にエラー内容を記録する。個々のValidationウィンドウ
        単位のエラーは"windows"配下にそのまま残る。
    """
    resolved_run_id = run_id if run_id is not None else str(uuid.uuid4())
    generated_at = datetime.now(timezone.utc).isoformat()

    errors: list[StageErrorEntry] = []
    warnings: list[StageErrorEntry] = []

    try:
        walkforward_result = run_walkforward_validation(
            code=code,
            strategy_fn=strategy_fn,
            strategy_name=strategy_name,
            period=period,
            splitter=splitter,
            date_col=date_col,
        )
    except Exception as exc:  # noqa: BLE001 - 致命的失敗をerrorsへ記録し、後続を止めるため意図的に捕捉する
        errors.append({"stage": _STAGE_WALKFORWARD, "message": f"{type(exc).__name__}: {exc}"})
        return _build_result(resolved_run_id, strategy_name, code, period, generated_at,
                              windows={"windows": []}, errors=errors, warnings=warnings,
                              extensions=extensions)

    if not walkforward_result.get("windows"):
        warnings.append({
            "stage": _STAGE_WALKFORWARD,
            "message": "Validationウィンドウが1つも生成されませんでした"
                       "（対象期間が短すぎる、またはsplitterの設定を確認してください）。",
        })

    try:
        walkforward_decision_result = run_walkforward_decision_validation(
            walkforward_result=walkforward_result,
            run_id=resolved_run_id,
            score_col=score_col,
            components_col=components_col,
        )
    except Exception as exc:  # noqa: BLE001
        errors.append({"stage": _STAGE_WALKFORWARD_DECISION, "message": f"{type(exc).__name__}: {exc}"})
        return _build_result(resolved_run_id, strategy_name, code, period, generated_at,
                              windows={"windows": walkforward_result.get("windows", [])},
                              errors=errors, warnings=warnings, extensions=extensions)

    try:
        walkforward_evaluation_result = run_walkforward_evaluation(
            walkforward_decision_result=walkforward_decision_result,
            run_id=resolved_run_id,
        )
    except Exception as exc:  # noqa: BLE001
        errors.append({"stage": _STAGE_WALKFORWARD_EVALUATION, "message": f"{type(exc).__name__}: {exc}"})
        return _build_result(resolved_run_id, strategy_name, code, period, generated_at,
                              windows={"windows": walkforward_decision_result.get("windows", [])},
                              errors=errors, warnings=warnings, extensions=extensions)

    return _build_result(resolved_run_id, strategy_name, code, period, generated_at,
                          windows=walkforward_evaluation_result, errors=errors,
                          warnings=warnings, extensions=extensions)


def _build_result(
    run_id: str,
    strategy_name: str,
    code: str,
    period: str,
    generated_at: str,
    windows: Mapping[str, object],
    errors: list[StageErrorEntry],
    warnings: list[StageErrorEntry],
    extensions: Optional[Mapping[str, object]],
) -> WalkForwardPipelineResult:
    """パイプライン全体の戻り値dictを組み立てる共通ヘルパー。"""
    result: WalkForwardPipelineResult = {
        "pipeline_version": WALKFORWARD_PIPELINE_VERSION,
        "pipeline_schema_version": WALKFORWARD_PIPELINE_VERSION,
        "run_id": run_id,
        "strategy": strategy_name,
        "code": code,
        "period": period,
        "generated_at": generated_at,
        "windows": windows,
        "errors": errors,
        "warnings": warnings,
    }
    if extensions is not None:
        result["extensions"] = extensions
    return result
