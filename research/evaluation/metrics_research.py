"""
metrics_research.py  v9 Research (Phase6-3: 評価層)
=====================================================
runner結果（Walk Forwardの実行結果に相当するデータ）から、
研究テーマ共通の評価指標を算出する。

【責務】
  - リターン列（およびエクイティカーブ）から、以下の指標を算出する:
      total_return / max_drawdown / win_rate / risk_reward /
      calmar_ratio / time_underwater / sortino_ratio
  - 算出のみを担当する。保存・表示・Walk Forward実行呼び出しは行わない。

【担当しないこと（Phase6-3時点で厳守）】
  - Walk Forward呼び出し（backtest.walkforward_runner等）
  - SQLite保存・research_storage呼び出し
  - UI表示（streamlit等）
  - 既存モジュール（app.py, strategy_v8, scoring_config等）への接続

【入力データについての重要な注意】
  本モジュールは「per-trade（銘柄・区間ごと）のリターン列」を
  基本入力として設計している。
  実際の backtest.walkforward_runner の戻り値（runner結果）の
  具体的なキー構造は本Phaseでは確認していないため、
  calculate_metrics_from_runner_result() は「想定される代表的な
  キー名」を複数試す防御的な実装としている。
  Walk Forward接続フェーズ（次Phase）では、実際のrunner結果の
  構造を確認したうえで、このアダプタ部分の見直しが必要になる
  可能性がある点に留意すること。

  【Phase6-3.5追記】
  実際にdebug_ui.pyの呼び出しパターンを調査した結果、
  run_walkforward_runner() の戻り値には "returns" 等の
  トップレベルキーは存在せず、代わりに
  summary["window_metrics"] （Window単位の集計リスト。
  各要素が avg_return / win_rate / max_dd 等を持つ）が
  実際のデータ構造であることが判明している。
  本ファイルのアダプタ部分（calculate_metrics_from_runner_result）
  は、この調査結果を反映するための修正がまだ行われていない
  （Phase6-3.5は調査のみのフェーズだったため）。
  Phase6-4での接続実装時に、この関数の候補キー探索ロジックを
  summary.window_metrics[].avg_return を組み立てる方式へ
  修正する必要がある。

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


def _calc_max_drawdown(returns: Sequence[float], equity: Sequence[float]) -> float:
    """最大ドローダウン（0以下の値。例: -0.23 は -23%）。"""
    return _max_drawdown_from_equity(equity)


def _calc_win_rate(returns: Sequence[float], equity: Sequence[float]) -> float:
    """勝率（プラスリターンの割合、0.0〜1.0）。"""
    if not returns:
        return 0.0
    wins = sum(1 for r in returns if r > 0)
    return wins / len(returns)


def _calc_risk_reward(returns: Sequence[float], equity: Sequence[float]) -> Optional[float]:
    """
    リスクリワード比（平均利益 ÷ 平均損失の絶対値）。

    損失トレードが1つもない場合は算出不能として None を返す
    （ゼロ除算を避けるため）。
    """
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]

    if not losses:
        return None

    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(losses) / len(losses))

    if avg_loss == 0:
        return None

    return avg_win / avg_loss


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
    "max_drawdown":    _calc_max_drawdown,
    "win_rate":        _calc_win_rate,
    "risk_reward":     _calc_risk_reward,
    "calmar_ratio":    _calc_calmar_ratio,
    "time_underwater": _calc_time_underwater,
    "sortino_ratio":   _calc_sortino_ratio,
}


def calculate_metrics(returns: Sequence[float]) -> dict:
    """
    per-trade（または区間ごと）のリターン列から、評価指標一式を算出する。

    Args:
        returns: リターンの列。例: [0.02, -0.01, 0.03, -0.02, ...]
                 （1トレード or 1区間あたりの騰落率）

    Returns:
        dict: {
            "total_return": float,
            "max_drawdown": float,
            "win_rate": float,
            "risk_reward": float | None,
            "calmar_ratio": float | None,
            "time_underwater": float,
            "sortino_ratio": float | None,
        }
        算出不能な指標（損失トレードなし等）は None を返す
        （Noneのまま握りつぶさず、呼び出し側で扱えるようにするため）。
    """
    returns = list(returns)
    equity = _build_equity_curve(returns)

    result = {}
    for metric_name, func in _METRIC_REGISTRY.items():
        result[metric_name] = func(returns, equity)

    return result


def calculate_metrics_from_runner_result(runner_result: dict) -> dict:
    """
    backtest.walkforward_runner の戻り値（runner結果）から
    リターン列を抽出し、calculate_metrics() を呼び出すアダプタ。

    【重要・Phase6-3.5調査結果を踏まえた注意】
      run_walkforward_runner() の実際の戻り値には、本関数が探索する
      "returns" / "trade_returns" / "period_returns" / "pnl_list" は
      存在しないことがPhase6-3.5の調査で判明している。
      実際のリターンに相当するデータは
      runner_result["summary"]["window_metrics"][i]["avg_return"]
      （Window単位の平均リターンのリスト）である可能性が高い。

      そのため、本関数は現時点（Phase6-3完了時点のまま）では、
      実際のrunner_resultを渡すと必ず ValueError が発生する
      （想定していたキーが実際には存在しないため）。
      これは「静かに誤った値を返す」よりは安全な失敗の仕方だが、
      Phase6-4でWalk Forwardへ実際に接続する際は、本関数の
      候補キー探索ロジックを summary.window_metrics 対応へ
      修正する必要がある（Phase6-3.5調査報告を参照）。

    Args:
        runner_result: run_walkforward_runner() 等の戻り値を想定したdict

    Returns:
        calculate_metrics() と同じ形式のdict

    Raises:
        ValueError: リターン列らしきデータが runner_result 内に
                    見つからなかった場合
    """
    candidate_keys = ("returns", "trade_returns", "period_returns", "pnl_list")

    for key in candidate_keys:
        if key in runner_result and runner_result[key] is not None:
            return calculate_metrics(runner_result[key])

    raise ValueError(
        "runner_result からリターン列を特定できませんでした。"
        f"想定したキー {candidate_keys} のいずれも見つかりません。"
        "実際のrunner結果の構造を確認し、本アダプタの候補キーを"
        "更新してください（Walk Forward接続フェーズでの対応事項）。"
    )
