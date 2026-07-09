"""
backtest/comparison.py (v9研究開発ブランチ 比較分析基盤)
====================================================================
同一銘柄・同一期間で実行したv8/v9（将来はv10等も含む）の
バックテスト結果を比較するための純粋な分析関数群。

【設計方針】
  Streamlit依存を持たない（st.は一切importしない）。
  debug_ui.py側がこのモジュールの関数を呼び出し、戻り値のdict/DataFrameを
  表示するだけの構成とすることで、「ロジック（分析）」と「表示」を
  引き続き分離する。

  既存のmetrics.py（calc_max_drawdown / calc_down10_rate /
  describe_score_distribution）は変更せずそのまま再利用する。
  重複した集計ロジックはこのファイルでは持たない。

【将来の投資判断スコアへの接続を見据えた設計】
  build_comparison_summary() の戻り値は strategy_key（"v8"/"v9"/将来の
  "v10"等）をトップレベルのキーとした辞書構造にしている。将来、v10や
  ファンダメンタル評価等を追加する場合も、この構造にキーを1つ追加する
  だけで対応でき、UI側の比較テーブル描画ロジックを変更する必要がない。

  summarize_component_contributions() は、strategy_v9.py側が既に
  「なぜ加点/減点されたか」を components 辞書として保持している点を
  活用し、「どの要因が何日・平均何点、スコアに寄与したか」を集計する。
  これは将来「なぜこのスコアなのか」を利用者に説明する投資判断スコアの
  理由付け生成の元データとして、そのまま使える構造を意図している。
  等級分け（90〜100点=強い買い候補、等）自体は今回実装しない。
"""

import pandas as pd

from backtest.metrics import calc_max_drawdown, calc_down10_rate, describe_score_distribution


# ── スコア推移の突き合わせ ──────────────────────────
def align_score_series(res_df_a: pd.DataFrame, res_df_b: pd.DataFrame,
                        label_a: str = "v8", label_b: str = "v9",
                        score_col: str = "total") -> pd.DataFrame:
    """
    2つのバックテスト結果を日付でつき合わせ、スコア推移を比較できる
    1つのDataFrame（date, {label_a}, {label_b}）に整形する。

    同一銘柄・同一期間で実行していれば判定対象日は基本的に一致するが、
    念のためouter joinとする（欠損日はNaNのまま。st.line_chartに渡せば
    自動的に欠損区間として描画される）。
    """
    a = res_df_a[["date", score_col]].rename(columns={score_col: label_a})
    b = res_df_b[["date", score_col]].rename(columns={score_col: label_b})
    merged = pd.merge(a, b, on="date", how="outer").sort_values("date")
    return merged.reset_index(drop=True)


# ── 高得点日の割合 ──────────────────────────────────
def calc_high_score_ratio(res_df: pd.DataFrame, score_col: str = "total",
                           top_quantile: float = 0.75) -> float | None:
    """
    「そのロジック自身のスコア分布の上位(1-top_quantile)」に入る日の割合(%)を返す。

    v8とv9はスコアの絶対スケールが異なる（v9はv8ベース+加減点のため
    値域が変わる）ため、絶対閾値ではなく相対的な「自分の分布内での
    上位何割か」で高得点日を定義することで、スケールの違いに影響
    されない比較を可能にする。

    Returns:
        高得点日の割合（%）。データが空の場合はNone。
    """
    if res_df.empty or score_col not in res_df.columns:
        return None
    valid = res_df[score_col].dropna()
    if valid.empty:
        return None
    threshold = valid.quantile(top_quantile)
    return float((valid >= threshold).mean() * 100)


# ── リターン傾向 ────────────────────────────────────
def calc_return_tendency(res_df: pd.DataFrame,
                          filtered_df: pd.DataFrame | None = None,
                          horizons=("fwd_return_1w", "fwd_return_1m", "fwd_return_3m")) -> dict:
    """
    将来リターン列（backtest_runner.run_backtestが既に付与済み）の
    平均・中央値を集計する。全営業日ベースと、閾値を満たしたシグナル日
    ベースの両方を返すことで、「シグナル日だけを見た場合にリターン傾向が
    改善しているか」を比較できるようにする。新たなリターン計算は行わない。
    """
    def _describe(df: pd.DataFrame) -> dict:
        out = {}
        for h in horizons:
            if h not in df.columns:
                out[h] = {"mean": None, "median": None}
                continue
            s = df[h].dropna()
            out[h] = {
                "mean": float(s.mean()) if not s.empty else None,
                "median": float(s.median()) if not s.empty else None,
            }
        return out

    result = {"all_days": _describe(res_df)}
    if filtered_df is not None:
        result["signal_days"] = _describe(filtered_df)
    return result


# ── 比較サマリーの統括 ──────────────────────────────
def build_comparison_summary(results: dict[str, dict]) -> dict:
    """
    複数ロジックの結果をまとめて比較サマリーを構築する。

    Args:
        results: {strategy_key: {"res_df":..., "filtered_df":..., "threshold":..., "label":...}}
                 strategy_keyは"v8"/"v9"に限らず、将来"v10"等を追加してもそのまま扱える。

    Returns:
        {strategy_key: {label, judged_days, signal_count, signal_rate,
                         high_score_ratio, max_drawdown, down10_rate,
                         score_dist, return_tendency}, ...}
        strategy_keyごとのフラットな辞書構造にしているのは、将来
        投資判断スコアへ発展させる際、各ブロックをそのまま
        「評価根拠データ」として引き渡せることを意図しているため。
    """
    summary = {}
    for key, r in results.items():
        res_df = r["res_df"]
        filtered_df = r["filtered_df"]
        judged_days = len(res_df)
        signal_count = len(filtered_df)
        signal_rate = (signal_count / judged_days * 100) if judged_days > 0 else None

        summary[key] = {
            "label": r.get("label", key),
            "threshold": r.get("threshold"),
            "judged_days": judged_days,
            "signal_count": signal_count,
            "signal_rate": signal_rate,
            "high_score_ratio": calc_high_score_ratio(res_df),
            "max_drawdown": calc_max_drawdown(filtered_df),
            "down10_rate": calc_down10_rate(filtered_df),
            "score_dist": describe_score_distribution(res_df),
            "return_tendency": calc_return_tendency(res_df, filtered_df),
        }
    return summary


# ── v9加減点要因の集計（将来の「理由付け」説明文生成の元データ） ──
def summarize_component_contributions(res_df: pd.DataFrame) -> pd.DataFrame | None:
    """
    v9スコアの内訳（strategy_v9.compute_score_at_v9が返す"components"辞書）を
    全営業日について集計し、「どの加減点要因が何日発火し、平均何点
    寄与したか」を1行=1コンポーネントのDataFrameにまとめる。

    v8の結果（"components"列を持たない）が渡された場合はNoneを返す。
    """
    if res_df.empty or "components" not in res_df.columns:
        return None

    all_names = set()
    for comp in res_df["components"]:
        if isinstance(comp, dict):
            all_names.update(comp.keys())

    records = []
    for name in sorted(all_names):
        values = res_df["components"].apply(lambda c: c.get(name, 0.0) if isinstance(c, dict) else 0.0)
        fired = values[values != 0]
        records.append({
            "component": name,
            "fired_days": int((values != 0).sum()),
            "fired_rate_pct": float((values != 0).mean() * 100),
            "avg_contribution_when_fired": float(fired.mean()) if not fired.empty else 0.0,
            "total_contribution": float(values.sum()),
        })

    return pd.DataFrame(records).sort_values("fired_days", ascending=False).reset_index(drop=True)
