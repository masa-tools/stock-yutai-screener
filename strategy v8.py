"""
backtest/strategy_v8.py  (v9研究開発ブランチ Step1)
====================================================
既存v8スコアリングロジック（calc_simple_score）を、
「過去の任意時点までのwindow dfを受け取り、その時点のスコアを返す」
形にラップするモジュール。

【設計方針】
  calc_simple_score / get_latest_values の中身には一切手を加えない。
  呼び出し順序を揃えるだけの薄いラッパーとする。
  （既存4系統への変更禁止という制約を厳守するため）
"""

from technical_analysis import get_latest_values, calc_simple_score


def compute_score_at(window_df, info: dict, code: str) -> dict:
    """
    ある時点までのwindow_dfを受け取り、その時点でのv8スコアを計算する。

    【Look Ahead Bias（未来情報リーク）に関する設計上の注意】

    ① OHLCVベースのテクニカル指標（MA25/MA75/RSI/MACD等）について：
       これらはリークしない。data_loader.fetch_stock_data() で
       add_indicators() を「全期間に対して1回だけ」適用しているが、
       pandasのrolling()/ewm()は各行の計算にその行より過去のデータ
       しか使わないため、window_df.iloc[-1]（=判定対象日）の指標値は
       判定対象日以前のデータのみから計算された値と一致する。
       window_df 自体も呼び出し側（backtest_runner.py）で
       「判定対象日までの行のみ」に絞り込まれた状態で渡される前提。

    ② finance系スコア（PER・PBR・配当利回り）について：
       【重要・参考値としての利用に留めること】
       この関数が受け取る info は、data_loader.fetch_stock_data() で
       取得した「現在時点」のyfinanceスナップショットである。
       yfinanceには過去の特定時点のPER/PBR/配当利回りを遡って取得する
       仕組みが存在しないため、window_dfがどの日付を指していても、
       finance系スコア（calc_simple_scoreの内訳の一部）は常に
       「現在時点の財務指標」を使って計算されることになる。
       これは軽微だが実質的な未来情報リークであり、
       finance/dividendスコアの解釈は「現在の財務指標を前提とした
       参考値」として扱い、technical/volumeスコアと同列の
       厳密な過去再現値とは区別すること。
       感度分析が必要な場合は、calc_simple_score()の戻り値内訳
       （finance/dividend/technical/volume）のうち technical のみを
       抽出して集計することで、リークの影響を除いた評価も可能。

    Args:
        window_df: 判定対象日までの行のみに絞り込まれたDataFrame
                   （add_indicators適用済み。呼び出し側で
                   df.iloc[:i+1] 等により切り出したもの）
        info     : get_stock_info()の戻り値（現在時点のスナップショット）
        code     : 証券コード

    Returns:
        {
            "date" : 判定対象日（window_df.index[-1]）,
            "total": calc_simple_scoreの合計スコア,
            "finance": ...,
            "dividend": ...,
            "technical": ...,
            "volume": ...,
            （calc_simple_scoreの戻り値をそのまま展開したもの）
        }
    """
    tv = get_latest_values(window_df)
    sc = calc_simple_score(info, tv, code)

    result = {"date": window_df.index[-1]}
    result.update(sc)
    return result
