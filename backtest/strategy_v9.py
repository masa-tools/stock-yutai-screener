"""
backtest/strategy_v9.py (v9研究開発ブランチ スコアリングエンジン Phase1)
====================================================================
既存v8スコア（strategy_v8.compute_score_at）をベースとして、
scoring_v9.pyの各calc_*_score関数を加点・減点として積み上げる
v9スコアリングエンジンのエントリポイント。

【設計方針（依頼書の最重要方針を反映）】
    score = existing_v8_score(...)
    score += calc_ma_score(...)
    score += calc_deviation_score(...) / calc_rsi_score(...) / ...
    score -= calc_gap_penalty(...) / calc_upper_shadow_penalty(...) / ...
  という「既存v8ロジックを土台に後段で積み上げる」構造を、
  strategy_v8.compute_score_at()の戻り値("total")を起点として実装する。
  既存v8ロジック（technical_analysis.calc_simple_score等）には
  一切手を加えない。

【ON/OFF・重み変更について】
  各コンポーネントの有効/無効・重みは v9_config.py の
  ENABLE / WEIGHT 辞書で制御する。本ファイルを変更せずに
  v9_config.py の値を書き換えるだけで、コンポーネント単位の
  ON/OFF・重み調整・将来のA/Bテストが可能な構造としている。

【Look Ahead Bias（未来情報リーク）に関する設計上の注意】
  strategy_v8.compute_score_at()と同様、本関数が受け取るwindow_dfは
  判定対象日までの行のみに絞り込まれた状態で呼び出し側
  （backtest_runner.run_backtest）から渡される前提。
  scoring_v9.pyの各関数もその前提の上でwindow_df内のみを参照するため、
  新たなリークは発生しない。
  （finance/dividend系スコアの「現在時点参照」という既存の軽微なリーク
  についてはstrategy_v8.compute_score_at()のdocstringを参照。v9側で
  新たに追加する加点・減点要素はすべてOHLCVベースのテクニカル指標のみを
  使用しており、この既存の制約を拡大させるものではない。）
"""

from backtest.strategy_v8 import compute_score_at
from backtest import v9_config as cfg
from backtest import scoring_v9 as sv9


# コンポーネント名 → 対応するcalc_*_score関数の対応表。
# 新しいコンポーネントを追加する場合は、
#   1. scoring_v9.py に calc_xxx_score(window_df) を追加
#   2. v9_config.py の ENABLE / WEIGHT に "xxx" を追加
#   3. 下記マッピングに "xxx": sv9.calc_xxx_score を追加
# の3ステップのみで組み込める（strategy_v9.py本体の分岐ロジックは変更不要）。
_COMPONENT_FUNCS = {
    "ma_trend":     sv9.calc_ma_score,
    "deviation":    sv9.calc_deviation_score,
    "upper_shadow": sv9.calc_upper_shadow_penalty,
    "gap":          sv9.calc_gap_penalty,
    "volume_surge": sv9.calc_volume_score,
    "rsi":          sv9.calc_rsi_score,
    "macd_cross":   sv9.calc_macd_score,
    "bollinger":    sv9.calc_bb_score,
    "weekday":      sv9.calc_weekday_score,
}


def compute_score_at_v9(window_df, info: dict, code: str) -> dict:
    """
    ある時点までのwindow_dfを受け取り、v9スコア（v8ベース＋加点減点）を計算する。

    backtest_runner.run_backtest()のstrategy_fn引数として、
    strategy_v8.compute_score_atの代わりにそのまま渡せる
    （シグネチャ (window_df, info, code) -> dict は共通）。

    Args:
        window_df: 判定対象日までの行のみに絞り込まれたDataFrame
                   （add_indicators適用済み。strategy_v8.compute_score_atと同じ前提）
        info     : get_stock_info()の戻り値
        code     : 証券コード

    Returns:
        {
            "date"      : 判定対象日,
            "total"     : v9合計スコア（v8ベース + 各コンポーネントの加減点合計）,
            "v8_total"  : ベースとなったv8スコア（既存calc_simple_scoreのtotal）,
            "v9_delta"  : v9側で加減点した合計,
            "components": {コンポーネント名: 加減点値} の内訳（OFFのものは含まれない）,
            ...strategy_v8.compute_score_atの戻り値（finance/dividend/technical/volume等）をそのまま引き継ぐ
        }
    """
    base = compute_score_at(window_df, info, code)
    v8_total = base["total"]

    components: dict[str, float] = {}
    delta_total = 0.0

    for name, func in _COMPONENT_FUNCS.items():
        if not cfg.ENABLE.get(name, False):
            continue
        raw_score = func(window_df)
        weighted = raw_score * cfg.WEIGHT.get(name, 1.0)
        components[name] = weighted
        delta_total += weighted

    result = dict(base)  # v8の内訳（finance/dividend/technical/volume等）を引き継ぐ
    result["v8_total"] = v8_total
    result["v9_delta"] = delta_total
    result["total"] = v8_total + delta_total
    result["components"] = components
    return result
