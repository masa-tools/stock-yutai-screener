"""
calendar_tab.py  v5.0
=====================
📅 配当・優待カレンダー

【v5.0 修正】
  - candidate_stocks.py の125銘柄を対象にする
  - yutai_data にないコードも権利月を推定して表示
  - スマホ対応: カラム幅をモバイル向けに調整
"""

import streamlit as st
from yutai_data        import YUTAI_DATA, get_yutai
from candidate_stocks  import get_candidates
from stock_data        import JP_NAMES

MONTH_LABELS = {
    1:"1月", 2:"2月", 3:"3月", 4:"4月",
    5:"5月", 6:"6月", 7:"7月", 8:"8月",
    9:"9月", 10:"10月", 11:"11月", 12:"12月",
}

# yutai_dataにない銘柄の権利確定月推定（一般的な3月期決算企業）
# コードがあれば上書き、なければ「3月」をデフォルト
DEFAULT_KENRI: dict[str, str] = {
    "9432":"3月", "9433":"3月", "9434":"3月",
    "8316":"3月・9月", "8306":"3月・9月", "8411":"3月・9月",
    "8058":"3月", "8053":"3月", "8001":"3月",
    "7203":"3月", "7267":"3月", "6758":"3月",
    "4502":"3月", "4503":"3月", "4063":"3月",
    "8801":"3月", "8802":"3月", "1925":"3月",
    "9101":"3月", "9104":"3月", "9107":"3月",
}


def _build_calendar() -> dict[int, list[dict]]:
    """candidate_stocks の全銘柄を月別に整理"""
    cal: dict[int, list[dict]] = {m: [] for m in range(1, 13)}
    seen: set[str] = set()

    for code, _ in get_candidates():
        if code in seen:
            continue
        seen.add(code)

        # 優待データから権利月取得 → なければ DEFAULT_KENRI → なければ「3月」
        yi    = get_yutai(code)
        kenri = yi.get("kenri_month", "") or DEFAULT_KENRI.get(code, "3月")
        yutai = yi.get("yutai", "―")
        name  = JP_NAMES.get(code, f"コード{code}")

        # 「3月・9月」のような複数月を分割
        for part in kenri.replace("・", " ").replace("、", " ").replace(",", " ").split():
            try:
                m = int(part.replace("月", ""))
                if 1 <= m <= 12:
                    cal[m].append({
                        "code" : code,
                        "name" : name,
                        "yutai": yutai,
                        "kenri": kenri,
                        "value": yi.get("yutai_value", 0),
                    })
            except ValueError:
                continue

    return cal


def render_calendar_tab() -> None:
    st.markdown("""
<div class="card" style="background:linear-gradient(135deg,#e8f5e9,#c8e6c9,#b2dfdb);
                          text-align:center;padding:1.2rem;">
    <div style="font-size:1.3rem;font-weight:700;color:#1b5e20;">
        📅 配当・優待カレンダー
    </div>
    <div style="color:#2e7d32;font-size:0.87rem;margin-top:0.3rem;">
        権利確定月ごとに銘柄を表示（125銘柄対象）
    </div>
</div>
""", unsafe_allow_html=True)

    cal = _build_calendar()

    from datetime import datetime
    cur = datetime.now().month
    ordered = list(range(cur, 13)) + list(range(1, cur))

    for m in ordered:
        items = cal.get(m, [])
        count = len(items)
        is_cur = (m == cur)
        label  = f"{'🔔 ' if is_cur else ''}{MONTH_LABELS[m]}{'（今月）' if is_cur else ''} — {count}銘柄"

        with st.expander(label, expanded=is_cur):
            if count == 0:
                st.caption("この月が権利確定月の銘柄はありません")
                continue

            # スマホ対応: 銘柄名・コード・優待内容のみ表示
            for item in sorted(items, key=lambda x: x["code"]):
                code  = item["code"]
                name  = item["name"]
                yutai = item["yutai"]
                val   = item["value"]

                yutai_s = yutai[:28] + "…" if len(yutai) > 28 else yutai
                val_tag = (
                    f' <span style="background:#fff9c4;color:#f57f17;'
                    f'border-radius:4px;padding:0 4px;font-size:0.72rem;">'
                    f'¥{val:,}</span>' if val > 0 else ""
                )

                st.markdown(
                    f"<div style='padding:0.35rem 0;border-bottom:1px solid #e8f5e9;"
                    f"font-size:0.9rem;'>"
                    f"<span style='background:#e8f5e9;color:#2e7d32;border-radius:4px;"
                    f"padding:0.05rem 0.4rem;font-size:0.75rem;font-weight:600;"
                    f"margin-right:0.4rem;'>{code}</span>"
                    f"<strong style='color:#1b5e20;'>{name}</strong>"
                    f"<span style='color:#555;font-size:0.82rem;margin-left:0.5rem;'>"
                    f"{yutai_s}</span>{val_tag}</div>",
                    unsafe_allow_html=True)

    st.markdown("""
<div class="disclaimer" style="background:#e8f5e9;border-color:#81c784;">
    📌 権利確定月は推定値を含みます。実際の日程は各社のIR情報でご確認ください。
</div>
""", unsafe_allow_html=True)
