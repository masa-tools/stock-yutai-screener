"""backtest/walkforward_storage.py (Walk Forward SQLite保存基盤 Phase1)
====================================================================
walkforward_runner.run_walkforward_runner() の戻り値（RunnerResult）を
SQLiteへ保存・読込するだけの永続化層。

責務:
    「保存」と「読込」のみ。新しい計算・判定・集計ロジックは一切
    実装しない。RunnerResultは加工せず json.dumps() した文字列
    （raw_json）を唯一の情報源として保存する。code/strategy_name/period
    という3つの検索用カラムも、RunnerResult内の既存フィールド
    （"pipeline"配下）をそのまま読み取るだけであり、新しい値の算出は
    行わない。

    walkforward.py〜walkforward_runner.py・walkforward_strategy_compare.py・
    walkforward_ranking.py・walkforward_export.py・types.pyのいずれにも
    依存しない（RunnerResultという「素のdict」のみを入力とするため）。
    これらのモジュールへは一切変更を加えていない。

    履歴一覧・検索・削除・更新・Windowテーブル・Compare専用テーブル・
    batch_id・Index最適化は今回のスコープ外。Phase1は
    「walkforward_runsテーブルへの保存・run_id指定での読込」のみを
    提供する。

    SQLiteのJSON1拡張機能には一切依存しない設計としている
    （raw_jsonはPython側でjson.dumps/json.loadsするだけの単純なTEXT
    カラムであり、SQL側でJSON関数を呼び出す処理は持たない）。これに
    より、JSON1が利用可能かどうかの実行時判定自体が不要になっている。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping, Optional, Union

__all__ = [
    "DEFAULT_DB_PATH",
    "initialize_database",
    "save_runner_result",
    "load_runner_result",
    "list_runner_results",
]

#: デフォルトのSQLiteデータベースファイルパス。
#: 呼び出し側は各関数の db_path 引数で任意のパスへ差し替えられる。
DEFAULT_DB_PATH = "walkforward.db"

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS walkforward_runs (
    run_id TEXT PRIMARY KEY,
    compare_run_id TEXT,
    code TEXT,
    strategy_name TEXT,
    period TEXT,
    status TEXT,
    started_at TEXT,
    finished_at TEXT,
    runner_schema_version TEXT,
    raw_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

_INSERT_SQL = """
INSERT INTO walkforward_runs (
    run_id, compare_run_id, code, strategy_name, period,
    status, started_at, finished_at, runner_schema_version, raw_json
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_SELECT_RAW_JSON_SQL = "SELECT raw_json FROM walkforward_runs WHERE run_id = ?"

_SELECT_LIST_SQL = """
SELECT run_id, code, strategy_name, period, status, started_at, created_at
FROM walkforward_runs
ORDER BY created_at DESC
"""


def initialize_database(db_path: Union[str, Path] = DEFAULT_DB_PATH) -> None:
    """walkforward_runsテーブルを作成する（既に存在する場合は何もしない）。

    Args:
        db_path: SQLiteデータベースファイルのパス。
    """
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(_CREATE_TABLE_SQL)
        conn.commit()
    finally:
        conn.close()


def _extract_indexed_fields(runner_result: Mapping[str, Any]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """RunnerResultの"pipeline"配下から、検索用カラムに複製する3値をそのまま読み取る。

    新しい計算・推定は行わない。pipeline_resultが存在しない
    （Stage1失敗等でNoneの）場合は、3値ともNoneを返す。

    Args:
        runner_result: run_walkforward_runner() の戻り値。

    Returns:
        (code, strategy_name, period) のタプル。
    """
    pipeline_result = runner_result.get("pipeline") or {}
    return (
        pipeline_result.get("code"),
        pipeline_result.get("strategy"),
        pipeline_result.get("period"),
    )


def save_runner_result(
    runner_result: Mapping[str, Any],
    db_path: Union[str, Path] = DEFAULT_DB_PATH,
    compare_run_id: Optional[str] = None,
) -> str:
    """RunnerResultを加工せずJSON化し、walkforward_runsへ1件挿入する。

    Args:
        runner_result: walkforward_runner.run_walkforward_runner() の
            戻り値。json.dumps()できる形であることのみを前提とする。
        db_path: SQLiteデータベースファイルのパス。
        compare_run_id: walkforward_strategy_compare経由で実行された
            場合の識別子（StrategyCompare結果の"run_id"）。単独実行の
            場合はNoneのまま保存する。

    Returns:
        保存したレコードのrun_id。

    Raises:
        ValueError: runner_resultに"run_id"キーが存在しない、または
            空の場合。
        sqlite3.IntegrityError: 同じrun_idが既に保存済みの場合
            （run_idは一意である前提のため、意図しない重複保存を
            検知できるよう、上書きはせず例外をそのまま送出する）。
    """
    run_id = runner_result.get("run_id")
    if not run_id:
        raise ValueError("runner_result に run_id が含まれていません。")

    code, strategy_name, period = _extract_indexed_fields(runner_result)
    raw_json = json.dumps(runner_result, ensure_ascii=False)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            _INSERT_SQL,
            (
                run_id,
                compare_run_id,
                code,
                strategy_name,
                period,
                runner_result.get("status"),
                runner_result.get("started_at"),
                runner_result.get("finished_at"),
                runner_result.get("runner_schema_version"),
                raw_json,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return run_id


def load_runner_result(
    run_id: str,
    db_path: Union[str, Path] = DEFAULT_DB_PATH,
) -> Optional[dict[str, Any]]:
    """run_idに対応するRunnerResultを読み込む。

    Args:
        run_id: 検索対象のrun_id。
        db_path: SQLiteデータベースファイルのパス。

    Returns:
        raw_jsonをjson.loads()した辞書（保存時のRunnerResultと同一の
        内容）。該当レコードが存在しない場合はNone。
    """
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(_SELECT_RAW_JSON_SQL, (run_id,)).fetchone()
    finally:
        conn.close()

    if row is None:
        return None
    return json.loads(row[0])


def list_runner_results(
    db_path: Union[str, Path] = DEFAULT_DB_PATH,
) -> list[dict[str, Any]]:
    """保存済みRunnerResultの一覧を、保存日時（created_at）降順で返す。

    raw_jsonは含まない（一覧取得のペイロードを軽量に保つため）。
    詳細を取得したい場合は、戻り値の"run_id"を load_runner_result() へ
    渡すこと。新しい計算・整形は一切行わず、単純なSELECT結果を
    そのまま返す。

    Args:
        db_path: SQLiteデータベースファイルのパス。

    Returns:
        [{"run_id", "code", "strategy_name", "period", "status",
        "started_at", "created_at"}, ...] のリスト（created_at降順）。
        保存済みレコードが無い場合は空リスト。
    """
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(_SELECT_LIST_SQL).fetchall()
    finally:
        conn.close()

    columns = ("run_id", "code", "strategy_name", "period", "status", "started_at", "created_at")
    return [dict(zip(columns, row)) for row in rows]
