"""
buy_timing.py
=============
🎯 AI買い時判定（完全ローカル・Gemini不使用）

テクニカル指標・配当・スコアから「今が買い時かどうか」を
★1〜5で評価し、理由を日本語で表示する。

【判定ロジック】
  ポイント制（合計50点満点 → 5段階に変換）

  RSI       : 0〜15点（低いほど高得点）
  MACD      :  0〜10点（上昇シグナルで高得点）
  トレンド  :  0〜10点（上昇トレンドで高得点）
  出来高    :  0〜5点（平均以上で高得点）
  配当利回り:  0〜5点（3%超で高得点）
  総合スコア:  0〜5点（高スコアで高得点）
"""

from scoring_config import (RSI_OVERSOLD, RSI_SLIGHTLY_OVERSOLD,
                             RSI_NEUTRAL_LOW, RSI_NEUTRAL_HIGH, RSI_OVERBOUGHT)
from stock_data import fmt_dividend_pct


def render_buy_timing(tv: dict, sc: dict, info: dict) -> None:
    """
    買い時判定セクションを描画する。
    銘柄分析タブのテクニカル分析の下に配置する。

    Args:
        tv  : get_latest_values() の戻り値
        sc  : calc_simple_score() の戻り値
        info: yfinanceの銘柄情報
    """
    st.markdown('<p class="sec-title">🎯 買い時判定（ローカルAI）</p>',
                unsafe_allow_html=True)

    stars, points, reasons, cautions = _judge(tv, sc, info)

    # 星評価表示
    star_html  = "★" * stars + "☆" * (5 - stars)
    star_color = (
        "#e91e63" if stars >= 4 else
        "#ff9800" if stars >= 3 else
        "#90a4ae"
    )
    label = (
        "長期投資なら検討余地あり 🌸" if stars >= 4 else
        "条件が整いつつあります"      if stars == 3 else
        "もう少し様子を見ましょう"    if stars == 2 else
        "現時点では慎重に"
    )

    st.markdown(f"""
<div class="card">
    <div style="display:flex;align-items:center;gap:1.5rem;flex-wrap:wrap;
                margin-bottom:1rem;">
        <div>
            <div class="m-label">買い時スコア</div>
            <div style="font-size:1.8rem;color:{star_color};
                        font-weight:700;margin-top:0.2rem;letter-spacing:2px;">
                {star_html}
            </div>
        </div>
        <div>
            <div class="m-label">判定</div>
            <div style="font-size:1rem;font-weight:700;color:{star_color};
                        margin-top:0.3rem;">{label}</div>
        </div>
        <div>
            <div class="m-label">根拠スコア</div>
            <div style="font-family:'Zen Maru Gothic',sans-serif;
                        font-size:1.4rem;font-weight:700;color:#3d2b1f;
                        margin-top:0.2rem;">{points}<span style="font-size:0.8rem;">/50pt</span></div>
        </div>
    </div>
""", unsafe_allow_html=True)

    # 理由リスト
    col_r, col_c = st.columns(2)

    with col_r:
        st.markdown("**💚 プラス要因**")
        for r in reasons:
            st.markdown(f"- {r}")

    with col_c:
        st.markdown("**🔶 注意点**")
        for c in cautions:
            st.markdown(f"- {c}")
        if not cautions:
            st.markdown("- 特になし")

    st.markdown("""
    <div style="font-size:0.78rem;color:#bbb;margin-top:0.8rem;">
        ⚠️ この判定はテクニカル指標のみによる参考情報です。
        投資判断はご自身でお願いします。
    </div>
</div>
""", unsafe_allow_html=True)


# ────────────────────────────────
# 判定ロジック
# ────────────────────────────────
def _judge(tv: dict, sc: dict, info: dict) -> tuple[int, int, list, list]:
    """
    各指標を採点して星数・ポイント・理由・注意点を返す。

    Returns:
        (stars, total_points, reasons, cautions)
    """
    points  = 0
    reasons : list[str] = []
    cautions: list[str] = []

    rsi     = tv.get("rsi")
    macd    = tv.get("macd")
    macd_s  = tv.get("macd_signal")
    trend   = tv.get("trend", "")
    vol_r   = tv.get("vol_ratio", 1.0)
    total_s = sc.get("total", 50)

    # 配当利回りの安全な変換（stock_data.fmt_dividend_pct に統一）
    dy_pct = fmt_dividend_pct(info.get("dividendYield"))

    # ── RSI評価（0〜15点） ───────────
    if rsi is not None:
        if rsi <= RSI_OVERSOLD:
            points += 15
            reasons.append(f"RSI {rsi:.0f}：売られすぎ水準（押し目圏）")
        elif rsi <= RSI_SLIGHTLY_OVERSOLD:
            points += 12
            reasons.append(f"RSI {rsi:.0f}：やや売られすぎ、下値限定的")
        elif rsi <= RSI_NEUTRAL_LOW:
            points += 8
            reasons.append(f"RSI {rsi:.0f}：過熱感なし・適正水準")
        elif rsi <= RSI_NEUTRAL_HIGH:
            points += 5
        elif rsi <= RSI_OVERBOUGHT:
            points += 2
            cautions.append(f"RSI {rsi:.0f}：やや過熱気味")
        else:
            points += 0
            cautions.append(f"RSI {rsi:.0f}：買われすぎ注意")

    # ── MACD評価（0〜10点） ──────────
    if macd is not None and macd_s is not None:
        if macd > macd_s and macd > 0:
            points += 10
            reasons.append("MACDが上昇シグナル・強い買い勢い")
        elif macd > macd_s:
            points += 7
            reasons.append("MACDが上向きに転換中")
        elif macd < macd_s and macd < 0:
            points += 1
            cautions.append("MACDが下降シグナル")
        else:
            points += 3
            cautions.append("MACD：下向きに転換中")

    # ── トレンド評価（0〜10点） ───────
    if "上昇" in trend:
        points += 10
        reasons.append(f"中期トレンドが上昇（{trend}）")
    elif "横ばい" in trend:
        points += 5
    elif "下降" in trend:
        points += 1
        cautions.append("中期トレンドが下降中")

    # ── 出来高評価（0〜5点） ─────────
    if vol_r >= 1.5:
        points += 5
        reasons.append(f"出来高が平均の{vol_r:.1f}倍・注目度高い")
    elif vol_r >= 1.0:
        points += 3
    else:
        points += 1
        cautions.append("出来高が平均を下回る（流動性注意）")

    # ── 配当利回り評価（0〜5点） ──────
    if dy_pct >= 4.0:
        points += 5
        reasons.append(f"配当利回り{dy_pct:.1f}%の高配当")
    elif dy_pct >= 3.0:
        points += 4
        reasons.append(f"配当利回り{dy_pct:.1f}%・魅力的な水準")
    elif dy_pct >= 1.5:
        points += 2
    elif dy_pct == 0:
        cautions.append("配当なし（成長株型）")

    # ── 総合スコア評価（0〜5点） ──────
    if total_s >= 75:
        points += 5
        reasons.append("銘柄の総合スコアが高水準")
    elif total_s >= 60:
        points += 3
    elif total_s < 45:
        cautions.append("総合スコアがやや低め")

    # 星数に変換（50点満点 → 5段階）
    points = min(50, max(0, points))
    if   points >= 42: stars = 5
    elif points >= 33: stars = 4
    elif points >= 24: stars = 3
    elif points >= 15: stars = 2
    else             : stars = 1

    return stars, points, reasons, cautions
