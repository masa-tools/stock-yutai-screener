"""tests/test_walkforward_storage.py
====================================================================
backtest.walkforward_storage の単体テスト。Runner実行・ネットワーク
アクセスは一切行わず、ダミーのRunnerResult形状の辞書のみを使用する。
DBは pytest の tmp_path フィクスチャで都度一時ファイルへ作成し、
テスト間で状態を共有しない。
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from backtest.walkforward_storage import (
    initialize_database,
    save_runner_result,
    load_runner_result,
)


def _dummy_runner_result(run_id: str = "run-123") -> dict:
    """walkforward_runner.run_walkforward_runner() の戻り値形状のダミー。"""
    return {
        "runner_schema_version": "1.0",
        "run_id": run_id,
        "started_at": "2026-01-01T00:00:00+00:00",
        "finished_at": "2026-01-01T00:01:00+00:00",
        "elapsed_seconds": 60.0,
        "status": "SUCCESS",
        "pipeline": {"code": "7203", "strategy": "v9", "period": "1y"},
        "benchmark": {"benchmark_schema_version": "1.0"},
        "summary": {"summary_schema_version": "1.0"},
        "context": {"context_schema_version": "1.0"},
        "stage_status": {"pipeline": "SUCCESS", "benchmark": "SUCCESS",
                          "summary": "SUCCESS", "context": "SUCCESS"},
        "stage_elapsed": {"pipeline": 10.0, "benchmark": 10.0, "summary": 10.0, "context": 10.0},
        "errors": [],
        "warnings": [],
    }


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "walkforward_test.db"


def test_initialize_database_creates_table(db_path):
    """DB初期化: テーブルを持つファイルが作成される。"""
    initialize_database(db_path)
    assert db_path.exists()


def test_initialize_database_is_idempotent(db_path):
    """DB初期化: 2回呼んでも例外にならない（CREATE TABLE IF NOT EXISTS）。"""
    initialize_database(db_path)
    initialize_database(db_path)


def test_save_and_load_returns_identical_json(db_path):
    """保存→読込で、保存前のRunnerResultと完全一致するJSONが返る。"""
    initialize_database(db_path)
    result = _dummy_runner_result()

    saved_run_id = save_runner_result(result, db_path=db_path)
    loaded = load_runner_result(saved_run_id, db_path=db_path)

    assert saved_run_id == "run-123"
    assert loaded == result


def test_save_result_is_json_roundtrip_safe(db_path):
    """raw_json列がjson.dumps/json.loadsで完全に往復可能であること。"""
    initialize_database(db_path)
    result = _dummy_runner_result()
    save_runner_result(result, db_path=db_path)

    loaded = load_runner_result("run-123", db_path=db_path)
    assert json.dumps(loaded, sort_keys=True) == json.dumps(result, sort_keys=True)


def test_load_nonexistent_run_id_returns_none(db_path):
    """存在しないrun_idを読み込むとNoneが返る。"""
    initialize_database(db_path)
    assert load_runner_result("does-not-exist", db_path=db_path) is None


def test_save_without_run_id_raises_value_error(db_path):
    """run_idキーが無いRunnerResultはValueErrorになる。"""
    initialize_database(db_path)
    with pytest.raises(ValueError):
        save_runner_result({"status": "SUCCESS"}, db_path=db_path)


def test_save_extracts_code_strategy_period_from_pipeline(db_path):
    """code/strategy_name/periodは"pipeline"結果からの読み取りのみで、新しい計算は行わない。"""
    initialize_database(db_path)
    result = _dummy_runner_result()
    save_runner_result(result, db_path=db_path)

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT code, strategy_name, period FROM walkforward_runs WHERE run_id = ?",
            ("run-123",),
        ).fetchone()
    finally:
        conn.close()

    assert row == ("7203", "v9", "1y")


def test_save_handles_missing_pipeline_gracefully(db_path):
    """Pipeline失敗時（pipeline=None）でも例外を出さず保存でき、raw_jsonは維持される。"""
    initialize_database(db_path)
    result = _dummy_runner_result()
    result["pipeline"] = None

    saved_run_id = save_runner_result(result, db_path=db_path)
    loaded = load_runner_result(saved_run_id, db_path=db_path)
    assert loaded == result


def test_compare_run_id_is_stored(db_path):
    """compare_run_idを指定した場合、そのままカラムへ保存される。"""
    initialize_database(db_path)
    result = _dummy_runner_result()
    save_runner_result(result, db_path=db_path, compare_run_id="compare-abc")

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT compare_run_id FROM walkforward_runs WHERE run_id = ?",
            ("run-123",),
        ).fetchone()
    finally:
        conn.close()

    assert row[0] == "compare-abc"


def test_duplicate_run_id_raises_integrity_error(db_path):
    """同じrun_idを2回保存すると、上書きせず例外を送出する（重複保存の検知）。"""
    initialize_database(db_path)
    result = _dummy_runner_result()
    save_runner_result(result, db_path=db_path)

    with pytest.raises(sqlite3.IntegrityError):
        save_runner_result(result, db_path=db_path)
