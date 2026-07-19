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
    list_runner_results,
    search_runner_results,
    save_compare_result,
    load_compare_result,
    list_compare_results,
    search_compare_results,
    delete_runner_result,
    delete_compare_result,
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


# ════════════════════════════════════════════════
# list_runner_results() のテスト（Phase3）
# ════════════════════════════════════════════════
def test_list_runner_results_empty(db_path):
    """保存済みレコードが無い場合、空リストが返る。"""
    initialize_database(db_path)
    assert list_runner_results(db_path=db_path) == []


def test_list_runner_results_returns_multiple_entries(db_path):
    """複数件保存した場合、すべてのrun_idが一覧へ含まれる。"""
    initialize_database(db_path)
    save_runner_result(_dummy_runner_result("run-1"), db_path=db_path)
    save_runner_result(_dummy_runner_result("run-2"), db_path=db_path)

    rows = list_runner_results(db_path=db_path)
    assert {r["run_id"] for r in rows} == {"run-1", "run-2"}


def test_list_runner_results_ordered_by_created_at_desc(db_path):
    """created_at降順（後から保存したものが先頭）で返る。"""
    initialize_database(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "INSERT INTO walkforward_runs "
            "(run_id, code, strategy_name, period, status, raw_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("run-old", "7203", "v9", "1y", "SUCCESS", "{}", "2026-01-01T00:00:00"),
        )
        conn.execute(
            "INSERT INTO walkforward_runs "
            "(run_id, code, strategy_name, period, status, raw_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("run-new", "7203", "v9", "1y", "SUCCESS", "{}", "2026-01-02T00:00:00"),
        )
        conn.commit()
    finally:
        conn.close()

    rows = list_runner_results(db_path=db_path)
    assert [r["run_id"] for r in rows] == ["run-new", "run-old"]


def test_list_runner_results_does_not_include_raw_json(db_path):
    """一覧取得の戻り値にraw_jsonキーが含まれない。"""
    initialize_database(db_path)
    save_runner_result(_dummy_runner_result(), db_path=db_path)

    rows = list_runner_results(db_path=db_path)
    assert "raw_json" not in rows[0]
    assert set(rows[0].keys()) == {
        "run_id", "code", "strategy_name", "period", "status", "started_at", "created_at",
    }


# ════════════════════════════════════════════════
# search_runner_results() のテスト（Phase4）
# ════════════════════════════════════════════════
def _seed_search_fixture(db_path):
    """検索テスト用に、条件の異なる3件を保存するヘルパー。"""
    initialize_database(db_path)
    r1 = _dummy_runner_result("run-a")
    r1["pipeline"] = {"code": "7203", "strategy": "v9", "period": "1y"}
    r1["status"] = "SUCCESS"

    r2 = _dummy_runner_result("run-b")
    r2["pipeline"] = {"code": "7203", "strategy": "v8", "period": "2y"}
    r2["status"] = "PARTIAL_SUCCESS"

    r3 = _dummy_runner_result("run-c")
    r3["pipeline"] = {"code": "8035", "strategy": "v9", "period": "1y"}
    r3["status"] = "FAILED"

    for r in (r1, r2, r3):
        save_runner_result(r, db_path=db_path)


def test_search_by_code_only(db_path):
    _seed_search_fixture(db_path)
    rows = search_runner_results(code="7203", db_path=db_path)
    assert {r["run_id"] for r in rows} == {"run-a", "run-b"}


def test_search_by_strategy_only(db_path):
    _seed_search_fixture(db_path)
    rows = search_runner_results(strategy_name="v9", db_path=db_path)
    assert {r["run_id"] for r in rows} == {"run-a", "run-c"}


def test_search_by_period_only(db_path):
    _seed_search_fixture(db_path)
    rows = search_runner_results(period="2y", db_path=db_path)
    assert {r["run_id"] for r in rows} == {"run-b"}


def test_search_by_status_only(db_path):
    _seed_search_fixture(db_path)
    rows = search_runner_results(status="FAILED", db_path=db_path)
    assert {r["run_id"] for r in rows} == {"run-c"}


def test_search_with_multiple_conditions_is_and(db_path):
    """複数条件を指定した場合はAND検索になる（両方満たすもののみ返る）。"""
    _seed_search_fixture(db_path)
    rows = search_runner_results(code="7203", strategy_name="v9", db_path=db_path)
    assert {r["run_id"] for r in rows} == {"run-a"}


def test_search_with_no_conditions_returns_all(db_path):
    """条件を1つも指定しない場合は全件が返る（list_runner_results()と同じ）。"""
    _seed_search_fixture(db_path)
    rows = search_runner_results(db_path=db_path)
    assert {r["run_id"] for r in rows} == {"run-a", "run-b", "run-c"}


def test_search_result_does_not_include_raw_json(db_path):
    _seed_search_fixture(db_path)
    rows = search_runner_results(code="7203", db_path=db_path)
    assert all("raw_json" not in r for r in rows)


# ════════════════════════════════════════════════
# メタデータ拡張のテスト（Phase5）
# ════════════════════════════════════════════════
def test_list_runner_results_includes_extended_metadata(db_path):
    """一覧取得結果に runner_schema_version / finished_at / elapsed_seconds が含まれる。"""
    initialize_database(db_path)
    save_runner_result(_dummy_runner_result(), db_path=db_path)

    rows = list_runner_results(db_path=db_path)
    row = rows[0]
    assert row["runner_schema_version"] == "1.0"
    assert row["finished_at"] == "2026-01-01T00:01:00+00:00"
    assert row["elapsed_seconds"] == 60.0


def test_search_runner_results_includes_extended_metadata(db_path):
    """検索取得結果にも runner_schema_version / finished_at / elapsed_seconds が含まれる。"""
    initialize_database(db_path)
    save_runner_result(_dummy_runner_result(), db_path=db_path)

    rows = search_runner_results(code="7203", db_path=db_path)
    row = rows[0]
    assert row["runner_schema_version"] == "1.0"
    assert row["finished_at"] == "2026-01-01T00:01:00+00:00"
    assert row["elapsed_seconds"] == 60.0


# ════════════════════════════════════════════════
# Strategy Compare履歴保存のテスト（Phase7）
# ════════════════════════════════════════════════
def _dummy_compare_result(run_id: str = "compare-123") -> dict:
    """walkforward_strategy_compare.run_walkforward_strategy_compare() の戻り値形状のダミー。"""
    return {
        "strategy_compare_schema_version": "1.0",
        "run_id": run_id,
        "status": "SUCCESS",
        "warnings": [],
        "errors": [],
        "code": "7203",
        "period": "1y",
        "strategies": {
            "v8": _dummy_runner_result("run-v8"),
            "v9": _dummy_runner_result("run-v9"),
        },
    }


def test_migration_v3_creates_walkforward_compares_table(db_path):
    """Migration v3適用後、walkforward_comparesテーブルが存在する。"""
    initialize_database(db_path)

    conn = sqlite3.connect(str(db_path))
    try:
        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='walkforward_compares'"
        ).fetchall()]
        versions = [row[0] for row in conn.execute(
            "SELECT version FROM walkforward_schema_version ORDER BY version"
        ).fetchall()]
    finally:
        conn.close()

    assert tables == ["walkforward_compares"]
    assert versions == [1, 2, 3]


def test_save_and_load_compare_result_returns_identical_json(db_path):
    """保存→読込で、保存前のStrategyCompareResultと完全一致するJSONが返る。"""
    initialize_database(db_path)
    compare_result = _dummy_compare_result()

    saved_id = save_compare_result(compare_result, db_path=db_path)
    loaded = load_compare_result(saved_id, db_path=db_path)

    assert saved_id == "compare-123"
    assert loaded == compare_result


def test_load_nonexistent_compare_run_id_returns_none(db_path):
    """存在しないcompare_run_idを読み込むとNoneが返る。"""
    initialize_database(db_path)
    assert load_compare_result("does-not-exist", db_path=db_path) is None


def test_save_compare_result_without_run_id_raises_value_error(db_path):
    """run_idキーが無いcompare_resultはValueErrorになる。"""
    initialize_database(db_path)
    with pytest.raises(ValueError):
        save_compare_result({"status": "SUCCESS"}, db_path=db_path)


def test_duplicate_compare_run_id_raises_integrity_error(db_path):
    """同じcompare_run_idを2回保存すると、上書きせず例外を送出する。"""
    initialize_database(db_path)
    compare_result = _dummy_compare_result()
    save_compare_result(compare_result, db_path=db_path)

    with pytest.raises(sqlite3.IntegrityError):
        save_compare_result(compare_result, db_path=db_path)


# ════════════════════════════════════════════════
# Strategy Compare履歴 一覧・検索のテスト（Phase8）
# ════════════════════════════════════════════════
def test_list_compare_results_empty(db_path):
    """保存済みレコードが無い場合、空リストが返る。"""
    initialize_database(db_path)
    assert list_compare_results(db_path=db_path) == []


def test_list_compare_results_returns_multiple_entries(db_path):
    """複数件保存した場合、すべてのcompare_run_idが一覧へ含まれる。"""
    initialize_database(db_path)
    save_compare_result(_dummy_compare_result("compare-1"), db_path=db_path)
    save_compare_result(_dummy_compare_result("compare-2"), db_path=db_path)

    rows = list_compare_results(db_path=db_path)
    assert {r["compare_run_id"] for r in rows} == {"compare-1", "compare-2"}


def test_list_compare_results_ordered_by_created_at_desc(db_path):
    """created_at降順（後から保存したものが先頭）で返る。"""
    initialize_database(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "INSERT INTO walkforward_compares (compare_run_id, code, period, status, raw_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("compare-old", "7203", "1y", "SUCCESS", "{}", "2026-01-01T00:00:00"),
        )
        conn.execute(
            "INSERT INTO walkforward_compares (compare_run_id, code, period, status, raw_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("compare-new", "7203", "1y", "SUCCESS", "{}", "2026-01-02T00:00:00"),
        )
        conn.commit()
    finally:
        conn.close()

    rows = list_compare_results(db_path=db_path)
    assert [r["compare_run_id"] for r in rows] == ["compare-new", "compare-old"]


def test_list_compare_results_does_not_include_raw_json(db_path):
    """一覧取得の戻り値にraw_jsonキーが含まれない。"""
    initialize_database(db_path)
    save_compare_result(_dummy_compare_result(), db_path=db_path)

    rows = list_compare_results(db_path=db_path)
    assert "raw_json" not in rows[0]
    assert set(rows[0].keys()) == {"compare_run_id", "code", "period", "status", "created_at"}


def _seed_compare_search_fixture(db_path):
    """検索テスト用に、条件の異なる3件を保存するヘルパー。"""
    initialize_database(db_path)
    c1 = _dummy_compare_result("compare-a")
    c1["code"] = "7203"
    c1["period"] = "1y"
    c1["status"] = "SUCCESS"

    c2 = _dummy_compare_result("compare-b")
    c2["code"] = "7203"
    c2["period"] = "2y"
    c2["status"] = "PARTIAL_SUCCESS"

    c3 = _dummy_compare_result("compare-c")
    c3["code"] = "8035"
    c3["period"] = "1y"
    c3["status"] = "FAILED"

    for c in (c1, c2, c3):
        save_compare_result(c, db_path=db_path)


def test_search_compare_results_by_code_only(db_path):
    _seed_compare_search_fixture(db_path)
    rows = search_compare_results(code="7203", db_path=db_path)
    assert {r["compare_run_id"] for r in rows} == {"compare-a", "compare-b"}


def test_search_compare_results_by_period_only(db_path):
    _seed_compare_search_fixture(db_path)
    rows = search_compare_results(period="2y", db_path=db_path)
    assert {r["compare_run_id"] for r in rows} == {"compare-b"}


def test_search_compare_results_by_status_only(db_path):
    _seed_compare_search_fixture(db_path)
    rows = search_compare_results(status="FAILED", db_path=db_path)
    assert {r["compare_run_id"] for r in rows} == {"compare-c"}


def test_search_compare_results_with_multiple_conditions_is_and(db_path):
    """複数条件を指定した場合はAND検索になる。"""
    _seed_compare_search_fixture(db_path)
    rows = search_compare_results(code="7203", period="1y", db_path=db_path)
    assert {r["compare_run_id"] for r in rows} == {"compare-a"}


def test_search_compare_results_with_no_conditions_returns_all(db_path):
    """条件を1つも指定しない場合は全件が返る（list_compare_results()と同じ）。"""
    _seed_compare_search_fixture(db_path)
    rows = search_compare_results(db_path=db_path)
    assert {r["compare_run_id"] for r in rows} == {"compare-a", "compare-b", "compare-c"}


def test_search_compare_results_does_not_include_raw_json(db_path):
    _seed_compare_search_fixture(db_path)
    rows = search_compare_results(code="7203", db_path=db_path)
    assert all("raw_json" not in r for r in rows)


# ════════════════════════════════════════════════
# 履歴削除のテスト（Phase10）
# ════════════════════════════════════════════════
def test_delete_runner_result_success(db_path):
    """保存済みRunnerResultを削除すると、Trueが返る。"""
    initialize_database(db_path)
    save_runner_result(_dummy_runner_result("run-to-delete"), db_path=db_path)

    assert delete_runner_result("run-to-delete", db_path=db_path) is True


def test_delete_runner_result_nonexistent_id_returns_false(db_path):
    """存在しないrun_idを削除しようとしてもFalseが返り、例外にならない。"""
    initialize_database(db_path)
    assert delete_runner_result("does-not-exist", db_path=db_path) is False


def test_load_after_delete_runner_result_returns_none(db_path):
    """削除後、load_runner_result()はNoneを返す。"""
    initialize_database(db_path)
    save_runner_result(_dummy_runner_result("run-to-delete-2"), db_path=db_path)
    delete_runner_result("run-to-delete-2", db_path=db_path)

    assert load_runner_result("run-to-delete-2", db_path=db_path) is None


def test_delete_compare_result_success(db_path):
    """保存済みStrategyCompareResultを削除すると、Trueが返る。"""
    initialize_database(db_path)
    save_compare_result(_dummy_compare_result("compare-to-delete"), db_path=db_path)

    assert delete_compare_result("compare-to-delete", db_path=db_path) is True


def test_delete_compare_result_nonexistent_id_returns_false(db_path):
    """存在しないcompare_run_idを削除しようとしてもFalseが返り、例外にならない。"""
    initialize_database(db_path)
    assert delete_compare_result("does-not-exist", db_path=db_path) is False


def test_load_after_delete_compare_result_returns_none(db_path):
    """削除後、load_compare_result()はNoneを返す。"""
    initialize_database(db_path)
    save_compare_result(_dummy_compare_result("compare-to-delete-2"), db_path=db_path)
    delete_compare_result("compare-to-delete-2", db_path=db_path)

    assert load_compare_result("compare-to-delete-2", db_path=db_path) is None
