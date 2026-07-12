"""backtest/walkforward_evaluation.py (v9研究開発ブランチ Walk Forward Evaluation Pipeline)
====================================================================
walkforward_decision.py が生成したValidation期間ごとのDecision結果へ、
既存の decision_validation.build_decision_validation_summary() と
decision_report.build_decision_report() を適用し、期間ごとの評価・
レポートを自動生成する橋渡しモジュール。

責務:
    walkforward_decision.run_walkforward_decision_validation() の戻り値
    を入力として受け取り、各ウィンドウのdecision_recordsのみを対象に
    上記2関数（いずれも無変更）を呼び出し、その戻り値をそのまま保持
    する。本モジュール自身はDecision・Confidence・Rating・Statistics・
    Benchmarkの計算を一切行わない。

    walkforward_decision.py（Decision列の付与）・decision_validation.py・
    decision_report.pyとは責務を重複させない。walkforward_decision.py
    がどのWindowSplitterに基づいてwindowsを生成したかには依存しない
    （各windowの共通キーのみを参照する）。

    1つのValidation期間の処理で例外が発生しても、そのウィンドウのみ
    errorフィールドへ記録し、他のウィンドウの処理は継続する。

Public API:
    run_walkforward_evaluation
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Optional

import pandas as pd

from backtest.decision_validation import build_decision_validation_summary
from backtest.decision_report import build_decision_report

__all__ = [
    "WALKFORWARD_EVALUATION_SCHEMA_VERSION",
    "run_walkforward_evaluation",
]

#: このモジュールの戻り値スキーマのバージョン。消費側が互換性を判断する。
WALKFORWARD_EVALUATION_SCHEMA_VERSION = "1.0"

#: decision_pipeline.attach_decision_columns() が付与する列名。
#: decision_validation.py側のデフォルトdecision_col="decision"（小文字）
#: とは異なるため、ここで明示的に指定する。
_DECISION_COLUMN = "Decision"


def _compute_report_hash(decision_report_result: Mapping[str, Any]) -> Optional[str]:
    """Decision Report結果からSHA256ハッシュを算出する（report_history.pyと同じ方式）。

    Args:
        decision_report_result: decision_report.build_decision_report() の戻り値。

    Returns:
        SHA256ハッシュの16進数文字列。算出に失敗した場合はNone。
    """
    try:
        canonical = json.dumps(decision_report_result, sort_keys=True,
                                ensure_ascii=False, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    except (TypeError, ValueError):
        return None


def _evaluate_window(
    decision_window: Mapping[str, Any],
    run_id: Optional[str],
) -> dict[str, Any]:
    """1つのValidationウィンドウについて、Decision Validation / Decision Reportを適用する。

    Args:
        decision_window: walkforward_decision.run_walkforward_decision_validation()
            の戻り値windows配列の1要素。
        run_id: 将来History保存等で利用する予約フィールド。

    Returns:
        decision_validation_result・decision_report_result・report_hash・
        errorを持つdict。
    """
    base = {
        "validation_period_id": decision_window.get("validation_period_id"),
        "run_id": run_id,
        "report_hash": None,
        "code": decision_window.get("code"),
        "strategy_name": decision_window.get("strategy_name"),
        "window_index": decision_window.get("window_index"),
        "train_start": decision_window.get("train_start"),
        "train_end": decision_window.get("train_end"),
        "train_count": decision_window.get("train_count"),
        "validation_start": decision_window.get("validation_start"),
        "validation_end": decision_window.get("validation_end"),
        "validation_count": decision_window.get("validation_count"),
    }

    # walkforward_decision.py側で既に失敗しているウィンドウは、Decision
    # Validation/Reportの呼び出し自体を行わない（存在しないDecision列に
    # 対する集計を避け、二重にエラーを発生させないため）。
    upstream_error = decision_window.get("error")
    if upstream_error:
        return {
            **base,
            "decision_validation_result": None,
            "decision_report_result": None,
            "error": f"upstream(walkforward_decision) error: {upstream_error}",
        }

    records = decision_window.get("decision_records") or []
    if not records:
        return {
            **base,
            "decision_validation_result": None,
            "decision_report_result": None,
            "error": None,
        }

    try:
        decision_df = pd.DataFrame.from_records(records)

        decision_validation_result = build_decision_validation_summary(
            decision_df, decision_col=_DECISION_COLUMN
        )
        decision_report_result = build_decision_report(
            decision_df,
            strategy_name=decision_window.get("strategy_name"),
            code=decision_window.get("code"),
        )

        return {
            **base,
            "report_hash": _compute_report_hash(decision_report_result),
            "decision_validation_result": decision_validation_result,
            "decision_report_result": decision_report_result,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001 - 1ウィンドウの失敗で全体を止めないため意図的に捕捉する
        return {
            **base,
            "decision_validation_result": None,
            "decision_report_result": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def run_walkforward_evaluation(
    walkforward_decision_result: Mapping[str, Any],
    run_id: Optional[str] = None,
) -> dict[str, Any]:
    """walkforward_decision.py の結果へDecision Validation / Decision Reportを適用し、
    Validation期間ごとの投資判断の再現性を自動的に評価・レポート化する。

    Args:
        walkforward_decision_result: walkforward_decision.
            run_walkforward_decision_validation() の戻り値。
        run_id: 実行全体を一意に識別する予約フィールド（現時点では未指定でもよい）。

    Returns:
        walkforward_evaluation_schema_version・run_id・code・strategy_name・
        period・total_windows・windows（各windowはdecision_validation_result・
        decision_report_result・report_hash等を持つ）を持つJSON互換dict。
        1ウィンドウでエラーが発生しても、そのウィンドウのみerrorに記録し、
        他のウィンドウの処理は継続する。
    """
    windows_in = walkforward_decision_result.get("windows") or []

    windows_out = [_evaluate_window(window, run_id) for window in windows_in]

    return {
        "walkforward_evaluation_schema_version": WALKFORWARD_EVALUATION_SCHEMA_VERSION,
        "run_id": run_id,
        "code": walkforward_decision_result.get("code"),
        "strategy_name": walkforward_decision_result.get("strategy_name"),
        "period": walkforward_decision_result.get("period"),
        "total_windows": len(windows_out),
        "windows": windows_out,
    }
