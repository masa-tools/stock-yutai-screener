"""
strategy_v9_per_sector_asymmetric.py  v9 Research (Phase9: 非対称PER評価モデル)
=================================================================================
「業種別PER山型評価（strategy_v9_per_sector.py）における低PER側の一律減点は、
長期投資銘柄評価として過剰ではないか」という仮説を検証するための、
非対称減衰カーブによるPER業種別評価モデル。

【本ファイルの位置付け（重要）】
  本ファイルはPhase9研究における「比較対象案（非対称PERモデル）」の実装であり、
  Baselineである strategy_v9_per_sector.py を置き換えるものではない。
  strategy_v9_per_sector.py は本ファイルの追加によって一切変更されない
  （既存ファイル本体には触れていない）。両ファイルは
  strategy_comparison.py 等から並行して呼び出され、Walk Forwardで
  比較評価される前提で設計している。

【責務】
  strategy_v9_per_sector.py・strategy_v9_rsi.py・strategy_v9_volume.py・
  strategy_v9_dividend.pyと同一の正式strategy_fn Interface契約
  （backtest_runner.run_backtest()から`strategy_fn(window_df, info, code)`
  の形で呼び出される契約）に準拠した compute_score(window_df, info, code)
  -> dict を提供する。

【Interface契約（既存戦略ファイルと共通）】
  compute_score(window_df: pd.DataFrame, info: dict, code: str) -> dict

  戻り値：
    "date" : window_df.index[-1]（文字列化・ISO変換はしない。
             walkforward.py側の_to_json_safe()が後段で変換するため）
    "total": int（0〜100の非対称PER評価スコア。必須キー）
    "note" : str（判定理由の短い説明。非契約的な補助情報）
    "components" は含めない（既存戦略ファイルと同じ方針）。

【strategy_v9_per_sector.py との関係（重要・データ再利用について）】
  業種別PERレンジ定義（SECTOR_PER_RANGES）は、strategy_v9_per_sector.py
  から直接importして再利用する。本研究のPhase9固定条件
  （「SECTOR_PER_RANGESは既存値を完全維持」「sector分類変更禁止」）を
  満たすため、レンジ値そのものを本ファイル内に再定義・複製しない。
  これにより、strategy_v9_per_sector.py 側でSECTOR_PER_RANGESが
  変更されない限り、本ファイルの業種別レンジも常に同一の値を
  参照し続けることが構造的に保証される。

  PER抽出ロジック（trailingPE優先・forwardPEフォールバック）は、
  strategy_v9_per_sector.py の _extract_per() と同一の挙動を本ファイル
  内に独立して再実装する（アンダースコア始まりの非公開関数を他モジュール
  からimportする設計は避け、モジュール間の結合を弱く保つため）。
  ロジックの中身自体はPhase9固定条件「PER取得方法変更禁止」に従い、
  strategy_v9_per_sector.py と完全に同一の挙動としている。

【v8.1 Stableとの関係】
  technical_analysis.py・strategy_v8.py・buy_timing.py・
  scoring_config.py・investment_judge.py・recommend.py 等、
  v8.1側の既存コードは一切importしない。使用するのは typing・pandas、
  および同じresearch/strategy/配下の strategy_v9_per_sector.py
  （SECTOR_PER_RANGESのみ）である。

【変更対象の範囲（Phase9固定条件の反映）】
  strategy_v9_per_sector.py との差分は、PERスコア変換関数（PERの値を
  0〜100点へ変換する部分）のみである。以下は一切変更していない。
    - SECTOR_PER_RANGES（業種別レンジ定義そのもの）
    - 業種分類（sector文字列の扱い）
    - PER取得方法（trailingPE優先・forwardPEフォールバック）
    - 異常値処理方針（PER None/NaN/inf/負値 → 0点）
    - Composite等、他モジュールへの統合（本ファイルは単独のstrategy_fn
      としてのみ存在し、strategy_v9_composite.py 等へは一切組み込んでいない）

【非対称減衰モデルの設計（Phase9 Architectレビュー確定版）】
  strategy_v9_per_sector.py の離散5段階ステップ評価
  （100 / 70 / 40 / 20 / 0）を、同一の境界値（ideal/good/caution帯の
  上下限）をアンカー点とする連続関数に置き換え、かつ
  ideal帯からの乖離に対する減点の傾きを左右非対称にする。

    - ideal帯内：Baselineと同じく満点（100点）
    - 高PER側（ideal_high超過）：ALPHA_HIGH（>1）を用いて、
      Baselineより急な速度で減点する（過熱リスクを強く見る）
    - 低PER側（ideal_low未満）：ALPHA_LOW（<1）を用いて、
      Baselineより緩やかな速度で減点する（割安の可能性を残す）

  下限保証（例：「低PERは何点であっても◯◯点を下回らない」という
  特別ルール）は設けていない。Architectレビュー（①）にて、下限保証が
  「減点緩和」ではなく「低PER優遇」に相当するとの指摘を受け、本モデル
  では撤廃した。ALPHA_LOW<1という単一の傾き調整のみによって非対称性を
  表現しており、caution_lowを超えて更に低いPERに対しては、Baseline
  同様、最終的に0点へ収束する（下記「スコア到達点」参照）。

  【スコア到達点（参考・仕様として明記）】
    高PER側：score=0 に到達するPERは
      p = ideal_high + (caution_high - ideal_high) / ALPHA_HIGH
    低PER側：score=0 に到達するPERは
      p = ideal_low - (ideal_low - caution_low) / ALPHA_LOW
    ALPHA_HIGH=1.5・ALPHA_LOW=0.5の場合、高PER側はcaution_highに
    到達する前に0点となり、低PER側はcaution_lowを超えてさらに
    下がった地点で0点となる（Baselineよりゆっくり0へ近づく）。

【固定係数（Walk Forward結果を見て調整しない・Phase9研究ルール）】
  ALPHA_HIGH = 1.5 : 高PER側の減点速度係数（Baseline相当=1.0の1.5倍）
  ALPHA_LOW  = 0.5 : 低PER側の減点速度係数（Baseline相当=1.0の0.5倍）
  この2値は本研究における唯一の可変パラメータであり、Walk Forward
  実行前に確定し、Validation結果・Forward結果を見た事後調整は行わない
  （V9_RESEARCH_ARCHITECTURE.md §13 過学習対策の遵守）。

【解釈上の注意（研究結果の解釈時に必ず考慮すること）】
  strategy_v9_per_sector.py（離散ステップ関数）との比較結果には、
  以下の2つの効果が混在する。
    (A) 非対称化効果：ALPHA_HIGH ≠ ALPHA_LOW によって生じる、
        高PER側・低PER側での警戒の強さの違いによる効果
    (B) 連続化効果：離散5段階ステップ関数を連続関数に変えたことに
        よる、境界値をまたぐ際の急激なスコア変化の解消による効果
  Baselineと本モデルの2群比較のみでは、改善（または悪化）が
  (A)非対称化によるものか(B)連続化によるものかを切り分けられない。
  本研究の結論は、原則として「非対称モデル全体としての効果」に
  留めること。非対称性そのものの効果を主張する場合は、
  ALPHA_HIGH=ALPHA_LOW=1.0（対称・連続版）との追加比較が必要になる
  点を、Architectとの合意事項として申し送る。

【安全側フォールバック（0点）となるケース】
  strategy_v9_per_sector.py と完全に同一の方針・同一の判定条件を用いる
  （Phase9固定条件「異常値処理は既存per_sectorと同じ扱い」に従う）。
    - infoがNoneまたは辞書でない
    - "sector"キーが存在しない、値がNone/空文字/文字列でない
    - sectorがSECTOR_PER_RANGESに未収録（非対応業種）
    - trailingPE・forwardPEのいずれもNone/NaN/キー欠損
    - PERデータが数値化できない
    - PERが負値（赤字等、PERとしての意味を持たない）
  いずれの場合も、"note"に該当理由を明記する。
"""

from typing import Optional

import pandas as pd

from strategy_v9_per_sector import SECTOR_PER_RANGES

# ── Phase9 固定係数（Architectレビュー確定版・調整禁止） ──────────
# Walk Forward実行前に確定し、以降の検証結果を見た再調整は行わない。
# ALPHA_HIGH > 1.0 : 高PER側（過熱リスク）を Baseline相当より強く減点
# ALPHA_LOW  < 1.0 : 低PER側（割安可能性）を Baseline相当より緩やかに減点
ALPHA_HIGH: float = 1.5
ALPHA_LOW: float = 0.5

# 判定不能・高リスクな場合の安全側フォールバックスコア。
# strategy_v9_per_sector.py と同一の値・同一の判定条件を用いる。
_SCORE_NO_DATA = 0
_SCORE_HIGH_RISK = 0
_SCORE_IDEAL = 100

# スコアの理論上限・下限（丸め誤差での範囲外逸脱を防ぐ）。
_SCORE_MAX = 100
_SCORE_MIN = 0


def _extract_per(info: dict) -> tuple[Optional[float], str]:
    """
    infoからPERを抽出する。trailingPEを優先し、None/NaNの場合は
    forwardPEにフォールバックする。

    strategy_v9_per_sector.py の _extract_per() と同一の挙動を持つ
    独立実装（Phase9固定条件「PER取得方法変更禁止」に従い、ロジックの
    中身は変更していない）。非公開関数の他モジュールからのimportを
    避けるため、モジュール内に同一ロジックを保持する。

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


def _clamp_score(value: float) -> float:
    """スコアを[0, 100]へ丸め込む（丸め誤差での範囲外逸脱を防ぐ）。"""
    return max(_SCORE_MIN, min(_SCORE_MAX, value))


def _score_from_per_sector_asymmetric(info: Optional[dict]) -> tuple[int, str]:
    """
    infoディクショナリの業種・PER情報から、非対称減衰カーブに基づく
    0〜100点のスコアと、判定理由の短い説明文を返す。

    業種別の適正PERレンジ（SECTOR_PER_RANGES、strategy_v9_per_sector.py
    からimportした既存値をそのまま使用）をアンカー点として、
    ideal帯からの乖離に対する減点速度を左右非対称にする。

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
    _good_low, _good_high = ranges["good"]  # 非対称モデルでは境界のアンカーとしては未使用（ideal/cautionのみ使用）
    caution_low, caution_high = ranges["caution"]

    # ideal帯内：Baselineと同じく満点
    if ideal_low <= per_value <= ideal_high:
        return _SCORE_IDEAL, (
            f"PER {per_value:.1f}倍（{source}）: 業種「{sector}」の理想帯"
            f"（{ideal_low:.1f}〜{ideal_high:.1f}倍）内、適正水準"
        )

    # 高PER側（過熱リスク）：ALPHA_HIGHによる急な減衰
    if per_value > ideal_high:
        denom = caution_high - ideal_high
        distance_ratio = (per_value - ideal_high) / denom if denom > 0 else 1.0
        raw_score = 100.0 * (1.0 - ALPHA_HIGH * distance_ratio)
        score = int(round(_clamp_score(raw_score)))
        return score, (
            f"PER {per_value:.1f}倍（{source}）: 業種「{sector}」の理想帯上限"
            f"（{ideal_high:.1f}倍）超、非対称モデルで強め減点"
            f"（ALPHA_HIGH={ALPHA_HIGH}, score={score}pt）"
        )

    # 低PER側（割安可能性）：ALPHA_LOWによる緩やかな減衰
    denom = ideal_low - caution_low
    distance_ratio = (ideal_low - per_value) / denom if denom > 0 else 1.0
    raw_score = 100.0 * (1.0 - ALPHA_LOW * distance_ratio)
    score = int(round(_clamp_score(raw_score)))
    return score, (
        f"PER {per_value:.1f}倍（{source}）: 業種「{sector}」の理想帯下限"
        f"（{ideal_low:.1f}倍）未満、非対称モデルで緩やか減点"
        f"（ALPHA_LOW={ALPHA_LOW}, score={score}pt）"
    )


def compute_score(window_df: pd.DataFrame, info: dict, code: str) -> dict:
    """
    PERを業種別の適正レンジに照らし、非対称減衰カーブで
    「割安・適正・割高」を0〜100点で評価する。

    strategy_v9_per_sector.py・strategy_v9_rsi.py・strategy_v9_volume.py・
    strategy_v9_dividend.pyと同一の正式strategy_fn Interfaceに準拠した
    シグネチャ（backtest_runner.run_backtest()から
    `strategy_fn(window_df, info, code)` の形で呼び出される）。

    Args:
        window_df: 判定対象日までの行のみに絞り込まれたDataFrame。
                   本実装ではスコア算出には使用せず、戻り値の
                   "date"を決定するためだけに参照する
                   （strategy_v9_per_sector.pyと同じ理由）。
        info     : yfinanceの銘柄情報。本実装では"sector"・
                   "trailingPE"・"forwardPE"のみを参照する。
        code     : 証券コード（本実装では未使用。将来の拡張に備えて
                   契約上受け取る）。

    Returns:
        dict:
          "date" : window_df.index[-1]（文字列化・ISO変換はしない）。
                   window_dfが空またはNoneで取得不能な場合はNoneとする。
          "total": int（0〜100の非対称PER評価スコア）
          "note" : str（判定理由の短い説明。非契約的な補助情報）
          "components" は含めない。
    """
    score, note = _score_from_per_sector_asymmetric(info)

    date = window_df.index[-1] if window_df is not None and not window_df.empty else None

    return {
        "date": date,
        "total": score,
        "note": note,
    }
