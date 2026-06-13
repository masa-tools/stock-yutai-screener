"""
calendar_tab.py
===============
📅 配当・優待カレンダータブ

既存の YUTAI_DATA を月別に整理して表示する。
APIゼロ・完全ローカル処理。

【表示構成】
  1月〜12月を st.expander() で折りたたみ
  各月に「権利確定月」が含まれる銘柄をリスト表示
"""

import streamlit as st
from yutai_data import YUTAI_DATA

# 月番号 → 表示名のマッピング
MONTH_LABELS = {
    1: "1月", 2: "2月",  3: "3月",  4: "4月",
    5: "5月", 6: "6月",  7: "7月",  8: "8月",
    9: "9月", 10: "10月", 11: "11月", 12: "12月",
}

# 月別に銘柄をまとめる（「3月・9月」のように複数月に登場する銘柄も対応）
def _build_calendar() -> dict[int, list[dict]]:
    """
    YUTAI_DATA を月別に整理した辞書を返す。

    Returns:
        {月番号: [{"code":..., "name":..., ...}, ...]}
    """
    cal: dict[int, list[dict]] = {m: [] for m in range(1, 13)}

    for code, data in YUTAI_DATA.items():
        kenri = data.get("kenri_month", "")
        if not kenri or kenri == "―":
            continue

        # 「3月・9月」「2月・8月」のような複数月を分割
        months_str = kenri.replace("・", "　").replace("、", "　").replace(",", "　")
        for part in months_str.split():
            part = part.strip()
            # 「3月」→ 3 に変換
            try:
                m = int(part.replace("月", ""))
                if 1 <= m <= 12:
                    cal[m].append({
                        "code"  : code,
                        "name"  : _get_name(code),
                        "yutai" : data.get("yutai", "―"),
                        "kenri" : kenri,
                        "value" : data.get("yutai_value", 0),
                    })
            except ValueError:
                continue

    return cal


def _get_name(code: str) -> str:
    """証券コードから銘柄名を返す（yfinanceは使わず固定辞書）"""
    names = {
        "9432": "NTT",        "9433": "KDDI",
        "9434": "ソフトバンク",  "8591": "オリックス",
        "8316": "三井住友FG",   "8058": "三菱商事",
        "2914": "JT",         "2502": "アサヒグループHD",
        "2503": "キリンHD",    "2897": "日清食品HD",
        "8267": "イオン",      "3382": "セブン&アイHD",
        "7203": "トヨタ自動車", "6758": "ソニーグループ",
        "4502": "武田薬品",    "4661": "OLC",
    }
    return names.get(code, f"コード {code}")


def render_calendar_tab() -> None:
    """配当・優待カレンダータブ全体を描画する"""

    st.markdown("""
<div class="card" style="background:linear-gradient(135deg,#e8f5e9,#c8e6c9,#b2dfdb);
                          text-align:center;padding:1.2rem;">
    <div style="font-family:'Zen Maru Gothic',sans-serif;font-size:1.3rem;
                font-weight:700;color:#1b5e20;">📅 配当・優待カレンダー</div>
    <div style="color:#2e7d32;font-size:0.87rem;margin-top:0.3rem;">
        権利確定月ごとに銘柄をまとめて表示します
    </div>
</div>
""", unsafe_allow_html=True)

    cal = _build_calendar()

    # 現在月を先頭に表示（利便性向上）
    from datetime import datetime
    current_month = datetime.now().month

    # 今月〜来月を先に開いた状態で表示
    ordered_months = (
        list(range(current_month, 13)) + list(range(1, current_month))
    )

    for m in ordered_months:
        items = cal.get(m, [])
        label = MONTH_LABELS[m]
        count = len(items)
        is_current = (m == current_month)

        header = (
            f"{'🔔 ' if is_current else ''}{label} "
            f"{'（今月）' if is_current else ''}"
            f"— {count}銘柄"
        )

        # 今月は最初から開いた状態
        with st.expander(header, expanded=is_current):
            if count == 0:
                st.caption("この月に権利確定する登録銘柄はありません")
                continue

            # カラムヘッダー
            h1, h2, h3, h4 = st.columns([1, 2, 2, 3])
            with h1: st.caption("コード")
            with h2: st.caption("銘柄名")
            with h3: st.caption("権利確定")
            with h4: st.caption("優待内容")

            st.markdown("<hr style='border:none;border-top:1px solid #e8f5e9;margin:0.2rem 0;'>",
                        unsafe_allow_html=True)

            for item in sorted(items, key=lambda x: x["value"], reverse=True):
                c1, c2, c3, c4 = st.columns([1, 2, 2, 3])
                with c1:
                    st.markdown(f"""
<span style="background:#e8f5e9;color:#2e7d32;border-radius:50px;
             padding:0.1rem 0.5rem;font-size:0.78rem;font-weight:600;">
    {item['code']}
</span>
""", unsafe_allow_html=True)
                with c2:
                    st.markdown(
                        f"<div style='font-weight:600;color:#3d2b1f;font-size:0.9rem;"
                        f"padding-top:0.1rem;'>{item['name']}</div>",
                        unsafe_allow_html=True)
                with c3:
                    st.markdown(
                        f"<div style='color:#555;font-size:0.88rem;"
                        f"padding-top:0.1rem;'>{item['kenri']}</div>",
                        unsafe_allow_html=True)
                with c4:
                    yutai_short = (
                        item["yutai"][:30] + "…"
                        if len(item["yutai"]) > 30
                        else item["yutai"]
                    )
                    val_badge = (
                        f'<span style="background:#fff9c4;color:#f57f17;'
                        f'border-radius:50px;padding:0.1rem 0.5rem;'
                        f'font-size:0.72rem;font-weight:600;margin-left:0.3rem;">'
                        f'¥{item["value"]:,}</span>'
                        if item["value"] > 0 else ""
                    )
                    st.markdown(
                        f"<div style='font-size:0.85rem;color:#555;"
                        f"padding-top:0.1rem;'>{yutai_short}{val_badge}</div>",
                        unsafe_allow_html=True)

                st.markdown(
                    "<hr style='border:none;border-top:1px dashed #e8f5e9;margin:0.15rem 0;'>",
                    unsafe_allow_html=True)

    # 凡例
    st.markdown("""
<div class="disclaimer" style="background:#e8f5e9;border-color:#81c784;">
    📌 表示データはアプリ内のマスターデータです。実際の権利確定日は各社のIRページでご確認ください。
</div>
""", unsafe_allow_html=True)
