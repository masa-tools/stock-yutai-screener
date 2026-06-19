"""
favorites.py  v8.0
==================
❤️ お気に入りウォッチリスト

【v8.0 修正 ① 根本原因】
  問題1: 分析画面が消える
    → on_click コールバック後、Streamlit が再描画を行う際に
      st.text_input の値がリセットされ、code が空になって
      「未入力状態」に戻っていた。
    → favorites.py 側の修正: on_click は維持。
      app.py 側で session_state["current_code"] を保持して
      再描画後も分析を継続する（app.py 参照）。

  問題2: ウォッチリストに保存されない
    → _ensure_loaded() が毎描画サイクルで呼ばれると
      session_state が上書きされるケースがあった。
    → 初回フラグ "_fav_loaded" で確実に1回だけ読み込む。
"""

import json
import os
import streamlit as st
from stock_data import get_stock_info, fmt_dividend_str

FAVORITES_FILE = "favorites.json"
_SS_KEY    = "fav_data"
_LOAD_FLAG = "_fav_loaded"   # 初回ロード済みフラグ


# ────────────────────────────────
# 内部: 読み書き
# ────────────────────────────────
def _ensure_loaded() -> None:
    """
    セッション開始時に1回だけJSONから読み込む。
    _LOAD_FLAG で「既に読んだ」かを管理することで
    再描画ごとの上書きを防ぐ。
    """
    if st.session_state.get(_LOAD_FLAG):
        return   # 既にロード済み

    data = []
    try:
        if os.path.exists(FAVORITES_FILE):
            with open(FAVORITES_FILE, encoding="utf-8") as f:
                data = json.load(f)
    except Exception:
        pass

    st.session_state[_SS_KEY]    = data
    st.session_state[_LOAD_FLAG] = True


def _save(data: list[dict]) -> None:
    """session_state を更新し、可能なら JSON にも書く"""
    st.session_state[_SS_KEY] = data
    try:
        with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        # Cloud環境など書き込み不可の場合はセッション内のみ保存
        # ユーザーに永続化されない旨を通知する
        st.session_state["_fav_save_warning"] = True

def _get() -> list[dict]:
    _ensure_loaded()
    return list(st.session_state.get(_SS_KEY, []))


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

    【設計】
      on_click コールバックで状態変更のみ行う（rerun なし）。
      分析画面が消える問題は app.py 側の session_state["current_code"]
      で解決する。このファイルは状態管理のみ担当。
    """
    _ensure_loaded()
    already = is_favorite(code)
    label   = "💔 ウォッチリストから削除" if already else "❤️ ウォッチリストに追加"
    ph      = st.empty()

    def _on_click():
        if is_favorite(code):
            remove_favorite(code)
            st.session_state[f"_fmsg_{code}"] = ("info",
                f"「{name}」をウォッチリストから削除しました")
        else:
            add_favorite(code, name, close, dy_str, score)
            st.session_state[f"_fmsg_{code}"] = ("success",
                f"「{name}」を追加しました ❤️")

    st.button(label, key=f"fav_btn_{code}", on_click=_on_click)

    mkey = f"_fmsg_{code}"
    if mkey in st.session_state:
        kind, msg = st.session_state.pop(mkey)
        if kind == "success":
            ph.success(msg)
        else:
            ph.info(msg)


# ────────────────────────────────
# ウォッチリストタブ
# ────────────────────────────────
def render_watchlist_tab() -> None:
    _ensure_loaded()

    # Cloud環境での保存失敗を通知
    if st.session_state.pop("_fav_save_warning", False):
        st.warning(
            "⚠️ ウォッチリストはこのセッション中のみ有効です。"
            "ページを閉じると登録内容が消える場合があります。",
            icon="⚠️",
        )

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
        def _clear(): clear_favorites()
        st.button("🗑️ 全削除", key="wl_clear", on_click=_clear)

    for col, lbl in zip(
        st.columns([3, 1, 2, 2, 2, 1]),
        ["銘柄名", "コード", "株価", "配当利回り", "スコア", ""],
    ):
        col.caption(lbl)
    st.markdown("<hr style='border:none;border-top:2px solid #fce4ec;'>",
                unsafe_allow_html=True)

for item in get_favorites():
        code = item.get("code", "")
        # リアルタイム株価・配当利回りを取得（失敗時はJSONの保存値を使用）
        try:
            live_info  = get_stock_info(code)
            raw_close  = live_info.get("currentPrice") or live_info.get("regularMarketPrice")
            live_close = float(raw_close) if raw_close else item.get("close", 0)
            live_dy    = fmt_dividend_str(live_info.get("dividendYield"))
            live_dy_str = live_dy if live_dy not in ("―", "無配当") else item.get("dy_str", "―")
            # 無配当は登録時の値より正確なため live_dy を優先
            if live_dy == "無配当":
                live_dy_str = "無配当"
        except Exception:
            live_close  = item.get("close", 0)
            live_dy_str = item.get("dy_str", "―")
        _render_row(item, live_close, live_dy_str)
  

def _render_row(item: dict, live_close: float, live_dy_str: str) -> None:
    code   = item.get("code", "")
    name   = item.get("name", code)
    close  = live_close
    dy_str = live_dy_str
    score  = item.get("score", 0)
  bg     = ("linear-gradient(135deg,#f48fb1,#ce93d8)" if score >= 70
              else "linear-gradient(135deg,#f8bbd0,#f48fb1)" if score >= 50
              else "linear-gradient(135deg,#e0e0e0,#bdbdbd)")

    c1,c2,c3,c4,c5,c6 = st.columns([3,1,2,2,2,1])
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
        def _del(c=code):
            remove_favorite(c)
        st.button("🗑️", key=f"wl_del_{code}", on_click=_del, help="削除")

    st.markdown(
        "<hr style='border:none;border-top:1px solid #fce4ec;margin:0.08rem 0;'>",
        unsafe_allow_html=True)
