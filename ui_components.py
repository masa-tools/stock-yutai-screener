"""
ui_components.py  v5.0
======================
UIパーツ共通モジュール

【v5.0 変更】
  ⑥ トップページの緑バナーを削除
  ⑨ スマホ対応CSS追加（メディアクエリ・タップ領域・フォントサイズ）
  ④ render_metrics の配当表示も安全変換に統一
"""

import streamlit as st


def render_css() -> None:
    """全体スタイル + スマホ対応CSSを適用"""
    st.markdown("""
<style>
/* ===== Google Fonts ===== */
@import url('https://fonts.googleapis.com/css2?family=Zen+Maru+Gothic:wght@400;700&family=Noto+Sans+JP:wght@300;400;500;700&display=swap');

/* ===== ベース ===== */
html, body, [class*="css"] {
    font-family: 'Noto Sans JP', sans-serif;
    background-color: #fdf8f5;
    color: #3d2b1f;
}
.main .block-container {
    padding-top: 1.2rem;
    padding-bottom: 3rem;
    max-width: 1050px;
    /* スマホ: 左右余白を小さく */
    padding-left: clamp(0.5rem, 3vw, 2rem);
    padding-right: clamp(0.5rem, 3vw, 2rem);
}

/* ===== ヘッダー ===== */
.app-header {
    background: linear-gradient(135deg, #fce4ec, #f8bbd0, #e1bee7);
    border-radius: 20px;
    padding: 1.4rem 1.8rem;
    text-align: center;
    margin-bottom: 1rem;
    box-shadow: 0 4px 18px rgba(233,30,99,0.08);
}
.app-header h1 {
    font-family: 'Zen Maru Gothic', sans-serif;
    font-size: clamp(1.3rem, 5vw, 1.9rem);   /* ⑨ レスポンシブフォント */
    font-weight: 700;
    color: #880e4f;
    margin: 0;
}
.app-header p {
    color: #ad1457;
    font-size: clamp(0.78rem, 3vw, 0.9rem);
    margin-top: 0.3rem;
}

/* ===== タブ ===== */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    border-bottom: 2px solid #f8bbd0;
    background: transparent;
    /* ⑨ スマホ: 横スクロール対応 */
    overflow-x: auto;
    flex-wrap: nowrap;
    -webkit-overflow-scrolling: touch;
}
.stTabs [data-baseweb="tab"] {
    background: #fff0f5;
    border-radius: 10px 10px 0 0 !important;
    padding: 0.45rem clamp(0.6rem, 2vw, 1.3rem);
    font-weight: 600;
    font-size: clamp(0.78rem, 2.5vw, 0.95rem);
    color: #c2185b;
    border: 1px solid #f8bbd0;
    border-bottom: none;
    white-space: nowrap;   /* ⑨ タブ名の折り返し禁止 */
}
.stTabs [aria-selected="true"] {
    background: #fce4ec !important;
    color: #880e4f !important;
}

/* ===== カード ===== */
.card {
    background: #fff;
    border-radius: 18px;
    padding: 1.1rem 1.3rem;
    box-shadow: 0 2px 14px rgba(200,100,120,0.08);
    border: 1px solid #fce4ec;
    margin-bottom: 0.8rem;
}

/* ===== メトリクスカード ===== */
.m-card {
    background: linear-gradient(135deg, #fff9fb, #fce4ec);
    border-radius: 14px;
    padding: 0.9rem 0.8rem;
    border: 1px solid #f8bbd0;
    text-align: center;
    height: 100%;
}
.m-label {
    font-size: clamp(0.62rem, 2vw, 0.7rem);
    color: #ad1457;
    font-weight: 600;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    margin-bottom: 0.2rem;
}
.m-value {
    font-family: 'Zen Maru Gothic', sans-serif;
    font-size: clamp(1.1rem, 4vw, 1.45rem);
    font-weight: 700;
    color: #3d2b1f;
}
.m-sub  { font-size: clamp(0.65rem, 2vw, 0.72rem); color: #999; margin-top: 0.1rem; }
.m-hint { font-size: clamp(0.62rem, 2vw, 0.7rem); color: #ce93d8; margin-top: 0.2rem; font-weight: 500; }

/* ===== セクションタイトル ===== */
.sec-title {
    font-family: 'Zen Maru Gothic', sans-serif;
    font-size: clamp(1rem, 4vw, 1.1rem);
    font-weight: 700;
    color: #880e4f;
    margin: 1.2rem 0 0.5rem;
    padding-left: 0.7rem;
    border-left: 4px solid #f48fb1;
}

/* ===== スコアバッジ ===== */
.score-badge {
    display: inline-block;
    background: linear-gradient(135deg, #f48fb1, #ce93d8);
    color: #fff;
    border-radius: 50px;
    padding: 0.28rem 0.9rem;
    font-weight: 700;
    font-size: clamp(0.9rem, 3vw, 1rem);
    box-shadow: 0 2px 8px rgba(206,147,216,0.4);
}

/* ===== プログレスバー ===== */
.bar-wrap {
    background: #fce4ec;
    border-radius: 50px;
    height: 10px;
    overflow: hidden;
    margin-top: 0.2rem;
}
.bar-fill {
    height: 100%;
    border-radius: 50px;
    background: linear-gradient(90deg, #f48fb1, #ce93d8);
}

/* ===== 免責 ===== */
.disclaimer {
    background: #fff9c4;
    border-left: 4px solid #ffd54f;
    border-radius: 0 10px 10px 0;
    padding: 0.55rem 0.9rem;
    font-size: clamp(0.72rem, 2.5vw, 0.78rem);
    color: #5d4037;
    margin: 0.6rem 0;
}

/* ===== ボタン ===== */
.stButton button {
    background: linear-gradient(135deg, #f48fb1, #ce93d8) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 50px !important;
    /* ⑨ スマホ: タップしやすい最小サイズを確保 */
    padding: clamp(0.45rem, 2vw, 0.55rem) clamp(1rem, 4vw, 1.7rem) !important;
    font-weight: 700 !important;
    font-size: clamp(0.85rem, 3vw, 1rem) !important;
    min-height: 44px;   /* iOS推奨タップ最小サイズ */
    box-shadow: 0 3px 12px rgba(244,143,177,0.4) !important;
}

/* ===== 入力フィールド ===== */
.stTextInput input, .stNumberInput input {
    border-radius: 12px !important;
    border: 2px solid #f8bbd0 !important;
    background: #fff9fb !important;
    font-size: clamp(0.9rem, 3vw, 1rem) !important;
    min-height: 44px;   /* ⑨ タップしやすい高さ */
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color: #f48fb1 !important;
    box-shadow: 0 0 0 3px rgba(244,143,177,0.2) !important;
}

/* ===== ラジオボタン ===== */
.stRadio label {
    font-size: clamp(0.85rem, 3vw, 0.95rem) !important;
    padding: 0.3rem 0 !important;
}

/* ===== フッター ===== */
.footer {
    text-align: center;
    font-size: clamp(0.65rem, 2vw, 0.73rem);
    color: #bbb;
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 1px solid #fce4ec;
}

/* ===== ⑨ スマホ専用メディアクエリ（〜600px） ===== */
@media (max-width: 600px) {
    /* カードの余白を狭く */
    .card { padding: 0.8rem 0.9rem; border-radius: 14px; }
    .m-card { padding: 0.7rem 0.5rem; border-radius: 12px; }

    /* st.columns が狭い画面で崩れないように */
    [data-testid="column"] { min-width: 0 !important; }

    /* expander タイトルを読みやすく */
    .streamlit-expanderHeader {
        font-size: 0.88rem !important;
        padding: 0.6rem 0.8rem !important;
    }

    /* ヘッダーの余白調整 */
    .app-header { padding: 1rem 1rem; border-radius: 14px; }
}
</style>
""", unsafe_allow_html=True)


def render_header() -> None:
    """アプリヘッダー（🌸は page_icon 側のみ・h1には含めない）"""
    st.markdown("""
<div class="app-header">
    <h1>株主優待スクリーナー</h1>
    <p>財務・テクニカル・配当・株主優待の4軸で日本株をやさしく分析</p>
</div>
""", unsafe_allow_html=True)


def render_stock_header(name: str, code: str, tv: dict, total_score: int) -> None:
    """銘柄名・株価・前日比・スコアのヘッダーカード"""
    close = tv.get("close", 0)
    chg   = tv.get("change", 0)
    chg_p = tv.get("change_pct", 0)
    c_col   = "#e91e63" if chg >= 0 else "#1565c0"
    c_arrow = "▲" if chg >= 0 else "▼"
    c_sign  = "+" if chg >= 0 else ""
    mark    = "◎" if total_score >= 72 else "○" if total_score >= 52 else "△"

    # ⑨ flex-wrap:wrap でスマホ時は縦積み
    st.markdown(f"""
<div class="card" style="display:flex;align-items:center;
                          justify-content:space-between;
                          flex-wrap:wrap;gap:0.8rem;">
    <div>
        <div style="font-family:'Zen Maru Gothic',sans-serif;
                    font-size:clamp(1.3rem,5vw,1.65rem);
                    font-weight:700;color:#880e4f;">{name}</div>
        <div style="color:#ad1457;font-size:0.86rem;margin-top:0.2rem;">
            証券コード: <strong>{code}</strong>
        </div>
    </div>
    <div style="text-align:right;">
        <div style="font-family:'Zen Maru Gothic',sans-serif;
                    font-size:clamp(1.5rem,6vw,2rem);
                    font-weight:700;color:#3d2b1f;">¥{close:,.0f}</div>
        <div style="color:{c_col};font-weight:600;font-size:clamp(0.85rem,3vw,1rem);">
            {c_arrow} {c_sign}{chg:,.0f}円（{c_sign}{chg_p:.2f}%）
        </div>
    </div>
    <div style="text-align:center;">
        <div style="font-size:0.7rem;color:#ad1457;font-weight:600;margin-bottom:0.2rem;">
            総合スコア
        </div>
        <div class="score-badge" style="font-size:clamp(1.3rem,5vw,1.7rem);
                                         padding:0.25rem 1rem;">
            {total_score}<span style="font-size:0.82rem;">点</span>
        </div>
        <div style="font-size:1.1rem;margin-top:0.2rem;">{mark}</div>
    </div>
</div>
""", unsafe_allow_html=True)


def render_metrics(info: dict, tv: dict) -> None:
    """PER・PBR・配当利回り・時価総額を4列カードで表示"""
    from stock_data import fmt_num, fmt_yen

    per = info.get("trailingPE") or info.get("forwardPE")
    pbr = info.get("priceToBook")
    dy  = info.get("dividendYield")
    mc  = info.get("marketCap")

    per_hint = ""
    if per:
        p = float(per)
        per_hint = ("割安水準" if p <= 12 else "標準的な水準" if p <= 22
                    else "やや割高" if p <= 30 else "高成長期待型")

    pbr_hint = ""
    if pbr:
        b = float(pbr)
        pbr_hint = ("解散価値以下（超割安）" if b < 1
                    else "割安〜適正水準" if b <= 2 else "やや割高")

    # ④ 安全な配当変換
    div_str, div_hint = _safe_dividend_display(dy)

    cols = st.columns(4)
    _metric(cols[0], "PER（株価収益率）",
            fmt_num(per,1,"倍") if per else "―", "10〜20倍が目安", per_hint)
    _metric(cols[1], "PBR（株価純資産倍率）",
            fmt_num(pbr,2,"倍") if pbr else "―", "1倍以下＝割安の目安", pbr_hint)
    _metric(cols[2], "配当利回り", div_str, "3〜5%が高配当", div_hint)
    _metric(cols[3], "時価総額", fmt_yen(mc), "大型ほど安定傾向", "")


def render_technical(tv: dict) -> None:
    """トレンド・RSI・MACD・出来高を意味付きで表示"""
    rsi       = tv.get("rsi")
    rsi_v     = rsi if rsi else 50
    rsi_color = ("#ef9a9a" if rsi_v >= 70 else "#90caf9" if rsi_v <= 30
                 else "linear-gradient(90deg,#f48fb1,#ce93d8)")
    trend     = tv.get("trend", "")
    t_color   = "#2e7d32" if "上昇" in trend else "#c62828" if "下降" in trend else "#555"
    macd_note = tv.get("macd_note", "")
    m_color   = "#2e7d32" if ("上昇" in macd_note or "🟢" in macd_note) else "#c62828"

    # ⑨ grid → flex-wrap でスマホでは縦積み
    st.markdown(f"""
<div class="card">
<div style="display:grid;
            grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
            gap:1.1rem;">

  <div>
    <div class="m-label">📉 中期トレンド</div>
    <div style="font-size:1.1rem;font-weight:700;color:{t_color};margin:0.3rem 0;">
      {trend}
    </div>
    <div style="font-size:0.83rem;color:#555;line-height:1.5;">
      {tv.get('trend_note','')}
    </div>
    <div style="font-size:0.76rem;color:#aaa;margin-top:0.25rem;">
      25日線 {_fp(tv.get('ma25'))} ／ 75日線 {_fp(tv.get('ma75'))}
    </div>
  </div>

  <div>
    <div class="m-label">🔥 RSI（相対力指数）</div>
    <div style="font-size:1rem;font-weight:600;color:#3d2b1f;margin:0.3rem 0;">
      {tv.get('rsi_note','')}
    </div>
    <div class="bar-wrap">
      <div class="bar-fill" style="width:{min(100,rsi_v):.0f}%;background:{rsi_color};"></div>
    </div>
    <div style="display:flex;justify-content:space-between;font-size:0.68rem;
                color:#bbb;margin-top:0.15rem;">
      <span>売られすぎ(30)</span><span>適正</span><span>買われすぎ(70)</span>
    </div>
  </div>

  <div>
    <div class="m-label">📊 MACD</div>
    <div style="font-size:1rem;font-weight:600;color:{m_color};margin:0.3rem 0;">
      {macd_note}
    </div>
    <div style="font-size:0.76rem;color:#888;">
      MACD線がシグナル線を上回ると → 上昇サイン
    </div>
  </div>

  <div>
    <div class="m-label">📦 出来高（20日平均比）</div>
    <div style="font-size:1rem;font-weight:600;color:#555;margin:0.3rem 0;">
      {tv.get('vol_note','')}
    </div>
    <div style="font-size:0.76rem;color:#888;">
      平均より多い → 市場で注目されている
    </div>
  </div>

</div>
</div>
""", unsafe_allow_html=True)

    with st.expander("📖 テクニカル指標の読み方"):
        st.markdown("""
| 指標 | 目安 |
|------|------|
| **移動平均線** | 25日線が75日線を上抜け → 上昇サイン候補 |
| **RSI** | 70超=買われすぎ ／ 30未満=売られすぎ |
| **MACD** | MACD線がシグナル線を上回る → 上昇の勢い増加 |
| **出来高** | 急増 → ニュースや材料があった可能性 |
> ⚠️ テクニカル指標は参考情報です。これだけで投資判断しないように！
        """)


def render_score(sc: dict) -> None:
    """簡易スコア・バー・コメントを表示"""
    total = sc.get("total", 0)
    lbl   = ("長期保有に向いています" if total >= 72
             else "まずまずの評価です" if total >= 52
             else "もう少し様子を見ましょう")

    st.markdown(f"""
<div class="card" style="display:flex;align-items:center;gap:1.8rem;
                          flex-wrap:wrap;padding-bottom:1rem;margin-bottom:0;">
    <div style="text-align:center;">
        <div class="m-label">総合スコア</div>
        <div class="score-badge" style="font-size:1.5rem;padding:0.28rem 1rem;margin-top:0.2rem;">
            {total}点
        </div>
    </div>
    <div style="text-align:center;">
        <div class="m-label">長期保有評価</div>
        <div style="font-size:1.5rem;margin-top:0.15rem;">{sc.get('long_mark','○')}</div>
        <div style="font-size:0.72rem;color:#888;">{lbl}</div>
    </div>
    <div style="text-align:center;">
        <div class="m-label">配当評価</div>
        <div style="font-size:1.5rem;margin-top:0.15rem;">{sc.get('div_mark','○')}</div>
    </div>
    <div style="text-align:center;">
        <div class="m-label">テクニカル</div>
        <div style="font-size:1.5rem;margin-top:0.15rem;">{sc.get('tech_mark','○')}</div>
    </div>
</div>
""", unsafe_allow_html=True)

    render_score_bars(sc)

    comments_html = "".join(
        f"<div style='padding:0.3rem 0;border-bottom:1px solid #fce4ec;"
        f"font-size:0.88rem;color:#3d2b1f;'>🌸 {c}</div>"
        for c in sc.get("comments", [])
    )
    st.markdown(f"""
<div class="card" style="margin-top:0.4rem;">
    <div style="font-weight:700;color:#880e4f;margin-bottom:0.4rem;font-size:0.9rem;">
        💬 簡易分析コメント
        <span style="background:#e8f5e9;color:#2e7d32;border-radius:50px;
                     padding:0.08rem 0.55rem;font-size:0.7rem;font-weight:600;
                     margin-left:0.4rem;">API不要</span>
    </div>
    {comments_html}
</div>
""", unsafe_allow_html=True)


def render_score_bars(sc: dict) -> None:
    """スコアバーを縦積み表示（⑨ スマホ対応）"""
    items = [
        ("💼 財務安定性", sc.get("finance",   0), "PER・PBR・時価総額"),
        ("💰 配当",       sc.get("dividend",  0), "配当利回り・配当性向"),
        ("📊 テクニカル", sc.get("technical", 0), "トレンド・RSI・MACD"),
        ("📈 出来高",     sc.get("volume",    0), "流動性・市場の注目度"),
    ]
    st.markdown('<div class="card" style="margin-top:0.4rem;">', unsafe_allow_html=True)
    for label, score, desc in items:
        bw = min(100, max(0, score))
        bg = ("linear-gradient(90deg,#f48fb1,#ce93d8)" if score >= 70
              else "linear-gradient(90deg,#f8bbd0,#f48fb1)" if score >= 45
              else "linear-gradient(90deg,#e0e0e0,#bdbdbd)")
        st.markdown(f"""
<div style="margin-bottom:0.75rem;">
    <div style="display:flex;justify-content:space-between;margin-bottom:0.12rem;">
        <span style="font-weight:600;font-size:clamp(0.82rem,3vw,0.88rem);">{label}</span>
        <span style="font-weight:700;color:#880e4f;font-size:0.88rem;">{score}点</span>
    </div>
    <div class="bar-wrap" style="height:10px;">
        <div style="width:{bw}%;height:100%;border-radius:50px;background:{bg};"></div>
    </div>
    <div style="font-size:0.68rem;color:#aaa;margin-top:0.1rem;">{desc}</div>
</div>
""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


# ────────────────────────────────
# 内部ヘルパー
# ────────────────────────────────
def _metric(col, label: str, value: str, sub: str, hint: str) -> None:
    hint_html = f'<div class="m-hint">💡 {hint}</div>' if hint else ""
    with col:
        st.markdown(f"""
<div class="m-card">
    <div class="m-label">{label}</div>
    <div class="m-value">{value}</div>
    <div class="m-sub">{sub}</div>
    {hint_html}
</div>
""", unsafe_allow_html=True)


def _safe_dividend_display(dy) -> tuple[str, str]:
    """配当利回りを (表示文字列, ヒント) に変換（安全版）"""
    if dy is None:
        return "無配当", ""
    try:
        val = float(dy)
        pct = val * 100 if val <= 1.0 else val
        if pct < 0.1 or pct > 30:
            return "―", ""
        hint = ("理想的な高配当 ✨" if 3 <= pct <= 5.5
                else "安定した配当" if pct >= 1.5
                else "低配当（成長型）")
        return f"{pct:.2f}%", hint
    except (TypeError, ValueError):
        return "―", ""


def _fp(val) -> str:
    """株価フォーマット"""
    if val is None:
        return "―"
    try:
        return f"¥{float(val):,.0f}"
    except Exception:
        return "―"
