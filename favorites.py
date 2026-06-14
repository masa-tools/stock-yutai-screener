"""
favorites.py  v5.0
==================
❤️ お気に入りウォッチリスト

【v5.0 修正】
  - Streamlit Cloud は書き込み不可のため session_state を正として使う
  - favorites.json はローカル実行時のみ有効（存在すれば読む）
  - ボタン押下を session_state フラグで検知して rerun を確実に発火
"""

import json
import os
import streamlit as st

FAVORITES_FILE = "favorites.json"
_SS_KEY = "wl_items"   # session_state のキー


# ────────────────────────────────
# 内部: 読み書き
# ────────────────────────────────
def _load() -> list[dict]:
    """session_state → ファイルの順で読む"""
    if _SS_KEY in st.session_state:
        return list(st.session_state[_SS_KEY])
    # 初回: ファイルがあれば読み込んでsession_stateに載せる
    try:
        if os.path.exists(FAVORITES_FILE):
            with open(FAVORITES_FILE, encoding="utf-8") as f:
                data = json.load(f)
                st.session_state[_SS_KEY] = data
                return list(data)
    except Exception:
        pass
    st.session_state[_SS_KEY] = []
    return []


def _save(data: list[dict]) -> None:
    """session_state とファイル（可能なら）に保存"""
    st.session_state[_SS_KEY] = data
    try:
        with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass  # Cloud環境など書き込み不可の場合は無視


# ────────────────────────────────
# 公開 API
# ────────────────────────────────
def is_favorite(code: str) -> bool:
    return any(d["code"] == code for d in _load())


def add_favorite(code: str, name: str, close: float,
                 dy_str: str, score: int) -> None:
    data = _load()
    if not any(d["code"] == code for d in data):
        data.append({"code": code, "name": name,
                     "close": close, "dy_str": dy_str, "score": score})
        _save(data)


def remove_favorite(code: str) -> None:
    _save([d for d in _load() if d["code"] != code])


def clear_favorites() -> None:
    _save([])


def get_favorites() -> list[dict]:
    return _load()


# ────────────────────────────────
# ❤️ 登録ボタン（銘柄分析画面用）
# ────────────────────────────────
def render_favorite_button(code: str, name: str, close: float,
                            dy_str: str, score: int) -> None:
    """
    ❤️ / 💔 トグルボタン。
    session_state に変更フラグを立ててから rerun することで
    ページ再描画後も正しいラベルを表示する。
    """
    already = is_favorite(code)
    label   = "💔 ウォッチリストから削除" if already else "❤️ ウォッチリストに追加"

    if st.button(label, key=f"fav_btn_{code}"):
        if already:
            remove_favorite(code)
            st.session_state[f"fav_msg_{code}"] = "remove"
        else:
            add_favorite(code, name, close, dy_str, score)
            st.session_state[f"fav_msg_{code}"] = "add"
        st.rerun()

    # rerun 後のトースト表示
    msg_key = f"fav_msg_{code}"
    if msg_key in st.session_state:
        m = st.session_state.pop(msg_key)
        if m == "add":
            st.success(f"「{name}」をウォッチリストに追加しました ❤️")
        elif m == "remove":
            st.info(f"「{name}」をウォッチリストから削除しました")


# ────────────────────────────────
# ❤️ ウォッチリストタブ
# ────────────────────────────────
def render_watchlist_tab() -> None:
    st.markdown("""
<div class="card" style="background:linear-gradient(135deg,#fce4ec,#f8bbd0);
                          text-align:center;padding:1.2rem;">
    <div style="font-size:1.3rem;font-weight:700;color:#880e4f;">
        ❤️ ウォッチリスト
    </div>
    <div style="color:#ad1457;font-size:0.87rem;margin-top:0.3rem;">
        気になる銘柄をまとめてチェック
    </div>
</div>
""", unsafe_allow_html=True)

    favs  = get_favorites()
    count = len(favs)

    if count == 0:
        st.markdown("""
<div class="card" style="text-align:center;padding:2.5rem;opacity:0.7;">
    <div style="font-size:2.5rem;">❤️</div>
    <div style="font-size:1rem;font-weight:600;color:#c2185b;margin-top:0.7rem;">
        ウォッチリストはまだ空です
    </div>
    <div style="font-size:0.85rem;color:#999;margin-top:0.4rem;">
        「🔍 銘柄分析」で分析後に「❤️ ウォッチリストに追加」を押してください
    </div>
</div>
""", unsafe_allow_html=True)
        return

    hcol, dcol = st.columns([5, 1])
    with hcol:
        st.markdown(f'<p class="sec-title">登録銘柄 {count}件</p>',
                    unsafe_allow_html=True)
    with dcol:
        if st.button("🗑️ 全件削除", key="wl_clear_all"):
            clear_favorites()
            st.rerun()

    # ヘッダー行
    for col, lbl in zip(
        st.columns([3, 1, 2, 2, 2, 1]),
        ["銘柄名", "コード", "現在株価", "配当利回り", "スコア", ""],
    ):
        col.caption(lbl)
    st.markdown("<hr style='border:none;border-top:2px solid #fce4ec;'>",
                unsafe_allow_html=True)

    for item in favs:
        _row(item)


def _row(item: dict) -> None:
    code   = item.get("code", "")
    name   = item.get("name", code)
    close  = item.get("close", 0)
    dy_str = item.get("dy_str", "―")
    score  = item.get("score", 0)
    bg     = ("linear-gradient(135deg,#f48fb1,#ce93d8)" if score >= 70
              else "linear-gradient(135deg,#f8bbd0,#f48fb1)" if score >= 50
              else "linear-gradient(135deg,#e0e0e0,#bdbdbd)")

    c1, c2, c3, c4, c5, c6 = st.columns([3, 1, 2, 2, 2, 1])
    c1.markdown(f"<div style='font-weight:700;color:#880e4f;padding-top:0.45rem;'>"
                f"{name}</div>", unsafe_allow_html=True)
    c2.markdown(f"<div style='background:#fce4ec;color:#ad1457;border-radius:50px;"
                f"padding:0.18rem 0.4rem;font-size:0.78rem;font-weight:600;"
                f"text-align:center;margin-top:0.38rem;'>{code}</div>",
                unsafe_allow_html=True)
    c3.markdown(f"<div style='text-align:right;padding-top:0.45rem;"
                f"font-weight:600;'>¥{close:,.0f}</div>", unsafe_allow_html=True)
    c4.markdown(f"<div style='text-align:center;padding-top:0.45rem;"
                f"font-weight:600;color:#e91e63;'>{dy_str}</div>",
                unsafe_allow_html=True)
    c5.markdown(f"<div style='text-align:center;margin-top:0.3rem;'>"
                f"<span style='background:{bg};color:#fff;border-radius:50px;"
                f"padding:0.15rem 0.65rem;font-size:0.85rem;font-weight:700;'>"
                f"{score}点</span></div>", unsafe_allow_html=True)
    with c6:
        if st.button("🗑️", key=f"wl_del_{code}", help="削除"):
            remove_favorite(code)
            st.rerun()
    st.markdown("<hr style='border:none;border-top:1px solid #fce4ec;margin:0.1rem 0;'>",
                unsafe_allow_html=True)
