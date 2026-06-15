"""
dividend_history.py  v7.0
=========================
③ 過去の配当推移グラフ

yfinance の .dividends で過去配当データを取得し、
年次で集計して折れ線グラフ + テーブル表示する。

ネットワークエラー・データなしの場合はグレースフルに非表示。
"""

import streamlit as st
import pandas as pd


@st.cache_data(ttl=86400)   # 1日キャッシュ（配当履歴は頻繁に変わらない）
def _fetch_dividends(code: str) -> pd.Series:
    """yfinanceから配当履歴を取得して年次集計で返す"""
    try:
        import yfinance as yf
        ticker = yf.Ticker(f"{code}.T")
        divs   = ticker.dividends
        if divs is None or divs.empty:
            return pd.Series(dtype=float)
        # タイムゾーン除去
        divs.index = pd.to_datetime(divs.index).tz_localize(None)
        # 年次で合計（同一年に中間・期末配当がある場合を合算）
        annual = divs.resample("YE").sum()
        annual.index = annual.index.year
        annual = annual[annual > 0]   # 0円は除外
        return annual.tail(10)        # 直近10年分
    except Exception:
        return pd.Series(dtype=float)


def render_dividend_history(code: str) -> None:
    """
    配当推移セクションを描画する。
    データがない場合はこのセクション自体を非表示にする。
    """
    annual = _fetch_dividends(code)

    if annual.empty:
        return   # データなし → 非表示

    st.markdown('<p class="sec-title">📊 配当推移（過去10年）</p>',
                unsafe_allow_html=True)

    years  = [str(y) for y in annual.index]
    values = annual.values.tolist()

    # ── 折れ線グラフ（Streamlit built-in chart） ──
    chart_df = pd.DataFrame({"1株配当（円）": values}, index=years)
    st.line_chart(chart_df, use_container_width=True, height=220)

    # ── 年次テーブル ────────────────────────────
    cols = st.columns(len(years))
    for col, yr, val in zip(cols, years, values):
        with col:
            # 前年比の計算
            idx   = years.index(yr)
            prev  = values[idx - 1] if idx > 0 else None
            delta = ""
            if prev and prev > 0:
                diff = val - prev
                pct  = diff / prev * 100
                if diff > 0:
                    delta = f"▲{diff:.1f}円 (+{pct:.1f}%)"
                elif diff < 0:
                    delta = f"▼{abs(diff):.1f}円 ({pct:.1f}%)"
                else:
                    delta = "→ 変化なし"

            st.markdown(
                f"<div style='text-align:center;background:linear-gradient(135deg,#fff9fb,#fce4ec);"
                f"border-radius:10px;padding:0.55rem 0.3rem;border:1px solid #f8bbd0;'>"
                f"<div style='font-size:0.7rem;color:#ad1457;font-weight:600;'>{yr}年</div>"
                f"<div style='font-size:1.05rem;font-weight:700;color:#880e4f;'>{val:.0f}円</div>"
                f"<div style='font-size:0.65rem;color:#888;margin-top:0.1rem;'>{delta}</div>"
                f"</div>",
                unsafe_allow_html=True)

    # 増配傾向の判定
    if len(values) >= 3:
        recent   = values[-3:]
        if all(recent[i] <= recent[i+1] for i in range(len(recent)-1)):
            st.success("📈 直近3年間、配当が増加傾向にあります（増配トレンド）")
        elif all(recent[i] >= recent[i+1] for i in range(len(recent)-1)):
            st.warning("📉 直近3年間、配当が減少傾向にあります")

    st.caption("※ 配当履歴はYahoo Finance提供のデータです。中間配当・記念配当を含む場合があります。")
