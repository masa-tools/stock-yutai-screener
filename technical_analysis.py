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
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import os

FONT_PATH = os.path.join(
    os.path.dirname(__file__),
    "NotoSansJP-VariableFont_wght.ttf"
)

fm.fontManager.addfont(FONT_PATH)
font_prop = fm.FontProperties(fname=FONT_PATH)

plt.rcParams["font.family"] = font_prop.get_name()
plt.rcParams["axes.unicode_minus"] = False
import matplotlib.patches as mpatches
import mplfinance as mpf
import streamlit as st
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
    df["MA25"] = df["Close"].rolling(25).mean()   # 短期トレンド
    df["MA75"] = df["Close"].rolling(75).mean()   # 中期トレンド

    # ── RSI（14日） ─────────────────
    # 0〜100。70超=買われすぎ、30未満=売られすぎ
    delta = df["Close"].diff()
    gain  = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    df["RSI"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))

    # ── MACD ───────────────────────
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"]        = ema12 - ema26
    df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_hist"]   = df["MACD"] - df["MACD_signal"]

    return df


def get_latest_values(df: pd.DataFrame) -> dict:
    """
    最新日付の各指標値と「初心者向けコメント」を辞書で返す

    ポイント: 数値だけでなく「意味」も一緒に返す
    例: rsi=72 → rsi_note="やや買われすぎ注意"
    """
    row = df.iloc[-1]
    close = float(row["Close"])

    # 前日比
    prev  = float(df["Close"].iloc[-2]) if len(df) > 1 else close
    chg   = close - prev
    chg_p = chg / prev * 100 if prev else 0

    # 各指標を安全に取り出す
    ma25  = _v(row, "MA25")
    ma75  = _v(row, "MA75")
    rsi   = _v(row, "RSI")
    macd  = _v(row, "MACD")
    macd_s= _v(row, "MACD_signal")

    # 出来高（20日平均との比率）
    vol_avg = float(df["Volume"].tail(20).mean())
    vol     = float(row["Volume"])
    vol_ratio = vol / vol_avg if vol_avg else 1.0

    # ── トレンド判定 ────────────────
    if ma25 and ma75:
        if ma25 > ma75 and close > ma25:
            trend = "上昇トレンド"
            trend_note = "25日線・75日線ともに上向き。強い上昇基調です 📈"
        elif ma25 > ma75:
            trend = "緩やかな上昇"
            trend_note = "25日線が75日線を上回り、上昇トレンド傾向です 📈"
        elif ma25 < ma75 and close < ma25:
            trend = "下降トレンド"
            trend_note = "下降トレンド中。様子見が無難かもしれません 📉"
        else:
            trend = "横ばい"
            trend_note = "方向感が定まっていません。しばらく観察を 📊"
    else:
        trend = trend_note = "データ不足"

    # ── RSI判定 ──────────────────
    if rsi:
        if   rsi >= RSI_OVERBOUGHT:        rsi_note = f"RSI {rsi:.0f} — 買われすぎ注意 ⚠️"
        elif rsi >= RSI_NEUTRAL_HIGH:      rsi_note = f"RSI {rsi:.0f} — やや過熱感あり"
        elif rsi <= RSI_OVERSOLD:          rsi_note = f"RSI {rsi:.0f} — 売られすぎ水準（反発期待も）"
        elif rsi <= RSI_SLIGHTLY_OVERSOLD: rsi_note = f"RSI {rsi:.0f} — やや売られすぎ"
        else:                              rsi_note = f"RSI {rsi:.0f} — 適正水準 👍"
    else:
        rsi_note = "RSI: 計算中"

    # ── MACD判定 ──────────────────
    if macd is not None and macd_s is not None:
        if macd > macd_s and macd > 0:
            macd_note = "上昇シグナル（強い買い勢い）🟢"
        elif macd > macd_s:
            macd_note = "上昇に転じつつある 📈"
        elif macd < macd_s and macd < 0:
            macd_note = "下降シグナル（売り勢い）🔴"
        else:
            macd_note = "下降に転じつつある 📉"
    else:
        macd_note = "計算中"

    # ── 出来高判定 ─────────────────
    if   vol_ratio >= 2.0: vol_note = f"平均の{vol_ratio:.1f}倍 🔥 非常に注目されています"
    elif vol_ratio >= 1.3: vol_note = f"平均の{vol_ratio:.1f}倍 注目度が上がっています"
    elif vol_ratio >= 0.7: vol_note = f"平均並み（{vol_ratio:.1f}倍）"
    else                 : vol_note = f"平均の{vol_ratio:.1f}倍 少なめ（流動性注意）"

    return {
        "close": close, "change": chg, "change_pct": chg_p,
        "ma25": ma25, "ma75": ma75,
        "rsi": rsi, "rsi_note": rsi_note,
        "macd": macd, "macd_signal": macd_s, "macd_note": macd_note,
        "trend": trend, "trend_note": trend_note,
        "volume": vol, "vol_ratio": vol_ratio, "vol_note": vol_note,
    }


# ════════════════════════════════
# 簡易スコアリング（APIゼロ）
# ════════════════════════════════
def calc_simple_score(info: dict, tv: dict, code: str) -> dict:
    """
    Gemini APIを一切使わずPythonのみで総合スコアを算出する

    スコア配分:
      財務（PER・PBR）  25点
      配当利回り        25点
      テクニカル        30点
      出来高            10点
      その他            10点
    合計 100点

    Args:
        info: yfinanceの銘柄情報
        tv  : get_latest_values()の戻り値
        code: 証券コード（優待チェック用）

    Returns:
        各スコアと簡易コメントの辞書
    """

    # ── ① 財務スコア（0〜25点） ────
    fin = 0
    per = safe_float(info, "trailingPE") or safe_float(info, "forwardPE")
    pbr = safe_float(info, "priceToBook")

    if per:
        if   10 <= per <= 20: fin += 13
        elif 20 <  per <= 30: fin += 9
        elif per < 10        : fin += 7
        else                 : fin += 3

    if pbr:
        if   0.5 <= pbr <= 2.0: fin += 12
        elif 2.0 <  pbr <= 3.0: fin += 7
        elif pbr < 0.5         : fin += 4
        else                   : fin += 2

    fin = min(25, fin)

    # ── ② 配当スコア（0〜25点） ────
    # Fix: yfinanceは小数形式(0.035=3.5%)で返すが稀に%形式(3.5)で返す
    #      1.0超なら既に%形式と判定し30%超は異常値として除外
    div = 0
    dy  = safe_float(info, "dividendYield")
    if dy is not None:
        raw_dy = float(info.get("dividendYield", 0) or 0)
        p = raw_dy * 100 if raw_dy <= 1.0 else raw_dy
        if 0.1 <= p <= 30:   # 現実的な範囲のみスコア計算
            if   3.0 <= p <= 5.5: div = 25
            elif 2.0 <= p < 3.0 : div = 18
            elif 5.5 < p <= 8.0 : div = 13   # 高すぎは持続性不安
            elif 1.0 <= p < 2.0 : div = 10
            elif p > 8.0         : div = 5

    # ── ③ テクニカルスコア（0〜30点） ─
    tech = 0
    close = tv.get("close", 0)
    ma25  = tv.get("ma25")
    ma75  = tv.get("ma75")
    rsi   = tv.get("rsi")
    macd  = tv.get("macd")
    macd_s= tv.get("macd_signal")

    # トレンド（最大12点）
    if ma25 and ma75:
        if ma25 > ma75 and close > ma25: tech += 12
        elif ma25 > ma75               : tech += 8
        elif close > ma25              : tech += 4
        else                           : tech += 1

    # RSI（最大10点）
    # 閾値設計: calc_simple_score専用のスコアリング配点閾値
    #   RSI_NEUTRAL_HIGH(65)は共通定数を使用
    #   35/45/70はスコアリング精度のための独自閾値（scoring_configに未定義のため残置）
    if rsi:
        if   45 <= rsi <= RSI_NEUTRAL_HIGH: tech += 10
        elif 35 <= rsi < 45               : tech += 7   # 35: スコアリング専用閾値
        elif RSI_NEUTRAL_HIGH < rsi <= 70 : tech += 5   # 70: スコアリング専用閾値
        elif rsi < 35                     : tech += 3   # 35: スコアリング専用閾値
        else                              : tech += 1

    # MACD（最大8点）
    if macd is not None and macd_s is not None:
        tech += 8 if macd > macd_s else 2

    tech = min(30, tech)

    # ── ④ 出来高スコア（0〜10点） ──
    vol_s = 0
    vr = tv.get("vol_ratio", 1.0)
    if   vr >= 2.0: vol_s = 10
    elif vr >= 1.3: vol_s = 8
    elif vr >= 0.7: vol_s = 6
    else           : vol_s = 3

    # ── ⑤ ボーナス（0〜10点） ──────
    bonus = 5   # ベース点
    oi = safe_float(info, "operatingIncome") or safe_float(info, "ebit")
    if oi and oi > 0:
        bonus += 3   # 黒字企業ボーナス
    mc = safe_float(info, "marketCap")
    if mc and mc >= 1e11:
        bonus += 2   # 大型株ボーナス

    # ── 合計 ───────────────────────
    total = min(100, fin + div + tech + vol_s + bonus)

    # ── コメント生成 ───────────────
    comments = _make_comments(total, tv, dy, per)

    # ── 評価マーク ─────────────────
    long_mark  = "◎" if total >= 72 else "○" if total >= 52 else "△"
    # 配当評価マーク（安全な変換を使用）
    _dp = fmt_dividend_pct(info.get("dividendYield"))
    div_mark   = "◎" if _dp >= 3 else "○" if _dp >= 1.5 else "△"
    tech_mark  = "◎" if tech >= 22 else "○" if tech >= 14 else "△"

    return {
        "total"    : total,
        "finance"  : min(100, int(fin  / 25 * 100)),
        "dividend" : min(100, int(div  / 25 * 100)),
        "technical": min(100, int(tech / 30 * 100)),
        "volume"   : min(100, int(vol_s/ 10 * 100)),
        "long_mark": long_mark,
        "div_mark" : div_mark,
        "tech_mark": tech_mark,
        "comments" : comments,
    }


def _make_comments(total: int, tv: dict, dy, per) -> list[str]:
    """スコアと指標から簡易コメントリストを生成"""
    comments = []
    trend = tv.get("trend", "")
    rsi   = tv.get("rsi")
    vr    = tv.get("vol_ratio", 1.0)

    # トレンド系コメント
    if "上昇" in trend:
        comments.append("長期トレンドは比較的安定しています。")
    elif "下降" in trend:
        comments.append("中期的には下降傾向です。焦らず様子を見ましょう。")
    else:
        comments.append("方向感が定まっていません。しばらく観察がおすすめです。")

    # RSI系コメント
    if rsi:
        if rsi >= RSI_OVERBOUGHT:
            comments.append("短期的にはやや過熱感があります。")
        elif rsi <= RSI_OVERSOLD:
            comments.append("売られすぎ水準です。反発のタイミングに注目。")
        else:
            comments.append("過熱感はなく、落ち着いた水準です。")
          
    # 配当コメント（安全な変換を使用）
    if dy is not None:
        try:
            raw_dy = float(dy)
            dy_pct = raw_dy * 100 if raw_dy <= 1.0 else raw_dy
            if 0.1 <= dy_pct <= 30:
                if dy_pct >= 3.0:
                    comments.append(f"配当利回り{dy_pct:.1f}%と魅力的な水準です。")
                elif dy_pct >= 1.5:
                    comments.append("安定した配当が見込めます。")
        except (TypeError, ValueError):
            pass

    # 出来高コメント
    if vr >= 1.5:
        comments.append("市場での注目度が高まっています。")

    # 総合コメント
    if total >= 70:
        comments.append("長期保有の候補として検討できる水準です 🌸")
    elif total >= 50:
        comments.append("バランスが取れた銘柄です。引き続き観察しましょう。")
    else:
        comments.append("現時点ではいくつかの課題があります。他の銘柄と比較してみましょう。")

    return comments[:4]   # 最大4コメント


# ════════════════════════════════
# ローソク足チャート（パステルカラー）
# ════════════════════════════════

# 色設定（ここを変えるとチャートの色が変わります）
COLORS = {
    "bg"  : "#fdf8f5",
    "up"  : "#f48fb1",   # 陽線: ピンク
    "down": "#90caf9",   # 陰線: ライトブルー
    "ma25": "#e91e63",   # 25日線
    "ma75": "#ce93d8",   # 75日線
    "vol" : "#f8bbd0",   # 出来高
    "grid": "#f5e6f0",
}


def draw_candlestick(df: pd.DataFrame, name: str = "") -> BytesIO | None:
    """
    パステルカラーのローソク足チャートを描画してBytesIOで返す

    含む要素: ローソク足・25日線・75日線・出来高バー
    """
    try:
        plot_df = df.tail(120).copy()   # 直近約半年
        if len(plot_df) < 10:
            return None

        # base_mpf_style="white" は mplfinance 新バージョンで廃止
        # → "default" を使い、rcで白背景を自前で上書きする
        mc = mpf.make_marketcolors(
            up=COLORS["up"], down=COLORS["down"],
            edge={"up": COLORS["up"], "down": COLORS["down"]},
            wick={"up": COLORS["up"], "down": COLORS["down"]},
            volume=COLORS["vol"],
        )
        style = mpf.make_mpf_style(
            base_mpf_style="default",
            marketcolors=mc,
            rc={
                "font.family"      : font_prop.get_name(),
                "axes.facecolor"   : COLORS["bg"],
                "figure.facecolor" : COLORS["bg"],
                "savefig.facecolor": COLORS["bg"],
                "axes.edgecolor"   : "#e0c8d0",
                "axes.spines.top"  : False,
                "axes.spines.right": False,
                "xtick.color"      : "#999",
                "ytick.color"      : "#999",
                "grid.color"       : COLORS["grid"],
                "grid.linestyle"   : "--",
                "grid.alpha"       : 0.6,
            },
        )

        adds = []
        if "MA25" in plot_df and plot_df["MA25"].notna().sum() > 5:
            adds.append(mpf.make_addplot(plot_df["MA25"],
                        color=COLORS["ma25"], width=1.6, label="25日線"))
        if "MA75" in plot_df and plot_df["MA75"].notna().sum() > 5:
            adds.append(mpf.make_addplot(plot_df["MA75"],
                        color=COLORS["ma75"], width=1.6,
                        linestyle="--", label="75日線"))

        fig, axes = mpf.plot(
            plot_df, type="candle", style=style, volume=True,
            addplot=adds if adds else None,
            figsize=(12, 6.5), returnfig=True,
            panel_ratios=(3, 1), tight_layout=True,
            warn_too_much_data=500,
        )

        axes[0].set_title(
            f"📈  {name}  ローソク足チャート（直近6ヶ月）",
            fontsize=12, fontweight="bold", color="#3d2b1f", pad=10,
        )

        # 凡例
        handles = [
            mpatches.Patch(color=COLORS["ma25"], label="25日移動平均"),
            mpatches.Patch(color=COLORS["ma75"], label="75日移動平均"),
        ]
        axes[0].legend(handles=handles, loc="upper left",
                       fontsize=9, framealpha=0.9,
                       facecolor="#fff9fb", edgecolor="#f8bbd0")

        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=108,
                    bbox_inches="tight", facecolor=COLORS["bg"])
        plt.close(fig)
        buf.seek(0)
        return buf

    except Exception as e:
        st.warning(f"チャート描画エラー: {e}")
        return None


# ────────────────────────────────
# 内部ヘルパー
# ────────────────────────────────
def _v(row, col: str) -> float | None:
    """DataFrame行から安全に数値を取り出す"""
    try:
        f = float(row[col])
        return None if (np.isnan(f) or np.isinf(f)) else f
    except Exception:
        return None
