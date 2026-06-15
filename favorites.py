"""
favorites.py  v7.0
==================
❤️ お気に入りウォッチリスト

【v7.0 不具合修正①】
  原因: render_favorite_button() で st.rerun() を呼ぶと、
        銘柄分析タブ全体（yfinance取得・指標計算・チャート描画）が
        再実行されてフリーズしていた。

  修正方針:
    - st.rerun() を完全廃止
    - st.button の on_click コールバックで状態変更のみ行う
    - メッセージは st.empty() プレースホルダーで即時表示
    - rerun なしでも session_state の変更は即反映される
"""

import json
import os
import streamlit as st

FAVORITES_FILE = "favorites.json"
_SS_KEY        = "fav_data"


# ────────────────────────────────
# 内部: 読み書き
# ────────────────────────────────
def _ensure_loaded() -> None:
    """初回のみファイルから session_state に読み込む"""
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
    """session_state を更新し、可能ならJSONにも書く"""
    st.session_state[_SS_KEY] = data
    try:
        with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass  # Cloud環境など書き込み不可の場合は無視


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
# ❤️ 登録ボタン（フリーズ修正版）
# ────────────────────────────────
def render_favorite_button(code: str, name: str, close: float,
                            dy_str: str, score: int) -> None:
    """
    ❤️ / 💔 トグルボタン。

    【v7.0 修正ポイント】
      st.rerun() を廃止。
      on_click コールバックで状態変更のみ行い、
      メッセージは st.empty() で即時表示する。
      これにより銘柄分析タブ全体の再実行（フリーズ）を防ぐ。
    """
    _ensure_loaded()

    already  = is_favorite(code)
    label    = "💔 ウォッチリストから削除" if already else "❤️ ウォッチリストに追加"
    msg_key  = f"_fav_msg_{code}"
    ph       = st.empty()   # メッセージ表示用プレースホルダー

    # on_click で状態変更（rerun なし）
    def _on_click():
        if is_favorite(code):
            remove_favorite(code)
            st.session_state[msg_key] = ("info", f"「{name}」をウォッチリストから削除しました")
        else:
            add_favorite(code, name, close, dy_str, score)
            st.session_state[msg_key] = ("success", f"「{name}」を追加しました ❤️")

    st.button(label, key=f"fav_btn_{code}", on_click=_on_click)

    # メッセージがあれば表示（次の描画サイクルで自動消去）
    if msg_key in st.session_state:
        kind, msg = st.session_state.pop(msg_key)
        if kind == "success":
            ph.success(msg)
        else:
            ph.info(msg)


# ────────────────────────────────
# ウォッチリストタブ
# ────────────────────────────────
def render_watchlist_tab() -> None:
    _ensure_loaded()

    st.markdown("""
<div class="card" style="background:linear-gradient(135deg,#fce4ec,#f8bbd0);
                          text-align:center;padding:1.1rem;">
    <div style="font-size:1.3rem;font-weight:700;color:#880e4f;">❤️ ウォッチリスト</div>
    <div style="color:#ad1457;font-size:0.85rem;margin-top:0.3rem;">
        気になる銘柄をまとめてチェック
    </div>
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
        def _clear():
            clear_favorites()
        st.button("🗑️ 全削除", key="wl_clear", on_click=_clear)

    for col, lbl in zip(
        st.columns([3, 1, 2, 2, 2, 1]),
        ["銘柄名", "コード", "株価", "配当利回り", "スコア", ""],
    ):
        col.caption(lbl)

    st.markdown("<hr style='border:none;border-top:2px solid #fce4ec;'>",
                unsafe_allow_html=True)

    for item in get_favorites():
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
    c1.markdown(f"<div style='font-weight:700;color:#880e4f;padding-top:0.4rem;'>{name}</div>",
                unsafe_allow_html=True)
    c2.markdown(f"<div style='background:#fce4ec;color:#ad1457;border-radius:50px;"
                f"padding:0.15rem 0.4rem;font-size:0.76rem;font-weight:600;"
                f"text-align:center;margin-top:0.35rem;'>{code}</div>",
                unsafe_allow_html=True)
    c3.markdown(f"<div style='text-align:right;padding-top:0.4rem;"
                f"font-weight:600;'>¥{close:,.0f}</div>", unsafe_allow_html=True)
    c4.markdown(f"<div style='text-align:center;padding-top:0.4rem;"
                f"font-weight:600;color:#e91e63;'>{dy_str}</div>", unsafe_allow_html=True)
    c5.markdown(f"<div style='text-align:center;margin-top:0.25rem;'>"
                f"<span style='background:{bg};color:#fff;border-radius:50px;"
                f"padding:0.13rem 0.6rem;font-size:0.82rem;font-weight:700;'>"
                f"{score}点</span></div>", unsafe_allow_html=True)

    with c6:
        def _del(c=code):
            remove_favorite(c)
        st.button("🗑️", key=f"wl_del_{code}", on_click=_del, help="削除")

    st.markdown("<hr style='border:none;border-top:1px solid #fce4ec;margin:0.08rem 0;'>",
                unsafe_allow_html=True)
