"""
backtest/backtest_runner.py  (v9研究開発ブランチ Step1)
=========================================================
全営業日ループでのスコア計算（Phase B）と、
将来リターン付与（Phase C）を1つの関数 run_backtest() に統合する。

【設計レビュー反映①】
  run_daily_scoring() と attach_future_returns() は分離せず、
  run_backtest() 単体に統合する。
  理由：スコア計算用のdfと将来リターン計算用のdfが別々の引数として
  露出すると、実装時に「異なる前処理をした2つのdfを誤って渡す」
  事故が起きやすいため。内部で単一のdfのみを一貫して使用することで
  この事故を構造的に防ぐ。

【設計レビュー反映③】
  required_history（MA75計算に必要な最低日数）をマジックナンバー
  にせず、REQUIRED_HISTORY_DAYS として定数化する。
  Step1時点では可変化・一般化は行わない。
"""

import pandas as pd

# ────────────────────────────────────────────────
# 判定対象日の開始位置を決める定数
#
# technical_analysis.add_indicators() は Close.rolling(75).mean() で
# MA75を計算しており、先頭74行はMA75がNaNになる（75行目で初めて
# 有効な値が出る）。この依存関係を明示するため定数化する。
#
# Step1時点では一般化（v9の別指標に応じた可変化等）は行わない。
# Step2でv9側の必要履歴日数が異なる場合、この定数を調整するか、
# strategy側から要求日数を受け取る形に拡張する。
# ────────────────────────────────────────────────
REQUIRED_HISTORY_DAYS = 75


def run_backtest(df: pd.DataFrame, info: dict, code: str, strategy_fn,
                  horizons: dict | None = None) -> pd.DataFrame:
    """
    全営業日について、その時点までのデータのみでスコアを計算し（Phase B）、
    続けて各営業日について将来リターン・将来ドローダウンを付与する（Phase C）。

    2つの処理を1つの関数に統合し、同一の df を一貫して使用することで、
    「スコア計算用dfと将来リターン計算用dfの不一致」という事故を防ぐ。

    【Look Ahead Bias（未来情報リーク）に関する設計上の注意】
        Phase B（スコア計算）では、各営業日 i について
        df.iloc[:i+1]（0〜i日目まで）のみを strategy_fn に渡す。
        i+1日目以降のデータは一切参照しない。
        Phase C（将来リターン付与）は、Phase Bで計算した「過去のスコア」に
        対して事後的に未来の値を紐付けるものであり、スコア計算そのものには
        一切影響しない。この順序（スコア確定→将来値の付与）を守ることで、
        「未来の値を見てスコアを計算する」というリークを構造的に防止する。

    Args:
        df         : add_indicators適用済みの全期間DataFrame
                     （data_loader.fetch_stock_data()の戻り値）
        info       : get_stock_info()の戻り値
        code       : 証券コード
        strategy_fn: strategy_v8.compute_score_at 等、
                     (window_df, info, code) -> dict の形の関数
        horizons   : 将来リターンを計算する営業日数のオフセット。
                     Noneの場合はデフォルト値を使用。
                     例: {"1w": 5, "1m": 20, "3m": 60}

    Returns:
        1行=1判定対象日のDataFrame。列は以下を含む：
          date, total, finance, dividend, technical, volume（strategy_fnの出力）
          fwd_return_1w, fwd_return_1m, fwd_return_3m（将来騰落率、%）
          max_drawdown_1m（判定日から1ヶ月以内の最大ドローダウン、%）
        判定対象日数が REQUIRED_HISTORY_DAYS 未満の期間はスキップされる。
        期間末尾で将来データが取得できない日は、該当列がNaNになる。
    """
    if horizons is None:
        horizons = {"1w": 5, "1m": 20, "3m": 60}

    if df is None or df.empty:
        return pd.DataFrame()

    n = len(df)
    records = []

    # ── Phase B: 全営業日ループでスコア計算 ──────────────
    # REQUIRED_HISTORY_DAYS - 1 を開始インデックスとする
    # （0-indexedで75行目＝インデックス74以降でMA75が有効になるため）
    start_idx = REQUIRED_HISTORY_DAYS - 1

    for i in range(start_idx, n):
        # その日までのデータのみに絞り込む（未来情報を含めない）
        window_df = df.iloc[: i + 1]

        try:
            sc = strategy_fn(window_df, info, code)
        except Exception:
            # get_latest_values は前日比計算のため最低2行を要求するが、
            # start_idx(=74)は十分に大きいため通常は到達しない例外パス。
            # 万一の異常データ（NaN混入等）はスキップして続行する。
            continue

        record = dict(sc)
        record["_row_index"] = i  # Phase Cで将来値を引くための内部インデックス
        records.append(record)

    if not records:
        return pd.DataFrame()

    result_df = pd.DataFrame(records)

    # ── Phase C: 将来リターン・将来ドローダウンの付与 ──────
    # 同一の df（Phase Bで使ったものと全く同じオブジェクト）から
    # 将来値を取得する。別のdfを渡す余地を排除するため、
    # ここでは引数として新たなdfを受け取らず、必ず関数冒頭で
    # 受け取った df のみを参照する。
    close = df["Close"]

    fwd_returns = {h: [] for h in horizons}
    max_dd_1m = []

    max_dd_window = horizons.get("1m", 20)

    for rec in records:
        i = rec["_row_index"]
        base_close = float(close.iloc[i])

        # 各horizon（1週間後・1ヶ月後・3ヶ月後）の騰落率
        for h_name, h_days in horizons.items():
            target_i = i + h_days
            if target_i < n:
                future_close = float(close.iloc[target_i])
                ret_pct = (future_close - base_close) / base_close * 100
                fwd_returns[h_name].append(ret_pct)
            else:
                # 期間末尾で将来データが存在しない
                fwd_returns[h_name].append(None)

        # 1ヶ月以内（max_dd_window営業日以内）の最大ドローダウン
        end_i = min(i + max_dd_window, n - 1)
        if end_i > i:
            future_slice = close.iloc[i : end_i + 1]
            min_future = float(future_slice.min())
            dd_pct = (min_future - base_close) / base_close * 100
            max_dd_1m.append(dd_pct)
        else:
            max_dd_1m.append(None)

    for h_name in horizons:
        result_df[f"fwd_return_{h_name}"] = fwd_returns[h_name]
    result_df["max_drawdown_1m"] = max_dd_1m

    result_df = result_df.drop(columns=["_row_index"])

    return result_df
