"""
stock_data.py
=============
yfinanceによる株価データ取得 + 日本語銘柄名マスター

【v5.0 追加】
  - JP_NAMES: 証券コード → 日本語銘柄名の対応辞書（④英語→日本語化）
  - get_display_name(): JP_NAMESを優先して日本語名を返す
"""

import yfinance as yf
import pandas as pd
import numpy as np
import streamlit as st

# ────────────────────────────────
# JP_NAMES は candidate_stocks.DISPLAY_NAMES への後方互換エイリアス（P4-2対応）
# 銘柄の正式名称は candidate_stocks.py の DISPLAY_NAMES を編集すること
# ────────────────────────────────
from candidate_stocks import DISPLAY_NAMES as JP_NAMES


@st.cache_data(ttl=1800)
def get_price_data(code: str, period: str = "1y") -> pd.DataFrame | None:
    """株価の時系列データ（OHLCV）を取得する"""
    try:
        ticker = yf.Ticker(f"{code}.T")
        df = ticker.history(period=period, auto_adjust=True)
        if df.empty:
            return None
        df.index = df.index.tz_localize(None)
        return df
    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        return None


@st.cache_data(ttl=1800)
def get_stock_info(code: str) -> dict:
    """銘柄の基本情報を取得する"""
    try:
        ticker = yf.Ticker(f"{code}.T")
        info = ticker.info
        return info if info else {}
    except Exception:
        return {}


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
    """数値を安全に文字列変換"""
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
    """
    銘柄名を返す。JP_NAMESを優先して日本語名を返す。

    優先順:
      1. JP_NAMES（日本語マスター）
      2. yfinanceの longName / shortName
      3. コード番号
    """
    # ① 日本語マスターから取得（最優先）
    jp = JP_NAMES.get(code)
    if jp:
        return jp
    # ② yfinanceから取得
    return (
        info.get("longName") or
        info.get("shortName") or
        f"銘柄コード {code}"
    )


def safe_float(d: dict, key: str) -> float | None:
    """
    辞書から安全に数値を取り出す（旧 _nv）。
    None・NaN・Inf はすべて None を返す。
    recommend.py / technical_analysis.py / dividend_ranking.py 共通で使用。
    """
    v = d.get(key)
    if v is None:
        return None
    try:
        f = float(v)
        return None if (np.isnan(f) or np.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def fmt_dividend_pct(dy) -> float:
    """
    yfinance の dividendYield を % に変換して返す（旧 _div_pct）。
    - yfinance は 0.03 形式（小数）と 3.0 形式（%）が混在するため正規化する
    - 変換後が 0.1〜30 の範囲外（異常値）は 0.0 を返す
    - None・変換失敗時は 0.0 を返す（フォールバック）
    """
    try:
        v = float(dy)
        p = v * 100 if v <= 1.0 else v
        return p if 0.1 <= p <= 30 else 0.0
    except (TypeError, ValueError):
        return 0.0


def fmt_dividend_str(dy) -> str:
    """
    yfinance の dividendYield を表示用文字列に変換して返す（旧 _fmt_div）。
    - 有効値: "3.50%" 形式で返す
    - 無配当（None）: "無配当" を返す
    - 異常値・変換失敗: "―" を返す
    """
    if dy is None:
        return "無配当"
    try:
        v = float(dy)
        p = v * 100 if v <= 1.0 else v
        return f"{p:.2f}%" if 0.1 <= p <= 30 else "―"
    except (TypeError, ValueError):
        return "―"
