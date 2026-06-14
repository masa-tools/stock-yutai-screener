"""
favorites.py  v6.0
==================
❤️ お気に入りウォッチリスト

【v6.0 バグ修正】
  ③ ウォッチリスト不具合の根本原因:
     number_input に "sim_shares" というキーを使っており、
     同じページで favorites の rerun が走ると widget の key が
     競合して状態が飛ぶ場合があった。
     → session_state の読み書きを完全に分離し、
       ボタン押下フラグ方式に統一。
     → _load() は毎回 session_state を参照するだけにする。
"""

import json
import os
import streamlit as st

FAVORITES_FILE = "favorites.json"
_SS_KEY        = "fav_data"   # session_state キー（他と被らない名前）


# ────────────────────────────────
# 内部: 読み書き
# ────────────────────────────────
def _ensure_loaded() -> None:
    """初回だけファイルから session_state に読み込む"""
    if _SS_KEY not in st.session_state:
        data = []
        try:
            if os.path.exists(FAVORITES_FILE):
                with open(FAVORITES_FILE, encoding="utf-8") as f:
                    data = json.load(f)
        except Exception:
            pass
        st.session_state[_SS_KEY] = data


def _save(data: list[dict]) -> None:
    """session_state を更新し、可能なら JSON にも書く"""
    st.session_state[_SS_KEY] = data
    try:
        with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _get() -> list[dict]:
    _ensure_loaded()
    return list(st.session_state[_SS_KEY])


# ────────────────────────────────
# 公開 API
# ────────────────────────────────
def is_favorite(code: str) -> bool:
    return any(d["code"] == code for d in _get())


def add_favorite(code: str, name: str, close: float,
                 dy_str: str, score: int) -> None:
    data = _get()
    if not any(d["code"] == code for d in data):
        data.append({"code": code, "name": name,
                     "close": close, "dy_str": dy_str, "score": score})
        _save(data)


def remove_favorite(code: str) -> None:
    _save([d for d in _get() if d["code"] != code])


def clear_favorites() -> None:
    _save([])


def get_favorites() -> list[dict]:
    return _get()


# ────────────────────────────────
# ❤️ 登録ボタン
# ────────────────────────────────
def render_favorite_button(code: str, name: str, close: float,
                            dy_str: str, score: int) -> None:
    """
    ❤️ / 💔 トグルボタン。

    【修正ポイント】
      st.button のクリックは「その描画サイクル内でのみ True」になる。
      rerun() を呼ぶと次のサイクルで button は False に戻るため、
      session_state フラグ経由でメッセージを持ち越す。
    """
    _ensure_loaded()
    already = is_favorite(code)
    label   = "💔 ウォッチリストから削除" if already else "❤️ ウォッチリストに追加"
    key     = f"fav_btn_{code}"

    clicked = st.button(label, key=key)
    if clicked:
        if already:
            remove_favorite(code)
            st.session_state[f"_fmsg_{code}"] = "remove"
        else:
            add_favorite(code, name, close, dy_str, score)
            st.session_state[f"_fmsg_{code}"] = "add"
        st.rerun()

    # rerun 後にメッセージを表示して消す
    mkey = f"_fmsg_{code}"
    if mkey in st.session_state:
        msg = st.session_state.pop(mkey)
        if msg == "add":
            st.success(f"「{name}」を追加しました ❤️")
        else:
            st.info(f"「{name}」を削除しました")


# ────────────────────────────────
# ウォッチリストタブ
# ────────────────────────────────
def render_watchlist_tab() -> None:
    _ensure_loaded()

    st.markdown("""
<div class="card" style="background:linear-gradient(135deg,#fce4ec,#f8bbd0);
                          text-align:center;padding:1.1rem;">
    <div style="font-size:1.3rem;font-weight:700;color:#880e4f;">❤️ ウォッチリスト</div>
    <div style="color:#ad1457;font-size:0.85rem;margin-top:0.3rem;">気になる銘柄をまとめてチェック</div>
</div>
""", unsafe_allow_html=True)

    favs  = get_favorites()
    count = len(favs)

    if count == 0:
        st.markdown("""
<div class="card" style="text-align:center;padding:2.2rem;opacity:0.7;">
    <div style="font-size:2.2rem;">❤️</div>
    <div style="font-size:0.97rem;font-weight:600;color:#c2185b;margin-top:0.6rem;">
        ウォッチリストはまだ空です
    </div>
    <div style="font-size:0.82rem;color:#999;margin-top:0.3rem;">
        「🔍 銘柄分析」タブで分析後、「❤️ ウォッチリストに追加」を押してください
    </div>
</div>
""", unsafe_allow_html=True)
        return

    hc, dc = st.columns([5, 1])
    with hc:
        st.markdown(f'<p class="sec-title">登録銘柄 {count}件</p>',
                    unsafe_allow_html=True)
    with dc:
        if st.button("🗑️ 全削除", key="wl_clear"):
            clear_favorites()
            st.rerun()

    for col, lbl in zip(
        st.columns([3, 1, 2, 2, 2, 1]),
        ["銘柄名", "コード", "株価", "配当利回り", "スコア", ""],
    ):
        col.caption(lbl)
    st.markdown("<hr style='border:none;border-top:2px solid #fce4ec;'>",
                unsafe_allow_html=True)

    for item in favs:
        _render_row(item)


def _render_row(item: dict) -> None:
    code   = item.get("code", "")
    name   = item.get("name", code)
    close  = item.get("close", 0)
    dy_str = item.get("dy_str", "―")
    score  = item.get("score", 0)
    bg     = ("linear-gradient(135deg,#f48fb1,#ce93d8)" if score >= 70
              else "linear-gradient(135deg,#f8bbd0,#f48fb1)" if score >= 50
              else "linear-gradient(135deg,#e0e0e0,#bdbdbd)")

    c1, c2, c3, c4, c5, c6 = st.columns([3, 1, 2, 2, 2, 1])
    c1.markdown(
        f"<div style='font-weight:700;color:#880e4f;padding-top:0.4rem;'>{name}</div>",
        unsafe_allow_html=True)
    c2.markdown(
        f"<div style='background:#fce4ec;color:#ad1457;border-radius:50px;"
        f"padding:0.15rem 0.4rem;font-size:0.76rem;font-weight:600;"
        f"text-align:center;margin-top:0.35rem;'>{code}</div>",
        unsafe_allow_html=True)
    c3.markdown(
        f"<div style='text-align:right;padding-top:0.4rem;"
        f"font-weight:600;'>¥{close:,.0f}</div>",
        unsafe_allow_html=True)
    c4.markdown(
        f"<div style='text-align:center;padding-top:0.4rem;"
        f"font-weight:600;color:#e91e63;'>{dy_str}</div>",
        unsafe_allow_html=True)
    c5.markdown(
        f"<div style='text-align:center;margin-top:0.25rem;'>"
        f"<span style='background:{bg};color:#fff;border-radius:50px;"
        f"padding:0.13rem 0.6rem;font-size:0.82rem;font-weight:700;'>"
        f"{score}点</span></div>",
        unsafe_allow_html=True)
    with c6:
        if st.button("🗑️", key=f"wl_del_{code}", help="削除"):
            remove_favorite(code)
            st.rerun()
    st.markdown(
        "<hr style='border:none;border-top:1px solid #fce4ec;margin:0.08rem 0;'>",
        unsafe_allow_html=True)
