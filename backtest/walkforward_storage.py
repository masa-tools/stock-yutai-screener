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
from typing import Any, Callable, Mapping, Optional, Union

__all__ = [
    "DEFAULT_DB_PATH",
    "initialize_database",
    "save_runner_result",
    "load_runner_result",
    "list_runner_results",
    "search_runner_results",
    "save_compare_result",
    "load_compare_result",
    "list_compare_results",
    "search_compare_results",
    "delete_runner_result",
    "delete_compare_result",
]

#: デフォルトのSQLiteデータベースファイルパス。
#: 呼び出し側は各関数の db_path 引数で任意のパスへ差し替えられる。
DEFAULT_DB_PATH = "walkforward.db"

#: Migration管理用テーブル。1行=1つの「適用済みversion」を表す
#: 単純な履歴テーブル（Migration履歴UIではなく、内部状態管理のみ）。
_CREATE_SCHEMA_VERSION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS walkforward_schema_version (
    version INTEGER PRIMARY KEY
)
"""

#: version 3: walkforward_strategy_compare.run_walkforward_strategy_compare()
#: の戻り値（StrategyCompareResult）を保存するための専用テーブル。
#: RunnerResult保存（walkforward_runs）とは責務を分離し、StrategyCompare
#: 全体（各戦略のRunnerResultを含む生JSON）をそのまま保持するだけの
#: テーブルとする。
_MIGRATION_V3_SQL = """
CREATE TABLE IF NOT EXISTS walkforward_compares (
    compare_run_id TEXT PRIMARY KEY,
    code TEXT,
    period TEXT,
    status TEXT,
    raw_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

_INSERT_COMPARE_SQL = """
INSERT INTO walkforward_compares (
    compare_run_id, code, period, status, raw_json
) VALUES (?, ?, ?, ?, ?)
"""

_SELECT_COMPARE_RAW_JSON_SQL = "SELECT raw_json FROM walkforward_compares WHERE compare_run_id = ?"

_DELETE_RUNNER_RESULT_SQL = "DELETE FROM walkforward_runs WHERE run_id = ?"
_DELETE_COMPARE_RESULT_SQL = "DELETE FROM walkforward_compares WHERE compare_run_id = ?"

#: search_compare_results() / list_compare_results() 共通のSELECT対象列。
#: raw_jsonは一覧・検索いずれの結果にも含めない
#: （walkforward_runs側の_LIST_COLUMNSと同じ設計方針）。
_LIST_COMPARE_COLUMNS = ("compare_run_id", "code", "period", "status", "created_at")

#: version 1: Phase1〜4時点のベーススキーマ（elapsed_secondsを含まない）。
#: 既にテーブルが存在する場合は IF NOT EXISTS により何もしない。
_MIGRATION_V1_SQL = """
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
    status, started_at, finished_at, elapsed_seconds, runner_schema_version, raw_json
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_SELECT_RAW_JSON_SQL = "SELECT raw_json FROM walkforward_runs WHERE run_id = ?"

_SELECT_LIST_SQL = """
-- search_runner_results() / list_runner_results() 共通のSELECT対象列。
-- raw_jsonは一覧・検索いずれの結果にも含めない。
-- Phase5でメタデータ（runner_schema_version/finished_at/elapsed_seconds）を追加。
-- SELECT対象列をこの1箇所に集約しているため、
-- list_runner_results()/search_runner_results()双方のSQLは変更不要。
"""
_LIST_COLUMNS = (
    "run_id", "code", "strategy_name", "period", "status",
    "started_at", "finished_at", "elapsed_seconds",
    "runner_schema_version", "created_at",
)

def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """指定テーブルに指定カラムが既に存在するかを確認する（Migration用の判定のみ）。"""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def _migrate_v1(conn: sqlite3.Connection) -> None:
    """version 1: walkforward_runsテーブルをベーススキーマで作成する（既存の場合は何もしない）。"""
    conn.execute(_MIGRATION_V1_SQL)


def _migrate_v2(conn: sqlite3.Connection) -> None:
    """version 2: walkforward_runsへelapsed_seconds列を追加する。

    既にPhase5の運用で手動追加済みの環境（既存DB）に対しては、
    列の存在を確認したうえで二重追加を避ける。
    """
    if not _column_exists(conn, "walkforward_runs", "elapsed_seconds"):
        conn.execute("ALTER TABLE walkforward_runs ADD COLUMN elapsed_seconds REAL")


def _migrate_v3(conn: sqlite3.Connection) -> None:
    """version 3: walkforward_comparesテーブルを作成する（既存の場合は何もしない）。"""
    conn.execute(_MIGRATION_V3_SQL)


#: 適用順に並んだ (version番号, Migration関数) のリスト。
#: 将来のスキーマ変更は、この末尾へ (次のversion, 新しいMigration関数) を
#: 1件追加するだけで対応できる。
_MIGRATIONS: tuple[tuple[int, Callable[[sqlite3.Connection], None]], ...] = (
    (1, _migrate_v1),
    (2, _migrate_v2),
    (3, _migrate_v3),
)


def _get_current_schema_version(conn: sqlite3.Connection) -> int:
    """walkforward_schema_versionテーブルから、現在適用済みの最大versionを取得する。

    レコードが1件も無い場合は0を返す（＝未初期化のDBとして扱う）。
    """
    row = conn.execute("SELECT MAX(version) FROM walkforward_schema_version").fetchone()
    return row[0] if row and row[0] is not None else 0


def _apply_migration(conn: sqlite3.Connection, version: int,
                      migrate_fn: Callable[[sqlite3.Connection], None]) -> None:
    """1つのMigrationを、DDL適用とversion記録を1トランザクションとして実行する。

    `with conn:` はブロック正常終了時にcommit、例外発生時にrollbackする
    （sqlite3標準のコンテキストマネージャ挙動）。これにより、
    「スキーマは変更されたがversionは記録されていない」あるいはその逆の
    中途半端な状態が残らないようにしている。

    Args:
        conn: 接続済みのSQLite Connection。
        version: 適用するMigrationのversion番号。
        migrate_fn: 実際のDDLを実行する関数。

    Raises:
        Exception: migrate_fn内で発生した例外をそのまま送出する
            （呼び出し元 initialize_database() へ伝播させ、Migration失敗を
            隠蔽しない）。
    """
    with conn:
        migrate_fn(conn)
        conn.execute("INSERT INTO walkforward_schema_version (version) VALUES (?)", (version,))


def initialize_database(db_path: Union[str, Path] = DEFAULT_DB_PATH) -> None:
    """walkforward_runsテーブルを、必要なMigrationを適用したうえで利用可能な状態にする。

    処理の流れ:
        1. walkforward_schema_versionテーブルが無ければ作成する。
        2. 現在適用済みの最大versionを取得する（未初期化なら0）。
        3. 未適用のMigration（_MIGRATIONS）だけを、version順に適用する。

    既にPhase1〜5で作成済みのDBファイル（walkforward_schema_versionを
    持たない）に対して実行した場合も、version 0からMigration 1・2が
    順に適用され、Migration 2は既存のelapsed_seconds列の有無を確認して
    から追加するため、安全に最新状態へ追従できる。

    本関数の呼び出しはRunnerResult・JSON構造・UIには一切影響しない
    （テーブル定義のみを操作する）。

    Args:
        db_path: SQLiteデータベースファイルのパス。
    """
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(_CREATE_SCHEMA_VERSION_TABLE_SQL)
        conn.commit()

        current_version = _get_current_schema_version(conn)
        for version, migrate_fn in _MIGRATIONS:
            if version > current_version:
                _apply_migration(conn, version, migrate_fn)
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
                runner_result.get("elapsed_seconds"),
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


def list_compare_results(
    db_path: Union[str, Path] = DEFAULT_DB_PATH,
) -> list[dict[str, Any]]:
    """保存済みStrategyCompareResultの一覧を、保存日時（created_at）降順で返す。

    raw_jsonは含まない。詳細を取得したい場合は、戻り値の
    "compare_run_id"を load_compare_result() へ渡すこと。新しい計算・
    整形は一切行わず、単純なSELECT結果をそのまま返す。

    内部的には search_compare_results() を条件なしで呼び出すだけの
    薄いラッパーであり、SQL構築ロジックを重複させない
    （list_runner_results()と同じ設計）。

    Args:
        db_path: SQLiteデータベースファイルのパス。

    Returns:
        [{"compare_run_id", "code", "period", "status", "created_at"}, ...]
        のリスト（created_at降順）。保存済みレコードが無い場合は空リスト。
    """
    return search_compare_results(db_path=db_path)


def search_compare_results(
    code: Optional[str] = None,
    period: Optional[str] = None,
    status: Optional[str] = None,
    db_path: Union[str, Path] = DEFAULT_DB_PATH,
) -> list[dict[str, Any]]:
    """保存済みStrategyCompareResultを、指定された条件のみでAND絞り込みして検索する。

    引数はすべてOptional。未指定（None）の項目はWHERE句に含めない
    （＝すべての値を許容する）。すべて未指定の場合は list_compare_results()
    と同じ全件結果を返す。列名はコード内の固定文字列のみを使用し、
    ユーザー由来の値は必ずプレースホルダ（?）経由でバインドするため、
    SQLインジェクションの余地はない。raw_jsonは含まない。新しい計算・
    判定ロジック（StrategyCompare解析・ランキング生成・RunnerResult
    変換・HealthScore抽出・Status再計算）は一切行わない
    （search_runner_results()と同じ設計）。

    Args:
        code: 完全一致させる銘柄コード。
        period: 完全一致させる期間文字列（例: "1y"）。
        status: 完全一致させるstatus（"SUCCESS"等）。
        db_path: SQLiteデータベースファイルのパス。

    Returns:
        [{"compare_run_id", "code", "period", "status", "created_at"}, ...]
        のリスト（created_at降順）。該当レコードが無い場合は空リスト。
    """
    conditions: list[str] = []
    params: list[Any] = []
    for column, value in (
        ("code", code),
        ("period", period),
        ("status", status),
    ):
        if value is not None:
            conditions.append(f"{column} = ?")
            params.append(value)

    sql = f"SELECT {', '.join(_LIST_COMPARE_COLUMNS)} FROM walkforward_compares"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY created_at DESC"

    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    return [dict(zip(_LIST_COMPARE_COLUMNS, row)) for row in rows]


def delete_runner_result(
    run_id: str,
    db_path: Union[str, Path] = DEFAULT_DB_PATH,
) -> bool:
    """run_idに対応するRunnerResultレコードを削除する。

    削除のみを行い、RunnerResultの解析・JSON加工・Status変更・集計・
    ランキング等は一切行わない。対象が存在しない場合も例外は送出せず、
    Falseを返すだけとする。

    Args:
        run_id: 削除対象のrun_id。
        db_path: SQLiteデータベースファイルのパス。

    Returns:
        True: レコードが削除された場合。
        False: 対象のrun_idが存在せず、何も削除されなかった場合。
    """
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute(_DELETE_RUNNER_RESULT_SQL, (run_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def delete_compare_result(
    compare_run_id: str,
    db_path: Union[str, Path] = DEFAULT_DB_PATH,
) -> bool:
    """compare_run_idに対応するStrategyCompareResultレコードを削除する。

    削除のみを行い、Compare内容の解析・JSON加工・Status変更・集計・
    ランキング等は一切行わない。対象が存在しない場合も例外は送出せず、
    Falseを返すだけとする（delete_runner_result()と対称の設計）。

    Args:
        compare_run_id: 削除対象のcompare_run_id。
        db_path: SQLiteデータベースファイルのパス。

    Returns:
        True: レコードが削除された場合。
        False: 対象のcompare_run_idが存在せず、何も削除されなかった場合。
    """
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute(_DELETE_COMPARE_RESULT_SQL, (compare_run_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def list_runner_results(
    db_path: Union[str, Path] = DEFAULT_DB_PATH,
) -> list[dict[str, Any]]:
    """保存済みRunnerResultの一覧を、保存日時（created_at）降順で返す。

    raw_jsonは含まない（一覧取得のペイロードを軽量に保つため）。
    詳細を取得したい場合は、戻り値の"run_id"を load_runner_result() へ
    渡すこと。新しい計算・整形は一切行わず、単純なSELECT結果を
    そのまま返す。

    内部的には search_runner_results() を条件なしで呼び出すだけの
    薄いラッパーであり、SQL構築ロジックを重複させない。

    Args:
        db_path: SQLiteデータベースファイルのパス。

    Returns:
        [{"run_id", "code", "strategy_name", "period", "status",
        "started_at", "created_at"}, ...] のリスト（created_at降順）。
        保存済みレコードが無い場合は空リスト。
    """
    return search_runner_results(db_path=db_path)


def save_compare_result(
    compare_result: Mapping[str, Any],
    db_path: Union[str, Path] = DEFAULT_DB_PATH,
) -> str:
    """StrategyCompareResultを加工せずJSON化し、walkforward_comparesへ1件挿入する。

    walkforward_strategy_compare.run_walkforward_strategy_compare() の
    戻り値をそのまま保存するだけで、中身の解析・ランキング計算・
    status再計算・health_score抽出・RunnerResultへの変換は一切行わない
    （save_runner_result()と対称の設計）。

    Args:
        compare_result: run_walkforward_strategy_compare() の戻り値。
            json.dumps()できる形であることのみを前提とする。
        db_path: SQLiteデータベースファイルのパス。

    Returns:
        保存したレコードのcompare_run_id
        （compare_result["run_id"]をそのまま返す）。

    Raises:
        ValueError: compare_resultに"run_id"キーが存在しない、または
            空の場合。
        sqlite3.IntegrityError: 同じcompare_run_idが既に保存済みの場合
            （上書きはせず例外をそのまま送出する）。
    """
    compare_run_id = compare_result.get("run_id")
    if not compare_run_id:
        raise ValueError("compare_result に run_id が含まれていません。")

    raw_json = json.dumps(compare_result, ensure_ascii=False)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            _INSERT_COMPARE_SQL,
            (
                compare_run_id,
                compare_result.get("code"),
                compare_result.get("period"),
                compare_result.get("status"),
                raw_json,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return compare_run_id


def load_compare_result(
    compare_run_id: str,
    db_path: Union[str, Path] = DEFAULT_DB_PATH,
) -> Optional[dict[str, Any]]:
    """compare_run_idに対応するStrategyCompareResultを読み込む。

    Args:
        compare_run_id: 検索対象のcompare_run_id。
        db_path: SQLiteデータベースファイルのパス。

    Returns:
        raw_jsonをjson.loads()した辞書（保存時のStrategyCompareResultと
        同一の内容）。該当レコードが存在しない場合はNone。
    """
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(_SELECT_COMPARE_RAW_JSON_SQL, (compare_run_id,)).fetchone()
    finally:
        conn.close()

    if row is None:
        return None
    return json.loads(row[0])


def search_runner_results(
    code: Optional[str] = None,
    strategy_name: Optional[str] = None,
    period: Optional[str] = None,
    status: Optional[str] = None,
    db_path: Union[str, Path] = DEFAULT_DB_PATH,
) -> list[dict[str, Any]]:
    """保存済みRunnerResultを、指定された条件のみでAND絞り込みして検索する。

    引数はすべてOptional。未指定（None）の項目はWHERE句に含めない
    （＝すべての値を許容する）。すべて未指定の場合は list_runner_results()
    と同じ全件結果を返す。列名はコード内の固定文字列のみを使用し、
    ユーザー由来の値は必ずプレースホルダ（?）経由でバインドするため、
    SQLインジェクションの余地はない。raw_jsonは含まない。新しい計算・
    判定ロジックは一切行わない（単純な完全一致検索のみ）。

    Args:
        code: 完全一致させる銘柄コード。
        strategy_name: 完全一致させる戦略名。
        period: 完全一致させる期間文字列（例: "1y"）。
        status: 完全一致させるstatus（"SUCCESS"等）。
        db_path: SQLiteデータベースファイルのパス。

    Returns:
        [{"run_id", "code", "strategy_name", "period", "status",
        "started_at", "created_at"}, ...] のリスト（created_at降順）。
        該当レコードが無い場合は空リスト。
    """
    conditions: list[str] = []
    params: list[Any] = []
    for column, value in (
        ("code", code),
        ("strategy_name", strategy_name),
        ("period", period),
        ("status", status),
    ):
        if value is not None:
            conditions.append(f"{column} = ?")
            params.append(value)

    sql = f"SELECT {', '.join(_LIST_COLUMNS)} FROM walkforward_runs"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY created_at DESC"

    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    return [dict(zip(_LIST_COLUMNS, row)) for row in rows]


# ════════════════════════════════════════════════
# Migration基盤のテスト（Phase6）
# ════════════════════════════════════════════════
def test_new_database_reaches_latest_schema_version(db_path):
    """新規DB作成時、walkforward_schema_versionへ最新version（2）まで記録される。"""
    initialize_database(db_path)

    conn = sqlite3.connect(str(db_path))
    try:
        versions = [row[0] for row in conn.execute(
            "SELECT version FROM walkforward_schema_version ORDER BY version"
        ).fetchall()]
    finally:
        conn.close()

    assert versions == [1, 2]


def test_migration_adds_elapsed_seconds_to_legacy_database(db_path):
    """
    walkforward_schema_versionを持たない「Phase1〜4相当」の旧スキーマDBに
    対してinitialize_database()を実行すると、elapsed_seconds列が追加される。
    """
    # Phase6以前のDB状態を素のSQLで再現する（elapsed_seconds列を持たない）。
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("""
            CREATE TABLE walkforward_runs (
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
        """)
        conn.execute(
            "INSERT INTO walkforward_runs (run_id, code, strategy_name, period, status, raw_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("legacy-run", "7203", "v9", "1y", "SUCCESS", json.dumps(_dummy_runner_result("legacy-run"))),
        )
        conn.commit()
    finally:
        conn.close()

    initialize_database(db_path)  # Migrationを適用させる

    conn = sqlite3.connect(str(db_path))
    try:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(walkforward_runs)").fetchall()]
    finally:
        conn.close()

    assert "elapsed_seconds" in columns


def test_migration_does_not_duplicate_existing_column(db_path):
    """
    elapsed_seconds列が既に存在する（Phase5運用で手動追加済み相当の）DBに
    対してMigrationを適用しても、エラーにならず二重追加もされない。
    """
    initialize_database(db_path)  # ここで既にversion 2まで適用済み

    # もう一度初期化しても例外が発生しないこと（冪等性の確認）。
    initialize_database(db_path)

    conn = sqlite3.connect(str(db_path))
    try:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(walkforward_runs)").fetchall()]
    finally:
        conn.close()

    assert columns.count("elapsed_seconds") == 1


def test_migration_is_idempotent_and_does_not_reinsert_versions(db_path):
    """Migrationを複数回実行しても、walkforward_schema_versionに重複行が増えない。"""
    initialize_database(db_path)
    initialize_database(db_path)
    initialize_database(db_path)

    conn = sqlite3.connect(str(db_path))
    try:
        versions = [row[0] for row in conn.execute(
            "SELECT version FROM walkforward_schema_version ORDER BY version"
        ).fetchall()]
    finally:
        conn.close()

    assert versions == [1, 2]


def test_existing_saved_runner_result_still_readable_after_migration(db_path):
    """Migration適用前に保存された既存RunnerResultが、Migration後も正しく読み込める。"""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("""
            CREATE TABLE walkforward_runs (
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
        """)
        result = _dummy_runner_result("legacy-run-2")
        conn.execute(
            "INSERT INTO walkforward_runs (run_id, code, strategy_name, period, status, raw_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("legacy-run-2", "7203", "v9", "1y", "SUCCESS", json.dumps(result)),
        )
        conn.commit()
    finally:
        conn.close()

    initialize_database(db_path)

    loaded = load_runner_result("legacy-run-2", db_path=db_path)
    assert loaded == result
