"""
metrics_research.py  v9 Research (Phase6-4: DESIGN.md確定設計への準拠)
=====================================================================
Walk Forward Summary（backtest.walkforward_summary.build_walkforward_summary()
の戻り値）の window_metrics を唯一の入力とし、Research評価層で新たに
必要となる指標のみを算出する。

【責務（DESIGN.md「v9研究 Research評価層 設計」に準拠）】
  Research評価層の入力は summary["window_metrics"] とする。
  算出する指標は以下の4つのみ:
      total_return / calmar_ratio / sortino_ratio / time_underwater
  これらは summary["window_metrics"][i]["avg_return"] をWindow順に
  並べた「Window平均リターン列」から算出する**近似指標**である。

【担当しないこと（DESIGN.md確定事項）】
  - win_rate・max_dd の算出（build_metric_statistics()が既に算出済み。
    Research評価層では再計算しない。既存値をそのまま参照すること）
  - risk_reward・平均利益・平均損失の算出（現行スキーマでは
    per-trade単位の生データが保持されないため、Phase6-4のスコープ対象外）
  - Walk Forward呼び出し（backtest.walkforward_runner等）
  - SQLite保存・research_storage呼び出し
  - UI表示（streamlit等）
  - 既存モジュール（app.py, strategy_v8, scoring_config等）への接続

【近似指標であることの明記】
  total_return: Window平均の複利合成であり、真のポートフォリオ全体の
    トータルリターンではない
  calmar_ratio: 年率換算を行わない簡易版（Window期間の粒度が
    不揃いなため）
  sortino_ratio: Window単位の下方偏差に基づく簡易版
  time_underwater: Window単位の疑似エクイティカーブに基づく粗い
    時間分解能の値（日次ではない）

【将来の指標追加方針】
  _METRIC_REGISTRY に (指標名, 算出関数) を追加するだけで、
  calculate_metrics() の戻り値に新しい指標を増やせる構造にしている。
  既存の指標関数・calculate_metrics() 本体の変更は不要。
"""

import statistics
from typing import Optional, Sequence


# ── 基礎計算ヘルパー ──────────────────────────────────────

def _build_equity_curve(returns: Sequence[float], initial: float = 1.0) -> list:
    """リターン列（例: [0.02, -0.01, 0.03, ...]）から累積エクイティカーブを作る。"""
    equity = [initial]
    for r in returns:
        equity.append(equity[-1] * (1.0 + r))
    return equity


def _max_drawdown_from_equity(equity: Sequence[float]) -> float:
    """
    エクイティカーブから最大ドローダウンを算出する。

    Returns:
        0以下の値（例: -0.23 は 23% のドローダウン）。
        エクイティが2点未満の場合は 0.0 を返す。
    """
    if len(equity) < 2:
        return 0.0

    peak = equity[0]
    max_dd = 0.0
    for v in equity:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (v - peak) / peak
            if dd < max_dd:
                max_dd = dd
    return max_dd


def _time_underwater_ratio(equity: Sequence[float]) -> float:
    """
    エクイティが直近ピークを下回っている期間の割合を返す（0.0〜1.0）。

    例: 全10期間中4期間がピーク未満なら 0.4 を返す。
    """
    if len(equity) < 2:
        return 0.0

    peak = equity[0]
    underwater_count = 0
    for v in equity:
        if v > peak:
            peak = v
        if v < peak:
            underwater_count += 1
    return underwater_count / len(equity)


# ── 個別指標算出関数 ──────────────────────────────────────

def _calc_total_return(returns: Sequence[float], equity: Sequence[float]) -> float:
    """トータルリターン（例: 0.15 は +15%）。"""
    if len(equity) < 2:
        return 0.0
    return (equity[-1] / equity[0]) - 1.0


def _calc_calmar_ratio(returns: Sequence[float], equity: Sequence[float]) -> Optional[float]:
    """
    Calmar Ratio（トータルリターン ÷ 最大ドローダウンの絶対値）。

    注意: 本来のCalmar Ratioは「年率リターン ÷ 最大ドローダウン」だが、
    runner結果の期間の粒度（日次/週次/銘柄単位など）が本Phaseでは
    未確認のため、年率換算は行わず「期間全体のトータルリターン」を
    使った簡易版としている。年率換算が必要な場合は、Walk Forward接続後、
    実際の期間定義に合わせて本関数を拡張する想定。

    最大ドローダウンが 0（下落が一切ない）場合は算出不能として None。
    """
    total_return = _calc_total_return(returns, equity)
    max_dd = _max_drawdown_from_equity(equity)

    if max_dd == 0:
        return None

    return total_return / abs(max_dd)


def _calc_time_underwater(returns: Sequence[float], equity: Sequence[float]) -> float:
    """Time Underwater（ピーク未満期間の割合、0.0〜1.0）。"""
    return _time_underwater_ratio(equity)


def _calc_sortino_ratio(returns: Sequence[float], equity: Sequence[float]) -> Optional[float]:
    """
    Sortino Ratio（参考指標）。

    平均リターン ÷ 下方偏差（マイナスリターンのみの標準偏差）。
    年率換算は行わない簡易版（Calmar Ratio注記と同様の理由）。

    マイナスリターンが1つもない、または2つ未満で標準偏差が
    計算できない場合は None を返す。
    """
    if not returns:
        return None

    downside = [r for r in returns if r < 0]
    if len(downside) < 2:
        return None

    downside_std = statistics.pstdev(downside)
    if downside_std == 0:
        return None

    mean_return = sum(returns) / len(returns)
    return mean_return / downside_std


# ── 将来拡張用レジストリ ──────────────────────────────────
# 新しい指標を追加する場合は、ここに (指標名, 算出関数) を1行追加するだけでよい。
# calculate_metrics() 本体・既存の指標関数には触れる必要がない。
_METRIC_REGISTRY: dict = {
    "total_return":    _calc_total_return,
    "calmar_ratio":    _calc_calmar_ratio,
    "sortino_ratio":   _calc_sortino_ratio,
    "time_underwater": _calc_time_underwater,
}


def calculate_metrics(returns: Sequence[float]) -> dict:
    """
    リターン列（Window平均リターンの列を想定）から、Research評価層の
    指標一式を算出する。

    Args:
        returns: リターンの列。例: [0.02, -0.01, 0.03, -0.02, ...]
                 （Phase6-4ではWindow単位のavg_returnの列を想定）

    Returns:
        dict: {
            "total_return": float,
            "calmar_ratio": float | None,
            "sortino_ratio": float | None,
            "time_underwater": float,
        }
        算出不能な指標（下落が一切ない等）は None を返す
        （Noneのまま握りつぶさず、呼び出し側で扱えるようにするため）。

        win_rate・max_dd・risk_reward はDESIGN.md確定事項により
        本関数では算出しない（win_rate・max_ddは
        backtest.walkforward_summary.build_metric_statistics() の
        既存値を、risk_rewardはPhase6-4のスコープ対象外として扱うこと）。
    """
    returns = list(returns)
    equity = _build_equity_curve(returns)

    result = {}
    for metric_name, func in _METRIC_REGISTRY.items():
        result[metric_name] = func(returns, equity)

    return result


def calculate_metrics_from_runner_result(runner_result: dict) -> dict:
    """
    backtest.walkforward_summary.build_walkforward_summary() の戻り値
    （runner_result["summary"]）が持つ window_metrics から、Window平均
    リターン列を組み立て、calculate_metrics() を呼び出すアダプタ。

    【DESIGN.md確定事項】
      Research評価層の入力は summary["window_metrics"] のみとする。
      各要素の "avg_return" を、"window_index" の昇順に並べたものを
      「Window平均リターン列」として扱う。
      "success" が False のWindow（decision_report_result取得失敗等）
      は avg_return が None であり、集計対象から除外する。

    Args:
        runner_result: run_walkforward_runner() の戻り値を想定したdict。
                       runner_result["summary"] が
                       build_walkforward_summary() の戻り値であること。

    Returns:
        calculate_metrics() と同じ形式のdict
        （total_return / calmar_ratio / sortino_ratio / time_underwater）

    Raises:
        ValueError: summary が存在しない、window_metrics が存在しない、
                    または有効な avg_return を持つWindowが1つもない場合
    """
    summary = runner_result.get("summary")
    if not isinstance(summary, dict):
        raise ValueError(
            "runner_result['summary'] が存在しません。"
            "Walk Forwardが正常に完了しているか（status/stage_statusを"
            "確認のうえ）、summaryを持つ戻り値を渡してください。"
        )

    window_metrics = summary.get("window_metrics")
    if not isinstance(window_metrics, list) or not window_metrics:
        raise ValueError(
            "runner_result['summary']['window_metrics'] が存在しないか"
            "空です。build_walkforward_summary() の戻り値であることを"
            "確認してください。"
        )

    # success=Falseのwindow（avg_returnがNone）を除外し、window_indexの
    # 昇順に並べ替えてからavg_returnを取り出す（時系列指標のため順序が重要）。
    valid_windows = [
        w for w in window_metrics
        if w.get("success") and w.get("avg_return") is not None
    ]
    valid_windows.sort(key=lambda w: (w.get("window_index") is None, w.get("window_index")))

    returns = [w["avg_return"] for w in valid_windows]

    if not returns:
        raise ValueError(
            "window_metrics内に有効な(success=True かつ avg_return を持つ)"
            "Windowが1件もありませんでした。"
        )

    return calculate_metrics(returns)
