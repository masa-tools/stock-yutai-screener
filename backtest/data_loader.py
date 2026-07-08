"""
backtest/data_loader.py  (v9研究開発ブランチ Step1)
====================================================
バックテスト用のデータ取得・整形専用モジュール。

【設計方針】
  既存の stock_data.py / technical_analysis.py の関数を
  そのまま呼び出すだけの薄いラッパーとする。
  ロジックの変更・追加は一切行わない（既存4系統への影響ゼロを担保）。

【Step1スコープ】
  対象: トヨタ（7203）1銘柄・過去1年（period="1y"）固定。
  複数銘柄対応（Step2以降）を見据え、引数は code を受け取る形にしておく。
"""

from stock_data import get_price_data, get_stock_info
from technical_analysis import add_indicators


def fetch_stock_data(code: str, period: str = "1y"):
    """
    バックテスト用に価格データ・指標付きdf・infoを取得する。

    既存の get_price_data / add_indicators / get_stock_info を
    順に呼び出すだけで、独自の計算ロジックは持たない。

    Args:
        code  : 証券コード（Step1では "7203" 固定で使用する想定）
        period: yfinanceの取得期間（Step1では "1y" 固定）

    Returns:
        (df, info) のタプル
          df  : add_indicators適用済みのDataFrame（MA25/MA75/RSI/MACD等の列を含む）
                取得失敗時は None
          info: get_stock_info()の戻り値（dict）。取得失敗時は空dict {}

    【Look Ahead Biasに関する注意】
        本関数はデータ取得のみを行い、日付によるフィルタリングは行わない。
        全期間のdfをそのまま返すため、呼び出し側（backtest_runner.py）で
        「その時点までのデータのみ」に絞り込む処理を必ず行うこと。
    """
    df_raw = get_price_data(code, period=period)
    if df_raw is None or df_raw.empty:
        return None, {}

    df = add_indicators(df_raw)
    info = get_stock_info(code)

    return df, info
