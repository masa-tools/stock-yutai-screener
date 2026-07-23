"""
strategy_registry.py  v9 Research (Phase5-1: 骨格のみ)
========================================================
研究テーマと戦略実装ファイルの対応関係を一元管理する。

【役割（将来）】
  テーマ名 → 対応する strategy_v9_* モジュール名 の対応表を持ち、
  views側がテーマ名だけで戦略を呼び出せるようにする窓口となる。

【Phase5-1時点の実装範囲】
  対応表（データ）のみを定義する。
  実際のモジュール読込・呼び出し処理はまだ実装しない
  （strategy_v9_rsi.py 等がまだ存在しないため）。
"""

# テーマID : 表示名 : 対応モジュール名（未実装のため文字列のみ保持） : 状態
THEME_REGISTRY = {
    "rsi": {
        "label": "① RSI改善",
        "module": "strategy_v9_rsi",   # Phase6で追加予定
        "status": "未着手",
    },
    "volume": {
        "label": "② 出来高改善",
        "module": "strategy_v9_volume",  # Phase7で追加予定
        "status": "未着手",
    },
    "dividend": {
        "label": "③ 配当性向",
        "module": "strategy_v9_dividend",  # Phase8で追加予定
        "status": "未着手",
    },
    "per_sector": {
        "label": "④ PER業種別",
        "module": "strategy_v9_per_sector",  # Phase9で追加予定
        "status": "未着手",
    },
}


def list_themes() -> list[dict]:
    """登録済みテーマの一覧を返す（骨格のみ・呼び出し処理は未実装）。"""
    return [
        {"id": theme_id, **info}
        for theme_id, info in THEME_REGISTRY.items()
    ]
