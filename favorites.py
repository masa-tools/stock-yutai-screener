"""
favorites.py
============
❤️ お気に入りウォッチリスト機能

【v4.1 修正】
  Fix③ st.rerun()後にsession_stateが消える問題を解消
       → JSONファイルを正とし、session_stateはキャッシュとして使わない
       → ボタン押下後はst.rerun()で確実に再描画
"""

import json
import os
import streamlit as st

FAVORITES_FILE = "favorites.json"


# ────────────────────────────────
# 読み書きユーティリティ
# ────────────────────────────────
def _load() -> list[dict]:
    """favorites.json から読み込む（常にファイルが正）"""
    try:
        if os.path.exists(FAVORITES_FILE):
            with open(FAVORITES_FILE, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []


def _save(data: list[dict]) -> None:
    """favorites.json に書き込む"""
    try:
        with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.warning(f"⚠️ お気に入りの保存に失敗しました: {e}")


# ────────────────────────────────
# 公開 API
# ────────────────────────────────
def is_favorite(code: str) -> bool:
    """登録済みかどうかを返す"""
    return any(item["code"] == code for item in _load())


def add_favorite(code: str, name: str, close: float,
                 dy_str: str, score: int) -> None:
    """お気に入りに追加（重複は無視）"""
    data = _load()
    if not any(d["code"] == code for d in data):
        data.append({
            "code"  : code,
            "name"  : name,
            "close" : close,
            "dy_str": dy_str,
            "score" : score,
        })
        _save(data)


def remove_favorite(code: str) -> None:
    """お気に入りから削除"""
    _save([d for d in _load() if d["code"] != code])


def clear_favorites() -> None:
    """全件削除"""
    _save([])


def get_favorites() -> list[dict]:
    """登録済み一覧を返す"""
    return _load()


# ────────────────────────────────
# ❤️ 登録ボタン
# ────────────────────────────────
def render_favorite_button(code: str, name: str, close: float,
                            dy_str: str, score: int) -> None:
    """
    「❤️ / 💔」トグルボタンを表示する。

    【Fix③ 修正ポイント】
      ボタンキーに code を含め、st.rerun() で確実に再描画する。
      session_state キャッシュに依存しない設計。
    """
    already = is_favorite(code)
    label   = "💔 ウォッチリストから削除" if already else "❤️ ウォッチリストに追加"

    if st.button(label, key=f"fav_{code}"):
        if already:
            remove_favorite(code)
            st.toast(f"「{name}」をウォッチリストから削除しました")
        else:
            add_favorite(code, name, close, dy_str, score)
            st.toast(f"「{name}」を追加しました ❤️")
        st.rerun()


# ────────────────────────────────
# ❤️ ウォッチリストタブ
# ────────────────────────────────
def render_watchlist_tab() -> None:
    """ウォッチリストタブ全体を描画する"""

    st.markdown("""
<div class="card" style="background:linear-gradient(135deg,#fce4ec,#f8bbd0);
                          text-align:center;padding:1.2rem;">
    <div style="font-family:'Zen Maru Gothic',sans-serif;font-size:1.3rem;
                font-weight:700;color:#880e4f;">❤️ ウォッチリスト</div>
    <div style="color:#ad1457;font-size:0.87rem;margin-top:0.3rem;">
        気になる銘柄をまとめてチェック
    </div>
</div>
""", unsafe_allow_html=True)

    favorites = get_favorites()
    count     = len(favorites)

    if count == 0:
        st.markdown("""
<div class="card" style="text-align:center;padding:2.5rem;opacity:0.7;">
    <div style="font-size:2.5rem;">❤️</div>
    <div style="font-size:1rem;font-weight:600;color:#c2185b;margin-top:0.7rem;">
        ウォッチリストはまだ空です
    </div>
    <div style="font-size:0.85rem;color:#999;margin-top:0.3rem;">
        「🔍 銘柄分析」タブで銘柄を分析して「❤️ ウォッチリストに追加」を押してください
    </div>
</div>
""", unsafe_allow_html=True)
        return

    col_h, col_del = st.columns([4, 1])
    with col_h:
        st.markdown(f'<p class="sec-title">登録銘柄 {count}件</p>',
                    unsafe_allow_html=True)
    with col_del:
        if st.button("🗑️ 全件削除", key="clear_all_fav"):
            clear_favorites()
            st.rerun()

    # カラムヘッダー
    h1, h2, h3, h4, h5 = st.columns([3, 1, 2, 2, 1])
    for col, label in zip([h1,h2,h3,h4,h5],
                          ["銘柄名","コード","株価","配当利回り","操作"]):
        col.caption(label)

    st.markdown("<hr style='border:none;border-top:2px solid #fce4ec;margin:0.2rem 0;'>",
                unsafe_allow_html=True)

    for item in favorites:
        _render_row(item)


def _render_row(item: dict) -> None:
    """ウォッチリスト1行を描画"""
    code   = item.get("code", "")
    name   = item.get("name", code)
    close  = item.get("close", 0)
    dy_str = item.get("dy_str", "―")
    score  = item.get("score", 0)

    badge_bg = (
        "linear-gradient(135deg,#f48fb1,#ce93d8)" if score >= 70 else
        "linear-gradient(135deg,#f8bbd0,#f48fb1)" if score >= 50 else
        "linear-gradient(135deg,#e0e0e0,#bdbdbd)"
    )

    c1, c2, c3, c4, c5 = st.columns([3, 1, 2, 2, 1])

    with c1:
        st.markdown(
            f"<div style='font-weight:700;color:#880e4f;padding-top:0.5rem;"
            f"font-family:\"Zen Maru Gothic\",sans-serif;'>{name}</div>",
            unsafe_allow_html=True)
    with c2:
        st.markdown(
            f"<div style='background:#fce4ec;color:#ad1457;border-radius:50px;"
            f"padding:0.2rem 0.4rem;font-size:0.78rem;font-weight:600;"
            f"text-align:center;margin-top:0.45rem;'>{code}</div>",
            unsafe_allow_html=True)
    with c3:
        st.markdown(
            f"<div style='text-align:right;padding-top:0.5rem;"
            f"font-weight:600;color:#3d2b1f;'>¥{close:,.0f}</div>",
            unsafe_allow_html=True)
    with c4:
        st.markdown(
            f"<div style='text-align:center;padding-top:0.5rem;"
            f"font-weight:600;color:#e91e63;'>{dy_str}</div>",
            unsafe_allow_html=True)
    with c5:
        if st.button("🗑️", key=f"del_{code}", help=f"{name}を削除"):
            remove_favorite(code)
            st.rerun()

    st.markdown(
        "<hr style='border:none;border-top:1px solid #fce4ec;margin:0.1rem 0;'>",
        unsafe_allow_html=True)
