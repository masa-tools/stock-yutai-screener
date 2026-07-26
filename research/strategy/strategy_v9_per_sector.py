"""
strategy_v9_per_sector.py  v9 Research (Phase7-6: PER業種別評価戦略)
======================================================================
「PERを業種別の適正レンジに照らして評価する」v9研究戦略。

【責務】
  strategy_v9_rsi.py・strategy_v9_volume.py・strategy_v9_dividend.pyと
  同一の正式strategy_fn Interface（backtest_runner.run_backtest()から
  `strategy_fn(window_df, info, code)` の形で呼び出される契約）に
  準拠した compute_score(window_df, info, code) -> dict を提供する。
  Walk Forwardで評価可能な最小実装（高度な最適化・機械学習・AI判定は
  含まない）にとどめる。

【Interface契約（既存3戦略ファイルと共通）】
  compute_score(window_df: pd.DataFrame, info: dict, code: str) -> dict

  戻り値：
    "date" : window_df.index[-1]（文字列化・ISO変換はしない。
             walkforward.py側の_to_json_safe()が後段で変換するため）
    "total": int（0〜100のPER業種別評価スコア。必須キー）
    "note" : str（判定理由の短い説明。非契約的な補助情報）
    "components" は含めない（他3戦略ファイルと同じ方針）。

【v8.1 Stableとの関係（重要）】
  technical_analysis.py・strategy_v8.py・buy_timing.py・
  scoring_config.py・investment_judge.py・recommend.py 等、
  v8.1側の既存コードは一切importしない。使用するのは typing・pandas
  のみ。PERの評価閾値・業種別レンジもv8.1側の値を再利用せず、
  本ファイル内で独立した候補値として定義する（v9研究をv8.1の
  設定値から完全に独立させるという、既存3戦略ファイルと共通の
  方針を踏襲）。既存コードのコピー＆改造ではなく、業種別のPER
  適正レンジによる評価という目的に必要な最小限のロジックのみを、
  本ファイル単体で完結する形で独立実装している。

【評価方針（最小実装・Phase7-6初期版）】
  window_dfではなく info["sector"]・info["trailingPE"]（または
  info["forwardPE"]）を評価対象とする（strategy_v9_dividend.pyと
  同様、PERと業種はファンダメンタルズ情報のためinfoを主対象とする）。

  V9_RESEARCH_ARCHITECTURE.md §10で言及されている「PER業種別最適化」
  の第一段階として、業種ごとに固定の適正PERレンジ（理想帯・良好帯・
  注意帯）をハードコードした最小実装とする。将来的には
  config/research_settings.json や業種別テーブルファイルへ置き換え
  やすいよう、業種別レンジ定義（SECTOR_PER_RANGES）を計算ロジックから
  分離した1つの辞書定数として保持し、置き換え時にこの定数のみを
  差し替えれば済む構成にしている（strategy_v9_rsi.py・
  strategy_v9_volume.py・strategy_v9_dividend.pyの「ロジックと定数の
  分離」方針を踏襲）。

  PERが業種の理想帯にあるほど「その業種の中で適正水準」と判断し
  スコアを高くする、strategy_v9_dividend.pyと同じ山型の5段階評価
  とする（低すぎる・高すぎるPERはともに注意対象とし、極端な高PER・
  負のPER（赤字）は高リスクとして最低スコアにする）。

  【業種が未対応の場合の扱い（重要・仕様として明記）】
  本Phaseの開発方針に明記されている通り、業種情報が
  取得できない・空文字・SECTOR_PER_RANGESに未収録の業種である
  場合は、"デフォルトレンジで代用する"のではなく、判定不能として
  安全側の0点にフォールバックする。これは、収録されていない業種に
  対して安易に一律のデフォルト値を適用すると、業種特性を無視した
  誤判定を生みかねない（Phase1設計レビューで指摘した「業種データ
  品質リスク」）ため、Phase7-6の段階では「対応業種のみ確信を持って
  評価し、非対応業種は評価しない」という保守的な設計を優先した
  判断による。SECTOR_PER_RANGESの収録業種を拡充することが、
  今後の主な改善対象となる。

【安全側フォールバック（0点）となるケース】
  以下のいずれかに該当する場合、判定不能または高リスクとして
  安全側の0点を返す（既存3戦略ファイルと同じ設計思想）。
    - infoがNoneまたは辞書でない
    - "sector"キーが存在しない、値がNone/空文字/文字列でない
    - sectorがSECTOR_PER_RANGESに未収録（非対応業種）
    - trailingPE・forwardPEのいずれもNone/NaN/キー欠損
    - PERデータが数値化できない
    - PERが負値（赤字等、PERとしての意味を持たない）
    - PERが該当業種のcaution帯上限を超える（強い割高リスク）
  いずれの場合も、"note"に該当理由を明記する。
"""

from typing import Optional

import pandas as pd

# ── PER業種別レンジ候補パラメータ（Phase7-6初期版） ──────────────
# v8.1側（investment_judge.py・recommend.py等）の値とは独立した、
# v9研究専用の候補値。将来的にconfig/research_settings.json経由、
# または業種別テーブルファイルへの置き換えを想定し、計算ロジックとは
# 分離してこの辞書定数にのみレンジ定義を持たせている。
#
# 各業種のレンジは (下限, 上限) のタプルで、
#   "ideal"  : 理想帯（最も適正水準とみなすPERレンジ）
#   "good"   : 良好帯（idealの外側だが妥当な範囲。idealを包含する広いレンジ）
#   "caution": 注意帯（goodの外側だがまだ評価対象とする範囲。
#              goodを包含する広いレンジ。この上限を超えると高リスク扱い）
# として定義する。goodはidealを、cautionはgoodをそれぞれ包含する
# 入れ子構造とする。
#
# yfinanceのinfo["sector"]で返る代表的な業種名を初期収録対象とした。
# 収録されていない業種は「非対応業種」として安全側0点にフォールバック
# する（本ファイル冒頭のdocstring参照）。
SECTOR_PER_RANGES: dict[str, dict[str, tuple[float, float]]] = {
    "Technology": {
        "ideal": (15.0, 30.0), "good": (10.0, 40.0), "caution": (5.0, 55.0),
    },
    "Financial Services": {
        "ideal": (7.0, 12.0), "good": (5.0, 15.0), "caution": (3.0, 20.0),
    },
    "Healthcare": {
        "ideal": (15.0, 25.0), "good": (10.0, 35.0), "caution": (5.0, 45.0),
    },
    "Consumer Defensive": {
        "ideal": (12.0, 20.0), "good": (8.0, 25.0), "caution": (5.0, 32.0),
    },
    "Consumer Cyclical": {
        "ideal": (10.0, 18.0), "good": (7.0, 24.0), "caution": (4.0, 32.0),
    },
    "Industrials": {
        "ideal": (10.0, 18.0), "good": (7.0, 24.0), "caution": (4.0, 30.0),
    },
    "Energy": {
        "ideal": (6.0, 12.0), "good": (4.0, 16.0), "caution": (2.0, 22.0),
    },
    "Utilities": {
        "ideal": (10.0, 16.0), "good": (8.0, 20.0), "caution": (5.0, 25.0),
    },
    "Real Estate": {
        "ideal": (10.0, 18.0), "good": (7.0, 24.0), "caution": (4.0, 30.0),
    },
    "Basic Materials": {
        "ideal": (8.0, 14.0), "good": (5.0, 18.0), "caution": (3.0, 24.0),
    },
    "Communication Services": {
        "ideal": (12.0, 22.0), "good": (8.0, 30.0), "caution": (5.0, 40.0),
    },
}

# 区分ごとの配点（0〜100点スケール。strategy_v9_dividend.pyと同じ構成）
_SCORE_IDEAL = 100
_SCORE_GOOD = 70
_SCORE_CAUTION = 40
_SCORE_LOW = 20
_SCORE_HIGH_RISK = 0

# 判定不能な場合のフォールバックスコア。
# Walk Forward実行を中断させないため、0点として安全側に倒す。
_SCORE_NO_DATA = 0


def _extract_per(info: dict) -> tuple[Optional[float], str]:
    """
    infoからPERを抽出する。trailingPEを優先し、None/NaNの場合は
    forwardPEにフォールバックする。

    Returns:
        (per_value, source) のタプル。抽出できなかった場合は
        (None, "") を返す。sourceは "trailingPE" または "forwardPE"。
    """
    for key in ("trailingPE", "forwardPE"):
        raw_value = info.get(key)
        if raw_value is None or pd.isna(raw_value):
            continue
        try:
            return float(raw_value), key
        except (TypeError, ValueError):
            continue
    return None, ""


def _score_from_per_sector(info: Optional[dict]) -> tuple[int, str]:
    """
    infoディクショナリの業種・PER情報から0〜100点のスコアと、
    判定理由の短い説明文を返す。

    業種ごとの適正PERレンジ（SECTOR_PER_RANGES）に照らして、
    strategy_v9_dividend.pyと同じ山型の5段階評価を行う。
    業種が非対応、またはPERデータが揃わない場合は安全側の0点を返す。

    Args:
        info: yfinanceの銘柄情報を想定したdict。
              "sector"・"trailingPE"・"forwardPE"キーを参照する。

    Returns:
        (score, note) のタプル。
    """
    if info is None or not isinstance(info, dict):
        return _SCORE_NO_DATA, "info情報がありません"

    sector = info.get("sector")
    if not sector or not isinstance(sector, str):
        return _SCORE_NO_DATA, "業種情報が取得できません（sectorキーがNone/空文字/未設定）"

    ranges = SECTOR_PER_RANGES.get(sector)
    if ranges is None:
        return _SCORE_NO_DATA, f"業種「{sector}」は非対応業種のため評価対象外です"

    per_value, source = _extract_per(info)
    if per_value is None:
        return _SCORE_NO_DATA, "PERデータなし（trailingPE・forwardPEともにNaN/None/キー欠損）"

    if per_value < 0:
        return _SCORE_HIGH_RISK, f"PER {per_value:.1f}倍（{source}）: 負値（赤字等）のため評価対象外"

    ideal_low, ideal_high = ranges["ideal"]
    good_low, good_high = ranges["good"]
    caution_low, caution_high = ranges["caution"]

    if per_value > caution_high:
        return _SCORE_HIGH_RISK, (
            f"PER {per_value:.1f}倍（{source}）: 業種「{sector}」の注意帯上限"
            f"（{caution_high:.1f}倍）超、強い割高リスク"
        )

    if ideal_low <= per_value <= ideal_high:
        return _SCORE_IDEAL, (
            f"PER {per_value:.1f}倍（{source}）: 業種「{sector}」の理想帯"
            f"（{ideal_low:.1f}〜{ideal_high:.1f}倍）内、適正水準"
        )

    if good_low <= per_value < ideal_low or ideal_high < per_value <= good_high:
        return _SCORE_GOOD, (
            f"PER {per_value:.1f}倍（{source}）: 業種「{sector}」の良好帯内、おおむね妥当"
        )

    if caution_low <= per_value < good_low or good_high < per_value <= caution_high:
        return _SCORE_CAUTION, (
            f"PER {per_value:.1f}倍（{source}）: 業種「{sector}」の注意帯、やや偏りがあり要観察"
        )

    # 残るのは 0 <= per_value < caution_low の範囲（極端な低PER）
    return _SCORE_LOW, (
        f"PER {per_value:.1f}倍（{source}）: 業種「{sector}」の注意帯下限"
        f"（{caution_low:.1f}倍）未満、割安すぎる可能性（要因確認推奨）"
    )


def compute_score(window_df: pd.DataFrame, info: dict, code: str) -> dict:
    """
    PERを業種別の適正レンジに照らして「割安・適正・割高」を
    0〜100点で評価する。

    strategy_v9_rsi.py・strategy_v9_volume.py・strategy_v9_dividend.pyと
    同一の正式strategy_fn Interfaceに準拠したシグネチャ
    （backtest_runner.run_backtest()から
    `strategy_fn(window_df, info, code)` の形で呼び出される）。

    Args:
        window_df: 判定対象日までの行のみに絞り込まれたDataFrame。
                   本実装ではスコア算出には使用せず、戻り値の
                   "date"を決定するためだけに参照する
                   （strategy_v9_dividend.pyと同じ理由。PERと業種は
                   日次の価格・出来高データではなくinfo側の
                   ファンダメンタルズ情報のため）。
        info     : yfinanceの銘柄情報。本実装では"sector"・
                   "trailingPE"・"forwardPE"のみを参照する。
        code     : 証券コード（本実装では未使用。将来の拡張に備えて
                   契約上受け取る）。

    Returns:
        dict:
          "date" : window_df.index[-1]（文字列化・ISO変換はしない）。
                   window_dfが空またはNoneで取得不能な場合はNoneとする。
          "total": int（0〜100のPER業種別評価スコア）
          "note" : str（判定理由の短い説明。非契約的な補助情報）
          "components" は含めない。
    """
    score, note = _score_from_per_sector(info)

    date = window_df.index[-1] if window_df is not None and not window_df.empty else None

    return {
        "date": date,
        "total": score,
        "note": note,
    }
