"""
strategy_v9_dividend.py  v9 Research (Phase7-5: 配当性向戦略)
================================================================
「配当性向（Payout Ratio）による配当の持続可能性を評価する」v9研究戦略。

【責務】
  strategy_v9_rsi.py・strategy_v9_volume.pyと同一の正式strategy_fn
  Interface（backtest_runner.run_backtest()から
  `strategy_fn(window_df, info, code)` の形で呼び出される契約）に
  準拠した compute_score(window_df, info, code) -> dict を提供する。
  Walk Forwardで評価可能な最小実装（高度な最適化・機械学習・AI判定は
  含まない）にとどめる。

【Interface契約（strategy_v9_rsi.py・strategy_v9_volume.pyと共通）】
  compute_score(window_df: pd.DataFrame, info: dict, code: str) -> dict

  戻り値：
    "date" : window_df.index[-1]（文字列化・ISO変換はしない。
             walkforward.py側の_to_json_safe()が後段で変換するため）
    "total": int（0〜100の配当性向スコア。必須キー）
    "note" : str（判定理由の短い説明。非契約的な補助情報）
    "components" は含めない（strategy_v9_volume.pyと同様、
    decision_pipeline.pyの実装確認により、この列を持たないres_dfを
    渡してもエラーにならないことを確認済みの方針を踏襲する）。

【v8.1 Stableとの関係（重要）】
  technical_analysis.py・strategy_v8.py・buy_timing.py・
  scoring_config.py・investment_judge.py・recommend.py 等、
  v8.1側の既存コードは一切importしない。使用するのは typing・pandas
  のみ。配当性向の評価閾値もv8.1側（recommend.pyの配当性向配点等）の
  値を再利用せず、本ファイル内で独立した候補値として定義する
  （v9研究をv8.1の設定値から完全に独立させるという、
  strategy_v9_rsi.py・strategy_v9_volume.pyと共通の方針を踏襲）。
  既存コードのコピー＆改造ではなく、配当性向による持続可能性評価
  という目的に必要な最小限のロジックのみを、本ファイル単体で
  完結する形で独立実装している。

【評価方針（最小実装）】
  window_dfではなく info["payoutRatio"] のみを評価対象とする
  （配当性向は日次の価格・出来高データではなく、銘柄のファンダメン
  タルズ情報としてyfinanceのinfoディクショナリから取得される値の
  ため。strategy_v9_rsi.py・strategy_v9_volume.pyがwindow_dfの列を
  参照するのに対し、本ファイルはinfoを主対象とする点が異なる）。

  配当性向（Payout Ratio = 配当金 ÷ 純利益）が高すぎず低すぎない
  「持続可能な範囲」にあるほど、長期保有に適した安定配当と判断して
  スコアを高くする。0〜100点のスケールとし、5段階の閾値で区分する。
  極端な高配当性向（利益のほとんどを配当に回している＝減配リスクが
  高い）や負の配当性向（赤字にもかかわらず配当を継続している）は
  最も低いスコアとする。

  yfinanceのpayoutRatioは小数（例: 0.45 = 45%）で返る場合と、
  既に百分率で返る場合が実運用上あり得るため、strategy_v9_rsi.py・
  strategy_v9_volume.pyと同様の「安全側フォールバック優先」の設計
  思想に基づき、他モジュールの実装をコピーせず本ファイル内で
  独立した変換処理を持つ（詳細は _to_payout_pct() 参照）。

  閾値・配点は「候補パラメータ（Phase7-5初期版）」として本ファイル内に
  定数で保持しており、strategy_v9_rsi.py・strategy_v9_volume.pyと
  同様、将来的なconfig駆動のパラメータ実験
  （config/research_settings.json経由での複数候補比較）に置き換え
  やすいよう、計算ロジックと定数を分離している。

【安全側フォールバック（0点）となるケース】
  以下のいずれかに該当する場合、判定不能または高リスクとして
  安全側の0点を返す（strategy_v9_rsi.py・strategy_v9_volume.pyの
  NaN対応と同じ設計思想）。
    - infoがNoneまたは辞書でない
    - "payoutRatio"キーが存在しない
    - payoutRatioがNaN/None
    - payoutRatioが数値化できない
    - 変換後の配当性向(%)が0%未満（赤字配当等の異常値）
    - 変換後の配当性向(%)が閾値の上限（VERY_HIGH）を超える
      （持続性への強い懸念があるため、判定不能ではなく明確な
      リスクとして0点にする）
  いずれの場合も、"note"に該当理由を明記する。
"""

from typing import Optional

import pandas as pd

# ── 配当性向候補パラメータ（Phase7-5初期版） ─────────────────────
# v8.1側（recommend.py等）の値とは独立した、v9研究専用の閾値候補。
# 将来的にconfig/research_settings.json経由で複数候補
# （candidate_a, candidate_b等）を切り替えられるようにする前提で、
# ロジックとは分離して定数化している
# （strategy_v9_rsi.py・strategy_v9_volume.pyと同じ方針）。

# 配当性向(%)の評価区分。持続可能性の観点で「30%〜55%」を最良帯とし、
# そこから離れるほどスコアを下げる山型の評価とする
# （RSI・Volumeの単調な閾値区分とは形が異なる点に注意）。
PAYOUT_IDEAL_LOW = 30.0        # 理想帯の下限
PAYOUT_IDEAL_HIGH = 55.0       # 理想帯の上限
PAYOUT_GOOD_LOW = 20.0         # 良好帯の下限
PAYOUT_GOOD_HIGH = 70.0        # 良好帯の上限
PAYOUT_CAUTION_LOW = 10.0      # 注意帯の下限
PAYOUT_CAUTION_HIGH = 85.0     # 注意帯の上限（これを超えると高リスク）

# 区分ごとの配点（0〜100点スケール）
_SCORE_IDEAL = 100        # 30%〜55%: 利益還元と内部留保のバランスが良い
_SCORE_GOOD = 70          # 20%〜30% または 55%〜70%: おおむね健全
_SCORE_CAUTION = 40       # 10%〜20% または 70%〜85%: やや偏り、要観察
_SCORE_LOW = 20           # 0%〜10%: 配当性向が低すぎる（成長株型・配当消極的）
_SCORE_HIGH_RISK = 0      # 85%超、または0%未満（赤字配当等）: 持続性に強い懸念

# 判定不能な場合のフォールバックスコア。
# Walk Forward実行を中断させないため、0点として安全側に倒す。
_SCORE_NO_DATA = 0


def _to_payout_pct(raw_value: float) -> float:
    """
    yfinanceのpayoutRatio生値を百分率(%)表記に変換する。

    yfinanceのpayoutRatioは実運用上、0.45（=45%）のような小数で
    返る場合が多いが、データソースや銘柄によっては既に百分率で
    返るケースも否定できないため、strategy_v9_rsi.py・
    strategy_v9_volume.pyと同じ「安全側優先」の考え方に基づき、
    絶対値が1.0以下なら小数表記とみなして100倍し、それ以外は
    既に百分率表記とみなしてそのまま扱う。

    Args:
        raw_value: info["payoutRatio"]のfloat変換後の値。

    Returns:
        百分率(%)表記の配当性向。

    Note:
        小数→百分率変換（×100）は浮動小数点演算のため、例えば
        0.55 が 55.00000000000001 のような値になり得る。これを
        そのまま閾値比較すると、本来は理想帯（境界値55%を含む）
        であるべき値が意図せず隣の区分に落ちてしまう。そのため
        小数点以下6桁で丸めてから返す。
    """
    payout_pct = raw_value * 100.0 if abs(raw_value) <= 1.0 else raw_value
    return round(payout_pct, 6)


def _score_from_payout_ratio(info: Optional[dict]) -> tuple[int, str]:
    """
    infoディクショナリの配当性向情報から0〜100点のスコアと、
    判定理由の短い説明文を返す。

    「30%〜55%」を最良帯とする山型評価で5段階に区分する。
    判定に必要なデータが揃わない、または異常値の場合は、安全側と
    して0点を返す。

    Args:
        info: yfinanceの銘柄情報を想定したdict。
              "payoutRatio"キーを参照する。

    Returns:
        (score, note) のタプル。
    """
    if info is None or not isinstance(info, dict):
        return _SCORE_NO_DATA, "info情報がありません"

    if "payoutRatio" not in info:
        return _SCORE_NO_DATA, "payoutRatioキーがありません"

    raw_value = info.get("payoutRatio")
    if raw_value is None or pd.isna(raw_value):
        return _SCORE_NO_DATA, "配当性向データなし（NaN/None）"

    try:
        raw_value_f = float(raw_value)
    except (TypeError, ValueError):
        return _SCORE_NO_DATA, "配当性向データが数値化できません"

    payout_pct = _to_payout_pct(raw_value_f)

    if payout_pct < 0.0:
        return _SCORE_HIGH_RISK, f"配当性向 {payout_pct:.1f}%: 負の値（赤字下配当等の異常値、持続性に強い懸念）"

    if payout_pct > PAYOUT_CAUTION_HIGH:
        return _SCORE_HIGH_RISK, f"配当性向 {payout_pct:.1f}%: {PAYOUT_CAUTION_HIGH}%超（利益のほとんどを配当に回しており、持続性に強い懸念）"

    if PAYOUT_IDEAL_LOW <= payout_pct <= PAYOUT_IDEAL_HIGH:
        return _SCORE_IDEAL, f"配当性向 {payout_pct:.1f}%: 理想的な範囲（利益還元と内部留保のバランスが良い）"

    if PAYOUT_GOOD_LOW <= payout_pct < PAYOUT_IDEAL_LOW or PAYOUT_IDEAL_HIGH < payout_pct <= PAYOUT_GOOD_HIGH:
        return _SCORE_GOOD, f"配当性向 {payout_pct:.1f}%: おおむね健全な範囲"

    if PAYOUT_CAUTION_LOW <= payout_pct < PAYOUT_GOOD_LOW or PAYOUT_GOOD_HIGH < payout_pct <= PAYOUT_CAUTION_HIGH:
        return _SCORE_CAUTION, f"配当性向 {payout_pct:.1f}%: やや偏りがあり要観察"

    # 残るのは 0.0 <= payout_pct < PAYOUT_CAUTION_LOW の範囲
    return _SCORE_LOW, f"配当性向 {payout_pct:.1f}%: 配当性向が低すぎる（成長株型、または配当に消極的）"


def compute_score(window_df: pd.DataFrame, info: dict, code: str) -> dict:
    """
    配当性向（Payout Ratio）から「配当の持続可能性」を0〜100点で
    評価する。

    strategy_v9_rsi.py・strategy_v9_volume.pyと同一の正式strategy_fn
    Interfaceに準拠したシグネチャ（backtest_runner.run_backtest()
    から `strategy_fn(window_df, info, code)` の形で呼び出される）。

    Args:
        window_df: 判定対象日までの行のみに絞り込まれたDataFrame。
                   本実装ではスコア算出には使用せず、戻り値の
                   "date"を決定するためだけに参照する（配当性向は
                   日次の価格・出来高データではなくinfo側の
                   ファンダメンタルズ情報のため）。
        info     : yfinanceの銘柄情報。本実装では"payoutRatio"の
                   みを参照する。
        code     : 証券コード（本実装では未使用。将来の拡張に備えて
                   契約上受け取る）。

    Returns:
        dict:
          "date" : window_df.index[-1]（文字列化・ISO変換はしない）。
                   window_dfが空またはNoneで取得不能な場合はNoneとする。
          "total": int（0〜100の配当性向スコア）
          "note" : str（判定理由の短い説明。非契約的な補助情報）
          "components" は含めない。
    """
    score, note = _score_from_payout_ratio(info)

    date = window_df.index[-1] if window_df is not None and not window_df.empty else None

    return {
        "date": date,
        "total": score,
        "note": note,
    }
