"""
ui_components.py
================
画面を構成するUIパーツをまとめたモジュール

【含む関数】
  render_css()          : パステルカラーのカスタムCSS
  render_header()       : アプリのタイトルバー
  render_stock_header() : 銘柄名・株価・前日比
  render_metrics()      : PER・PBR・配当・時価総額カード
  render_technical()    : テクニカル指標（数値の意味付き）
  render_score()        : 簡易スコアとコメント
  render_score_bars()   : スコアのバーグラフ
"""

import streamlit as st


# ════════════════════════════════
# カスタムCSS（パステル・カフェ風）
# ════════════════════════════════
def render_css():
    """アプリ全体のスタイルを適用する（最初に一度だけ呼ぶ）"""
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Zen+Maru+Gothic:wght@400;700&family=Noto+Sans+JP:wght@300;400;500;700&display=swap');

/* ===== ベース ===== */
html, body, [class*="css"] {
    font-family: 'Noto Sans JP', sans-serif;
    background-color: #fdf8f5;
    color: #3d2b1f;
}
.main .block-container {
    padding-top: 1.5rem;
    padding-bottom: 3rem;
    max-width: 1050px;
}

/* ===== ヘッダー ===== */
.app-header {
    background: linear-gradient(135deg, #fce4ec, #f8bbd0, #e1bee7);
    border-radius: 20px;
    padding: 1.6rem 2rem;
    text-align: center;
    margin-bottom: 1.2rem;
    box-shadow: 0 4px 18px rgba(233,30,99,0.08);
}
.app-header h1 {
    font-family: 'Zen Maru Gothic', sans-serif;
    font-size: 1.9rem;
    font-weight: 700;
    color: #880e4f;
    margin: 0;
}
.app-header p {
    color: #ad1457;
    font-size: 0.9rem;
    margin-top: 0.3rem;
}

/* ===== タブ ===== */
.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    border-bottom: 2px solid #f8bbd0;
    background: transparent;
}
.stTabs [data-baseweb="tab"] {
    background: #fff0f5;
    border-radius: 12px 12px 0 0 !important;
    padding: 0.5rem 1.3rem;
    font-weight: 600;
    color: #c2185b;
    border: 1px solid #f8bbd0;
    border-bottom: none;
}
.stTabs [aria-selected="true"] {
    background: #fce4ec !important;
    color: #880e4f !important;
}

/* ===== カード ===== */
.card {
    background: #fff;
    border-radius: 18px;
    padding: 1.3rem 1.5rem;
    box-shadow: 0 2px 14px rgba(200,100,120,0.08);
    border: 1px solid #fce4ec;
    margin-bottom: 0.9rem;
}

/* ===== メトリクスカード ===== */
.m-card {
    background: linear-gradient(135deg, #fff9fb, #fce4ec);
    border-radius: 16px;
    padding: 1rem 1.1rem;
    border: 1px solid #f8bbd0;
    text-align: center;
    height: 100%;
    box-shadow: 0 2px 10px rgba(200,100,120,0.06);
}
.m-label {
    font-size: 0.7rem;
    color: #ad1457;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-bottom: 0.2rem;
}
.m-value {
    font-family: 'Zen Maru Gothic', sans-serif;
    font-size: 1.45rem;
    font-weight: 700;
    color: #3d2b1f;
}
.m-sub  { font-size: 0.72rem; color: #999; margin-top: 0.1rem; }
.m-hint { font-size: 0.7rem;  color: #ce93d8; margin-top: 0.2rem; font-weight: 500; }

/* ===== セクションタイトル ===== */
.sec-title {
    font-family: 'Zen Maru Gothic', sans-serif;
    font-size: 1.1rem;
    font-weight: 700;
    color: #880e4f;
    margin: 1.3rem 0 0.6rem;
    padding-left: 0.7rem;
    border-left: 4px solid #f48fb1;
}

/* ===== スコアバッジ ===== */
.score-badge {
    display: inline-block;
    background: linear-gradient(135deg, #f48fb1, #ce93d8);
    color: #fff;
    border-radius: 50px;
    padding: 0.3rem 1rem;
    font-weight: 700;
    font-size: 1rem;
    box-shadow: 0 2px 8px rgba(206,147,216,0.4);
}

/* ===== ヒントバッジ ===== */
.hint-ok   { background:#e8f5e9; color:#2e7d32; border-radius:50px; padding:0.12rem 0.6rem; font-size:0.73rem; font-weight:600; display:inline-block; }
.hint-warn { background:#fff3e0; color:#e65100; border-radius:50px; padding:0.12rem 0.6rem; font-size:0.73rem; font-weight:600; display:inline-block; }
.hint-info { background:#e8eaf6; color:#283593; border-radius:50px; padding:0.12rem 0.6rem; font-size:0.73rem; font-weight:600; display:inline-block; }

/* ===== プログレスバー ===== */
.bar-wrap {
    background: #fce4ec;
    border-radius: 50px;
    height: 10px;
    overflow: hidden;
    margin-top: 0.25rem;
}
.bar-fill {
    height: 100%;
    border-radius: 50px;
    background: linear-gradient(90deg, #f48fb1, #ce93d8);
    transition: width 0.5s ease;
}

/* ===== 免責 ===== */
.disclaimer {
    background: #fff9c4;
    border-left: 4px solid #ffd54f;
    border-radius: 0 10px 10px 0;
    padding: 0.6rem 0.9rem;
    font-size: 0.78rem;
    color: #5d4037;
    margin: 0.7rem 0;
}

/* ===== ボタン ===== */
.stButton button {
    background: linear-gradient(135deg, #f48fb1, #ce93d8) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 50px !important;
    padding: 0.5rem 1.7rem !important;
    font-weight: 700 !important;
    box-shadow: 0 3px 12px rgba(244,143,177,0.4) !important;
}
.stButton button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 5px 18px rgba(244,143,177,0.5) !important;
}

/* ===== 入力 ===== */
.stTextInput input {
    border-radius: 12px !important;
    border: 2px solid #f8bbd0 !important;
    background: #fff9fb !important;
}
.stTextInput input:focus {
    border-color: #f48fb1 !important;
    box-shadow: 0 0 0 3px rgba(244,143,177,0.2) !important;
}

/* ===== フッター ===== */
.footer {
    text-align: center;
    font-size: 0.73rem;
    color: #bbb;
    margin-top: 2.5rem;
    padding-top: 1rem;
    border-top: 1px solid #fce4ec;
}
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════
# ヘッダー
# ════════════════════════════════
def render_header():
    """アプリのタイトルと説明を表示する"""
    st.markdown("""
<div class="app-header">
    <h1>🌸 株主優待スクリーナー</h1>
    <p>財務・テクニカル・配当の3軸で日本株をやさしく分析します</p>
</div>
<div class="disclaimer">
    ⚠️ このアプリは情報提供のみを目的としています。投資判断はご自身でお願いします。
</div>
""", unsafe_allow_html=True)


# ════════════════════════════════
# 銘柄ヘッダー（名前・株価・前日比）
# ════════════════════════════════
def render_stock_header(name: str, code: str, tv: dict, total_score: int):
    """
    銘柄名・現在株価・前日比・総合スコアをカード表示

    Args:
        name       : 銘柄名
        code       : 証券コード
        tv         : get_latest_values()の戻り値
        total_score: 総合スコア（100点満点）
    """
    close = tv.get("close", 0)
    chg   = tv.get("change", 0)
    chg_p = tv.get("change_pct", 0)

    c_col   = "#e91e63" if chg >= 0 else "#1565c0"
    c_arrow = "▲" if chg >= 0 else "▼"
    c_sign  = "+" if chg >= 0 else ""

    mark = "◎" if total_score >= 72 else "○" if total_score >= 52 else "△"

    st.markdown(f"""
<div class="card" style="display:flex;align-items:center;
                          justify-content:space-between;flex-wrap:wrap;gap:1rem;">
    <div>
        <div style="font-family:'Zen Maru Gothic',sans-serif;font-size:1.65rem;
                    font-weight:700;color:#880e4f;">{name}</div>
        <div style="color:#ad1457;font-size:0.86rem;margin-top:0.2rem;">
            証券コード: <strong>{code}</strong>
        </div>
    </div>
    <div style="text-align:right;">
        <div style="font-family:'Zen Maru Gothic',sans-serif;font-size:2rem;
                    font-weight:700;color:#3d2b1f;">¥{close:,.0f}</div>
        <div style="color:{c_col};font-weight:600;">
            {c_arrow} {c_sign}{chg:,.0f}円（{c_sign}{chg_p:.2f}%）
        </div>
    </div>
    <div style="text-align:center;">
        <div style="font-size:0.7rem;color:#ad1457;font-weight:600;margin-bottom:0.2rem;">
            総合スコア
        </div>
        <div class="score-badge" style="font-size:1.7rem;padding:0.3rem 1.1rem;">
            {total_score}<span style="font-size:0.85rem;">点</span>
        </div>
        <div style="font-size:1.1rem;margin-top:0.2rem;">{mark}</div>
    </div>
</div>
""", unsafe_allow_html=True)


# ════════════════════════════════
# 基本指標カード
# ════════════════════════════════
def render_metrics(info: dict, tv: dict):
    """
    PER・PBR・配当利回り・時価総額を4列カードで表示

    数値の意味（ヒント）も一緒に表示する
    """
    from stock_data import fmt_num, fmt_yen

    per = info.get("trailingPE") or info.get("forwardPE")
    pbr = info.get("priceToBook")
    dy  = info.get("dividendYield")
    mc  = info.get("marketCap")

    # PERのヒント
    per_hint = ""
    if per:
        p = float(per)
        per_hint = (
            "割安水準" if p <= 12 else
            "標準的な水準" if p <= 22 else
            "やや割高" if p <= 30 else
            "高成長期待型"
        )

    # PBRのヒント
    pbr_hint = ""
    if pbr:
        b = float(pbr)
        pbr_hint = (
            "解散価値以下（超割安）" if b < 1 else
            "割安〜適正水準" if b <= 2 else
            "やや割高"
        )

    # 配当のヒント
    div_str  = f"{float(dy)*100:.2f}%" if dy else "無配当"
    div_hint = ""
    if dy:
        d = float(dy) * 100
        div_hint = (
            "理想的な高配当 ✨" if 3 <= d <= 5.5 else
            "安定した配当"     if d >= 1.5 else
            "低配当（成長型）"
        )

    cols = st.columns(4)
    _metric(cols[0], "PER（株価収益率）",
            fmt_num(per, 1, "倍") if per else "―",
            "10〜20倍が目安", per_hint)
    _metric(cols[1], "PBR（株価純資産倍率）",
            fmt_num(pbr, 2, "倍") if pbr else "―",
            "1倍以下＝割安の目安", pbr_hint)
    _metric(cols[2], "配当利回り",
            div_str, "3〜5%が高配当", div_hint)
    _metric(cols[3], "時価総額",
            fmt_yen(mc), "大型ほど安定傾向", "")


# ════════════════════════════════
# テクニカル指標
# ════════════════════════════════
def render_technical(tv: dict):
    """
    トレンド・RSI・MACD・出来高を「意味付きコメント」で表示

    数値だけでなく「これが何を意味するか」を
    初心者でも分かる言葉で表示するのがポイント
    """
    rsi   = tv.get("rsi")
    rsi_v = rsi if rsi else 50

    # RSIゲージの色
    rsi_color = (
        "#ef9a9a" if rsi_v >= 70 else
        "#90caf9" if rsi_v <= 30 else
        "linear-gradient(90deg,#f48fb1,#ce93d8)"
    )

    # トレンド色
    trend = tv.get("trend", "")
    t_color = "#2e7d32" if "上昇" in trend else "#c62828" if "下降" in trend else "#555"

    # MACD色
    macd_note = tv.get("macd_note", "")
    m_color = "#2e7d32" if "上昇" in macd_note or "🟢" in macd_note else "#c62828"

    st.markdown(f"""
<div class="card">
<div style="display:grid;grid-template-columns:1fr 1fr;gap:1.3rem;">

  <!-- トレンド -->
  <div>
    <div class="m-label">📉 中期トレンド</div>
    <div style="font-size:1.15rem;font-weight:700;color:{t_color};margin:0.35rem 0;">
      {trend}
    </div>
    <div style="font-size:0.84rem;color:#555;line-height:1.6;">
      {tv.get('trend_note','')}
    </div>
    <div style="font-size:0.78rem;color:#aaa;margin-top:0.3rem;">
      25日線 {fmt_price(tv.get('ma25'))} ／ 75日線 {fmt_price(tv.get('ma75'))}
    </div>
  </div>

  <!-- RSI -->
  <div>
    <div class="m-label">🔥 RSI（相対力指数）</div>
    <div style="font-size:1.05rem;font-weight:600;color:#3d2b1f;margin:0.35rem 0;">
      {tv.get('rsi_note','')}
    </div>
    <div class="bar-wrap" style="margin-top:0.4rem;">
      <div class="bar-fill" style="width:{min(100,rsi_v):.0f}%;background:{rsi_color};"></div>
    </div>
    <div style="display:flex;justify-content:space-between;font-size:0.7rem;color:#bbb;margin-top:0.15rem;">
      <span>売られすぎ(30)</span><span>適正</span><span>買われすぎ(70)</span>
    </div>
  </div>

  <!-- MACD -->
  <div>
    <div class="m-label">📊 MACD</div>
    <div style="font-size:1.05rem;font-weight:600;color:{m_color};margin:0.35rem 0;">
      {macd_note}
    </div>
    <div style="font-size:0.78rem;color:#888;">
      MACDがシグナル線を上回ると → 上昇サイン
    </div>
  </div>

  <!-- 出来高 -->
  <div>
    <div class="m-label">📦 出来高（20日平均比）</div>
    <div style="font-size:1.05rem;font-weight:600;color:#555;margin:0.35rem 0;">
      {tv.get('vol_note','')}
    </div>
    <div style="font-size:0.78rem;color:#888;">
      平均より多い → 市場で注目されている
    </div>
  </div>

</div>
</div>
""", unsafe_allow_html=True)

    # 初心者向け解説（折りたたみ）
    with st.expander("📖 テクニカル指標の読み方（初心者向け）"):
        st.markdown("""
| 指標 | 何を見る？ | 目安 |
|------|----------|------|
| **移動平均線** | 平均株価の動き | 25日線が75日線を下から上抜け→上昇サイン候補 |
| **RSI** | 買われすぎ・売られすぎ（0〜100） | **70超**=買われすぎ ／ **30未満**=売られすぎ |
| **MACD** | トレンドの強さと方向 | MACD線がシグナル線を上回る→上昇の勢い増加 |
| **出来高** | 売買の活発さ | 急増するとニュースや材料があった可能性 |
> ⚠️ テクニカル指標はあくまで「参考情報」です。これだけで投資判断しないように！
        """)


# ════════════════════════════════
# 簡易スコア表示
# ════════════════════════════════
def render_score(sc: dict):
    """
    総合評価・各カテゴリ点数・簡易コメントを表示する

    Args:
        sc: calc_simple_score()の戻り値
    """
    total = sc.get("total", 0)
    mark  = "◎" if total >= 72 else "○" if total >= 52 else "△"
    lbl   = (
        "長期保有に向いています" if total >= 72 else
        "まずまずの評価です"     if total >= 52 else
        "もう少し様子を見ましょう"
    )

    # ── 上部: スコアと評価マーク ──────
    st.markdown(f"""
<div class="card" style="display:flex;align-items:center;gap:2rem;flex-wrap:wrap;
                          padding-bottom:1.1rem;margin-bottom:0;">
    <div style="text-align:center;">
        <div class="m-label">総合スコア</div>
        <div class="score-badge" style="font-size:1.6rem;padding:0.3rem 1rem;margin-top:0.25rem;">
            {total}点
        </div>
    </div>
    <div style="text-align:center;">
        <div class="m-label">長期保有評価</div>
        <div style="font-size:1.6rem;margin-top:0.2rem;">{sc.get('long_mark','○')}</div>
        <div style="font-size:0.72rem;color:#888;">{lbl}</div>
    </div>
    <div style="text-align:center;">
        <div class="m-label">配当評価</div>
        <div style="font-size:1.6rem;margin-top:0.2rem;">{sc.get('div_mark','○')}</div>
    </div>
    <div style="text-align:center;">
        <div class="m-label">テクニカル評価</div>
        <div style="font-size:1.6rem;margin-top:0.2rem;">{sc.get('tech_mark','○')}</div>
    </div>
</div>
""", unsafe_allow_html=True)

    # ── スコアバー ─────────────────────
    render_score_bars(sc)

    # ── 簡易コメント ───────────────────
    comments_html = "".join(
        f'<div style="padding:0.35rem 0;border-bottom:1px solid #fce4ec;'
        f'font-size:0.9rem;color:#3d2b1f;">🌸 {c}</div>'
        for c in sc.get("comments", [])
    )
    st.markdown(f"""
<div class="card" style="margin-top:0.5rem;">
    <div style="font-weight:700;color:#880e4f;margin-bottom:0.5rem;font-size:0.92rem;">
        💬 簡易分析コメント
        <span style="background:#e8f5e9;color:#2e7d32;border-radius:50px;
                     padding:0.1rem 0.6rem;font-size:0.72rem;font-weight:600;margin-left:0.5rem;">
            API不要
        </span>
    </div>
    {comments_html}
</div>
""", unsafe_allow_html=True)


def render_score_bars(sc: dict):
    """各カテゴリのスコアをバーグラフで表示"""
    items = [
        ("💼 財務安定性", sc.get("finance",   0), "PER・PBR・時価総額"),
        ("💰 配当",       sc.get("dividend",  0), "配当利回り・配当性向"),
        ("📊 テクニカル", sc.get("technical", 0), "トレンド・RSI・MACD"),
        ("📈 出来高",     sc.get("volume",    0), "流動性・市場の注目度"),
    ]
    st.markdown('<div class="card" style="margin-top:0.5rem;">', unsafe_allow_html=True)
    for label, score, desc in items:
        bw = min(100, max(0, score))
        bg = (
            "linear-gradient(90deg,#f48fb1,#ce93d8)" if score >= 70 else
            "linear-gradient(90deg,#f8bbd0,#f48fb1)" if score >= 45 else
            "linear-gradient(90deg,#e0e0e0,#bdbdbd)"
        )
        st.markdown(f"""
<div style="margin-bottom:0.8rem;">
    <div style="display:flex;justify-content:space-between;margin-bottom:0.15rem;">
        <span style="font-weight:600;font-size:0.88rem;">{label}</span>
        <span style="font-weight:700;color:#880e4f;">{score}点</span>
    </div>
    <div class="bar-wrap" style="height:10px;">
        <div style="width:{bw}%;height:100%;border-radius:50px;background:{bg};"></div>
    </div>
    <div style="font-size:0.7rem;color:#aaa;margin-top:0.1rem;">{desc}</div>
</div>
""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


# ════════════════════════════════
# 内部ヘルパー
# ════════════════════════════════
def _metric(col, label: str, value: str, sub: str, hint: str):
    """メトリクスカードを1つ描画（列オブジェクトを受け取る）"""
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


def fmt_price(val) -> str:
    """株価を「¥1,234」形式で表示。Noneなら「―」"""
    if val is None:
        return "―"
    try:
        return f"¥{float(val):,.0f}"
    except Exception:
        return "―"
