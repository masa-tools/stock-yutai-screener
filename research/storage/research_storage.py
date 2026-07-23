"""
research_storage.py  v9 Research (Phase5-1: 骨格のみ)
=======================================================
研究データ（Walk Forward結果・研究ログ・採用履歴・比較結果）の
保存・読込を担当する専用モジュール（予定）。

【重要】
  本モジュールが扱うのは研究専用の保存領域のみであり、
  既存の walkforward_storage.py（本番Walk Forward保存領域）とは
  完全に分離する。本番ストレージへは一切書き込まない。

【想定する保存構造（将来）】
  research/storage/data/
  ├─ walkforward_results/{theme}/{run_id}.json
  ├─ experiment_logs/{theme}/experiment_log.jsonl
  ├─ adoption_history/adoption_log.json
  └─ comparisons/{theme}/{comparison_id}.json

【Phase5-1時点の実装範囲】
  関数のシグネチャ（インターフェース）のみ定義する。
  実際のファイル読み書き処理は行わない
  （今回のPhaseでは「データ保存処理」は禁止事項のため）。
"""


def save_walkforward_result(theme: str, run_id: str, result: dict) -> None:
    """Walk Forward結果を保存する（骨格のみ・未実装）。"""
    raise NotImplementedError("Phase5-1は骨格のみ。保存処理はPhase6以降で実装予定です。")


def load_walkforward_result(theme: str, run_id: str) -> dict:
    """Walk Forward結果を読み込む（骨格のみ・未実装）。"""
    raise NotImplementedError("Phase5-1は骨格のみ。読込処理はPhase6以降で実装予定です。")


def list_experiment_logs(theme: str) -> list[dict]:
    """研究ログの一覧を返す（骨格のみ・未実装）。"""
    raise NotImplementedError("Phase5-1は骨格のみ。ログ管理はPhase6以降で実装予定です。")
