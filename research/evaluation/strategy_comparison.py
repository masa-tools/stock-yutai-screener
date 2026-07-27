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
  - Walk Forwardの計算ロジック（run_and_evaluate()へ完全委譲。
    backtest/walkforward_runner.py・
    research/evaluation/walkforward_connector.pyには一切手を加えない）
  - 採用基準の判定（V9_RESEARCH_ARCHITECTURE.md §12の判定自体は
    呼び出し元 or 別モジュールの責務とする）
  - UI表示（walkforward_result_view.py側の責務）

【同一条件比較の前提（確認済み事項）】
  backtest/walkforward_runner.py の実コード確認により、Window分割
  （splitter）は strategy_fn と完全に独立した引数として渡されることを
  確認済み。したがって、code・period・splitter を全戦略で固定すれば、
  Window分割自体はstrategy_fnの中身（RSI/Volume/Dividend/PER Sector/
  Composite）に一切影響されず、同一条件比較が構造的に成立する。
  本関数はrunner_kwargsを通じてこれらを一括で全戦略へ伝搬する。

【win_rate・max_ddの取得パスについて（確認済み事項）】
  runner_result["summary"]["metric_statistics"]["win_rate"] および
  ["max_dd"] は {"mean", "median", "stdev"} のdictであり、スカラー値
  ではない（build_metric_statistics()参照）。本モジュールでは比較表の
  代表値として["mean"]を採用する。

【将来拡張：window_metrics】
  採用判定でWindow単位の生データが必要になる可能性があるため、
  runner_result["summary"]["window_metrics"]（Window単位の
  win_rate/max_dd等を含むリスト）を各結果に含める。今回のUI
  （render_walkforward_comparison）では表示しないが、本モジュールの
  戻り値からは常に取得可能な構造を維持する。

【backtest_runner.run_backtest() との関係について（確認済み事項）】
  walkforward_runner.pyはbacktest_runner.run_backtest()を一切
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
            例: [(rsi_fn, "v9_rsi"), (volume_fn, "v9_volume"), ...]
        period: 全戦略共通のyfinance期間文字列（同一条件比較のため固定）。
        **runner_kwargs: 全戦略共通で渡すrun_walkforward_runner()の引数
            （splitter等）。戦略ごとに変えず、呼び出し元で固定した値を
            渡すこと（固定しないと「同一条件比較」が成立しない。詳細は
            モジュールdocstring「同一条件比較の前提」を参照）。

    Returns:
        list[dict]: strategies引数の順序を保持した結果リスト。各要素は

            {
                "strategy_name": str,
                "research_metrics": dict | None,
                    # total_return / calmar_ratio / sortino_ratio /
                    # time_underwater の4指標
                    # （run_and_evaluate()のresearch_metricsをそのまま格納）
                "win_rate": float | None,
                    # summary.metric_statistics.win_rate.mean
                "max_dd": float | None,
                    # summary.metric_statistics.max_dd.mean
                "window_metrics": list | None,
                    # summary.window_metrics（将来のWindow単位比較用。
                    # 今回のUIでは未使用だが常に取得可能な構造を維持）
                "error": str | None,
                    # run_and_evaluate()がValueErrorを送出した場合の
                    # メッセージ。正常時はNone。
            }
    """
    results: list[dict] = []

    for strategy_fn, strategy_name in strategies:
        try:
            r = run_and_evaluate(
                code=code,
                strategy_fn=strategy_fn,
                strategy_name=strategy_name,
                period=period,
                **runner_kwargs,
            )
        except ValueError as e:
            # calculate_metrics_from_runner_result()が送出する例外
            # （summary=None・window_metricsなし・有効Windowなし等）を
            # ここで捕捉し、1戦略の失敗が他戦略の比較を止めないようにする。
            results.append({
                "strategy_name": strategy_name,
                "research_metrics": None,
                "win_rate": None,
                "max_dd": None,
                "window_metrics": None,
                "error": str(e),
            })
            continue

        runner_result = r.get("runner_result", {}) or {}
        summary = runner_result.get("summary", {}) or {}
        metric_stats = summary.get("metric_statistics", {}) or {}

        # win_rate / max_dd は {"mean", "median", "stdev"} のdictとして
        # 格納されている。比較表の代表値としては"mean"を採用する。
        win_rate_stat = metric_stats.get("win_rate") or {}
        max_dd_stat = metric_stats.get("max_dd") or {}

        results.append({
            "strategy_name": strategy_name,
            "research_metrics": r.get("research_metrics"),
            "win_rate": win_rate_stat.get("mean"),
            "max_dd": max_dd_stat.get("mean"),
            "window_metrics": summary.get("window_metrics"),
            "error": None,
        })

    return results
