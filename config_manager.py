"""
config_manager.py  v1.0（Phase2-1: Config Manager 土台）
=======================================================
設定ファイル（config/settings.json）の読込・生成・フォールバック・
型チェック・保存のみを担当するモジュール。

【責務（担当すること）】
  - settings.json の読込
  - ファイルが存在しない場合のデフォルト値からの新規生成
  - JSON破損時のデフォルト値フォールバック
  - キー欠損時のデフォルト値フォールバック（再帰的マージ）
  - 型チェック（デフォルト値と型が異なる場合はデフォルト値を採用）
  - save()

【担当しないこと（禁止事項）】
  - スコア計算・判定ロジック
  - UI / Streamlit
  - Walk Forward関連処理
  - app.py や scoring_config.py など既存モジュールとの接続
    （本フェーズでは、どこからも import されない独立した土台として存在する）

【設計方針】
  - シングルトン化・グローバルキャッシュ化は行わない。
    通常のクラスとして ConfigManager() を都度生成して利用する。
  - デフォルト値は既存 scoring_config.py の値と完全一致させる。
    settings.json が存在しない／壊れている／キーが欠けている場合でも、
    現状（scoring_config.py）と同じ値で動作することを保証する。

【settings.json 構造】
  {
    "schema_version": 1,
    "scoring": {
      "rsi": {...},
      "dividend": {...},
      "per": {...}
    }
  }

  schema_version をトップレベルに持たせることで、将来のGUI編集・
  Android版・API化・設定マイグレーション時に構造変化を検知できるようにする。
"""

import json
import os
from copy import deepcopy


# ── デフォルト値（scoring_config.py と完全一致） ─────────────────
# 万一 settings.json が存在しない／破損している／キーが欠けていても、
# 必ずこの値にフォールバックする。
DEFAULT_SETTINGS = {
    "schema_version": 1,
    "scoring": {
        "rsi": {
            "oversold": 30,
            "slightly_oversold": 40,
            "neutral_low": 55,
            "neutral_high": 65,
            "overbought": 75,
        },
        "dividend": {
            "high": 3.0,
            "attractive": 3.5,
            "caution": 8.0,
        },
        "per": {
            "undervalue": 10,
            "fair": 20,
            "slightly_high": 25,
        },
    },
}

# config_manager.py 自身の場所を基準にパスを解決する。
# （実行時のカレントディレクトリに依存させないため）
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SETTINGS_PATH = os.path.join(_MODULE_DIR, "config", "settings.json")


def _is_type_compatible(value, default_value):
    """
    型チェック。デフォルト値と互換性のある型かどうかを判定する。

    - bool は int のサブクラスだが、数値項目としては別物として扱うため
      bool を明示的に除外する。
    - int/float 同士は相互に許容する（例: 30 と 30.0 はどちらも数値としてOK）。
    """
    if isinstance(default_value, bool):
        return isinstance(value, bool)
    if isinstance(default_value, (int, float)):
        if isinstance(value, bool):
            return False
        return isinstance(value, (int, float))
    if isinstance(default_value, dict):
        return isinstance(value, dict)
    if isinstance(default_value, str):
        return isinstance(value, str)
    return isinstance(value, type(default_value))


def _merge_with_defaults(loaded, defaults):
    """
    読み込んだ設定値をデフォルト値へ再帰的にマージする。

    - キーが存在しない場合 → デフォルト値を採用
    - 型が一致しない場合 → デフォルト値を採用（型チェック）
    - dict の場合 → さらに再帰的にマージ（ネストしたキー欠損にも対応）

    戻り値は常に defaults と同じ構造を持つ（欠損・型不正が
    自動的にデフォルト値で補完された）新しい dict。
    """
    result = {}

    for key, default_value in defaults.items():
        if not isinstance(loaded, dict) or key not in loaded:
            result[key] = deepcopy(default_value)
            continue

        loaded_value = loaded[key]

        if isinstance(default_value, dict):
            result[key] = _merge_with_defaults(loaded_value, default_value)
        elif _is_type_compatible(loaded_value, default_value):
            result[key] = loaded_value
        else:
            # 型不一致 → デフォルト値へフォールバック
            result[key] = deepcopy(default_value)

    return result


class ConfigManager:
    """
    settings.json の読込・生成・フォールバック・保存を担当するクラス。

    シングルトンではない。必要な箇所でその都度インスタンス化して使う。

    使用例:
        cm = ConfigManager()
        oversold = cm.get("scoring.rsi.oversold")
        cm.save()
    """

    def __init__(self, path: str = None):
        self.path = path or DEFAULT_SETTINGS_PATH
        self._data = self._load()

    # ── 読込 ──────────────────────────────────────────────
    def _load(self) -> dict:
        """
        settings.json を読み込む。

        - ファイルが存在しない → デフォルト値から新規生成し、保存する
        - JSONが破損している   → デフォルト値を採用する（既存ファイルは
                                   上書きしない。原因調査ができるよう温存する）
        - 読込には成功したが構造が一部欠損／型不正 → デフォルト値で補完する
        """
        if not os.path.exists(self.path):
            data = deepcopy(DEFAULT_SETTINGS)
            self._data = data
            self.save()
            return data

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError, ValueError):
            # 破損時は現状と同じ挙動（デフォルト値）を保証する。
            # 壊れたファイル自体は上書きしない。
            return deepcopy(DEFAULT_SETTINGS)

        if not isinstance(raw, dict):
            return deepcopy(DEFAULT_SETTINGS)

        return _merge_with_defaults(raw, DEFAULT_SETTINGS)

    # ── 取得 ──────────────────────────────────────────────
    def get(self, dotted_key: str, default=None):
        """
        ドット区切りのキーで設定値を取得する。

        例: cm.get("scoring.rsi.oversold") -> 30

        キーが存在しない場合は default（省略時 None）を返す。
        """
        node = self._data
        for part in dotted_key.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node

    def as_dict(self) -> dict:
        """現在の設定値全体のコピーを返す（呼び出し側での誤った直接変更を防ぐ）。"""
        return deepcopy(self._data)

    # ── 保存 ──────────────────────────────────────────────
    def save(self) -> None:
        """現在の設定値を settings.json へ保存する。"""
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
