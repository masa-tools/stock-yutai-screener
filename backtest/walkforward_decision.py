"""backtest/walkforward_decision.py (v9研究開発ブランチ Walk Forward Decision Validation)
====================================================================
walkforward.py（Walk Forward Validation基盤）が生成したValidation期間の
結果へ、既存のDecision Engine（decision_pipeline.attach_decision_columns()）
を適用するだけの橋渡しモジュール。

責務:
    walkforward.run_walkforward_validation() の戻り値（windows配列。
    各ウィンドウはtrain/validationの境界情報とvalidation_records
    （JSON互換dictのリスト）を持つ）を入力として受け取り、各ウィンドウの
    validation_recordsのみを対象に decision_pipeline.attach_decision_columns()
    （無変更）を適用し、結果をJSON互換dictへ変換して返す。

    Decisionの計算そのもの（Score→Grade→Statistics→Confidence→Decision
    の判定ロジック）は一切実装せず、すべて decision_pipeline.py
    （さらにその内部で rating.py / statistics.py / confidence.py /
    decision.py）へ委譲する。本モジュールが新規に行うのは
        - JSON dict群 → pandas.DataFrame への一時的な復元
        - attach_decision_columns() の呼び出し
        - 結果 pandas.DataFrame → JSON互換dict への変換
        - train/validation境界情報・メタ情報の受け渡し
    のみである。

    decision.py（最終判断そのもの）・decision_report.py
    （Decisionラベルごとの集計）・decision_validation.py
    （既存の集計専用モジュール）とは責務を重複させない。
    本モジュールは「Walk Forward結果へDecision列を付与する橋渡し」に
    限定し、集計・レポート化は行わない
    （それらはvalidation_dashboard.py・decision_report.py・
    benchmark.py・report_history.py側の責務として残す）。

    walkforward.py がどのWindowSplitter（FixedWindowSplitter・
    将来のRollingWindowSplitter・ExpandingWindowSplitter等）を
    使って windows を生成したかには一切依存しない。本モジュールが
    参照するのは各windowの
    "validation_period_id" / "code" / "strategy_name" / "window_index" /
    "train_start" / "train_end" / "train_count" /
    "validation_start" / "validation_end" / "validation_count" /
    "validation_records" という共通キーのみであるため、将来
    walkforward.py側の分割方式が変わっても本モジュールは無修正で
    利用できる。

    公開インターフェース（引数・戻り値）はJSON完全互換のdict/listのみ
    （pandas.DataFrame・numpy型・pandas.Timestampは含まない）で構成する。
    内部処理では decision_pipeline.attach_decision_columns() が
    pandas.DataFrameを要求するためpandasを一時的に利用するが、これは
    既存Decision Engineの入出力形式を再利用するために避けられない
    ものであり、walkforward.py と同様の設計判断である。Streamlit依存は
    一切持たない。
"""

from __future__ import annotations

import math
from typing import Any, Optional

import pandas as pd

from backtest.decision_pipeline import attach_decision_columns


#: このモジュールの戻り値スキーマのバージョン。
#: 戻り値の構造（トップレベルキー構成）を変更する場合はこの値を更新し、
#: 消費側（validation_dashboard.py・decision_validation.py・
#: benchmark.py・report_history.py等）が互換性を判断できるようにする。
WALKFORWARD_DECISION_SCHEMA_VERSION = "1.0"


# ════════════════════════════════════════════════
# JSON変換ヘルパー（walkforward.pyと同様の方針。
# 別モジュールのprivateヘルパーへ依存しないよう本ファイル内に複製する）
# ════════════════════════════════════════════════
def _to_json_safe(value: Any) -> Any:
    """pandas/numpyの値をJSON互換のプリミティブ型へ変換する。

    Args:
        value: 変換対象の値（pandas.Timestamp・numpy数値型・dict・
            None・NaN等を想定）。

    Returns:
        str（日時はISO8601） / float / int / bool / None / dict / list
        のいずれか。NaNはNoneに変換する。
    """
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
    """DataFrameの1行（pandas.Series）を、JSON互換dictへ変換する。

    Args:
        row: DataFrame.iloc[i] 等で取得した1行。

    Returns:
        列名をキーとし、値をすべてJSON互換型へ変換したdict。
    """
    return {col: _to_json_safe(row[col]) for col in row.index}


# ════════════════════════════════════════════════
# 1ウィンドウ分の処理
# ════════════════════════════════════════════════
def _apply_decision_to_window(
    window: dict[str, Any],
    run_id: Optional[str],
    score_col: str,
    components_col: str,
) -> dict[str, Any]:
    """1つのValidationウィンドウについて、Decision Engineを適用する。

    walkforward.py の1ウィンドウ分の出力
    （validation_periond_id・train/validation境界情報・
    validation_records）をそのまま引き継ぎつつ、validation_recordsを
    decision_pipeline.attach_decision_columns() に通した結果
    （decision_records）へ差し替える。

    Args:
        window: walkforward.run_walkforward_validation() の戻り値
            windows配列の1要素。
        run_id: 将来SQLite保存等で利用する予約フィールド。
            未指定時はNoneのまま保持する。
        score_col: attach_decision_columns() へ渡すスコア列名。
        components_col: attach_decision_columns() へ渡すcomponents列名。

    Returns:
        以下のキーを持つdict（JSON完全互換）::

            {
                "validation_period_id": ...,
                "run_id": ...,
                "code": ...,
                "strategy_name": ...,
                "window_index": ...,
                "train_start": ..., "train_end": ..., "train_count": ...,
                "validation_start": ..., "validation_end": ..., "validation_count": ...,
                "decision_count": ...,
                "decision_records": [...],
                "error": None | str,  # attach_decision_columns()適用中にエラーが発生した場合のみメッセージが入る
            }
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


# ════════════════════════════════════════════════
# 入口となるAPI
# ════════════════════════════════════════════════
def run_walkforward_decision_validation(
    walkforward_result: dict[str, Any],
    run_id: Optional[str] = None,
    score_col: str = "total",
    components_col: str = "components",
) -> dict[str, Any]:
    """walkforward.py の結果へDecision Engineを適用し、期間ごとの投資判断の
    再現性を検証するためのデータ基盤を構築する。

    walkforward.run_walkforward_validation() の戻り値をそのまま入力として
    受け取る。各ウィンドウのvalidation_recordsのみを対象に
    decision_pipeline.attach_decision_columns()（無変更）を適用する。
    新しい売買判定・新しい統計・新しいConfidence・新しいDecisionは
    一切実装しない。

    Args:
        walkforward_result: walkforward.run_walkforward_validation() の
            戻り値（"code"/"strategy_name"/"period"/"windows"等を持つdict）。
        run_id: 将来SQLite保存等でこの実行全体を一意に識別するための
            予約フィールド。現時点では未指定（None）でもよい。
        score_col: attach_decision_columns() へ渡すスコア列名。
        components_col: attach_decision_columns() へ渡すcomponents列名。

    Returns:
        以下の構造を持つJSON互換dict::

            {
                "walkforward_decision_schema_version": "1.0",
                "run_id": None,
                "code": "7203",
                "strategy_name": "v9",
                "period": "1y",
                "total_windows": 4,
                "windows": [
                    {
                        "validation_period_id": "7203_v9_w0",
                        "run_id": None,
                        "code": "7203",
                        "strategy_name": "v9",
                        "window_index": 0,
                        "train_start": "2025-01-06", "train_end": "2025-03-10",
                        "train_count": 45,
                        "validation_start": "2025-03-11", "validation_end": "2025-04-01",
                        "validation_count": 15,
                        "decision_count": 15,
                        "decision_records": [
                            {"date": "2025-03-11", "total": 78.0, "Decision": "Buy",
                             "Grade": "A", "Confidence": "Medium", "Risk": "Low",
                             "Summary": "...", "Strategy": "v9", ...},
                            ...
                        ],
                        "error": None,
                    },
                    ...
                ],
            }

        walkforward_resultにwindowsが無い、または空の場合、
        "windows" は空リストになる（例外は送出しない）。
        1ウィンドウでattach_decision_columns()の適用中にエラーが
        発生した場合、そのウィンドウのみ decision_records=[] ・
        error にエラー内容を記録し、他のウィンドウの処理は継続する。
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
