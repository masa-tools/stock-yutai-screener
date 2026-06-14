"""
dividend_sim.py  v6.0
=====================
💰 配当シミュレーター

【v6.0 バグ修正】
  ④ +ボタン競合の根本原因:
     number_input(key="sim_shares") と st.button を同一フレームで
     使うと、ボタン押下 → session_state["sim_shares"] を書き換え →
     st.rerun() の順番でうまく動かないケースがある。

     修正: number_input の key を廃止し、value= に
     session_state から読んだ値を直接渡す方式に変更。
     ボタン押下は session_state の別キーを使って管理し、
     on_change コールバック不要の安全な設計に変更。
"""

import streamlit as st

TAX_RATE = 0.20315   # 20.315%（所得税+住民税+復興特別所得税）
_SHARES_KEY = "dsim_shares"   # sim_shares と被らない独自キー


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

    # 初期値をセッション管理
    if _SHARES_KEY not in st.session_state:
        st.session_state[_SHARES_KEY] = 100

    current = int(st.session_state[_SHARES_KEY])

    with st.container():
        # ── ① クイックボタン（number_input の上に配置）──────────
        btn_cols = st.columns([2, 1, 1, 1])
        with btn_cols[0]:
            st.markdown(
                "<div style='font-size:0.82rem;color:#666;margin-bottom:0.2rem;'>"
                "保有株数を変更</div>",
                unsafe_allow_html=True)
        with btn_cols[1]:
            if st.button("＋100株", key="dsim_p100", use_container_width=True):
                st.session_state[_SHARES_KEY] = min(500_000, current + 100)
                st.rerun()
        with btn_cols[2]:
            if st.button("＋500株", key="dsim_p500", use_container_width=True):
                st.session_state[_SHARES_KEY] = min(500_000, current + 500)
                st.rerun()
        with btn_cols[3]:
            if st.button("＋1000株", key="dsim_p1000", use_container_width=True):
                st.session_state[_SHARES_KEY] = min(500_000, current + 1000)
                st.rerun()

        # ── ② number_input（keyなし・valueで制御）──────────────
        inp_col, cost_col = st.columns([2, 3])
        with inp_col:
            # key を使わず value= で渡すことで widget 競合を回避
            shares = st.number_input(
                "保有株数（株）",
                min_value=100,
                max_value=500_000,
                value=current,
                step=100,
            )
            # 手入力で変更された場合は session_state を更新
            if shares != current:
                st.session_state[_SHARES_KEY] = shares

        with cost_col:
            cost = close * shares
            st.markdown(
                f"<div style='padding-top:1.7rem;font-size:0.84rem;color:#666;'>"
                f"💴 取得コスト目安: <strong>¥{cost:,.0f}</strong>"
                f"（¥{close:,.0f} × {shares:,}株）</div>",
                unsafe_allow_html=True)

        # ── ③ 計算 ────────────────────────────────────────────
        annual      = div_per_share * shares
        annual_net  = annual * (1 - TAX_RATE)
        monthly_net = annual_net / 12
        y5          = annual_net * 5
        y10         = annual_net * 10
        rate        = dy_pct / 100
        y5_rei      = _compound(annual_net, rate, 5)
        y10_rei     = _compound(annual_net, rate, 10)
        breakeven   = (int(close / (div_per_share * (1 - TAX_RATE)))
                       if div_per_share > 0 else 0)

        st.markdown("<div style='height:0.35rem'></div>", unsafe_allow_html=True)

        r1 = st.columns(4)
        _card(r1[0], "年間配当（税引後）", f"¥{annual_net:,.0f}",
              f"税前 ¥{annual:,.0f}")
        _card(r1[1], "月換算（税引後）",   f"¥{monthly_net:,.0f}",
              f"利回り {dy_pct:.2f}%")
        _card(r1[2], "5年累計",           f"¥{y5:,.0f}", "配当不変の場合")
        _card(r1[3], "10年累計",          f"¥{y10:,.0f}", "配当不変の場合")

        st.markdown("<div style='height:0.25rem'></div>", unsafe_allow_html=True)

        r2 = st.columns(4)
        _card(r2[0], "5年（再投資）",   f"¥{y5_rei:,.0f}",
              "税引後を再投資した場合", accent=True)
        _card(r2[1], "10年（再投資）",  f"¥{y10_rei:,.0f}",
              "税引後を再投資した場合", accent=True)
        _card(r2[2], "1株あたり配当",   f"¥{div_per_share:,.1f}",
              f"税引後 ¥{div_per_share*(1-TAX_RATE):,.1f}")
        _card(r2[3], "元本回収（概算）",
              f"約{breakeven}年" if breakeven else "―",
              "税引後・配当のみベース")

        st.caption("⚠️ 税率20.315%控除の概算。NISA口座は税率0%になります。")


def _card(col, label: str, value: str, sub: str, accent: bool = False) -> None:
    bg  = "linear-gradient(135deg,#e8f5e9,#c8e6c9)" if accent else "linear-gradient(135deg,#fff9fb,#fce4ec)"
    vc  = "#2e7d32" if accent else "#880e4f"
    brd = "#a5d6a7" if accent else "#f8bbd0"
    with col:
        st.markdown(
            f"<div style='background:{bg};border-radius:13px;"
            f"padding:0.8rem 0.65rem;border:1px solid {brd};"
            f"text-align:center;margin-bottom:0.25rem;'>"
            f"<div class='m-label'>{label}</div>"
            f"<div style='font-size:1.05rem;font-weight:700;color:{vc};"
            f"margin:0.18rem 0;'>{value}</div>"
            f"<div class='m-sub'>{sub}</div></div>",
            unsafe_allow_html=True)


def _compound(annual_net: float, rate: float, years: int) -> float:
    if rate <= 0:
        return annual_net * years
    return annual_net * ((1 + rate) ** years - 1) / rate
