"""
dividend_sim.py  v5.0
=====================
💰 配当シミュレーター

【v5.0 修正】
  - +100/+500/+1000株クイックボタン追加
  - 税引後配当を表示（20.315%控除）
  - number_input の key を固定（コードに依存させない）
"""

import streamlit as st

TAX_RATE = 0.20315   # 配当税率（所得税+住民税+復興特別所得税）


def render_dividend_simulator(info: dict, close: float) -> None:
    dy_raw = info.get("dividendYield")
    if dy_raw is None:
        return

    try:
        val    = float(dy_raw)
        dy_pct = val * 100 if val <= 1.0 else val
        if dy_pct < 0.1 or dy_pct > 30:
            return
    except (TypeError, ValueError):
        return

    div_per_share = close * dy_pct / 100

    st.markdown('<p class="sec-title">💰 配当シミュレーター</p>',
                unsafe_allow_html=True)

    with st.container():
        # ── 保有株数入力 + クイックボタン ──────────────
        row = st.columns([2, 1, 1, 1, 2])

        with row[0]:
            # session_state で株数を管理
            if "sim_shares" not in st.session_state:
                st.session_state["sim_shares"] = 100

            shares = st.number_input(
                "保有株数（株）",
                min_value=100,
                max_value=500_000,
                step=100,
                key="sim_shares",
            )

        with row[1]:
            st.markdown("<div style='height:1.65rem'></div>", unsafe_allow_html=True)
            if st.button("+100株", key="sim_p100", use_container_width=True):
                st.session_state["sim_shares"] = min(500_000, shares + 100)
                st.rerun()
        with row[2]:
            st.markdown("<div style='height:1.65rem'></div>", unsafe_allow_html=True)
            if st.button("+500株", key="sim_p500", use_container_width=True):
                st.session_state["sim_shares"] = min(500_000, shares + 500)
                st.rerun()
        with row[3]:
            st.markdown("<div style='height:1.65rem'></div>", unsafe_allow_html=True)
            if st.button("+1000株", key="sim_p1000", use_container_width=True):
                st.session_state["sim_shares"] = min(500_000, shares + 1000)
                st.rerun()

        with row[4]:
            cost = close * shares
            st.markdown(
                f"<div style='padding-top:1.75rem;font-size:0.85rem;color:#666;'>"
                f"💴 取得コスト: <strong>¥{cost:,.0f}</strong></div>",
                unsafe_allow_html=True)

        # ── 計算 ────────────────────────────────────────
        annual      = div_per_share * shares
        annual_net  = annual * (1 - TAX_RATE)   # 税引後
        monthly_net = annual_net / 12
        y5          = annual_net * 5
        y10         = annual_net * 10
        rate        = dy_pct / 100
        y5_rei      = _compound(annual_net, rate, 5)
        y10_rei     = _compound(annual_net, rate, 10)
        breakeven   = int(close / (div_per_share * (1 - TAX_RATE))) if div_per_share > 0 else 0

        st.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)

        # 行1: 基本
        r1 = st.columns(4)
        _card(r1[0], "年間配当（税引後）",  f"¥{annual_net:,.0f}",
              f"税前 ¥{annual:,.0f}")
        _card(r1[1], "月換算（税引後）",    f"¥{monthly_net:,.0f}",
              f"利回り {dy_pct:.2f}%")
        _card(r1[2], "5年累計（税引後）",   f"¥{y5:,.0f}",
              "配当不変の場合")
        _card(r1[3], "10年累計（税引後）",  f"¥{y10:,.0f}",
              "配当不変の場合")

        st.markdown("<div style='height:0.3rem'></div>", unsafe_allow_html=True)

        # 行2: 再投資
        r2 = st.columns(4)
        _card(r2[0], "5年累計（再投資）",  f"¥{y5_rei:,.0f}",
              "税引後配当を再投資", accent=True)
        _card(r2[1], "10年累計（再投資）", f"¥{y10_rei:,.0f}",
              "税引後配当を再投資", accent=True)
        _card(r2[2], "1株あたり配当",      f"¥{div_per_share:,.1f}",
              f"税引後 ¥{div_per_share*(1-TAX_RATE):,.1f}")
        _card(r2[3], "元本回収（配当のみ）",
              f"約{breakeven}年" if breakeven else "―",
              "税引後ベース")

        st.caption("⚠️ 税率20.315%を控除した概算です。実際は特定口座・NISA等で異なります。")


def _card(col, label: str, value: str, sub: str, accent: bool = False) -> None:
    bg  = "linear-gradient(135deg,#e8f5e9,#c8e6c9)" if accent else "linear-gradient(135deg,#fff9fb,#fce4ec)"
    vc  = "#2e7d32" if accent else "#880e4f"
    brd = "#a5d6a7" if accent else "#f8bbd0"
    with col:
        st.markdown(
            f"<div style='background:{bg};border-radius:14px;"
            f"padding:0.85rem 0.7rem;border:1px solid {brd};"
            f"text-align:center;margin-bottom:0.3rem;'>"
            f"<div class='m-label'>{label}</div>"
            f"<div style='font-family:\"Zen Maru Gothic\",sans-serif;"
            f"font-size:1.1rem;font-weight:700;color:{vc};"
            f"margin:0.2rem 0;'>{value}</div>"
            f"<div class='m-sub'>{sub}</div></div>",
            unsafe_allow_html=True)


def _compound(annual_net: float, rate: float, years: int) -> float:
    if rate <= 0:
        return annual_net * years
    return annual_net * ((1 + rate) ** years - 1) / rate
