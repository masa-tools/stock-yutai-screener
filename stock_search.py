"""
stock_search.py  v8.0
=====================
銘柄検索・コード解決専用モジュール（P4-1: app.py 責務分離）

【移動元】
  app.py より以下を移動:
    - ALIAS 辞書
    - _build_name_to_code()
    - _resolve_code()

【依存モジュール】
  stock_data.JP_NAMES     : 正式名称117件（P4-2対応済みエイリアス）
  candidate_stocks.get_candidates : 略称288件
  streamlit               : @st.cache_data
"""

import streamlit as st
from stock_data       import JP_NAMES
from candidate_stocks import get_candidates


# ════════════════════════════════════════
# 企業名→コード変換（強化版）
# ════════════════════════════════════════

# 略称・カタカナ・通称マスター（部分一致で拾えない表記ゆれを補完）
ALIAS: dict[str, str] = {
    # 通信
    "ドコモ": "9437", "ntt docomo": "9437",
    # 銀行・金融
    "みずほ": "8411", "みずほ銀行": "8411", "mizuho": "8411",
    "三菱ufj銀行": "8306", "mufg": "8306", "三菱ufj": "8306",
    "三井住友": "8316", "smfg": "8316", "smbc": "8316",
    "りそな": "8308",
    # 商社
    "伊藤忠": "8001", "丸紅": "8002", "三井物産": "8031",
    "住友商事": "8053", "三菱商事": "8058",
    # 製造
    "コマツ": "6301", "komatsu": "6301",
    "デンソー": "6902",
    "ブリジストン": "5108", "ブリヂストン": "5108", "bridgestone": "5108",
    "キャノン": "7751", "キヤノン": "7751", "canon": "7751",
    "パナソニック": "6752", "panasonic": "6752",
    "ニデック": "6594", "日本電産": "6594", "nidec": "6594",
    # 食品
    "キッコーマン": "2801", "味の素": "2802",
    "明治": "2269", "森永": "2264",
    "日清": "2897", "日清食品": "2897",
    "アサヒ": "2502", "キリン": "2503",
    "ヤクルト": "2267",
    # 小売
    "ニトリ": "9843", "良品計画": "7453", "無印良品": "7453",
    "ローソン": "2651", "ファミマ": "8028", "ファミリーマート": "8028",
    # 電機・精密
    "ソニー": "6758", "sony": "6758",
    "日立": "6501", "hitachi": "6501",
    "富士通": "6702", "fujitsu": "6702",
    "京セラ": "6971", "kyocera": "6971",
    "村田製作所": "6981", "murata": "6981",
    "ファナック": "6954", "fanuc": "6954",
    "シスメックス": "6869",
    # 自動車
    "トヨタ": "7203", "toyota": "7203",
    "ホンダ": "7267", "honda": "7267",
    "スバル": "7270", "subaru": "7270",
    "スズキ": "7269", "suzuki": "7269",
    "日産": "7201", "nissan": "7201",
    # 不動産
    "三井不動産": "8801", "三菱地所": "8802",
    "ヒューリック": "3003",
    # 海運
    "日本郵船": "9101", "郵船": "9101",
    "商船三井": "9104",
    "川崎汽船": "9107",
    # 保険
    "東京海上": "8766", "東京海上日動": "8766",
    "損保ジャパン": "8630", "sompo": "8630",
    # その他
    "オリックス": "8591", "orix": "8591",
    "jt": "2914", "日本たばこ": "2914",
    "花王": "4452", "kao": "4452",
    "信越化学": "4063",
    "セブンイレブン": "3382", "7-eleven": "3382",
    "イオン": "8267", "aeon": "8267",
    "オリエンタルランド": "4661", "olc": "4661", "ディズニー": "4661",
    "東宝": "9602",
    "kddi": "9433",
    "ntt": "9432", "エヌティティ": "9432",
    "ソフトバンク": "9434", "sb": "9434",
}


@st.cache_data
def _build_name_to_code() -> dict[str, str]:
    """JP_NAMES + CANDIDATES から企業名→コード辞書を構築"""
    mapping: dict[str, str] = {}
    for code, name in JP_NAMES.items():
        mapping[name.lower()] = code
        # 「ホールディングス」「グループ」などを除いた短縮形
        short = (name.replace("ホールディングス", "HD")
                     .replace("ホールディング",   "HD")
                     .replace("フィナンシャルグループ", "FG")
                     .replace("グループ", "G")
                     .replace("株式会社", "")
                     .replace("（株）", "")
                     .strip())
        mapping[short.lower()] = code
        # 最初の単語（スペース・括弧前）
        first = name.split("（")[0].split("・")[0].split(" ")[0]
        if len(first) >= 2:
            mapping[first.lower()] = code
    for code, label in get_candidates():
        mapping[label.lower()] = code
    # エイリアスを上書き登録
    for alias, code in ALIAS.items():
        mapping[alias.lower()] = code
    return mapping


def _resolve_code(raw: str) -> tuple[str, str]:
    """
    入力文字列を証券コードに変換する。

    Returns:
        (code, matched_name) matched_name は "" の場合は直接入力
    """
    raw = raw.strip()
    if raw.isdigit():
        return raw, ""

    mapping = _build_name_to_code()
    lower   = raw.lower()

    # 1. 完全一致
    if lower in mapping:
        return mapping[lower], raw

    # 2. 前方一致
    for key, code in mapping.items():
        if key.startswith(lower) or lower.startswith(key):
            return code, key

    # 3. 部分一致（最初のヒット）
    for key, code in mapping.items():
        if lower in key or key in lower:
            return code, key

    return raw, ""   # 変換できなければ原文をそのまま返す
