"""
technical_analysis.py
=====================
テクニカル指標の計算・チャート描画・簡易スコアリング

【前半MVPで含む機能】
  - 移動平均線（25日・75日）
  - RSI（買われすぎ・売られすぎ判定）
  - MACD（トレンド方向判定）
  - 出来高分析
  - ローソク足チャート（パステルカラー）
  - 簡易スコアリング（API不要・Python只）
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")          # サーバー環境ではGUI不要
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm  # P5-1: フォント強制ロード用
import mplfinance as mpf
import streamlit as st
import os
from io import BytesIO
from stock_data import safe_float, fmt_dividend_pct
from scoring_config import (
    RSI_OVERSOLD,
    RSI_SLIGHTLY_OVERSOLD,
    RSI_NEUTRAL_LOW,
    RSI_NEUTRAL_HIGH,
    RSI_OVERBOUGHT,
)

# ════════════════════════════════
# テクニカル指標の計算
# ════════════════════════════════
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    DataFrameに移動平均・RSI・MACDを追加して返す

    Args:
        df: yfinanceから取得したOHLCVのDataFrame

    Returns:
        指標を追加したDataFrame
    """
    df = df.copy()

    # ── 移動平均線 ──────────────────
    df["MA25"] = df["Close"].rolling(25).mean()
    df["MA75"] = df["Close"].rolling(75).mean()

    # ── RSI ─────────────────────────
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df["RSI"] = 100 - (100 / (1 + rs))

    # ── MACD ────────────────────────
    exp1 = df["Close"].ewm(span=12, adjust=False).mean()
    exp2 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = exp1 - exp2
    df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["Signal"]

    return df

# ════════════════════════════════
# 直近値の抽出
# ════════════════════════════════
def get_latest_values(df: pd.DataFrame) -> dict:
    """
    計算した指標の最新の値を辞書で返す
    """
    if df.empty or len(df) < 2:
        return {}
    
    last = df.iloc[-1]
    prev = df.iloc[-2]

    return {
        "price":       safe_float(last.get("Close")),
        "ma25":        safe_float(last.get("MA25")),
        "ma75":        safe_float(last.get("MA75")),
        "rsi":         safe_float(last.get("RSI")),
        "macd":        safe_float(last.get("MACD")),
        "signal":      safe_float(last.get("Signal")),
        "hist":        safe_float(last.get("MACD_Hist")),
        "prev_hist":   safe_float(prev.get("MACD_Hist")),
        "volume":      safe_float(last.get("Volume")),
    }

# ════════════════════════════════
# テクニカル指標に基づくスコアリング
# ════════════════════════════════
def calc_simple_score(vals: dict) -> tuple:
    """
    テクニカル指標の数値から100点満点のスコアを算出し、理由リストを返す
    """
    if not vals:
        return 0, ["データが不足しています"]

    score = 50
    reasons = []

    # 1. トレンド判断 (株価 vs 25日線)
    p = vals.get("price")
    m25 = vals.get("ma25")
    if p and m25:
        if p > m25 * 1.03:
            score += 10
            reasons.append("株価が25日移動平均線の上方を堅調に推移（+10）")
        elif p < m25 * 0.97:
            score -= 10
            reasons.append("株価が25日移動平均線を下回り軟調な展開（-10）")
        else:
            reasons.append("株価は25日移動平均線付近で保ち合い（±0）")

    # 2. RSIによる過熱度判断
    rsi = vals.get("rsi")
    if rsi:
        if rsi <= RSI_OVERSOLD:
            score += 15
            reasons.append(f"RSIが{rsi:.1f}%と極めて売られすぎ。反発の好機（+15）")
        elif rsi <= RSI_SLIGHTLY_OVERSOLD:
            score += 5
            reasons.append(f"RSIが{rsi:.1f}%とやや売られすぎゾーン（+5）")
        elif rsi >= RSI_OVERBOUGHT:
            score -= 15
            reasons.append(f"RSIが{rsi:.1f}%と買われすぎ。高値警戒感あり（-15）")
        elif RSI_NEUTRAL_LOW <= rsi <= RSI_NEUTRAL_HIGH:
            reasons.append(f"RSIは{rsi:.1f}%と中立圏内（±0）")

    # 3. MACDによるトレンド転換判断
    hist = vals.get("hist")
    prev_hist = vals.get("prev_hist")
    if hist is not None and prev_hist is not None:
        if prev_hist < 0 and hist > 0:
            score += 15
            reasons.append("MACDがゴールデンクロスを達成。上昇トレンド転換の兆し（+15）")
        elif prev_hist > 0 and hist < 0:
            score -= 15
            reasons.append("MACDがデッドクロスを形成。下降トレンド入りの警戒（-15）")
        elif hist > 0:
            score += 5
            reasons.append("MACDヒストグラムがプラス圏を維持、上昇圧力が継続（+5）")
        else:
            score -= 5
            reasons.append("MACDヒストグラムがマイナス圏、上値が重い展開（-5）")

    score = max(0, min(100, score))
    return score, reasons

# ════════════════════════════════
# パステル調ローソク足チャート描画
# ════════════════════════════════
def draw_candlestick(df: pd.DataFrame, name: str) -> BytesIO:
    """
    直近6ヶ月のローソク足チャート（移動平均線付き）を描画し、BytesIOオブジェクトを返す
    """
    if df.empty:
        return None

    # 直近6ヶ月（約130営業日）に絞る
    plot_df = df.tail(130).copy()
    if plot_df.empty:
        return None

    # ───【P5-1】フォント読み込みをこの描画処理の中だけで完結させます ───
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    FONT_PATH = os.path.join(BASE_DIR, "NotoSansJP-Regular.ttf")

    if os.path.exists(FONT_PATH):
        try:
            fm.fontManager.addfont(FONT_PATH)
            font_prop = fm.FontProperties(fname=FONT_PATH)
            FONT_NAME = font_prop.get_name()
        except:
            FONT_NAME = "IPAGothic"
    else:
        FONT_NAME = "IPAGothic"

    plt.rcParams["font.family"] = FONT_NAME
    plt.rcParams["axes.unicode_minus"] = False
    # ──────────────────────────────────────────────────────────────────

    # パステル風カスタムカラー設定
    COLORS = {
        "bg": "#ffffff",
        "up": "#ffadad",      # 陽線：優しい赤
        "down": "#9bf6ff",    # 陰線：優しい青
        "edge": "#555555",
        "volume": "#e8eaf6",
        "ma25": "#ffb7b2",    # 25日線：パステルオレンジ
        "ma75": "#bdb2ff",    # 75日線：パステルパープル
    }

    style = mpf.make_mpf_style(
        marketcolors=mpf.make_marketcolors(
            type="candle",
            up=COLORS["up"], down=COLORS["down"],
            edge=COLORS["edge"], wick=COLORS["edge"],
            volume=COLORS["volume"], inherit=True
        ),
        gridcolor="#f0f0f0",
        gridstyle="-",
        facecolor=COLORS["bg"],
        rc={"font.size": 9}
    )

    try:
        adds = []
        if "MA25" in plot_df and not plot_df["MA25"].dropna().empty:
            adds.append(mpf.make_addplot(plot_df["MA25"],
                        color=COLORS["ma25"], width=1.8,
                        linestyle="-", label="25日線"))
        if "MA75" in plot_df and not plot_df["MA75"].dropna().empty:
            adds.append(mpf.make_addplot(plot_df["MA75"],
                        color=COLORS["ma75"], width=1.6,
                        linestyle="--", label="75日線"))

        # returnfig=True で axes オブジェクトを取得
        fig, axes = mpf.plot(
            plot_df, type="candle", style=style, volume=True,
            addplot=adds if adds else None,
            figsize=(12, 6.5), returnfig=True,
            panel_ratios=(3, 1), tight_layout=True,
            warn_too_much_data=500,
        )

        # ──────────────────────────────────────────────────────────────────
        # 各Axesのテキストフォントを強制上書き
        # ──────────────────────────────────────────────────────────────────
        
        # ① メインタイトルの個別上書き指定
        axes[0].set_title(
            f"📈  {name}  ローソク足チャート（直近6ヶ月）",
            fontsize=12, fontweight="bold", color="#3d2b1f", pad=10,
            fontname=FONT_NAME
        )

        # ② 凡例（Legend）の個別上書き指定
        handles = [
            mpatches.Patch(color=COLORS["ma25"], label="25日移動平均"),
            mpatches.Patch(color=COLORS["ma75"], label="75日移動平均"),
        ]
        leg = axes[0].legend(handles=handles, loc="upper left",
                             fontsize=9, framealpha=0.9,
                             facecolor="#fff9fb", edgecolor="#f8bbd0")
        
        # 凡例内のテキストをフォント上書き
        for text in leg.get_texts():
            text.set_fontname(FONT_NAME)

        # ③ 各軸（価格軸、日付軸、出来高軸）の目盛りテキストを強制適用
        for ax in axes:
            for label in ax.get_xticklabels() + ax.get_yticklabels():
                label.set_fontname(FONT_NAME)
            ax.xaxis.label.set_fontname(FONT_NAME)
            ax.yaxis.label.set_fontname(FONT_NAME)

        # ──────────────────────────────────────────────────────────────────

        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=108,
                    bbox_inches="tight", facecolor=COLORS["bg"])
        plt.close(fig)
        buf.seek(0)
        return buf

    except Exception as e:
        st.warning(f"チャート描画エラー: {e}")
        try:
            plt.close()
        except:
            pass
        return None
