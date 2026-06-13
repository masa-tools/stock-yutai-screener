"""
recommend.py  v4.1
==================
⭐ AIおすすめ銘柄TOP5

【v4.1 修正】
  Fix①  _render_card のHTML内f-stringでシングルクォートが文字列を
         閉じてしまう問題を修正
         → item['name'] → {name} のように事前に変数に展開してから渡す
  Fix⑥  CANDIDATESを candidate_stocks.py から読み込むよう変更

【スコアリング（計100点）】
  財務健全性   30点 : 営業利益・ROE・PER・PBR・利益成長
  配当評価     25点 : 利回り・配当性向・増配余地
  長期保有評価 20点 : 業種・時価総額・安定性
  テクニカル   15点 : RSI・MACD・トレンド・出来高
  優待評価     10点 : 優待金額・内容充実度
"""

import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime

from stock_data          import get_price_data, get_stock_info, get_display_name
from technical_analysis  import add_indicators, get_latest_values
from yutai_data          import get_yutai, yutai_score
from candidate_stocks    import get_candidates

# ディフェンシブ・インフラ・通信・商社（長期評価で加点）
DEFENSIVE_CODES = {
    "9432","9433","9434","9503","9502","9531","9532",
    "8591","8316","8306","8411","8058","8053","8001","8002","8031",
    "2914","2502","2503",
}


# ════════════════════════════════════════
# メイン描画
# ════════════════════════════════════════
def render_recommend_tab(is_ai: bool = False) -> None:
    st.markdown("""
<div class="card" style="background:linear-gradient(135deg,#fce4ec,#f8bbd0,#e1bee7);
                          text-align:center;padding:1.3rem;">
    <div style="font-family:'Zen Maru Gothic',sans-serif;font-size:1.35rem;
                font-weight:700;color:#880e4f;">⭐ AIおすすめ銘柄 TOP5</div>
    <div style="color:#ad1457;font-size:0.87rem;margin-top:0.3rem;">
        財務・配当・優待・テクニカル・長期保有の5軸で厳選
    </div>
</div>
""", unsafe_allow_html=True)

    with st.expander("📋 スコアリング基準を見る"):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("""
**✅ 採点基準（計100点）**
| カテゴリ | 配点 |
|---------|------|
| 財務健全性 | 30点 |
| 配当評価 | 25点 |
| 長期保有評価 | 20点 |
| テクニカル | 15点 |
| 優待評価 | 10点 |
            """)
        with c2:
            candidates = get_candidates()
            st.markdown(f"""
**❌ 除外条件**
- 営業赤字企業
- 無配当・異常高配当（8%超）
- 株価300円未満
- 出来高5万株/日未満

**候補数**: {len(candidates)}銘柄からTOP5を選定
            """)

    today     = datetime.now().strftime("%Y-%m-%d")
    cache_key = f"ranking_v4_{today}"

    if cache_key not in st.session_state:
        ranking = _run_screening()
        st.session_state[cache_key] = ranking
    else:
        ranking = st.session_state[cache_key]

    if not ranking:
        st.error("ランキングデータの取得に失敗しました。しばらくしてリロードしてください。")
        return

    st.markdown('<p class="sec-title">🏆 今日のおすすめ銘柄</p>',
                unsafe_allow_html=True)

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    for rank, item in enumerate(ranking[:5], 1):
        _render_card(rank, item, medals[rank - 1])

    st.markdown(f"""
<div style="text-align:right;font-size:0.73rem;color:#bbb;margin-top:0.7rem;">
    📅 {today} 更新 ｜ スコアリングv4.1 ｜ {len(get_candidates())}銘柄から選出
</div>
<div class="disclaimer">
    ⚠️ ランキングは自動スコアリングによる参考情報です。投資判断はご自身でお願いします。
</div>
""", unsafe_allow_html=True)


# ════════════════════════════════════════
# スクリーニング実行
# ════════════════════════════════════════
def _run_screening() -> list[dict]:
    candidates = get_candidates()
    results: list[dict] = []
    total = len(candidates)
    pb    = st.progress(0, text="🌸 銘柄データをスキャン中...")

    try:
        for i, (code, default_name) in enumerate(candidates):
            try:
                pb.progress((i + 1) / total,
                            text=f"📊 {default_name} ({i+1}/{total})")

                df_raw = get_price_data(code)
                if df_raw is None or df_raw.empty:
                    continue

                info = get_stock_info(code)
                if _exclude(info, df_raw):
                    continue

                df   = add_indicators(df_raw)
                tv   = get_latest_values(df)
                yi   = get_yutai(code)
                name = get_display_name(info, code)
                sc   = _calc_scores(info, tv, code)

                results.append({
                    "code"  : code,
                    "name"  : name,
                    "scores": sc,
                    "total" : sc["total"],
                    "close" : tv.get("close", 0),
                    "trend" : tv.get("trend", "―"),
                    "dy_str": _fmt_div(info.get("dividendYield")),
                    "dy_pct": _div_pct(info.get("dividendYield")),
                    "yutai" : yi.get("yutai", "―"),
                    "kenri" : yi.get("kenri_month", "―"),
                    "lm"    : "◎" if sc["total"] >= 72 else "○" if sc["total"] >= 52 else "△",
                    "dm"    : _div_mark(_div_pct(info.get("dividendYield"))),
                    "reason": _make_reason(sc, info, tv, yi),
                })
                time.sleep(0.15)
            except Exception:
                continue
    finally:
        pb.empty()

    results.sort(key=lambda x: x["total"], reverse=True)
    return results


def _exclude(info: dict, df: pd.DataFrame) -> bool:
    try:
        oi = info.get("operatingIncome") or info.get("ebit")
        if oi is not None and float(oi) < 0:
            return True
    except (TypeError, ValueError):
        pass
    if df.empty:
        return True
    try:
        if float(df["Close"].iloc[-1]) < 300:
            return True
    except (IndexError, ValueError):
        pass
    try:
        if float(df["Volume"].tail(20).mean()) < 50_000:
            return True
    except ValueError:
        pass
    dy = _div_pct(info.get("dividendYield"))
    if dy == 0 or dy > 8.0:
        return True
    return False


# ════════════════════════════════════════
# スコアリング
# ════════════════════════════════════════
def _calc_scores(info: dict, tv: dict, code: str) -> dict:
    fin  = _score_finance(info)
    div  = _score_dividend(info)
    lt   = _score_longterm(code, info)
    tech = _score_technical(tv)
    yu   = min(10.0, yutai_score(code))
    total = int(min(100, fin + div + lt + tech + yu))
    return {
        "total": total,
        "finance": round(fin, 1),
        "dividend": round(div, 1),
        "longterm": round(lt, 1),
        "technical": round(tech, 1),
        "yutai": round(yu, 1),
    }


def _score_finance(info: dict) -> float:
    s = 0.0
    oi = _nv(info, "operatingIncome") or _nv(info, "ebit")
    if oi and oi > 0: s += 8
    roe = _nv(info, "returnOnEquity")
    if roe is not None:
        if   roe >= 0.15: s += 7
        elif roe >= 0.10: s += 5
        elif roe >= 0.05: s += 3
        elif roe >= 0   : s += 1
    per = _nv(info, "trailingPE") or _nv(info, "forwardPE")
    if per and per > 0:
        if   10 <= per <= 18: s += 7
        elif 18 <  per <= 25: s += 5
        elif  7 <= per < 10 : s += 4
        elif per < 7         : s += 2
        else                 : s += 1
    pbr = _nv(info, "priceToBook")
    if pbr is not None:
        if   0.8 <= pbr <= 2.0: s += 5
        elif 2.0 <  pbr <= 3.0: s += 3
        elif pbr < 0.8         : s += 2
        else                   : s += 1
    rg = _nv(info, "revenueGrowth")
    if rg is not None:
        if   rg >= 0.08: s += 3
        elif rg >= 0   : s += 2
    return min(30.0, s)


def _score_dividend(info: dict) -> float:
    s  = 0.0
    dy = _div_pct(info.get("dividendYield"))
    if   3.5 <= dy <= 5.0: s += 15
    elif 3.0 <= dy < 3.5 : s += 13
    elif 5.0 < dy <= 6.5 : s += 10
    elif 2.0 <= dy < 3.0 : s += 8
    elif dy >= 1.5        : s += 4
    elif dy > 0           : s += 2
    pr = info.get("payoutRatio")
    try:
        pp = float(pr) * 100 if pr else 0
        if   30 <= pp <= 55: s += 7
        elif 55 < pp <= 70 : s += 5
        elif 20 <= pp < 30 : s += 4
        elif 70 < pp <= 85 : s += 2
        elif pp > 0         : s += 3
    except (TypeError, ValueError):
        pass
    oi = _nv(info, "operatingIncome") or _nv(info, "ebit")
    try:
        pp2 = float(info.get("payoutRatio", 1) or 1) * 100
        if oi and oi > 0 and pp2 < 55:
            s += 3
    except (TypeError, ValueError):
        pass
    return min(25.0, s)


def _score_longterm(code: str, info: dict) -> float:
    s = 3.0
    if code in DEFENSIVE_CODES:
        s += 8
    mc = _nv(info, "marketCap")
    if mc:
        if   mc >= 5e12: s += 7
        elif mc >= 1e12: s += 6
        elif mc >= 5e11: s += 4
        elif mc >= 1e11: s += 2
        else           : s += 1
    roe = _nv(info, "returnOnEquity")
    pm  = _nv(info, "profitMargins")
    if roe and roe >= 0.08: s += 3
    if pm  and pm  >= 0.10: s += 2
    return min(20.0, s)


def _score_technical(tv: dict) -> float:
    s     = 0.0
    rsi   = tv.get("rsi")
    macd  = tv.get("macd")
    macd_s= tv.get("macd_signal")
    trend = tv.get("trend", "")
    vol_r = tv.get("vol_ratio", 1.0)
    if rsi is not None:
        if   30 <= rsi <= 50: s += 5
        elif 50 <  rsi <= 65: s += 4
        elif rsi < 30        : s += 4
        elif 65 <  rsi <= 72: s += 2
    if macd is not None and macd_s is not None:
        if macd > macd_s and macd > 0: s += 4
        elif macd > macd_s           : s += 3
        else                         : s += 1
    if "上昇" in trend: s += 4
    elif "横ばい" in trend: s += 2
    if vol_r >= 1.3: s += 2
    elif vol_r >= 0.8: s += 1
    return min(15.0, s)


def _make_reason(scores: dict, info: dict, tv: dict, yi: dict) -> str:
    parts: list[str] = []
    dy = _div_pct(info.get("dividendYield"))
    if scores.get("finance", 0) >= 24: parts.append("財務が非常に堅固")
    elif scores.get("finance", 0) >= 18: parts.append("財務安定")
    if scores.get("dividend", 0) >= 20: parts.append(f"高配当{dy:.1f}%で魅力的")
    elif scores.get("dividend", 0) >= 14: parts.append(f"配当{dy:.1f}%と安定")
    if scores.get("longterm", 0) >= 16: parts.append("長期保有向きの安定セクター")
    rsi = tv.get("rsi")
    if scores.get("technical", 0) >= 12 and rsi and rsi <= 55:
        parts.append("テクニカル的に押し目圏")
    elif scores.get("technical", 0) >= 10:
        parts.append("テクニカル良好")
    yv = yi.get("yutai_value", 0)
    if yv >= 3000: parts.append("充実した株主優待あり")
    elif yv > 0: parts.append("株主優待あり")
    if not parts: parts.append("複合的に見てバランスが取れた銘柄")
    return "・".join(parts[:4]) + "。"


# ════════════════════════════════════════
# カード描画（Fix① f-string内クォート修正）
# ════════════════════════════════════════
def _render_card(rank: int, item: dict, medal: str) -> None:
    """
    おすすめ銘柄カードを描画する。

    【Fix① 修正ポイント】
      f-string内で item['name'] のようにシングルクォートを使うと、
      f-stringのクォートと衝突してSyntaxErrorや意図しない文字列終端が
      発生し、HTMLがそのまま表示される。
      → すべての変数を f-string の外で先に変数に代入してから使う。
    """
    scores = item["scores"]
    total  = item["total"]
    # ↓ f-string外で全変数を展開しておく（Fix①の核心）
    name        = item["name"]
    code        = item["code"]
    trend       = item.get("trend", "")
    reason      = item["reason"]
    dy_str      = item["dy_str"]
    kenri       = item["kenri"]
    close_str   = f"¥{item['close']:,.0f}"
    lm          = item.get("lm", "○")
    trend_icon  = "📈" if "上昇" in trend else "📉"
    yutai_raw   = item["yutai"]
    yutai_short = yutai_raw[:24] + "…" if len(yutai_raw) > 24 else yutai_raw

    badge_bg = (
        "linear-gradient(135deg,#f48fb1,#ce93d8)" if total >= 80 else
        "linear-gradient(135deg,#f8bbd0,#f48fb1)" if total >= 65 else
        "linear-gradient(135deg,#e0e0e0,#bdbdbd)"
    )

    # メダル + カード本体 + スコアバッジ
    c_medal, c_main, c_score = st.columns([0.5, 4, 1.5])

    with c_medal:
        st.markdown(
            f"<div style='font-size:1.8rem;text-align:center;"
            f"padding-top:0.6rem;'>{medal}</div>",
            unsafe_allow_html=True)

    with c_main:
        # 変数はすべて上で展開済みなのでf-string内にクォートなし
        html = (
            "<div style='background:linear-gradient(135deg,#fff,#fdf0f8);"
            "border-radius:16px;padding:1.1rem 1.3rem;"
            "border:1px solid #fce4ec;"
            "box-shadow:0 2px 12px rgba(200,100,120,0.09);'>"
            "<div style='display:flex;align-items:center;gap:0.5rem;"
            "margin-bottom:0.6rem;'>"
            f"<span style='font-family:\"Zen Maru Gothic\",sans-serif;"
            f"font-size:1.2rem;font-weight:700;color:#880e4f;'>{name}</span>"
            f"<span style='background:#fce4ec;color:#ad1457;border-radius:50px;"
            f"padding:0.1rem 0.5rem;font-size:0.78rem;font-weight:600;'>{code}</span>"
            f"<span style='font-size:0.82rem;color:#888;'>"
            f"{trend_icon} {trend}</span>"
            "</div>"
            f"<div style='font-size:0.9rem;color:#555;margin-bottom:0.7rem;"
            f"line-height:1.6;font-style:italic;'>{reason}</div>"
            "<div style='display:flex;gap:0.5rem;flex-wrap:wrap;'>"
            f"<span style='background:#fce4ec;color:#c2185b;border-radius:50px;"
            f"padding:0.12rem 0.6rem;font-size:0.74rem;font-weight:600;'>"
            f"💰 {dy_str}</span>"
            f"<span style='background:#fce4ec;color:#c2185b;border-radius:50px;"
            f"padding:0.12rem 0.6rem;font-size:0.74rem;font-weight:600;'>"
            f"🎁 {yutai_short}</span>"
            f"<span style='background:#fce4ec;color:#c2185b;border-radius:50px;"
            f"padding:0.12rem 0.6rem;font-size:0.74rem;font-weight:600;'>"
            f"📅 {kenri}</span>"
            f"<span style='background:#fce4ec;color:#c2185b;border-radius:50px;"
            f"padding:0.12rem 0.6rem;font-size:0.74rem;font-weight:600;'>"
            f"💴 {close_str}</span>"
            "</div>"
            "</div>"
        )
        st.markdown(html, unsafe_allow_html=True)

    with c_score:
        score_html = (
            "<div style='text-align:center;padding-top:0.5rem;'>"
            "<div class='m-label'>総合スコア</div>"
            f"<div style='background:{badge_bg};color:#fff;border-radius:50px;"
            f"padding:0.3rem 0.8rem;font-weight:700;font-size:1.3rem;"
            f"display:inline-block;margin:0.3rem 0;"
            f"box-shadow:0 2px 8px rgba(244,143,177,0.35);'>"
            f"{total}点</div>"
            f"<div style='font-size:1.1rem;margin-top:0.2rem;'>{lm}</div>"
            "</div>"
        )
        st.markdown(score_html, unsafe_allow_html=True)

    # スコア内訳バー
    _render_score_breakdown(scores)

    _, btn_col = st.columns([5, 1])
    with btn_col:
        if st.button("🔍 詳細", key=f"rec_{rank}_{code}"):
            st.info(f"💡「🔍 銘柄分析」タブで「{code}」を入力してください")

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)


def _render_score_breakdown(scores: dict) -> None:
    cats = [
        ("財務",   scores.get("finance",    0), 30, "#f48fb1"),
        ("配当",   scores.get("dividend",   0), 25, "#ce93d8"),
        ("長期",   scores.get("longterm",   0), 20, "#80cbc4"),
        ("ﾃｸﾆｶﾙ", scores.get("technical",  0), 15, "#90caf9"),
        ("優待",   scores.get("yutai",      0), 10, "#a5d6a7"),
    ]
    cols = st.columns(5)
    for col, (label, raw, max_pt, color) in zip(cols, cats):
        pct = int(min(100, raw / max_pt * 100)) if max_pt else 0
        with col:
            st.markdown(
                f"<div style='text-align:center;padding:0.3rem 0.2rem;'>"
                f"<div style='font-size:0.67rem;color:#999;margin-bottom:0.2rem;'>{label}</div>"
                f"<div style='background:#fce4ec;border-radius:50px;height:7px;overflow:hidden;'>"
                f"<div style='width:{pct}%;height:100%;border-radius:50px;background:{color};'>"
                f"</div></div>"
                f"<div style='font-size:0.72rem;color:#888;margin-top:0.2rem;'>"
                f"{raw:.0f}/{max_pt}</div></div>",
                unsafe_allow_html=True)


# ════════════════════════════════════════
# ユーティリティ
# ════════════════════════════════════════
def _fmt_div(dy) -> str:
    if dy is None: return "無配当"
    try:
        v = float(dy)
        p = v * 100 if v <= 1.0 else v
        return f"{p:.2f}%" if 0.1 <= p <= 30 else "―"
    except (TypeError, ValueError): return "―"

def _div_pct(dy) -> float:
    try:
        v = float(dy)
        p = v * 100 if v <= 1.0 else v
        return p if 0.1 <= p <= 30 else 0.0
    except (TypeError, ValueError): return 0.0

def _div_mark(dy_pct: float) -> str:
    return "◎" if dy_pct >= 3 else "○" if dy_pct >= 1.5 else "△"

def _nv(d: dict, key: str):
    v = d.get(key)
    if v is None: return None
    try:
        f = float(v)
        return None if (np.isnan(f) or np.isinf(f)) else f
    except (TypeError, ValueError): return None
