"""backtest/decision_report.py (v9研究開発ブランチ Decision Report)
====================================================================
Decision Pipeline（decision_pipeline.py）が付与したDecision/Grade/
Confidence/Risk列を持つDataFrameを受け取り、Decisionラベルごとの
実績をJSON化しやすいdict構造に集計するレポート層。

責務:
    「Decision付きDataFrameを受け取り、Decisionごとの実績を集計して
    返す」ことのみ。新しい売買判定・Decision Engineの再実行・新しい
    計算式の導入は一切行わない。平均リターン・勝率は
    ``backtest.statistics``、最大ドローダウン・-10%以上下落率は
    ``backtest.metrics`` の既存関数をそのまま再利用する。

    Streamlitその他UIライブラリはimportしない（CSV/PDF/API/本番UI/
    Evaluation Labなど、どこからでも呼び出せる純粋関数として設計する）。
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from backtest.metrics import calc_max_drawdown, calc_down10_rate
from backtest.statistics import calc_avg_return, calc_win_rate


# Confidence/Risk は "High"/"Medium"/"Low" という3値の文字列ラベルであり、
# そのままでは数値平均を取れない。confidence.py / decision.py が実際に
# 出力するラベル集合に合わせた順序尺度への変換テーブルをここに定義する
# （新しい判定ロジックではなく、既存の3値ラベルを集計可能にするための
# 表示用の変換に過ぎない）。未知のラベルは平均計算から除外する。
_CONFIDENCE_ORDINAL: dict[str, int] = {"Low": 1, "Medium": 2, "High": 3}
_RISK_ORDINAL: dict[str, int] = {"Low": 1, "Medium": 2, "High": 3}


def _safe_mean(series: pd.Series) -> float | None:
    """Series の平均値を返す。空またはすべて欠損の場合は None を返す。

    Args:
        series: 平均を取る対象のSeries。

    Returns:
        平均値（float）。対象データが存在しない場合はNone。
    """
    valid = series.dropna()
    if valid.empty:
        return None
    return float(valid.mean())


def _ordinal_average(series: pd.Series, ordinal_map: dict[str, int]) -> float | None:
    """カテゴリラベルのSeriesを順序尺度に変換し、平均値を返す。

    Args:
        series: "High"/"Medium"/"Low" 等のラベルが入ったSeries。
        ordinal_map: ラベル文字列 -> 数値の変換テーブル。

    Returns:
        変換後の数値の平均値。ordinal_mapに存在するラベルが
        1件も無い場合はNone。
    """
    mapped = series.map(ordinal_map).dropna()
    if mapped.empty:
        return None
    return float(mapped.mean())


def _build_report_info(
    df: pd.DataFrame,
    strategy_name: str | None,
    code: str | None,
    date_col: str,
    strategy_col: str,
    code_col: str,
) -> dict[str, Any]:
    """レポート全体のメタ情報（report_info）を組み立てる。

    strategy_name / code が明示的に渡されなかった場合は、DataFrame内の
    対応する列（存在すれば）から推定する。列も引数も無い場合はNoneとする。

    Args:
        df: Decision Pipeline適用後のDataFrame。
        strategy_name: 呼び出し側が明示的に指定する戦略名。Noneの場合は
            strategy_col列から推定する。
        code: 呼び出し側が明示的に指定する銘柄コード。Noneの場合は
            code_col列から推定する。
        date_col: 判定対象日の列名。
        strategy_col: 戦略名が入っている列名（decision_pipeline.pyの
            "Strategy"列を想定）。
        code_col: 銘柄コードが入っている列名（存在すれば利用する）。

    Returns:
        strategy_name・code・period_start・period_end・total_days・
        total_decisions を持つdict。
    """
    resolved_strategy = strategy_name
    if resolved_strategy is None and strategy_col in df.columns and not df.empty:
        unique_strategies = df[strategy_col].dropna().unique()
        if len(unique_strategies) == 1:
            resolved_strategy = str(unique_strategies[0])
        elif len(unique_strategies) > 1:
            resolved_strategy = ", ".join(sorted(str(s) for s in unique_strategies))

    resolved_code = code
    if resolved_code is None and code_col in df.columns and not df.empty:
        unique_codes = df[code_col].dropna().unique()
        if len(unique_codes) == 1:
            resolved_code = str(unique_codes[0])
        elif len(unique_codes) > 1:
            resolved_code = ", ".join(sorted(str(c) for c in unique_codes))

    period_start = None
    period_end = None
    if date_col in df.columns and not df.empty:
        valid_dates = df[date_col].dropna()
        if not valid_dates.empty:
            start_val = valid_dates.min()
            end_val = valid_dates.max()
            period_start = start_val.isoformat() if hasattr(start_val, "isoformat") else str(start_val)
            period_end = end_val.isoformat() if hasattr(end_val, "isoformat") else str(end_val)

    return {
        "strategy_name": resolved_strategy,
        "code": resolved_code,
        "period_start": period_start,
        "period_end": period_end,
        "total_days": int(len(df)),
        "total_decisions": int(len(df)),
    }


def _build_decision_entry(
    group: pd.DataFrame,
    total_days: int,
    score_col: str,
    confidence_col: str,
    risk_col: str,
    return_col: str,
) -> dict[str, Any]:
    """1つのDecisionラベルに属する行の集計結果を組み立てる。

    平均リターン・勝率は ``backtest.statistics`` の既存関数、最大
    ドローダウン・-10%以上下落率は ``backtest.metrics`` の既存関数を
    それぞれそのまま呼び出すのみで、新しい計算式は定義しない。

    Args:
        group: 特定のDecisionラベルに属する行のみのDataFrame。
        total_days: レポート対象全体の営業日数（割合計算の分母）。
        score_col: スコア列名。
        confidence_col: Confidenceラベル列名。
        risk_col: Riskラベル列名。
        return_col: 勝率・平均リターン算出に使う将来リターン列名。

    Returns:
        件数・割合・平均リターン・勝率・最大DD・-10%以上下落率・
        平均Score・平均Confidence・平均Risk・confidence_sample_size を
        持つdict。
    """
    count = int(len(group))
    ratio_pct = (count / total_days * 100) if total_days > 0 else None

    valid_return = group[return_col].dropna() if return_col in group.columns else pd.Series(dtype=float)

    return {
        "count": count,
        "ratio_pct": ratio_pct,
        "avg_return": calc_avg_return(group, return_col) if return_col in group.columns else None,
        "win_rate": calc_win_rate(group, return_col) if return_col in group.columns else None,
        "max_dd": calc_max_drawdown(group),
        "down10_rate": calc_down10_rate(group),
        "avg_score": _safe_mean(group[score_col]) if score_col in group.columns else None,
        "avg_confidence": (
            _ordinal_average(group[confidence_col], _CONFIDENCE_ORDINAL)
            if confidence_col in group.columns else None
        ),
        "avg_risk": (
            _ordinal_average(group[risk_col], _RISK_ORDINAL)
            if risk_col in group.columns else None
        ),
        "confidence_sample_size": int(len(valid_return)),
    }


def build_decision_report(
    df: pd.DataFrame,
    strategy_name: str | None = None,
    code: str | None = None,
    decision_col: str = "Decision",
    score_col: str = "total",
    confidence_col: str = "Confidence",
    risk_col: str = "Risk",
    return_col: str = "fwd_return_1m",
    date_col: str = "date",
    strategy_col: str = "Strategy",
    code_col: str = "code",
) -> dict[str, Any]:
    """Decisionラベルごとの実績を集計したレポートを構築する。

    Decision Engineの再実行、新しい売買判定・計算式の導入は一切行わない。
    decision_col列に実際に存在するラベルを動的に取得してgroupbyし、
    ``backtest.metrics`` / ``backtest.statistics`` の既存関数を適用する
    だけの純粋な集計関数。Streamlit等のUIライブラリには依存しない。

    Args:
        df: Decision Pipeline適用後のDataFrame（Decision/Grade/
            Confidence/Risk列等を保持する想定）。
        strategy_name: レポートに記載する戦略名。省略時は strategy_col
            列（存在すれば）から推定する。
        code: レポートに記載する銘柄コード。省略時は code_col列
            （存在すれば）から推定する。
        decision_col: Decisionラベルが入っている列名。
        score_col: スコア列名。
        confidence_col: Confidenceラベル列名。
        risk_col: Riskラベル列名。
        return_col: 勝率・平均リターン算出に使う将来リターン列名
            （デフォルトは1ヶ月後リターン）。
        date_col: 判定対象日の列名（対象期間の算出に使用）。
        strategy_col: 戦略名列（strategy_name省略時のフォールバック）。
        code_col: 銘柄コード列（code省略時のフォールバック。
            現行のdecision_pipeline.pyはこの列を生成しないため、
            通常はNoneのままか、呼び出し側が code 引数で明示する運用を想定）。

    Returns:
        以下の構造を持つdict（DataFrameを含まず、JSON化可能）::

            {
                "report_info": {
                    "strategy_name": ...,
                    "code": ...,
                    "period_start": ...,
                    "period_end": ...,
                    "total_days": ...,
                    "total_decisions": ...,
                },
                "Strong Buy": {
                    "count": ..., "ratio_pct": ...,
                    "avg_return": ..., "win_rate": ...,
                    "max_dd": ..., "down10_rate": ...,
                    "avg_score": ..., "avg_confidence": ...,
                    "avg_risk": ..., "confidence_sample_size": ...,
                },
                "Buy": {...},
                ...
            }

        decision_col が df に存在しない、または df が空の場合は
        "report_info" のみを持つdictを返す（例外は送出しない）。
    """
    report_info = _build_report_info(df, strategy_name, code, date_col, strategy_col, code_col)

    if df.empty or decision_col not in df.columns:
        return {"report_info": report_info}

    total_days = len(df)
    labels = sorted(str(v) for v in df[decision_col].dropna().unique())

    report: dict[str, Any] = {"report_info": report_info}
    for label in labels:
        group = df[df[decision_col] == label]
        report[label] = _build_decision_entry(
            group, total_days, score_col, confidence_col, risk_col, return_col
        )

    return report
