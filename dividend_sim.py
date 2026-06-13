"""
dividend_sim.py
===============
💰 配当シミュレーター

【v4.1 修正】
  Fix④ st.markdown で <div class="card"> を開いたまま st.columns() を
       使うと Streamlit の描画が崩れて画面がリセットされる問題を修正。
       → HTMLカードラッパーを廃止し、st.container() に変更。
"""

import streamlit as st
import math


def render_dividend_simulator(info: dict, close: float) -> None:
    """
    配当シミュレーターを描画する。

    Args:
        info : yfinanceから取得した銘柄情報
        close: 現在株価
    """
    # 配当利回りを安全に取得
    dy_raw = info.get("dividendYield")
    if dy_raw is None:
        return  # 配当なし銘柄は非表示

    try:
        val    = float(dy_raw)
        dy_pct = val * 100 if val <= 1.0 else val
        if dy_pct < 0.1 or dy_pct > 30:
            return  # 異常値は非表示
    except (TypeError, ValueError):
        return

    div_per_share = close * dy_pct / 100

    st.markdown('<p class="sec-title">💰 配当シミュレーター</p>',
                unsafe_allow_html=True)

    # Fix④: st.container() でラップ（HTMLタグで div を開いたまま
    #        st.columns を呼ぶと描画が壊れるため）
    with st.container():
        # 保有株数入力
        col_in, col_note = st.columns([2, 3])
        with col_in:
            shares = st.number_input(
                "保有株数（株）",
                min_value=100,
                max_value=100_000,
                value=100,
                step=100,
                key=f"sim_shares_{info.get('symbol','x')}",
            )
        with col_note:
            cost = close * shares
            st.markdown(
                f"<div style='padding-top:1.8rem;font-size:0.88rem;color:#666;'>"
                f"💴 取得コスト目安: <strong>¥{cost:,.0f}</strong>"
                f"（¥{close:,.0f} × {shares:,}株）</div>",
                unsafe_allow_html=True)

        # 計算
        annual  = div_per_share * shares
        monthly = annual / 12
        y5      = annual * 5
        y10     = annual * 10
        rate    = dy_pct / 100
        y5_rei  = _compound(annual, rate, 5)
        y10_rei = _compound(annual, rate, 10)
        breakeven = int(close / div_per_share) if div_per_share > 0 else 0

        # 1行目：基本4指標
        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        r1 = st.columns(4)
        _card(r1[0], "年間配当",   f"¥{annual:,.0f}",  f"利回り {dy_pct:.2f}%")
        _card(r1[1], "月換算配当", f"¥{monthly:,.0f}", "毎月の参考値")
        _card(r1[2], "5年累計",    f"¥{y5:,.0f}",      "配当不変の場合")
        _card(r1[3], "10年累計",   f"¥{y10:,.0f}",     "配当不変の場合")

        # 2行目：再投資シミュレーション
        st.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)
        r2 = st.columns(4)
        _card(r2[0], "5年累計（再投資）",  f"¥{y5_rei:,.0f}",
              "配当を毎年再投資", accent=True)
        _card(r2[1], "10年累計（再投資）", f"¥{y10_rei:,.0f}",
              "配当を毎年再投資", accent=True)
        _card(r2[2], "1株あたり配当", f"¥{div_per_share:,.1f}", "年間概算")
        _card(r2[3], "配当のみ元本回収",
              f"約{breakeven}年" if breakeven else "―",
              "配当が続いた場合の試算")

        st.caption(
            "⚠️ 現在の配当利回りが継続する前提の概算です。"
            "減配・株価変動・税金（約20%）は含みません。"
        )


def _card(col, label: str, value: str, sub: str, accent: bool = False) -> None:
    """シミュレーション結果の1マスを描画"""
    bg  = "linear-gradient(135deg,#e8f5e9,#c8e6c9)" if accent else "linear-gradient(135deg,#fff9fb,#fce4ec)"
    vc  = "#2e7d32" if accent else "#880e4f"
    brd = "#a5d6a7" if accent else "#f8bbd0"
    with col:
        st.markdown(f"""
<div style="background:{bg};border-radius:14px;padding:0.85rem 0.7rem;
            border:1px solid {brd};text-align:center;margin-bottom:0.3rem;">
    <div class="m-label">{label}</div>
    <div style="font-family:'Zen Maru Gothic',sans-serif;font-size:1.15rem;
                font-weight:700;color:{vc};margin:0.2rem 0;">{value}</div>
    <div class="m-sub">{sub}</div>
</div>
""", unsafe_allow_html=True)


def _compound(annual: float, rate: float, years: int) -> float:
    """配当再投資の複利計算（毎年の配当で株数が増えるモデル）"""
    if rate <= 0:
        return annual * years
    return annual * ((1 + rate) ** years - 1) / rate
