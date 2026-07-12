"""backtest/walkforward_pipeline.py (v9研究開発ブランチ Walk Forward Pipeline)
====================================================================
walkforward.py → walkforward_decision.py → walkforward_evaluation.py を
順番に呼び出すだけの統合オーケストレーター。

責務:
    「Walk Forward → Decision → Validation → Report」をワンコールで
    実行できるようにするための配線のみを担う。本モジュール自身は
    Decision・Confidence・Rating・Statistics・Benchmark・Validation・
    Reportの計算を一切行わない。それぞれ
        1. walkforward.run_walkforward_validation()
        2. walkforward_decision.run_walkforward_decision_validation()
        3. walkforward_evaluation.run_walkforward_evaluation()
    （いずれも無変更）を順に呼び出し、各段階の戻り値をそのまま次の
    段階の入力として渡すのみである。

    walkforward.py（期間分割＋バックテスト実行）・walkforward_decision.py
    （Decision列の付与）・walkforward_evaluation.py（Decision Validation
    ／Decision Reportの適用）とは責務を重複させない。本モジュールは
    それらの「呼び出し順序の固定化」にのみ責任を持つ。

    walkforward.py がどのWindowSplitter（FixedWindowSplitter・将来の
    RollingWindowSplitter・ExpandingWindowSplitter等）を使うかには
    一切依存しない。splitter引数はそのままwalkforward.
    run_walkforward_validation()へ透過的に渡すのみで、本モジュール側で
    分岐・分岐処理は行わない。

    公開インターフェース（引数・戻り値）はJSON完全互換のdict/listのみで
    構成する。Streamlit・UIライブラリへの依存は一切持たない。

    トップレベルの errors / warnings は、各段階の呼び出し自体が
    例外を送出した場合（＝パイプライン全体を継続できない致命的な
    失敗）のみを記録する。個々のValidationウィンドウ単位のエラーは、
    既存の walkforward_decision.py（windows[].error）・
    walkforward_evaluation.py（windows[].error）が既に保持している
    ため、本モジュールで重複して集計・再記録はしない
    （そのまま "windows" キー配下に残す）。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import pandas as pd

from backtest.walkforward import run_walkforward_validation, WindowSplitter
from backtest.walkforward_decision import run_walkforward_decision_validation
from backtest.walkforward_evaluation import run_walkforward_evaluation


#: このパイプライン全体の戻り値スキーマのバージョン。
#: 戻り値の構造（トップレベルキー構成）を変更する場合はこの値を更新し、
#: 消費側（Validation Dashboard・History・Benchmark・SQLite/CSV保存・
#: PDFレポート・本番画面等）が互換性を判断できるようにする。
WALKFORWARD_PIPELINE_VERSION = "1.0"


def run_walkforward_pipeline(
    code: str,
    strategy_fn: Callable[[pd.DataFrame, dict, str], dict],
    strategy_name: str,
    period: str = "1y",
    splitter: Optional[WindowSplitter] = None,
    date_col: str = "date",
    score_col: str = "total",
    components_col: str = "components",
    run_id: Optional[str] = None,
    extensions: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Walk Forward検証パイプライン全体（Validation生成→Decision付与→
    Decision Validation/Report適用）をワンコールで実行する統合エントリ
    ポイント。

    以下の既存関数を、各段階の戻り値をそのまま次の段階の入力として渡す
    形で順に呼び出すだけであり、本関数自身は計算・判定・集計ロジックを
    一切実装しない。
        1. walkforward.run_walkforward_validation(code, strategy_fn,
           strategy_name, period, splitter, date_col)
        2. walkforward_decision.run_walkforward_decision_validation(
           walkforward_result, run_id, score_col, components_col)
        3. walkforward_evaluation.run_walkforward_evaluation(
           walkforward_decision_result, run_id)

    Args:
        code: 対象銘柄コード（例: "7203"）。walkforward.py へそのまま
            渡す。
        strategy_fn: backtest_runner.run_backtest() へ最終的に渡される
            スコアリング関数（例: strategy_v9.compute_score_at_v9）。
            walkforward.py へそのまま渡す。
        strategy_name: レポート上の戦略識別子（例: "v9"）。
        period: yfinance期間文字列（例: "1y"）。walkforward.py へ
            そのまま渡す。
        splitter: 期間分割方式（WindowSplitterのインスタンス）。
            省略時はwalkforward.py側のデフォルト
            （FixedWindowSplitter）が使われる。本関数はこの引数の中身に
            一切関知せず、そのままwalkforward.run_walkforward_validation()
            へ透過的に渡すのみ（＝Window方式に依存しない）。
        date_col: walkforward.py内でres_dfの判定日列名として使う列名。
        score_col: walkforward_decision.py・decision_pipeline.py が
            スコア列として参照する列名。
        components_col: walkforward_decision.py・decision_pipeline.py
            がcomponents列として参照する列名。
        run_id: この実行全体を一意に識別する予約フィールド。
            省略時はUUID4を新規生成する（History/SQLite保存等での
            一意識別を見据えたもの。現時点ではこの値を保存する処理
            自体は実装していない）。
        extensions: 将来のFundamental分析・配当分析・AIコメント等の
            追加ステップを見据えた予約引数（dict）。現時点では内容の
            解釈・実行を一切行わず、指定された場合のみ戻り値の
            "extensions"キーへそのまま格納する（デフォルトNone、
            その場合戻り値にこのキーは含まれない）。将来これらを
            実行する場合も、本関数内の「呼び出し先を1つ追加する」
            だけで対応できる拡張ポイントとして用意している。

    Returns:
        以下のトップレベルキーを持つJSON互換dict（"extensions"を除き
        常にすべてのキーが存在する）::

            {
                "pipeline_version": "1.0",
                "run_id": "生成または指定されたUUID文字列",
                "strategy": "v9",
                "code": "7203",
                "period": "1y",
                "generated_at": "2026-07-12T00:00:00+00:00",  # ISO8601
                "windows": walkforward_evaluation.run_walkforward_evaluation()の戻り値,
                "errors": [
                    {"stage": "walkforward" | "walkforward_decision" | "walkforward_evaluation",
                     "message": str},
                    ...
                ],
                "warnings": [
                    {"stage": ..., "message": str},
                    ...
                ],
                "extensions": extensions引数の値,  # extensionsが指定された場合のみ
            }

        いずれかの段階で例外が発生した場合、その段階以降の呼び出しは
        行わず、"errors" にエラー内容を記録して "windows" は
        {"windows": [], ...} に相当する空の構造（該当段階の
        スキーマ_versionのみを持つ最小構成）を返す。個々のValidation
        ウィンドウ単位のエラーは "windows" 配下（walkforward_decision.py
        ／walkforward_evaluation.py が既に付与したerrorフィールド）に
        そのまま残る。
    """
    resolved_run_id = run_id if run_id is not None else str(uuid.uuid4())
    generated_at = datetime.now(timezone.utc).isoformat()

    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    # ── Stage 1: walkforward.py ─────────────────────
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
        errors.append({"stage": "walkforward", "message": f"{type(exc).__name__}: {exc}"})
        return _build_result(resolved_run_id, strategy_name, code, period, generated_at,
                              windows={"windows": []}, errors=errors, warnings=warnings,
                              extensions=extensions)

    if not walkforward_result.get("windows"):
        warnings.append({
            "stage": "walkforward",
            "message": "Validationウィンドウが1つも生成されませんでした"
                       "（対象期間が短すぎる、またはsplitterの設定を確認してください）。",
        })

    # ── Stage 2: walkforward_decision.py ─────────────
    try:
        walkforward_decision_result = run_walkforward_decision_validation(
            walkforward_result=walkforward_result,
            run_id=resolved_run_id,
            score_col=score_col,
            components_col=components_col,
        )
    except Exception as exc:  # noqa: BLE001
        errors.append({"stage": "walkforward_decision", "message": f"{type(exc).__name__}: {exc}"})
        return _build_result(resolved_run_id, strategy_name, code, period, generated_at,
                              windows={"windows": walkforward_result.get("windows", [])},
                              errors=errors, warnings=warnings, extensions=extensions)

    # ── Stage 3: walkforward_evaluation.py ───────────
    try:
        walkforward_evaluation_result = run_walkforward_evaluation(
            walkforward_decision_result=walkforward_decision_result,
            run_id=resolved_run_id,
        )
    except Exception as exc:  # noqa: BLE001
        errors.append({"stage": "walkforward_evaluation", "message": f"{type(exc).__name__}: {exc}"})
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
    windows: dict[str, Any],
    errors: list[dict[str, str]],
    warnings: list[dict[str, str]],
    extensions: Optional[dict[str, Any]],
) -> dict[str, Any]:
    """パイプライン全体の戻り値dictを組み立てる共通ヘルパー。

    Args:
        run_id: 解決済みのrun_id（Noneではなく必ず文字列）。
        strategy_name: 戦略識別子。
        code: 銘柄コード。
        period: 期間文字列。
        generated_at: ISO8601形式の生成日時。
        windows: 各段階の戻り値（正常時はwalkforward_evaluation.py の
            戻り値そのもの、異常時は前段の戻り値または{"windows": []}）。
        errors: 致命的エラーのリスト。
        warnings: 警告のリスト。
        extensions: 将来拡張用の予約dict（Noneの場合は戻り値に含めない）。

    Returns:
        run_walkforward_pipeline() のdocstringに記載の構造を持つdict。
    """
    result: dict[str, Any] = {
        "pipeline_version": WALKFORWARD_PIPELINE_VERSION,
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
