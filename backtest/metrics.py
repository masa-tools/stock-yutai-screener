"""
backtest/metrics.py  (v9研究開発ブランチ Step1)
=================================================
バックテスト結果の集計指標を計算するモジュール。

【設計レビュー反映④】
  Step1で実装する評価指標は以下の2つのみに絞る。
    - 最大ドローダウン
    - -10%以上下落した割合
  勝率・平均リターン・リスクリワード比はStep2へ先送りする。

【設計レビュー反映⑤】
  describe_score_distribution() を追加する。
  閾値決定のためのスコア分布把握が目的であり、
  ヒストグラム描画等の可視化はStep1のスコープ外とする。

すべて純粋な数値計算関数であり、副作用（ファイル書き込み・
外部API呼び出し等）は一切持たない。
"""

import pandas as pd


def filter_by_threshold(df: pd.DataFrame, threshold: float,
                         score_col: str = "total") -> pd.DataFrame:
    """
    スコアが閾値以上の行のみを抽出する（Phase D：エントリー判定）。

    全営業日のスコアを先に計算済みのdfから、事後的に
    「その閾値だったらエントリーしていたはずの日」を抽出する。
    閾値を変えて何度でも再集計できるよう、この関数は
    df自体を変更せず、フィルタ後の新しいDataFrameを返す。

    Args:
        df       : run_backtest()の戻り値
        threshold: スコアの閾値（この値以上の行を抽出）
        score_col: 判定に使うスコア列名（デフォルトは"total"）

    Returns:
        条件を満たす行のみのDataFrame（コピー）
    """
    return df[df[score_col] >= threshold].copy()


def calc_max_drawdown(df: pd.DataFrame,
                       dd_col: str = "max_drawdown_1m") -> float | None:
    """
    最大ドローダウン（フィルタ済みdf内での最悪値）を計算する。

    Step1の最優先評価指標①。
    「高値掴みを避ける」というv9のコンセプトに直結する指標であり、
    フィルタ済みの各エントリー日について記録済みの
    1ヶ月以内最大ドローダウンのうち、最も悪い（最も下落した）値を返す。

    Args:
        df    : filter_by_threshold()の戻り値
        dd_col: ドローダウン列名（%表記、下落时は負の値）

    Returns:
        最大ドローダウン（%）。NaNを除いた最小値（最も下落した値）。
        データが空、または全てNaNの場合はNone。
    """
    if df.empty:
        return None
    valid = df[dd_col].dropna()
    if valid.empty:
        return None
    return float(valid.min())


def calc_down10_rate(df: pd.DataFrame,
                      dd_col: str = "max_drawdown_1m") -> float | None:
    """
    -10%以上下落した日の割合を計算する。

    Step1の最優先評価指標②。
    「負けを減らすAI」というv9のコンセプトを直接数値化したもの。
    フィルタ済みの各エントリー日のうち、1ヶ月以内に-10%以上
    下落したケースが何%あったかを返す。

    Args:
        df    : filter_by_threshold()の戻り値
        dd_col: ドローダウン列名（%表記、下落时は負の値）

    Returns:
        -10%以上下落した割合（%）。0〜100の範囲。
        データが空、または全てNaNの場合はNone。
    """
    if df.empty:
        return None
    valid = df[dd_col].dropna()
    if valid.empty:
        return None
    down10_count = (valid <= -10.0).sum()
    return float(down10_count / len(valid) * 100)


def describe_score_distribution(df: pd.DataFrame,
                                 score_col: str = "total") -> dict:
    """
    スコアの分布を確認するための基本統計量を返す。

    Step1の目的は「閾値をどこに設定するのが妥当か」の
    判断材料を得ることであり、ヒストグラム描画等の可視化は
    Step1のスコープ外とする（数値のみで十分と判断）。

    Args:
        df       : run_backtest()の戻り値（閾値フィルタ前の全営業日データ）
        score_col: 対象スコア列名（デフォルトは"total"）

    Returns:
        {
            "count" : 件数,
            "mean"  : 平均,
            "median": 中央値,
            "min"   : 最小値,
            "max"   : 最大値,
            "q25"   : 25%点（第1四分位数）,
            "q75"   : 75%点（第3四分位数）,
        }
        dfが空の場合は全項目Noneの辞書を返す。
    """
    if df.empty or score_col not in df.columns:
        return {
            "count": 0, "mean": None, "median": None,
            "min": None, "max": None, "q25": None, "q75": None,
        }

    s = df[score_col].dropna()
    if s.empty:
        return {
            "count": 0, "mean": None, "median": None,
            "min": None, "max": None, "q25": None, "q75": None,
        }

    return {
        "count": int(len(s)),
        "mean": float(s.mean()),
        "median": float(s.median()),
        "min": float(s.min()),
        "max": float(s.max()),
        "q25": float(s.quantile(0.25)),
        "q75": float(s.quantile(0.75)),
    }
