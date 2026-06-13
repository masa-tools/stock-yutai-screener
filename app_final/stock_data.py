"""
stock_data.py
=============
yfinanceで日本株データを取得するモジュール

日本株のティッカー形式: コード + ".T"
例: 7203 → 7203.T（トヨタ）
"""

import yfinance as yf
import pandas as pd
import numpy as np
import streamlit as st


# ────────────────────────────────
# 株価データ取得（30分キャッシュ）
# ────────────────────────────────
@st.cache_data(ttl=1800)
def get_price_data(code: str, period: str = "1y") -> pd.DataFrame | None:
    """
    株価の時系列データ（OHLCV）を取得する

    Args:
        code  : 4桁の証券コード（例: "7203"）
        period: 取得期間 "6mo" / "1y" / "2y"

    Returns:
        DataFrame または None（取得失敗時）
    """
    try:
        ticker = yf.Ticker(f"{code}.T")
        df = ticker.history(period=period, auto_adjust=True)
        if df.empty:
            return None
        # タイムゾーンを除去（mplfinanceで必要）
        df.index = df.index.tz_localize(None)
        return df
    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        return None


@st.cache_data(ttl=1800)
def get_stock_info(code: str) -> dict:
    """
    銘柄の基本情報（PER・PBR・配当など）を取得する

    Returns:
        銘柄情報の辞書。失敗時は空辞書。
    """
    try:
        ticker = yf.Ticker(f"{code}.T")
        info = ticker.info
        return info if info else {}
    except Exception:
        return {}


# ────────────────────────────────
# 数値フォーマット ユーティリティ
# ────────────────────────────────
def fmt_yen(num) -> str:
    """大きな数字を「億円・兆円」で表示"""
    if num is None:
        return "―"
    try:
        n = float(num)
        if np.isnan(n):
            return "―"
        if n >= 1e12:
            return f"{n/1e12:.1f}兆円"
        if n >= 1e8:
            return f"{n/1e8:.0f}億円"
        return f"{n:,.0f}円"
    except Exception:
        return "―"


def fmt_num(val, decimals: int = 2, suffix: str = "") -> str:
    """数値を安全に文字列変換（None・NaN対応）"""
    if val is None:
        return "―"
    try:
        f = float(val)
        if np.isnan(f) or np.isinf(f):
            return "―"
        return f"{f:.{decimals}f}{suffix}"
    except Exception:
        return "―"


def get_display_name(info: dict, code: str) -> str:
    """銘柄名を取得（取れない場合はコードを返す）"""
    return (
        info.get("longName") or
        info.get("shortName") or
        f"銘柄コード {code}"
    )


def get_min_investment(info: dict, close: float) -> str:
    """最低投資金額を計算して表示用文字列で返す"""
    try:
        # lotSize = 単元株数（通常100株）
        lot = int(info.get("lotSize") or 100)
        amount = close * lot
        return f"¥{amount:,.0f}（{lot}株単元）"
    except Exception:
        return "―"
