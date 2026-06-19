"""
dividend_ranking.py  v6.0
=========================
📈 増配ランキングタブ

CANDIDATES の銘柄を「配当の質」でランキングする。
Gemini API不使用・完全ローカル判定。

【スコアリング（計100点）】
  配当利回り    : 40点（3〜5%が満点）
  配当性向      : 20点（30〜60%が理想）
  財務健全性    : 20点（営業利益・PBR）
  長期保有スコア: 20点（業種・時価総額）

【増配余地コメント】
  財務データと配当性向からローカル判定で生成
"""

import streamlit as st
import time
from datetime import datetime

from stock_data         import (get_price_data, get_stock_info, get_display_name,
                                JP_NAMES, safe_float, fmt_dividend_pct)
from yutai_data         import get_yutai

from candidate_stocks import get_candidates as _get_candidates
CANDIDATES = _get_candidates()


def render_dividend_ranking_tab() -> None:
    """増配ランキングタブを描画する"""

    st.markdown("""
<div class="card" style="background:linear-gradient(135deg,#e3f2fd,#bbdefb,#e8eaf6);
                          text-align:center;padding:1.2rem;">
    <div style="font-family:'Zen Maru Gothic',sans-serif;font-size:1.3rem;
                font-weight:700;color:#1565c0;">📈 増配ランキング</div>
    <div style="color:#1976d2;font-size:0.87rem;margin-top:0.3rem;">
        配当の質・安定性・増配余地でランキング
    </div>
</div>
""", unsafe_allow_html=True)

    # 1日1回キャッシュ
    today     = datetime.now().strftime("%Y-%m-%d")
    cache_key = f"div_ranking_{today}"

    if cache_key not in st.session_state:
        ranking = _build_ranking()
        st.session_state[cache_key] = ranking
    else:
        ranking = st.session_state[cache_key]

    if not ranking:
        st.error("データ取得に失敗しました。しばらくしてリロードしてください。")
        return

    st.markdown('<p class="sec-title">🏅 配当ランキング TOP10</p>',
                unsafe_allow_html=True)

    # ヘッダー行
    hc = st.columns([0.5, 2.5, 1.2, 1.2, 1.2, 1.2, 2.5])
    for col, label in zip(hc, ["順位","銘柄","利回り","配当性向","財務","増配余地","評価コメント"]):
        col.caption(label)
    st.markdown("<hr style='border:none;border-top:2px solid #bbdefb;margin:0.2rem 0;'>",
                unsafe_allow_html=True)

    medals = ["🥇", "🥈", "🥉"]

    for i, item in enumerate(ranking[:10]):
        rank_icon = medals[i] if i < 3 else f"**{i+1}**"
        _render_row(rank_icon, item)

    st.markdown("""
<div class="disclaimer" style="background:#e3f2fd;border-color:#90caf9;">
    ※ 増配余地はPythonの条件分岐による自動判定です。実際の配当方針はIR情報をご確認ください。
</div>
""", unsafe_allow_html=True)


# ────────────────────────────────
# ランキング構築
# ────────────────────────────────
def _build_ranking() -> list[dict]:
    results: list[dict] = []
    total = len(CANDIDATES)
    pb    = st.progress(0, text="📊 配当データを集計中...")

    try:
        for i, (code, default_name) in enumerate(CANDIDATES):
            try:
                pb.progress((i+1)/total,
                            text=f"分析中: {default_name} ({i+1}/{total})")
                info = get_stock_info(code)
                name = get_display_name(info, code)

                score, dy_pct, payout_pct, fin_score, comment = _score(info, code)

                results.append({
                    "code"       : code,
                    "name"       : name,
                    "div_score"  : score,
                    "dy_str"     : f"{dy_pct:.2f}%" if dy_pct else "―",
                    "dy_pct"     : dy_pct or 0,
                    "payout_str" : f"{payout_pct:.0f}%" if payout_pct else "―",
                    "fin_str"    : f"{fin_score:.0f}点",
                    "comment"    : comment,
                })
                time.sleep(0.15)
            except Exception:
                continue
    finally:
        pb.empty()

    results.sort(key=lambda x: x["div_score"], reverse=True)
    return results


def _score(info: dict, code: str) -> tuple[float, float, float, float, str]:
    """配当スコアを計算して (スコア, 利回り%, 配当性向%, 財務点, コメント) を返す"""

    # 配当利回り
    dy_pct = fmt_dividend_pct(info.get("dividendYield"))
  
    # 配当性向
    pr = info.get("payoutRatio")
    payout = 0.0
    try:
        payout = float(pr) * 100 if pr else 0
    except Exception:
        pass

    # ── 配当利回りスコア（40点） ────
    if   4.0 <= dy_pct <= 5.5: dy_sc = 40
    elif 3.0 <= dy_pct < 4.0 : dy_sc = 35
    elif 5.5 < dy_pct <= 7.0 : dy_sc = 28
    elif 2.0 <= dy_pct < 3.0 : dy_sc = 20
    elif dy_pct > 7.0         : dy_sc = 10
    elif dy_pct > 0           : dy_sc = 8
    else                      : dy_sc = 0

    # ── 配当性向スコア（20点） ──────
    if   30 <= payout <= 55: po_sc = 20
    elif 55 < payout <= 70 : po_sc = 14
    elif 20 <= payout < 30 : po_sc = 12
    elif 70 < payout <= 85 : po_sc = 6
    elif payout > 85        : po_sc = 2
    else                    : po_sc = 5

    # ── 財務健全性スコア（20点） ────
    oi  = safe_float(info, "operatingIncome") or safe_float(info, "ebit")
    pbr = safe_float(info, "priceToBook")
    mc  = safe_float(info, "marketCap")
    fin = 0.0
    if oi and oi > 0          : fin += 8
    if pbr and pbr <= 2.0     : fin += 6
    elif pbr and pbr <= 3.0   : fin += 3
    if mc and mc >= 1e12      : fin += 6
    elif mc and mc >= 1e11    : fin += 4
    fin = min(20, fin)

    # ── 長期保有スコア（20点） ──────
    # 業種・規模・安定性で評価
    lt_sc = _longterm_score(code, info)

    total = dy_sc + po_sc + fin + lt_sc

    # ── 増配余地コメント ────────────
    comment = _make_comment(dy_pct, payout, oi, fin, lt_sc)

    return total, dy_pct, payout, fin, comment


def _longterm_score(code: str, info: dict) -> float:
    """長期保有評価（0〜20点）: 業種・規模・安定性"""
    score = 0.0
    # 通信・インフラ・商社・ディフェンシブを優遇
    infra_codes = {"9432","9433","9434","8591","8316","8058","2914"}
    if code in infra_codes:
        score += 10
    mc = safe_float(info, "marketCap")
    if mc and mc >= 1e12: score += 6
    elif mc and mc >= 1e11: score += 4
    roe = safe_float(info, "returnOnEquity")
    if roe and roe >= 0.10: score += 4
    elif roe and roe >= 0.05: score += 2
    return min(20, score)


def _make_comment(dy: float, payout: float, oi, fin: float, lt: float) -> str:
    """増配余地コメントをローカル判定で生成する"""
    parts: list[str] = []

    if dy >= 3.5:
        parts.append("高配当")
    if 30 <= payout <= 55:
        parts.append("配当性向が健全で増配余地あり")
    elif payout > 75:
        parts.append("配当性向が高く減配リスクに注意")
    if oi and oi > 0 and fin >= 14:
        parts.append("財務安定")
    if lt >= 10:
        parts.append("長期保有向き")
    if dy >= 4.5:
        parts.append("利回り魅力大")

    if not parts:
        parts.append("データを確認中")

    return "・".join(parts)


def _render_row(rank_icon, item: dict) -> None:
    """ランキング1行を描画"""
    cols = st.columns([0.5, 2.5, 1.2, 1.2, 1.2, 1.2, 2.5])

    cols[0].markdown(f"<div style='padding-top:0.5rem;text-align:center;'>{rank_icon}</div>",
                     unsafe_allow_html=True)

    cols[1].markdown(f"""
<div style="padding-top:0.4rem;">
    <span style="font-weight:700;color:#880e4f;">{item['name']}</span>
    <span style="background:#fce4ec;color:#ad1457;border-radius:50px;
                 padding:0.05rem 0.4rem;font-size:0.72rem;margin-left:0.3rem;">
        {item['code']}
    </span>
</div>
""", unsafe_allow_html=True)

    dy_color = "#e91e63" if item["dy_pct"] >= 3 else "#555"
    cols[2].markdown(
        f"<div style='padding-top:0.45rem;font-weight:700;color:{dy_color};'>"
        f"{item['dy_str']}</div>",
        unsafe_allow_html=True)

    cols[3].markdown(
        f"<div style='padding-top:0.45rem;color:#555;'>{item['payout_str']}</div>",
        unsafe_allow_html=True)

    cols[4].markdown(
        f"<div style='padding-top:0.45rem;color:#555;'>{item['fin_str']}</div>",
        unsafe_allow_html=True)

    sc = item["div_score"]
    badge = (
        "linear-gradient(135deg,#f48fb1,#ce93d8)" if sc >= 75 else
        "linear-gradient(135deg,#90caf9,#80cbc4)"
    )
    cols[5].markdown(f"""
<div style="margin-top:0.3rem;">
    <span style="background:{badge};color:#fff;border-radius:50px;
                 padding:0.15rem 0.6rem;font-size:0.85rem;font-weight:700;">
        {sc:.0f}点
    </span>
</div>
""", unsafe_allow_html=True)

    cols[6].markdown(
        f"<div style='padding-top:0.45rem;font-size:0.82rem;color:#555;'>"
        f"{item['comment']}</div>",
        unsafe_allow_html=True)

    st.markdown("<hr style='border:none;border-top:1px solid #e3f2fd;margin:0.2rem 0;'>",
                unsafe_allow_html=True)
