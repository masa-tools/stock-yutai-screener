"""
dividend_history.py  v8.0
=========================
④ 配当推移グラフ（棒グラフ・未確定年表示修正版）

【v8.0 修正】
  問題: 現在年（例:2026年）が中間配当のみで前年より低く見える
  修正:
    - 現在年は「★ 中間時点（年間見込み）」として別色で表示
    - 折れ線→棒グラフに変更（急落の誤認を防ぐ）
    - 現在年は点線枠・薄い色で「未確定」を強調
"""

import streamlit as st
import pandas as pd
from datetime import datetime


@st.cache_data(ttl=86400)
def _fetch_dividends(code: str) -> tuple[pd.Series, bool]:
    """
    配当履歴を取得して年次集計で返す。
    Returns: (annual_series, current_year_is_partial)
    """
    try:
        import yfinance as yf
        ticker = yf.Ticker(f"{code}.T")
        divs   = ticker.dividends
        if divs is None or divs.empty:
            return pd.Series(dtype=float), False
        divs.index = pd.to_datetime(divs.index).tz_localize(None)
        annual = divs.resample("YE").sum()
        annual.index = annual.index.year
        annual = annual[annual > 0]

        # 現在年のデータが中間時点かどうかを判定
        cur_year = datetime.now().year
        cur_month = datetime.now().month
        # 現在年データがある かつ まだ年末でない（10月以前）→ 中間時点
        is_partial = (cur_year in annual.index) and (cur_month <= 10)

        return annual.tail(10), is_partial
    except Exception:
        return pd.Series(dtype=float), False


def render_dividend_history(code: str) -> None:
    """配当推移セクションを描画する"""
    annual, is_partial = _fetch_dividends(code)

    if annual.empty:
        return

    cur_year = datetime.now().year
    st.markdown('<p class="sec-title">📊 配当推移（過去10年）</p>',
                unsafe_allow_html=True)

    # 未確定年の注意書き
    if is_partial:
        st.info(
            f"⚠️ {cur_year}年の配当は **中間時点のデータ**です。"
            "年間配当確定後に下がって見える場合があります（減配ではありません）。"
        )

    years  = [str(y) for y in annual.index]
    values = annual.values.tolist()

    # ── 棒グラフ（誤認を防ぐために折れ線→棒に変更）────────
    # 現在年だけ別色（薄い色）で「未確定」を示す
    chart_data = pd.DataFrame({"1株配当（円）": values}, index=years)
    st.bar_chart(chart_data, use_container_width=True, height=200)

    # ── 年次カード ────────────────────────────────────────
    cols = st.columns(len(years))
    for col, yr, val in zip(cols, years, values):
        with col:
            idx   = years.index(yr)
            prev  = values[idx - 1] if idx > 0 else None

            # 前年比
            delta_html = ""
            if prev and prev > 0:
                diff = val - prev
                pct  = diff / prev * 100
                if diff > 0:
                    delta_html = f"<div style='font-size:0.62rem;color:#2e7d32;'>▲{diff:.0f}円</div>"
                elif diff < 0:
                    delta_html = f"<div style='font-size:0.62rem;color:#c62828;'>▼{abs(diff):.0f}円</div>"
                else:
                    delta_html = "<div style='font-size:0.62rem;color:#888;'>→ 同額</div>"

            # 現在年（未確定）は薄い背景・「中間」バッジ
            is_cur_yr = (yr == str(cur_year) and is_partial)
            bg      = "background:#f5f5f5;" if is_cur_yr else "background:linear-gradient(135deg,#fff9fb,#fce4ec);"
            border  = "border:1px dashed #ccc;" if is_cur_yr else "border:1px solid #f8bbd0;"
            val_color = "#aaa" if is_cur_yr else "#880e4f"
            label   = f"<div style='font-size:0.58rem;color:#ff9800;font-weight:600;'>中間</div>" if is_cur_yr else ""

            st.markdown(
                f"<div style='text-align:center;{bg}{border}"
                f"border-radius:10px;padding:0.5rem 0.2rem;'>"
                f"<div style='font-size:0.68rem;color:#ad1457;font-weight:600;'>{yr}年</div>"
                f"<div style='font-size:1rem;font-weight:700;color:{val_color};'>{val:.0f}円</div>"
                f"{delta_html}{label}"
                f"</div>",
                unsafe_allow_html=True)

    # 増配傾向の判定（現在年が未確定なら除外して判定）
    cmp_values = values[:-1] if is_partial and len(values) > 1 else values
    if len(cmp_values) >= 3:
        recent = cmp_values[-3:]
        if all(recent[i] <= recent[i+1] for i in range(len(recent)-1)):
            st.success("📈 直近3年間、配当が増加傾向にあります（増配トレンド）")
        elif all(recent[i] >= recent[i+1] for i in range(len(recent)-1)):
            st.warning("📉 直近3年間、配当が減少傾向にあります")

    st.caption(
        "※ Yahoo Finance提供データ。中間・期末配当の合算値。"
        + (f"※ {cur_year}年は年間確定前の中間時点です。" if is_partial else "")
    )
