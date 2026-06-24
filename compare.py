"""
compare.py  v8.0
================
📊 銘柄比較機能（P4-1b: app.py 責務分離）

【移動元】
  app.py の以下を移動:
    - _fetch_compare_data()
    - _render_compare_table()
    - render_compare_section()

【依存モジュール】
  streamlit              : UI描画
  stock_data             : get_stock_info / get_price_data / get_display_name
                           fmt_dividend_pct / fmt_dividend_str
  technical_analysis     : add_indicators / get_latest_values / calc_simple_score
  yutai_data             : get_yutai
  stock_search           : _resolve_code

【_investment_judge の扱い】
  _investment_judge は app.py 内に残存（P4-1c で分離予定）。
  render_compare_section() の引数として受け取り、
  循環 import を回避する。
"""

import streamlit as st
import numpy as np

from stock_data         import (get_stock_info, get_price_data, get_display_name,
                                fmt_dividend_pct, fmt_dividend_str)
from technical_analysis import add_indicators, get_latest_values, calc_simple_score
from yutai_data         import get_yutai
from stock_search       import _resolve_code


# ════════════════════════════════════════
# データ取得
# ════════════════════════════════════════
def _fetch_compare_data(code: str, investment_judge_fn) -> dict:
    """
    比較用データを1銘柄分まとめて取得して辞書で返す。
    取得失敗時は {"error": True, "code": code} を返す。
    総合利回り計算は _render_total_yield と同ロジックを使用。
    総合評価判定は investment_judge_fn（app.py の _investment_judge）を使用。

    Args:
        code               : 証券コード
        investment_judge_fn: _investment_judge 関数（循環import回避のため引数渡し）
    """
    try:
        info = get_stock_info(code)
        if not info:
            return {"error": True, "code": code}

        df_raw = get_price_data(code)
        if df_raw is None or df_raw.empty:
            return {"error": True, "code": code}

        df   = add_indicators(df_raw)
        tv   = get_latest_values(df)
        sc   = calc_simple_score(info, tv, code)
        yi   = get_yutai(code)
        jd   = investment_judge_fn(sc, tv, info)

        close      = tv.get("close", 0)
        dy_pct     = fmt_dividend_pct(info.get("dividendYield"))
        dy_str     = fmt_dividend_str(info.get("dividendYield"))
        yutai_val  = yi.get("yutai_value", 0)
        min_shares = yi.get("min_shares", 100)
        invest     = close * min_shares if close > 0 else 0
        yutai_pct  = (yutai_val / invest * 100) if invest > 0 and yutai_val > 0 else 0.0
        total_pct  = dy_pct + yutai_pct

        per = info.get("trailingPE") or info.get("forwardPE")
        pbr = info.get("priceToBook")
        roe = info.get("returnOnEquity")

        def _nv_str(v, decimals=1, suffix=""):
            if v is None:
                return "―"
            try:
                f = float(v)
                if np.isnan(f) or np.isinf(f):
                    return "―"
                return f"{f:.{decimals}f}{suffix}"
            except (TypeError, ValueError):
                return "―"

        name       = get_display_name(info, code)
        yutai_text = yi.get("yutai", "優待なし")
        if "データなし" in yutai_text:
            yutai_text = "優待なし"
        if len(yutai_text) > 18:
            yutai_text = yutai_text[:18] + "…"

        return {
            "error"      : False,
            "code"       : code,
            "name"       : name,
            "close"      : f"¥{close:,.0f}" if close else "―",
            "total"      : sc.get("total", 0),
            "long_mark"  : sc.get("long_mark", "○"),
            "dy_str"     : dy_str,
            "yutai_pct"  : f"{yutai_pct:.2f}%" if yutai_pct > 0 else "―",
            "total_pct"  : f"{total_pct:.2f}%" if total_pct > 0 else "―",
            "per"        : _nv_str(per, 1, "倍"),
            "pbr"        : _nv_str(pbr, 2, "倍"),
            "roe"        : _nv_str(roe and roe * 100, 1, "%"),
            "kenri"      : yi.get("kenri_month", "―"),
            "yutai_text" : yutai_text,
            "judge_stars": "★" * jd["stars"] + "☆" * (5 - jd["stars"]),
            "judge_label": jd["label"],
            "judge_pts"  : jd["points"],
        }
    except Exception:
        return {"error": True, "code": code}


# ════════════════════════════════════════
# 比較テーブル描画
# ════════════════════════════════════════
def _render_compare_table(items: list[dict]) -> None:
    """
    比較テーブルを描画する。
    2銘柄: 項目列＋銘柄A＋銘柄Bの3列レイアウト
    3銘柄: 各銘柄をカード形式で横3列（モバイル対応）
    """
    valid = [it for it in items if not it.get("error")]
    error = [it for it in items if it.get("error")]

    for e in error:
        st.warning(f"⚠️ {e['code']} のデータを取得できませんでした。時間をおいて再試行してください。")

    if not valid:
        return

    rows = [
        ("📊 総合スコア",  lambda d: f"{d['total']}点 {d['long_mark']}"),
        ("💴 株価",        lambda d: d["close"]),
        ("💰 配当利回り",  lambda d: d["dy_str"]),
        ("🎁 優待利回り",  lambda d: d["yutai_pct"]),
        ("✨ 総合利回り",  lambda d: d["total_pct"]),
        ("📈 PER",         lambda d: d["per"]),
        ("📉 PBR",         lambda d: d["pbr"]),
        ("💹 ROE",         lambda d: d["roe"]),
        ("📅 権利確定月",  lambda d: d["kenri"]),
        ("🎁 優待内容",    lambda d: d["yutai_text"]),
        ("🌸 総合評価",    lambda d: f"{d['judge_stars']} {d['judge_label']}"),
    ]

    n = len(valid)

    if n <= 2:
        col_w = [1.4] + [1.0] * n
        header_cols = st.columns(col_w)
        header_cols[0].markdown(
            "<div style='font-size:0.78rem;color:#aaa;padding:0.3rem 0;'>比較項目</div>",
            unsafe_allow_html=True)
        for i, item in enumerate(valid):
            star_color = ("#e91e63" if item["total"] >= 70
                          else "#ff9800" if item["total"] >= 55 else "#90a4ae")
            header_cols[i + 1].markdown(
                f"<div style='font-weight:700;color:{star_color};"
                f"font-size:0.88rem;padding:0.3rem 0;'>"
                f"{item['name']}<br>"
                f"<span style='font-size:0.73rem;background:#fce4ec;color:#ad1457;"
                f"border-radius:50px;padding:0.05rem 0.4rem;'>{item['code']}</span></div>",
                unsafe_allow_html=True)
        st.markdown(
            "<hr style='border:none;border-top:2px solid #fce4ec;margin:0.3rem 0;'>",
            unsafe_allow_html=True)
        for label, fn in rows:
            row_cols = st.columns(col_w)
            row_cols[0].markdown(
                f"<div style='font-size:0.80rem;color:#666;padding:0.25rem 0;"
                f"border-bottom:1px solid #fce4ec;'>{label}</div>",
                unsafe_allow_html=True)
            for i, item in enumerate(valid):
                row_cols[i + 1].markdown(
                    f"<div style='font-size:0.85rem;font-weight:600;color:#3d2b1f;"
                    f"padding:0.25rem 0;border-bottom:1px solid #fce4ec;'>{fn(item)}</div>",
                    unsafe_allow_html=True)
    else:
        card_cols = st.columns(3)
        for i, item in enumerate(valid):
            star_color = ("#e91e63" if item["total"] >= 70
                          else "#ff9800" if item["total"] >= 55 else "#90a4ae")
            rows_html = "".join(
                f"<div style='display:flex;justify-content:space-between;"
                f"padding:0.2rem 0;border-bottom:1px solid #fce4ec;font-size:0.80rem;'>"
                f"<span style='color:#888;'>{lbl}</span>"
                f"<span style='font-weight:600;color:#3d2b1f;'>{fn(item)}</span></div>"
                for lbl, fn in rows
            )
            with card_cols[i]:
                st.markdown(f"""
<div style='background:linear-gradient(135deg,#fff,#fdf0f8);border-radius:14px;
            padding:0.9rem 1rem;border:1px solid #fce4ec;margin-bottom:0.5rem;'>
    <div style='font-weight:700;color:{star_color};font-size:0.95rem;
                margin-bottom:0.5rem;text-align:center;'>
        {item['name']}<br>
        <span style='font-size:0.73rem;background:#fce4ec;color:#ad1457;
                     border-radius:50px;padding:0.05rem 0.5rem;'>{item['code']}</span>
    </div>
    {rows_html}
</div>
""", unsafe_allow_html=True)


# ════════════════════════════════════════
# 銘柄比較セクション（公開API）
# ════════════════════════════════════════
def render_compare_section(investment_judge_fn) -> None:
    """
    銘柄比較セクション。render_analysis_tab() の末尾から呼び出す。
    2銘柄必須・3銘柄目任意。_resolve_code() で企業名・コード両対応。
    compare_results は session_state にキャッシュし再描画後も保持。

    Args:
        investment_judge_fn: app.py の _investment_judge 関数
                             （循環 import 回避のため引数渡し）
    """
    with st.expander("📊 銘柄比較（2〜3銘柄）", expanded=False):
        st.caption("企業名または証券コードで入力してください（例: 9432 / NTT / コマツ）")

        c1, c2, c3 = st.columns(3)
        with c1:
            inp1 = st.text_input("銘柄1（必須）", placeholder="9432 / NTT",
                                 key="compare_input_1")
        with c2:
            inp2 = st.text_input("銘柄2（必須）", placeholder="9433 / KDDI",
                                 key="compare_input_2")
        with c3:
            inp3 = st.text_input("銘柄3（任意）", placeholder="8316 / 三菱UFJ",
                                 key="compare_input_3")

        btn_col, _ = st.columns([1, 3])
        with btn_col:
            run = st.button("🔍 比較する", key="compare_run", use_container_width=True)

        if run:
            if not inp1.strip() or not inp2.strip():
                st.error("銘柄1・銘柄2は必須です。証券コードまたは企業名を入力してください。")
                return
            codes = []
            for raw in [inp1, inp2, inp3]:
                if raw.strip():
                    code, _ = _resolve_code(raw.strip())
                    codes.append(code)
            with st.spinner("📡 比較データを取得中..."):
                results = [_fetch_compare_data(c, investment_judge_fn) for c in codes]
            st.session_state["compare_results"] = results

        results = st.session_state.get("compare_results")
        if results:
            st.markdown(
                "<div style='margin-top:0.8rem;margin-bottom:0.4rem;"
                "font-size:0.82rem;color:#aaa;'>"
                "※ 総合評価は銘柄分析タブと同じロジックで判定しています</div>",
                unsafe_allow_html=True)
            _render_compare_table(results)

