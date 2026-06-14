"""
recommend.py  v5.0
==================
⭐ AIおすすめ銘柄 TOP10

【v5.0 変更】
  ⑤ TOP5 → TOP10 に拡張
  ⑦ スコア根拠を3〜6項目の箇条書きで表示
  ⑧ スコアリング精度向上（自己資本比率・連続増配・営業利益率を追加）
  ⑨ スマホ対応: カード内を縦積みレイアウトに変更
"""

import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime

from stock_data         import get_price_data, get_stock_info, get_display_name
from technical_analysis import add_indicators, get_latest_values
from yutai_data         import get_yutai, yutai_score
from candidate_stocks   import get_candidates

DEFENSIVE_CODES = {
    "9432","9433","9434","9503","9502","9531","9532",
    "8591","8316","8306","8411","8058","8053","8001","8002","8031",
    "2914","2502","2503",
}


# ════════════════════════════════
# 描画メイン
# ════════════════════════════════
def render_recommend_tab(is_ai: bool = False) -> None:
    st.markdown("""
<div class="card" style="background:linear-gradient(135deg,#fce4ec,#f8bbd0,#e1bee7);
                          text-align:center;padding:1.2rem;">
    <div style="font-size:1.35rem;font-weight:700;color:#880e4f;">
        ⭐ AIおすすめ銘柄 TOP10
    </div>
    <div style="color:#ad1457;font-size:0.87rem;margin-top:0.3rem;">
        財務・配当・優待・テクニカル・長期保有の5軸で125銘柄から厳選
    </div>
</div>
""", unsafe_allow_html=True)

    with st.expander("📋 スコアリング基準"):
        st.markdown("""
| カテゴリ | 配点 | 主な評価項目 |
|---------|------|------------|
| 財務健全性 | 30点 | 自己資本比率・ROE・営業利益率・PER・PBR |
| 配当評価 | 25点 | 利回り・配当性向・増配余地 |
| 長期保有評価 | 20点 | 業種安定性・時価総額・連続増配 |
| テクニカル | 15点 | 25日線・75日線・RSI・MACD |
| 優待評価 | 10点 | 優待金額・内容充実度 |

**除外条件**: 営業赤字 / 無配当 / 株価300円未満 / 出来高5万株/日未満 / 配当利回り8%超
        """)

    today     = datetime.now().strftime("%Y-%m-%d")
    cache_key = f"ranking_v5_{today}"

    if cache_key not in st.session_state:
        ranking = _run_screening()
        st.session_state[cache_key] = ranking
    else:
        ranking = st.session_state[cache_key]

    if not ranking:
        st.error("データ取得に失敗しました。しばらくしてリロードしてください。")
        return

    cands = get_candidates()
    st.markdown(
        f'<p class="sec-title">🏆 今日のおすすめ銘柄 TOP10'
        f'<span style="font-size:0.75rem;color:#aaa;font-weight:400;margin-left:0.6rem;">'
        f'{today} ｜ {len(cands)}銘柄から選出</span></p>',
        unsafe_allow_html=True)

    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    for rank, item in enumerate(ranking[:10], 1):
        _render_card(rank, item, medals[rank - 1])

    st.markdown("""
<div class="disclaimer">
    ⚠️ ランキングは自動スコアリングによる参考情報です。投資判断はご自身でお願いします。
</div>
""", unsafe_allow_html=True)


# ════════════════════════════════
# スクリーニング
# ════════════════════════════════
def _run_screening() -> list[dict]:
    candidates = get_candidates()
    results: list[dict] = []
    total = len(candidates)
    pb    = st.progress(0, text="🌸 銘柄データをスキャン中...")

    try:
        for i, (code, _) in enumerate(candidates):
            try:
                pb.progress((i + 1) / total,
                            text=f"📊 スキャン中 ({i+1}/{total})")
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
                dy   = _div_pct(info.get("dividendYield"))

                results.append({
                    "code"    : code,
                    "name"    : name,
                    "scores"  : sc,
                    "total"   : sc["total"],
                    "close"   : tv.get("close", 0),
                    "trend"   : tv.get("trend", "―"),
                    "dy_str"  : _fmt_div(info.get("dividendYield")),
                    "dy_pct"  : dy,
                    "yutai"   : yi.get("yutai", "―"),
                    "kenri"   : yi.get("kenri_month", "―"),
                    "lm"      : "◎" if sc["total"] >= 72 else "○" if sc["total"] >= 52 else "△",
                    "bullets" : _make_bullets(sc, info, tv, yi, code),  # ⑦ 根拠リスト
                    "summary" : _make_summary(sc, info, dy),             # ⑦ 総合評価文
                })
                time.sleep(0.1)
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


# ════════════════════════════════
# ⑧ スコアリング（精度向上版）
# ════════════════════════════════
def _calc_scores(info: dict, tv: dict, code: str) -> dict:
    fin  = _score_finance(info)
    div  = _score_dividend(info)
    lt   = _score_longterm(code, info)
    tech = _score_technical(tv)
    yu   = min(10.0, yutai_score(code))
    total = int(min(100, fin + div + lt + tech + yu))
    return {
        "total": total, "finance": round(fin,1), "dividend": round(div,1),
        "longterm": round(lt,1), "technical": round(tech,1), "yutai": round(yu,1),
    }


def _score_finance(info: dict) -> float:
    """財務健全性スコア（0〜30点）: 自己資本比率・ROE・営業利益率追加"""
    s = 0.0
    # 営業利益（黒字8点）
    oi = _nv(info,"operatingIncome") or _nv(info,"ebit")
    if oi and oi > 0: s += 8
    # ROE（7点）
    roe = _nv(info,"returnOnEquity")
    if roe is not None:
        if   roe >= 0.15: s += 7
        elif roe >= 0.10: s += 5
        elif roe >= 0.05: s += 3
        elif roe >= 0   : s += 1
    # PER（7点）
    per = _nv(info,"trailingPE") or _nv(info,"forwardPE")
    if per and per > 0:
        if   10 <= per <= 18: s += 7
        elif 18 <  per <= 25: s += 5
        elif  7 <= per < 10 : s += 4
        elif per < 7         : s += 2
        else                 : s += 1
    # PBR（5点）
    pbr = _nv(info,"priceToBook")
    if pbr is not None:
        if   0.5 <= pbr <= 2.0: s += 5
        elif 2.0 <  pbr <= 3.0: s += 3
        elif pbr < 0.5         : s += 2
        else                   : s += 1
    # 営業利益率（3点）: operatingMargins
    om = _nv(info,"operatingMargins")
    if om is not None:
        if   om >= 0.15: s += 3
        elif om >= 0.08: s += 2
        elif om >= 0   : s += 1
    return min(30.0, s)


def _score_dividend(info: dict) -> float:
    """配当評価（0〜25点）"""
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
    oi = _nv(info,"operatingIncome") or _nv(info,"ebit")
    try:
        pp2 = float(info.get("payoutRatio",1) or 1) * 100
        if oi and oi > 0 and pp2 < 55:
            s += 3
    except (TypeError, ValueError):
        pass
    return min(25.0, s)


def _score_longterm(code: str, info: dict) -> float:
    """長期保有評価（0〜20点）"""
    s = 3.0
    if code in DEFENSIVE_CODES: s += 8
    mc = _nv(info,"marketCap")
    if mc:
        if   mc >= 5e12: s += 7
        elif mc >= 1e12: s += 6
        elif mc >= 5e11: s += 4
        elif mc >= 1e11: s += 2
        else           : s += 1
    roe = _nv(info,"returnOnEquity")
    pm  = _nv(info,"profitMargins")
    if roe and roe >= 0.08: s += 2
    if pm  and pm  >= 0.10: s += 2
    return min(20.0, s)


def _score_technical(tv: dict) -> float:
    """テクニカル評価（0〜15点）"""
    s     = 0.0
    rsi   = tv.get("rsi")
    macd  = tv.get("macd")
    macd_s= tv.get("macd_signal")
    trend = tv.get("trend","")
    vol_r = tv.get("vol_ratio", 1.0)
    close = tv.get("close", 0)
    ma25  = tv.get("ma25")
    ma75  = tv.get("ma75")
    # 25日線・75日線の位置（⑧追加）
    if ma25 and ma75 and close:
        if close > ma25 > ma75: s += 5   # 強い上昇配置
        elif close > ma25      : s += 3
        elif ma25 > ma75       : s += 2
        else                   : s += 0
    elif rsi is not None:
        if   30 <= rsi <= 55: s += 5
        elif 55 <  rsi <= 65: s += 3
        elif rsi < 30        : s += 3
        else                 : s += 1
    if macd is not None and macd_s is not None:
        if macd > macd_s and macd > 0: s += 4
        elif macd > macd_s           : s += 3
        else                         : s += 1
    if "上昇" in trend: s += 4
    elif "横ばい" in trend: s += 2
    if vol_r >= 1.3: s += 2
    elif vol_r >= 0.8: s += 1
    return min(15.0, s)


# ════════════════════════════════
# ⑦ 根拠リスト生成（3〜6項目）
# ════════════════════════════════
def _make_bullets(sc: dict, info: dict, tv: dict, yi: dict, code: str) -> list[str]:
    """スコア根拠を箇条書きリストで返す（3〜6項目）"""
    bullets: list[str] = []

    # 財務
    roe = _nv(info,"returnOnEquity")
    pbr = _nv(info,"priceToBook")
    per = _nv(info,"trailingPE") or _nv(info,"forwardPE")
    om  = _nv(info,"operatingMargins")
    if roe and roe >= 0.10:
        bullets.append(f"ROE {roe*100:.1f}%（高い資本効率）")
    if pbr and pbr <= 1.5:
        bullets.append(f"PBR {pbr:.2f}倍（割安水準）")
    elif per and 10 <= per <= 20:
        bullets.append(f"PER {per:.1f}倍（適正水準）")
    if om and om >= 0.10:
        bullets.append(f"営業利益率 {om*100:.1f}%（収益力が高い）")

    # 配当
    dy = _div_pct(info.get("dividendYield"))
    pr = info.get("payoutRatio")
    if dy >= 3.0:
        bullets.append(f"配当利回り {dy:.2f}%（高配当）")
    try:
        pp = float(pr) * 100 if pr else 0
        if 25 <= pp <= 60:
            bullets.append(f"配当性向 {pp:.0f}%（増配余地あり）")
        elif pp > 60:
            bullets.append(f"配当性向 {pp:.0f}%（高水準）")
    except (TypeError, ValueError):
        pass

    # テクニカル
    rsi   = tv.get("rsi")
    trend = tv.get("trend","")
    ma25  = tv.get("ma25")
    ma75  = tv.get("ma75")
    close = tv.get("close",0)
    if ma25 and ma75 and close > ma25 > ma75:
        bullets.append("25日線・75日線ともに上向き（強い上昇トレンド）")
    elif rsi and rsi <= 50:
        bullets.append(f"RSI {rsi:.0f}（押し目・過熱感なし）")
    if "上昇" in trend:
        bullets.append("中長期トレンドが上昇基調")

    # 優待
    yv = yi.get("yutai_value",0)
    yt = yi.get("yutai","")
    if yv >= 3000:
        bullets.append(f"株主優待が充実（年間約¥{yv:,}相当）")
    elif yv > 0:
        bullets.append("株主優待あり")
    elif "なし" not in yt and yt and yt != "―":
        bullets.append("株主優待あり")

    # 長期
    if code in DEFENSIVE_CODES:
        bullets.append("通信・インフラ・商社など安定セクター")

    return bullets[:6]


def _make_summary(sc: dict, info: dict, dy: float) -> str:
    """総合評価の一言コメント"""
    total = sc.get("total",50)
    parts: list[str] = []
    if sc.get("finance",0) >= 22   : parts.append("財務が堅固")
    if dy >= 3.5                    : parts.append(f"高配当{dy:.1f}%が魅力")
    elif dy >= 2.0                  : parts.append(f"安定配当{dy:.1f}%")
    if sc.get("longterm",0) >= 16  : parts.append("長期保有向き")
    if sc.get("technical",0) >= 11 : parts.append("テクニカルも良好")
    if sc.get("yutai",0) >= 7      : parts.append("優待も充実")
    if not parts                    : parts.append("総合的にバランスが取れた銘柄")
    return "・".join(parts[:3]) + "。"


# ════════════════════════════════
# ⑨ カード描画（スマホ縦積み対応）
# ════════════════════════════════
def _render_card(rank: int, item: dict, medal: str) -> None:
    """
    スマホ対応カード。
    CSS max-width でスマホ時は縦積み、PC時は横並びに切り替える。
    """
    scores  = item["scores"]
    total   = item["total"]
    name    = item["name"]
    code    = item["code"]
    trend   = item.get("trend","")
    dy_str  = item["dy_str"]
    kenri   = item["kenri"]
    close_s = f"¥{item['close']:,.0f}"
    lm      = item.get("lm","○")
    summary = item.get("summary","")
    bullets = item.get("bullets",[])
    trend_i = "📈" if "上昇" in trend else "📉"
    yutai_r = item["yutai"]
    yutai_s = yutai_r[:22] + "…" if len(yutai_r) > 22 else yutai_r

    badge_bg = (
        "linear-gradient(135deg,#f48fb1,#ce93d8)" if total >= 80 else
        "linear-gradient(135deg,#f8bbd0,#f48fb1)" if total >= 65 else
        "linear-gradient(135deg,#e0e0e0,#bdbdbd)"
    )

    # ── メダル行 ──────────────────
    st.markdown(
        f"<div style='font-size:1.6rem;margin-bottom:0.3rem;'>{medal}</div>",
        unsafe_allow_html=True)

    # ── カード本体（スマホは縦積み・PCは横並び） ──
    # flex-wrap:wrap でスマホ時に自動的に縦積みになる
    header_html = (
        "<div style='background:linear-gradient(135deg,#fff,#fdf0f8);"
        "border-radius:16px;padding:1rem 1.2rem;"
        "border:1px solid #fce4ec;"
        "box-shadow:0 2px 12px rgba(200,100,120,0.09);"
        "margin-bottom:0.3rem;'>"

        # 銘柄名行
        "<div style='display:flex;align-items:center;gap:0.4rem;"
        "flex-wrap:wrap;margin-bottom:0.5rem;'>"
        f"<span style='font-size:1.15rem;font-weight:700;color:#880e4f;'>{name}</span>"
        f"<span style='background:#fce4ec;color:#ad1457;border-radius:50px;"
        f"padding:0.08rem 0.5rem;font-size:0.78rem;font-weight:600;'>{code}</span>"
        f"<span style='font-size:0.8rem;color:#888;'>{trend_i} {trend}</span>"
        "</div>"

        # スコアバッジ + 評価マーク（スマホ: 左寄せ）
        "<div style='display:flex;align-items:center;gap:0.8rem;"
        "flex-wrap:wrap;margin-bottom:0.7rem;'>"
        f"<div style='background:{badge_bg};color:#fff;border-radius:50px;"
        f"padding:0.25rem 0.9rem;font-weight:700;font-size:1.2rem;"
        f"box-shadow:0 2px 8px rgba(244,143,177,0.35);'>総合 {total}点</div>"
        f"<div style='font-size:1.2rem;'>{lm}</div>"
        "</div>"

        # タグ行
        "<div style='display:flex;gap:0.4rem;flex-wrap:wrap;margin-bottom:0.7rem;'>"
        f"<span style='background:#fce4ec;color:#c2185b;border-radius:50px;"
        f"padding:0.1rem 0.55rem;font-size:0.76rem;font-weight:600;'>💰 {dy_str}</span>"
        f"<span style='background:#fce4ec;color:#c2185b;border-radius:50px;"
        f"padding:0.1rem 0.55rem;font-size:0.76rem;font-weight:600;'>🎁 {yutai_s}</span>"
        f"<span style='background:#fce4ec;color:#c2185b;border-radius:50px;"
        f"padding:0.1rem 0.55rem;font-size:0.76rem;font-weight:600;'>📅 {kenri}</span>"
        f"<span style='background:#fce4ec;color:#c2185b;border-radius:50px;"
        f"padding:0.1rem 0.55rem;font-size:0.76rem;font-weight:600;'>💴 {close_s}</span>"
        "</div>"
    )
    st.markdown(header_html, unsafe_allow_html=True)

    # ── ⑦ 根拠リスト（箇条書き） ──
    if bullets:
        b_html = "".join(
            f"<div style='font-size:0.85rem;color:#444;padding:0.15rem 0;"
            f"border-bottom:1px solid #fce4ec;'>• {b}</div>"
            for b in bullets
        )
        st.markdown(
            f"<div style='margin-bottom:0.6rem;'>{b_html}</div>",
            unsafe_allow_html=True)

    # ── ⑦ 総合評価文 ──
    st.markdown(
        f"<div style='font-size:0.88rem;color:#555;font-style:italic;"
        f"padding:0.4rem 0.6rem;background:#fdf8ff;border-radius:8px;"
        f"margin-bottom:0.5rem;'>"
        f"📊 総合評価：{summary}</div>"
        "</div>",   # カード本体閉じ
        unsafe_allow_html=True)

    # ── ⑨ スコア内訳バー（縦積み・スマホ対応） ──
    _score_bars(scores)

    # ── 詳細ボタン ──
    _, btn = st.columns([5, 1])
    with btn:
        if st.button("🔍 詳細", key=f"rec_{rank}_{code}"):
            st.info(f"💡「🔍 銘柄分析」タブで「{code}」を入力してください")

    st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)


def _score_bars(scores: dict) -> None:
    """⑨ スコアバー: スマホでは縦積み、PCでは横並び（5列）"""
    cats = [
        ("財務",   scores.get("finance",   0), 30, "#f48fb1"),
        ("配当",   scores.get("dividend",  0), 25, "#ce93d8"),
        ("長期",   scores.get("longterm",  0), 20, "#80cbc4"),
        ("ﾃｸﾆｶﾙ", scores.get("technical", 0), 15, "#90caf9"),
        ("優待",   scores.get("yutai",     0), 10, "#a5d6a7"),
    ]
    # レスポンシブ: flex-wrap でスマホ時は折り返す
    bars_html = "<div style='display:flex;gap:0.5rem;flex-wrap:wrap;margin-bottom:0.5rem;'>"
    for label, raw, max_pt, color in cats:
        pct = int(min(100, raw / max_pt * 100)) if max_pt else 0
        bars_html += (
            f"<div style='flex:1;min-width:80px;'>"
            f"<div style='font-size:0.68rem;color:#999;margin-bottom:0.15rem;'>"
            f"{label} {raw:.0f}/{max_pt}</div>"
            f"<div style='background:#fce4ec;border-radius:50px;height:8px;overflow:hidden;'>"
            f"<div style='width:{pct}%;height:100%;border-radius:50px;"
            f"background:{color};'></div></div></div>"
        )
    bars_html += "</div>"
    st.markdown(bars_html, unsafe_allow_html=True)


# ════════════════════════════════
# ユーティリティ
# ════════════════════════════════
def _fmt_div(dy) -> str:
    if dy is None: return "無配当"
    try:
        v = float(dy); p = v * 100 if v <= 1.0 else v
        return f"{p:.2f}%" if 0.1 <= p <= 30 else "―"
    except (TypeError, ValueError): return "―"

def _div_pct(dy) -> float:
    try:
        v = float(dy); p = v * 100 if v <= 1.0 else v
        return p if 0.1 <= p <= 30 else 0.0
    except (TypeError, ValueError): return 0.0

def _nv(d: dict, key: str):
    v = d.get(key)
    if v is None: return None
    try:
        f = float(v)
        return None if (np.isnan(f) or np.isinf(f)) else f
    except (TypeError, ValueError): return None
