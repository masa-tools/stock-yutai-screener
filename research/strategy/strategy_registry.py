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

import importlib
from typing import Callable

# テーマID : 表示名 : 対応モジュール名（未実装のため文字列のみ保持） : 状態
THEME_REGISTRY = {
    "rsi": {
        "label": "① RSI改善",
        "module": "strategy_v9_rsi",   # Phase6で追加予定
        "status": "未着手",
    },
    "volume": {
        "label": "② 出来高改善",
        "module": "strategy_v9_volume",  # Phase7-3で実装済み
        "status": "研究準備",
    },
    "dividend": {
        "label": "③ 配当性向",
        "module": "strategy_v9_dividend",  # Phase7-5で実装済み
        "status": "研究準備",
    },
    "per_sector": {
        "label": "④ PER業種別",
        "module": "strategy_v9_per_sector",  # Phase7-6で実装済み
        "status": "研究準備",
    },
    "composite": {
        "label": "⑤ Composite（複合評価）",
        "module": "strategy_v9_composite",  # Phase7-9で実装済み
        "status": "研究準備",
    },
}


def list_themes() -> list[dict]:
    """登録済みテーマの一覧を返す（骨格のみ・呼び出し処理は未実装）。"""
    return [
        {"id": theme_id, **info}
        for theme_id, info in THEME_REGISTRY.items()
    ]


def resolve_strategy_fn(theme_id: str) -> Callable[..., dict]:
    """
    テーマIDに対応する strategy_fn（compute_score）を動的に解決する。
    THEME_REGISTRY[theme_id]["module"] を手がかりに strategy.{module} を
    動的importし、compute_score属性を返す。

    Raises:
        NotImplementedError: テーマ未登録、モジュール未実装、
            compute_score未実装のいずれかの場合。
    """
    theme_info = THEME_REGISTRY.get(theme_id)
    if theme_info is None:
        raise NotImplementedError(f"テーマ '{theme_id}' はTHEME_REGISTRYに登録されていません。")

    module_name = theme_info["module"]
    try:
        module = importlib.import_module(f"strategy.{module_name}")
    except ImportError as exc:
        raise NotImplementedError(
            f"テーマ '{theme_id}' の実装モジュール 'strategy.{module_name}' が"
            f"まだ利用できません（{type(exc).__name__}: {exc}）。"
        ) from exc

    compute_score = getattr(module, "compute_score", None)
    if compute_score is None or not callable(compute_score):
        raise NotImplementedError(f"'strategy.{module_name}' は compute_score() を実装していません。")
    return compute_score
