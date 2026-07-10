"""
backtest/decision_validation.py (v9研究開発ブランチ Decision Validation)
====================================================================
「Strong Buyが本当にStrong Buiだったか」を検証する、バックテスト基盤の
品質保証層。Decision Engine（decision.py）が出した判断ラベルごとに、
過去の結果（リターン・勝率・最大DD・下落率）を集計する。

【責務（重要）】
  Decision Validationは「判断」も「計算（Decision Engineの再実行）」も
  行わない。入力は res_df（1行=1判定対象日のDataFrame）のみであり、
  res_dfに既に含まれている決定ラベル列（decision_col、デフォルト
  "decision"）を groupby して既存の集計関数（metrics.py / statistics.py）
  を適用するだけの、純粋な集計層である。

  そのため本ファイルは decision.py / rating.py / confidence.py の
  いずれにも依存しない（importしていない）。これにより
  「Decision Engineを再実行しない」という制約を、うっかり違反しようが
  ない構造として型で保証している。

【現時点の前提について（重要な申し送り事項）】
  本関数は res_df に decision_col で指定した列（各営業日のDecision
  ラベル、例: "Strong Buy"/"Buy"/"Watch"/"Avoid"）が既に付与されている
  ことを前提とする。2026年7月時点では、この列を res_df へ実際に
  付与する処理はまだどこにも実装されていない
  （backtest_runner.run_backtest() は "decision" 列を生成しない）。
  次フェーズでEvaluation Labへ組み込む際、日次でDecisionラベルを
  付与する処理（decision.pyを使って、グレード帯ごとに1回だけ
  Decision Engineを呼び出し、該当する行へ結果をブロードキャストする、
  といった実装が想定される）と合わせて呼び出すことになる。
  decision_colが存在しないres_dfを渡した場合、本関数は黙って空の
  結果を返すのではなく、ValueErrorを送出して呼び出し側に気付かせる。

【将来拡張性について】
  集計項目は DEFAULT_VALIDATION_METRICS という
  「メトリクス名 → (グループ内res_dfを受け取り値を返す関数)」の
  登録テーブルで管理している。将来、保有30日・保有60日・利確・損切・
  ATR等の新しい列がres_dfに追加された場合も、
    1. その列を使う集計関数を1つ定義する
    2. DEFAULT_VALIDATION_METRICS に1行追加する
  の2ステップのみで対応でき、build_decision_validation_summary()の
  グルーピングロジック自体（本ファイルの中核）は変更不要。
  呼び出し側が独自のmetrics辞書を渡すことも可能なため、
  Evaluation Lab側で一時的に項目を絞ったり増やしたりする実験も、
  本ファイルを変更せずに行える。
"""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from backtest.metrics import calc_max_drawdown, calc_down10_rate
from backtest.statistics import calc_avg_return, calc_win_rate


# ════════════════════════════════════════════════
# 表示順のデフォルト（Decision Engineの判断ラベルと対応）
# ════════════════════════════════════════════════
# decision.py の _DEFAULT_DECISION_MATRIX が返しうるラベルと
# 対応させているが、本ファイルはdecision.pyに依存しないため、
# ここでは単なる「望ましい表示順」の文字列リストとして独立して持つ。
DEFAULT_DECISION_ORDER: tuple[str, ...] = ("Strong Buy", "Buy", "Watch", "Avoid")


# ════════════════════════════════════════════════
# 集計項目の登録テーブル（拡張ポイント）
# ════════════════════════════════════════════════
# 各関数は「1つのDecisionラベルに属する行だけを含むres_dfの部分集合」を
# 受け取り、1つの値を返す。count以外はいずれも既存のmetrics.py /
# statistics.py の関数をそのまま呼び出すだけで、新しい計算式は
# 本ファイルで一切定義していない。
DEFAULT_VALIDATION_METRICS: dict[str, Callable[[pd.DataFrame], Any]] = {
    "count":          lambda g: int(len(g)),
    "avg_return":      lambda g: calc_avg_return(g, "fwd_return_1m"),   # PM出力例の"avg_return"に対応（1ヶ月後リターン）
    "avg_return_1w":   lambda g: calc_avg_return(g, "fwd_return_1w"),
    "avg_return_3m":   lambda g: calc_avg_return(g, "fwd_return_3m"),
    "win_rate":        lambda g: calc_win_rate(g, "fwd_return_1m"),
    "max_dd":          lambda g: calc_max_drawdown(g),
    "down10_rate":     lambda g: calc_down10_rate(g),
}


def build_decision_validation_summary(
    res_df: pd.DataFrame,
    decision_col: str = "decision",
    metrics: dict[str, Callable[[pd.DataFrame], Any]] = None,
    order: tuple[str, ...] = DEFAULT_DECISION_ORDER,
) -> dict[str, dict[str, Any]]:
    """
    Decisionラベル（decision_col列）ごとに res_df をグルーピングし、
    metrics に登録された集計関数をそれぞれ適用する。

    Decision Engine（decision.py）の再実行は一切行わない。
    res_df に既に含まれている決定ラベル列を集計するだけ。

    Args:
        res_df      : 1行=1判定対象日のDataFrame。decision_col列に加え、
                       fwd_return_1w/1m/3m・max_drawdown_1m 列
                       （backtest_runner.run_backtest()が付与する列）を
                       前提とする。
        decision_col: Decisionラベルが入っている列名（デフォルト "decision"）。
        metrics     : {メトリクス名: 集計関数} の登録テーブル。
                       省略時は DEFAULT_VALIDATION_METRICS を使う。
                       呼び出し側で独自の辞書を渡せば、集計項目を
                       増減・差し替えできる（本ファイルの変更は不要）。
        order       : 出力dictのキー順（実際にres_dfに現れるラベルの
                       うち、このリストに含まれるものを先に、
                       含まれない未知のラベルはアルファベット順で後に並べる）。

    Returns:
        {
            "Strong Buy": {"count": 18, "avg_return": 12.4, "win_rate": 83.3,
                            "max_dd": -3.2, "down10_rate": 0.0, ...},
            "Buy": {...},
            ...
        }
        該当日が0件のラベルについては、countのみ0を返し、他の指標は
        すべてNoneになる（metrics.py / statistics.py 側の既存の
        「空データはNoneを返す」という規約をそのまま踏襲している）。

    Raises:
        ValueError: res_dfにdecision_col列が存在しない場合。
                    Decisionラベルが未付与のres_dfを渡してしまう
                    設定ミスに気付けるよう、黙って空の結果を返す
                    ことはしない。
    """
    if decision_col not in res_df.columns:
        raise ValueError(
            f"res_dfに '{decision_col}' 列が見つかりません。"
            " Decision Validationはres_dfに既にDecisionラベルが"
            "付与されていることを前提とする集計専用モジュールです"
            "（Decision Engineの再実行は行いません）。"
            "呼び出し側で先にDecisionラベルをres_dfへ付与してください。"
        )

    if metrics is None:
        metrics = DEFAULT_VALIDATION_METRICS

    present_labels = list(res_df[decision_col].dropna().unique())
    ordered_labels = [lbl for lbl in order if lbl in present_labels]
    ordered_labels += sorted(lbl for lbl in present_labels if lbl not in order)

    summary: dict[str, dict[str, Any]] = {}
    for label in ordered_labels:
        group = res_df[res_df[decision_col] == label]
        summary[label] = {name: fn(group) for name, fn in metrics.items()}

    return summary
