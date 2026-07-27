"""
research/evaluation/strategy_comparison.py  (Phase8: Walk Forward比較検証)
============================================================================
複数戦略を同一条件（code / period / splitter / その他runner_kwargs）で
walkforward_connector.run_and_evaluate() へ順次渡し、結果を
比較用リストとして集約する薄いオーケストレーション層。

【責務】
  - 複数戦略を同一条件で実行するループ制御のみ
  - 戦略単位でValueErrorを捕捉し、1戦略の失敗が他戦略の比較を
    妨げないようにする（握りつぶさず、結果に含めて返す）

【担当しないこと】
  - Walk Forwardの計算ロジック（run_and_evaluate()へ完全委譲）
  - 採用基準の判定（V9_RESEARCH_ARCHITECTURE.md §12の判定自体は
    呼び出し元 or 別モジュールの責務とする）
  - UI表示（walkforward_result_view.py側の責務）

【同一条件比較の前提（確認済み事項）】
  backtest/walkforward_runner.py の実コード確認により、
  run_walkforward_runner() のWindow分割（splitter）は strategy_fn と
  完全に独立した引数として渡されることを確認済み。したがって、
  code・period・splitter を全戦略で固定すれば、Window分割自体は
  strategy_fnの中身（RSI/Volume/Dividend/PER Sector/Composite）に
  一切影響されず、同一条件比較が構造的に成立する。
  本関数は runner_kwargs を通じてこれらを一括で全戦略へ伝搬する。

【win_rate・max_ddの取得パスについて（確認済み事項）】
  backtest/walkforward_summary.py の build_walkforward_summary() /
  build_metric_statistics() の実コード確認により、以下を確認済み：

    runner_result["summary"]["metric_statistics"]["win_rate"]
    runner_result["summary"]["metric_statistics"]["max_dd"]

  というパスでアクセス可能だが、両者の値は
  {"mean": float|None, "median": float|None, "stdev": float|None}
  という dict であり、スカラー値ではない（成功Windowのみを対象に、
  Window単位の集約値をさらに平均・中央値・標準偏差化したもの）。
  本モジュールでは比較表に使う代表値として ["mean"] を採用する。

  なお、Window単位の生データが必要な場合は
  runner_result["summary"]["window_metrics"][i]["win_rate"] /
  ["max_dd"] を別途参照できる（本モジュールでは扱わない）。

【backtest_runner.run_backtest() との関係について（確認済み事項）】
  walkforward_runner.py は backtest_runner.run_backtest() を一切
  import・呼び出ししていないことを実コードで確認済み。本モジュールも
  同様にbacktest_runner.pyには一切依存しない。
"""

from typing import Any, Callable

from evaluation.walkforward_connector import run_and_evaluate


def run_comparison(
    code: str,
    strategies: list[tuple[Callable[..., dict], str]],
    period: str = "1y",
    **runner_kwargs: Any,
) -> list[dict]:
    """
    複数戦略を同一条件で実行し、比較用の結果リストを返す。

    Args:
        code: 対象銘柄コード。全戦略で共通。
        strategies: (strategy_fn, strategy_name) のタプルのリスト。
        period:
