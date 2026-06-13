"""
recommend.py
============
タブ2「⭐ AIおすすめ銘柄TOP5」

【設計方針】
  - スクリーニングは簡易スコア（APIゼロ）で実行
  - 1日1回だけ計算してキャッシュ（節約）
  - 除外フィルター: 赤字・低位株・出来高不足
  - カード形式で上位5銘柄を表示
"""

import streamlit as st
import pandas as pd
import time
from datetime import datetime

from stock_data         import get_price_data, get_stock_info, get_display_name
from technical_analysis import add_indicators, get_latest_values, calc_simple_score
from yutai_data         import get_yutai


# ────────────────────────────────
# スクリーニング対象の候補銘柄
# ────────────────────────────────
# 追加・削除したい場合はここのリストを編集するだけ
CANDIDATES = [
    ("8591", "オリックス"),
    ("9432", "NTT"),
    ("9433", "KDDI"),
    ("9434", "ソフトバンク"),
    ("2914", "JT"),
    ("8316", "三井住友FG"),
    ("8267", "イオン"),
    ("3382", "セブン&アイHD"),
    ("2503", "キリンHD"),
    ("2502", "アサヒグループHD"),
    ("2897", "日清食品HD"),
    ("8058", "三菱商事"),
    ("7203", "トヨタ自動車"),
    ("4661", "オリエンタルランド"),
    ("6758", "ソニーグループ"),
]


# ────────────────────────────────
# メイン描画関数
# ────────────────────────────────
def render_recommend_tab():
    """おすすめ銘柄タブを描画する"""

    # ── タブヘッダー ──────────────
    st.markdown("""
<div class="card" style="background:linear-gradient(135deg,#fce4ec,#f8bbd0,#e1bee7);
                          text-align:center;padding:1.3rem;">
    <div style="font-family:'Zen Maru Gothic',sans-serif;font-size:1.35rem;
                font-weight:700;color:#880e4f;">⭐ AIおすすめ銘柄 TOP5</div>
    <div style="color:#ad1457;font-size:0.87rem;margin-top:0.3rem;">
        財務・配当・優待・テクニカルを総合スコアでランキング
    </div>
</div>
""", unsafe_allow_html=True)

    # ── スクリーニング条件の説明 ──
    with st.expander("📋 スクリーニング条件を見る"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
**✅ 選定基準**
1. 東証プライム大型・中型株
2. 営業利益が黒字
3. 配当利回りあり
4. 出来高が一定以上
5. 優待あり銘柄を加点
            """)
        with col2:
            st.markdown("""
**❌ 除外条件**
- 赤字企業
- 株価200円未満（低位株）
- 20日平均出来高1万株未満
            """)

    # ── 1日1回キャッシュでスコア計算 ─
    today = datetime.now().strftime("%Y-%m-%d")
    cache_key = f"ranking_{today}"

    if cache_key not in st.session_state:
        ranking = _run_screening()
        st.session_state[cache_key] = ranking
    else:
        ranking = st.session_state[cache_key]

    if not ranking:
        st.error("ランキングデータの取得に失敗しました。しばらくしてリロードしてください。")
        return

    # ── TOP5 カード表示 ───────────
    st.markdown('<p class="sec-title">🏆 今日のおすすめ銘柄</p>',
                unsafe_allow_html=True)

    for rank, item in enumerate(ranking[:5], 1):
        _render_card(rank, item)

    # 更新日時・免責
    st.markdown(f"""
<div style="text-align:right;font-size:0.73rem;color:#bbb;margin-top:0.7rem;">
    📅 {today} 更新 ｜ データ: Yahoo Finance
</div>
<div class="disclaimer">
    ⚠️ このランキングは自動スコアリングによる参考情報です。
    投資判断はご自身でお願いします。
</div>
""", unsafe_allow_html=True)


# ────────────────────────────────
# スクリーニング実行
# ────────────────────────────────
def _run_screening() -> list[dict]:
    """全候補銘柄をスキャンしてスコア順に返す"""
    results = []
    total   = len(CANDIDATES)
    pb = st.progress(0, text="🌸 銘柄データをスキャン中...")

    for i, (code, default_name) in enumerate(CANDIDATES):
        try:
            pb.progress((i + 1) / total,
                        text=f"📊 分析中: {default_name} ({i+1}/{total})")

            df_raw = get_price_data(code)
            if df_raw is None or df_raw.empty:
                continue

            info = get_stock_info(code)

            # 除外フィルター
            if _exclude(info, df_raw):
                continue

            df   = add_indicators(df_raw)
            tv   = get_latest_values(df)
            sc   = calc_simple_score(info, tv, code)
            yi   = get_yutai(code)
            name = get_display_name(info, code)

            dy   = info.get("dividendYield")

            st.write(code, dy)
            results.append({
                "code"    : code,
                "name"    : name,
                "score"   : sc["total"],
                "sc"      : sc,
                "close"   : tv.get("close", 0),
                "trend"   : tv.get("trend", "―"),
                "dy_str"  : f"{float(dy)*100:.2f}%" if dy else "無配当",
                "yutai"   : yi.get("yutai", "―"),
                "kenri"   : yi.get("kenri_month", "―"),
                "long_mark": sc.get("long_mark", "○"),
                "div_mark" : sc.get("div_mark",  "○"),
            })

            time.sleep(0.2)   # yfinanceへの負荷軽減

        except Exception:
            continue

    pb.empty()
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def _exclude(info: dict, df: pd.DataFrame) -> bool:
    """除外フィルター: Trueなら対象外"""
    # 赤字チェック
    oi = info.get("operatingIncome") or info.get("ebit")
    try:
        if oi is not None and float(oi) < 0:
            return True
    except Exception:
        pass

    if not df.empty:
        # 低位株チェック（200円未満）
        if float(df["Close"].iloc[-1]) < 200:
            return True
        # 出来高チェック（20日平均1万株未満）
        if float(df["Volume"].tail(20).mean()) < 10_000:
            return True

    return False


# ────────────────────────────────
# おすすめカード描画
# ────────────────────────────────
def _render_card(rank: int, item: dict):
    st.markdown("### テスト成功")