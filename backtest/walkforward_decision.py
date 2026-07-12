"""backtest/walkforward_decision.py (v9研究開発ブランチ Walk Forward Decision Validation)
====================================================================
walkforward.py が生成したValidation期間の結果へ、既存のDecision Engine
（decision_pipeline.attach_decision_columns()）を適用するだけの
橋渡しモジュール。

責務:
    walkforward.run_walkforward_validation() の戻り値（windows配列）を
    入力として受け取り、各ウィンドウのvalidation_recordsのみを対象に
    decision_pipeline.attach_decision_columns()（無変更）を適用し、
    結果をJSON互換dictへ変換して返す。Decisionの計算そのものは一切
    実装せず、すべてdecision_pipeline.py（さらにその内部でrating.py /
    statistics.py / confidence.py / decision.py）へ委譲する。

    decision.py（最終判断そのもの）・decision_report.py・
    decision_validation.pyとは責務を重複させない。本モジュールは
    「Walk Forward結果へDecision列を付与する橋渡し」に限定する。

    walkforward.pyがどのWindowSplitterを使って windows を生成したかに
    は一切依存しない（各windowの共通キーのみを参照する）。

    公開インターフェース（引数・戻り値）はJSON完全互換のdict/listのみ
    で構成する。1つのValidation期間の処理で例外が発生しても、他の
    ウィンドウの処理は継続する。

Public API:
    run_walkforward_decision_validation
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Optional

import pandas as pd

from backtest.decision_pipeline import attach_decision_columns

__all__ = [
    "WALKFORWARD_DECISION_SCHEMA_VERSION",
    "run_walkforward_decision_validation",
]

#: このモジュールの戻り値スキーマのバージョン。消費側が互換性を判断する。
WALKFORWARD_DECISION_SCHEMA_VERSION = "1.0"


def _to_json_safe(value: Any) -> Any:
    """pandas/numpyの値をJSON互換のプリミティブ型へ変換する（日時はISO8601、NaNはNone）。"""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(v) for v in value]
    try:
        if isinstance(value, float) and math.isnan(value):
            return None
    except TypeError:
        pass
    if isinstance(value, (int, float, str, bool)):
        return value
    try:
        f = float(value)
        if math.isnan(f):
            return None
        if f.is_integer() and not isinstance(value, float):
            return int(f)
        return f
    except (TypeError, ValueError):
        return str(value)


def _row_to_record(row: pd.Series) -> dict[str, Any]:
    """DataFrameの1行をJSON互換dictへ変換する。"""
    return {col: _to_json_safe(row[col]) for col in row.index}


def _apply_decision_to_window(
    window: Mapping[str, Any],
    run_id: Optional[str],
    score_col: str,
    components_col: str,
) -> dict[str, Any]:
    """1つのValidationウィンドウについて、Decision Engineを適用する。

    Args:
        window: walkforward.run_walkforward_validation() の戻り値
            windows配列の1要素。
        run_id: 将来SQLite保存等で利用する予約フィールド。
        score_col: attach_decision_columns() へ渡すスコア列名。
        components_col: attach_decision_columns() へ渡すcomponents列名。

    Returns:
        train/validation境界情報・decision_count・decision_records・
        errorを持つdict。
    """
    base = {
        "validation_period_id": window.get("validation_period_id"),
        "run_id": run_id,
        "code": window.get("code"),
        "strategy_name": window.get("strategy_name"),
        "window_index": window.get("window_index"),
        "train_start": window.get("train_start"),
        "train_end": window.get("train_end"),
        "train_count": window.get("train_count"),
        "validation_start": window.get("validation_start"),
        "validation_end": window.get("validation_end"),
        "validation_count": window.get("validation_count"),
    }

    records = window.get("validation_records") or []
    if not records:
        return {**base, "decision_count": 0, "decision_records": [], "error": None}

    try:
        validation_df = pd.DataFrame.from_records(records)
        decision_df = attach_decision_columns(
            validation_df,
            strategy_name=window.get("strategy_name"),
            score_col=score_col,
            components_col=components_col,
        )
        decision_records = [_row_to_record(row) for _, row in decision_df.iterrows()]
        return {
            **base,
            "decision_count": len(decision_records),
            "decision_records": decision_records,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001 - 1ウィンドウの失敗で全体を止めないため意図的に捕捉する
        return {
            **base,
            "decision_count": 0,
            "decision_records": [],
            "error": f"{type(exc).__name__}: {exc}",
        }


def run_walkforward_decision_validation(
    walkforward_result: Mapping[str, Any],
    run_id: Optional[str] = None,
    score_col: str = "total",
    components_col: str = "components",
) -> dict[str, Any]:
    """walkforward.py の結果へDecision Engineを適用し、期間ごとの投資判断の
    再現性を検証するためのデータ基盤を構築する。

    Args:
        walkforward_result: walkforward.run_walkforward_validation() の戻り値。
        run_id: 実行全体を一意に識別する予約フィールド（現時点では未指定でもよい）。
        score_col: attach_decision_columns() へ渡すスコア列名。
        components_col: attach_decision_columns() へ渡すcomponents列名。

    Returns:
        walkforward_decision_schema_version・run_id・code・strategy_name・
        period・total_windows・windows（各windowはdecision_records等を持つ）
        を持つJSON互換dict。1ウィンドウでエラーが発生しても、そのウィンドウ
        のみerrorに記録し、他のウィンドウの処理は継続する。
    """
    windows_in = walkforward_result.get("windows") or []

    windows_out = [
        _apply_decision_to_window(window, run_id, score_col, components_col)
        for window in windows_in
    ]

    return {
        "walkforward_decision_schema_version": WALKFORWARD_DECISION_SCHEMA_VERSION,
        "run_id": run_id,
        "code": walkforward_result.get("code"),
        "strategy_name": walkforward_result.get("strategy_name"),
        "period": walkforward_result.get("period"),
        "total_windows": len(windows_out),
        "windows": windows_out,
    }
