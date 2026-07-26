"""
strategy_v9_composite.py  v9 Research (Phase7-9: Composite Strategy)
=======================================================================
RSI・Volume・Dividend・PER業種別の4つのv9研究戦略を重み付き合成し、
単一の総合スコアを算出する複合評価戦略。

【責務】
  strategy_v9_rsi.py・strategy_v9_volume.py・strategy_v9_dividend.py・
  strategy_v9_per_sector.pyの各compute_score()を呼び出し、それぞれの
  "total"（0〜100点）を重み付き平均して単一の総合スコアを算出する。
  4戦略と同一の正式strategy_fn Interface（backtest_runner.run_backtest()
  から`strategy_fn(window_df, info, code)`の形で呼び出される契約）に
  準拠したcompute_score(window_df, info, code) -> dictを提供する。

【Interface契約（4戦略ファイルと共通）】
  compute_score(window_df: pd.DataFrame, info: dict, code: str) -> dict

  戻り値：
    "date" : window_df.index[-1]（文字列化・ISO変換はしない。
             walkforward.py側の_to_json_safe()が後段で変換するため）
    "total": int（0〜100の複合スコア。必須キー）
    "note" : str（各構成戦略のスコア内訳を含む短い説明。
             非契約的な補助情報）
    "components" は含めない（4戦略ファイルと同じ方針。decision_
    pipeline.pyの実装確認により、この列を持たないres_dfを渡しても
    エラーにならないことを確認済みの方針を踏襲する）。

【v8.1 Stableとの関係（重要）】
  technical_analysis.py・strategy_v8.py・buy_timing.py・
  scoring_config.py・investment_judge.py・recommend.py 等、
  v8.1側の既存コードは一切importしない。使用するのはtyping・pandas、
  および同じresearch/strategy/配下の4つのv9研究戦略モジュール
  （strategy_v9_rsi・strategy_v9_volume・strategy_v9_dividend・
  strategy_v9_per_sector）のみである。

  【既存4戦略ファイルとの関係（重要・importの扱いについて）】
  本ファイルが行っているのは、v8.1側のロジックのコピー＆改造ではなく、
  既にPhase7-2〜7-6でInterface契約に準拠する形で独立実装済みの
  4つのv9研究戦略モジュールを、Composite Strategyとしてそのまま
  部品として呼び出す（import する）ことである。これらは同じv9研究
  ラインの正式な成果物であり、v8.1側の変更禁止対象ファイルではない
  ため、importして再利用することは「v8.1側コードのコピー禁止」
  方針とは矛盾しない。逆に、4戦略のロジックをここへコピー＆再実装
  すると、DEVELOPMENT_RULE.mdが禁止する「重複コードの増加」に
  該当してしまうため、importによる再利用を正式な設計として採用する。
  既存4戦略ファイル自体への変更は一切行っていない。

【合成方針（初期実装・Phase7-9初期版）】
  各構成戦略のスコア（0〜100点）に対して、COMPOSITE_WEIGHTSで定義した
  重みを掛けた加重平均を算出し、0〜100点の総合スコアとする。

  初期実装では4戦略を均等（各25%）に重み付けする。将来的にWalk Forward
  の検証結果に基づき重みを調整できるよう、重みをロジックから分離した
  1つの辞書定数（COMPOSITE_WEIGHTS）として保持しており、重み変更時は
  この定数のみを差し替えれば済む構成にしている（4戦略ファイルの
  「ロジックと定数の分離」方針を踏襲）。COMPOSITE_WEIGHTSの合計は
  常に1.0になっている必要があり、モジュール読込時に検証する
  （_validate_weights()参照）。

  各構成戦略の呼び出しは、想定外の例外（本来は各戦略が内部で
  安全側フォールバックする契約だが、将来の戦略追加や改修で契約が
  破られた場合に備える防御的実装）が発生しても複合スコア全体が
  落ちないよう、1戦略ずつtry/exceptで保護し、例外時はその戦略の
  スコアを0点として扱う。

【安全側フォールバック（0点）となるケース】
  以下のいずれかに該当する場合、該当する構成戦略のスコアを0点として
  扱う（各戦略ファイル自身の安全側フォールバック契約を尊重する形）。
    - 各戦略のcompute_score()が0点を返した場合（各戦略内部の
      安全側フォールバックがそのまま反映される）
    - 各戦略のcompute_score()の呼び出し自体が例外を送出した場合
      （契約違反への防御的フォールバック。本来発生しない想定）
    - 各戦略のcompute_score()が"total"キーを持たない、またはtotalが
      数値化できない場合（同上の防御的フォールバック）
  window_df・infoそのものがNone等で不正な場合も、各構成戦略が
  自身の契約に従って安全側の値を返すため、本ファイル側で個別の
  事前チェックは行わない（4戦略の既存の安全側設計をそのまま信頼し、
  重複したチェックロジックを持たないため）。
"""

import pandas as pd

from strategy_v9_dividend import compute_score as _dividend_compute_score
from strategy_v9_per_sector import compute_score as _per_sector_compute_score
from strategy_v9_rsi import compute_score as _rsi_compute_score
from strategy_v9_volume import compute_score as _volume_compute_score

# ── Composite重み候補パラメータ（Phase7-9初期版） ──────────────
# 初期実装は4戦略均等（各25%）とする。将来的にWalk Forwardの検証
# 結果を踏まえて調整することを前提に、ロジックとは分離してこの辞書
# 定数にのみ重み定義を持たせている（4戦略ファイルと同じ「ロジックと
# 定数の分離」方針）。将来的にconfig/research_settings.json経由での
# 複数重みパターン比較へ置き換えることも想定する。
COMPOSITE_WEIGHTS: dict[str, float] = {
    "rsi": 0.25,
    "volume": 0.25,
    "dividend": 0.25,
    "per_sector": 0.25,
}

# 重み合計の許容誤差（浮動小数点誤差対策）。
_WEIGHT_SUM_TOLERANCE = 1e-6

# 各構成戦略の呼び出し関数と表示ラベルの対応表。
# COMPOSITE_WEIGHTSのキーと1:1で対応させる。
_COMPONENT_FUNCS = {
    "rsi": (_rsi_compute_score, "RSI"),
    "volume": (_volume_compute_score, "Volume"),
    "dividend": (_dividend_compute_score, "Dividend"),
    "per_sector": (_per_sector_compute_score, "PER業種別"),
}

# 個別戦略呼び出しが失敗した場合のフォールバックスコア（安全側）。
_COMPONENT_SCORE_ON_ERROR = 0


def _validate_weights(weights: dict[str, float]) -> None:
    """
    COMPOSITE_WEIGHTSの整合性を検証する。

    - _COMPONENT_FUNCSと同じキー集合であること
    - 重みの合計が1.0（許容誤差内）であること
    - 各重みが0以上であること

    不整合な場合はValueErrorを送出する（モジュール読込時に検出し、
    誤った重み設定のままWalk Forwardが走ってしまう事態を防ぐため）。
    """
    if set(weights.keys()) != set(_COMPONENT_FUNCS.keys()):
        raise ValueError(
            "COMPOSITE_WEIGHTSのキーが構成戦略と一致しません。"
            f"期待: {sorted(_COMPONENT_FUNCS.keys())} / 実際: {sorted(weights.keys())}"
        )
    if any(w < 0 for w in weights.values()):
        raise ValueError("COMPOSITE_WEIGHTSに負の重みが含まれています。")

    total = sum(weights.values())
    if abs(total - 1.0) > _WEIGHT_SUM_TOLERANCE:
        raise ValueError(f"COMPOSITE_WEIGHTSの合計は1.0である必要があります（現在: {total}）。")


_validate_weights(COMPOSITE_WEIGHTS)


def _call_component_safely(
    func, window_df: pd.DataFrame, info: dict, code: str, label: str
) -> tuple[int, str]:
    """
    1つの構成戦略のcompute_score()を安全に呼び出す。

    契約上は各戦略が内部で安全側フォールバックする設計だが、将来の
    改修等で契約が破られた場合に備え、例外・不正な戻り値も
    ここで防御的に0点へフォールバックする。

    Returns:
        (score, note) のタプル。
    """
    try:
        result = func(window_df, info, code)
    except Exception as exc:  # noqa: BLE001 - 防御的フォールバックのため意図的に広く捕捉
        return _COMPONENT_SCORE_ON_ERROR, f"{label}呼び出しエラー（{type(exc).__name__}）"

    if not isinstance(result, dict) or "total" not in result:
        return _COMPONENT_SCORE_ON_ERROR, f"{label}の戻り値が契約に違反しています（totalキーなし）"

    try:
        score = int(result["total"])
    except (TypeError, ValueError):
        return _COMPONENT_SCORE_ON_ERROR, f"{label}のtotalが数値化できません"

    return score, result.get("note", "")


def get_component_scores(window_df: pd.DataFrame, info: dict, code: str) -> dict:
    """
    4つの構成戦略それぞれのスコア・判定理由を個別に取得する。

    compute_score()の正式Interface契約（"components"キーを含めない）
    とは別に、研究・分析目的で内訳を確認したい場合のための補助関数
    として提供する（compute_score()自体はこの関数を使わずシンプルに
    実装しており、契約を満たすためだけの最小経路を保っている）。

    Returns:
        dict: {theme_id: {"score": int, "note": str}, ...}
    """
    return {
        theme_id: {
            "score": (r := _call_component_safely(func, window_df, info, code, label))[0],
            "note": r[1],
        }
        for theme_id, (func, label) in _COMPONENT_FUNCS.items()
    }


def compute_score(window_df: pd.DataFrame, info: dict, code: str) -> dict:
    """
    RSI・Volume・Dividend・PER業種別の4戦略を重み付き合成し、
    0〜100点の総合スコアを算出する。

    4戦略ファイルと同一の正式strategy_fn Interfaceに準拠した
    シグネチャ（backtest_runner.run_backtest()から
    `strategy_fn(window_df, info, code)` の形で呼び出される）。

    Args:
        window_df: 判定対象日までの行のみに絞り込まれたDataFrame。
                   そのまま各構成戦略へ渡す。
        info     : yfinanceの銘柄情報。そのまま各構成戦略へ渡す。
        code     : 証券コード。そのまま各構成戦略へ渡す。

    Returns:
        dict:
          "date" : window_df.index[-1]（文字列化・ISO変換はしない）。
                   window_dfが空またはNoneで取得不能な場合はNoneとする。
          "total": int（0〜100の複合スコア。COMPOSITE_WEIGHTSに基づく
                   加重平均を四捨五入したもの）
          "note" : str（各構成戦略のスコア内訳を含む短い説明。
                   非契約的な補助情報）
          "components" は含めない。
    """
    weighted_sum = 0.0
    note_parts = []

    for theme_id, (func, label) in _COMPONENT_FUNCS.items():
        score, _ = _call_component_safely(func, window_df, info, code, label)
        weight = COMPOSITE_WEIGHTS[theme_id]
        weighted_sum += score * weight
        note_parts.append(f"{label}={score}pt(重み{weight*100:.0f}%)")

    total = int(round(weighted_sum))
    total = min(100, max(0, total))  # 丸め誤差での範囲外逸脱を防ぐ安全策

    note = f"複合スコア{total}pt [" + ", ".join(note_parts) + "]"

    date = window_df.index[-1] if window_df is not None and not window_df.empty else None

    return {
        "date": date,
        "total": total,
        "note": note,
    }
