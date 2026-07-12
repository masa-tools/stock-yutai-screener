"""backtest/walkforward_evaluation.py (v9研究開発ブランチ Walk Forward Evaluation Pipeline)
====================================================================
walkforward_decision.py（Walk Forward Decision Validation基盤）が
生成したValidation期間ごとのDecision結果へ、既存の
decision_validation.build_decision_validation_summary() と
decision_report.build_decision_report() を適用し、期間ごとの評価・
レポートを自動生成する橋渡しモジュール。

責務:
    walkforward_decision.run_walkforward_decision_validation() の
    戻り値（windows配列。各ウィンドウはtrain/validationの境界情報と
    decision_records＝Decision列付与済みのJSON互換dictのリストを持つ）
    を入力として受け取り、各ウィンドウのdecision_recordsのみを対象に
        - decision_validation.build_decision_validation_summary()
        - decision_report.build_decision_report()
    （いずれも無変更）を呼び出し、その戻り値をそのまま保持する。

    本モジュール自身はDecision・Confidence・Rating・Statistics・
    Benchmarkの計算を一切行わない。行うのは
        - JSON dict群 → pandas.DataFrame への一時的な復元
        - build_decision_validation_summary() / build_decision_report()
          の呼び出し
        - report_hash（Decision Report内容のSHA256）の算出
        - train/validation境界情報・メタ情報の受け渡し
    のみである。

    walkforward_decision.py（Decision列の付与）・decision_validation.py
    （Decisionラベルごとの統計集計）・decision_report.py（JSON互換の
    レポート生成）とは責務を重複させない。本モジュールはそれらの
    「呼び出しと束ね」に限定し、集計ロジック自体は一切再実装しない。

    walkforward_decision.py がどのWindowSplitter（FixedWindowSplitter・
    将来のRollingWindowSplitter・ExpandingWindowSplitter等）に基づいて
    windowsを生成したかには一切依存しない。本モジュールが参照するのは
    各windowの
    "validation_period_id" / "code" / "strategy_name" / "window_index" /
    "train_start" / "train_end" / "train_count" /
    "validation_start" / "validation_end" / "validation_count" /
    "decision_records" / "error" という共通キーのみであるため、将来
    walkforward.py・walkforward_decision.py側の分割方式が変わっても
    本モジュールは無修正で利用できる。

    公開インターフェース（引数・戻り値）はJSON完全互換のdict/listのみ
    （pandas.DataFrame・numpy型は含まない）で構成する。内部処理では
    decision_validation.py / decision_report.py が pandas.DataFrame を
    要求するためpandasを一時的に利用するが、これは既存モジュールの
    入出力形式を再利用するために避けられないものであり、walkforward.py・
    walkforward_decision.pyと同様の設計判断である。Streamlit依存は
    一切持たない。

    1つのValidation期間の処理で例外が発生しても、そのウィンドウのみ
    errorフィールドへ記録し、他のウィンドウの処理は継続する
    （walkforward_decision.py の _apply_decision_to_window と同じ方針）。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

import pandas as pd

from backtest.decision_validation import build_decision_validation_summary
from backtest.decision_report import build_decision_report


#: このモジュールの戻り値スキーマのバージョン。
#: 戻り値の構造（トップレベルキー構成）を変更する場合はこの値を更新し、
#: 消費側（validation_dashboard.py・benchmark.py・report_history.py・
#: SQLite/CSV保存・PDFレポート等）が互換性を判断できるようにする。
WALKFORWARD_EVALUATION_SCHEMA_VERSION = "1.0"

#: decision_pipeline.attach_decision_columns() が付与する列名
#: （debug_ui.py・walkforward_decision.py等、既存の他モジュールでも
#: 使われている実際の列名）。decision_validation.py側のデフォルト
#: decision_col="decision"（小文字）とは異なるため、ここで明示的に
#: 指定する。decision_report.py側のデフォルト列名（Decision/Grade/
#: Confidence/Risk/Strategy）は decision_pipeline.py の出力と
#: 一致しているため、そちらは上書きしない。
_DECISION_COLUMN = "Decision"


def _compute_report_hash(decision_report_result: dict[str, Any]) -> Optional[str]:
    """Decision Report結果からSHA256ハッシュを算出する。

    report_history.py の _compute_config_hash() と同じ方式
    （キー順序に依存しないよう sort_keys=True でJSON文字列化してから
    ハッシュ化）を用いる。将来Benchmarkが「2つのValidation期間の
    Decision Reportが同一内容かどうか」を素早く比較する際に利用できる。

    Args:
        decision_report_result: decision_report.build_decision_report()
            の戻り値。

    Returns:
        SHA256ハッシュの16進数文字列。ハッシュ化に失敗した場合はNone
        （例外は送出しない）。
    """
    try:
        canonical = json.dumps(decision_report_result, sort_keys=True,
                                ensure_ascii=False, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    except (TypeError, ValueError):
        return None


def _evaluate_window(
    decision_window: dict[str, Any],
    run_id: Optional[str],
) -> dict[str, Any]:
    """1つのValidationウィンドウについて、Decision Validation / Decision
    Reportを適用する。

    walkforward_decision.py の1ウィンドウ分の出力
    （validation_period_id・train/validation境界情報・decision_records）
    をそのまま引き継ぎつつ、decision_validation_result・
    decision_report_result・report_hashを追加する。

    Args:
        decision_window: walkforward_decision.
            run_walkforward_decision_validation() の戻り値windows配列の
            1要素。
        run_id: 将来History保存等で利用する予約フィールド。
            未指定時はNoneのまま保持する。

    Returns:
        以下のキーを持つdict（JSON完全互換）::

            {
                "validation_period_id": ...,
                "run_id": ...,
                "report_hash": ...,
                "code": ...,
                "strategy_name": ...,
                "window_index": ...,
                "train_start": ..., "train_end": ..., "train_count": ...,
                "validation_start": ..., "validation_end": ..., "validation_count": ...,
                "decision_validation_result": {...} | None,
                "decision_report_result": {...} | None,
                "error": None | str,
            }
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

    # walkforward_decision.py 側で既にこのウィンドウの処理が失敗している
    # 場合は、そのエラーをそのまま引き継ぎ、Decision Validation/Report
    # の呼び出し自体は行わない（存在しないDecision列に対する集計は
    # 無意味であり、二重にエラーを発生させないため）。
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
        report_hash = _compute_report_hash(decision_report_result)

        return {
            **base,
            "report_hash": report_hash,
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
    walkforward_decision_result: dict[str, Any],
    run_id: Optional[str] = None,
) -> dict[str, Any]:
    """walkforward_decision.py の結果へDecision Validation / Decision
    Reportを適用し、Validation期間ごとの投資判断の再現性を自動的に
    評価・レポート化する。

    walkforward_decision.run_walkforward_decision_validation() の
    戻り値をそのまま入力として受け取る。各ウィンドウのdecision_records
    のみを対象に decision_validation.build_decision_validation_summary()
    と decision_report.build_decision_report()（いずれも無変更）を
    呼び出す。新しい売買判定・新しい統計・新しいConfidence・新しい
    Decision・新しいBenchmarkは一切実装しない。

    Args:
        walkforward_decision_result: walkforward_decision.
            run_walkforward_decision_validation() の戻り値
            （"code"/"strategy_name"/"period"/"windows"等を持つdict）。
        run_id: 将来SQLite保存等でこの実行全体を一意に識別するための
            予約フィールド。現時点では未指定（None）でもよい。

    Returns:
        以下の構造を持つJSON互換dict::

            {
                "walkforward_evaluation_schema_version": "1.0",
                "run_id": None,
                "code": "7203",
                "strategy_name": "v9",
                "period": "1y",
                "total_windows": 4,
                "windows": [
                    {
                        "validation_period_id": "7203_v9_w0",
                        "run_id": None,
                        "report_hash": "a1b2c3...",
                        "code": "7203",
                        "strategy_name": "v9",
                        "window_index": 0,
                        "train_start": "2025-01-06", "train_end": "2025-03-10",
                        "train_count": 45,
                        "validation_start": "2025-03-11", "validation_end": "2025-04-01",
                        "validation_count": 15,
                        "decision_validation_result": {
                            "Strong Buy": {"count": 2, "avg_return": 5.1, "win_rate": 100.0, ...},
                            ...
                        },
                        "decision_report_result": {
                            "report_info": {...},
                            "Strong Buy": {"count": 2, "ratio_pct": 13.3, ...},
                            ...
                        },
                        "error": None,
                    },
                    ...
                ],
            }

        walkforward_decision_resultにwindowsが無い、または空の場合、
        "windows" は空リストになる（例外は送出しない）。
        1ウィンドウの処理でエラーが発生した場合、そのウィンドウのみ
        decision_validation_result / decision_report_result が None に
        なり、error にエラー内容が記録される。他のウィンドウの処理は
        継続する。
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
