"""tests/test_walkforward_strategy_compare.py
====================================================================
backtest.walkforward_strategy_compare.run_walkforward_strategy_compare()
の単体テスト。run_walkforward_runner() をmonkeypatchで差し替え、実際の
バックテスト・ネットワークアクセスは一切行わない。本テストが検証する
のは「複数戦略についてRunnerを正しい引数で繰り返し呼び出し、結果を
束ねる」という配線のみであり、Runner自体の計算内容は対象外とする。
"""

from __future__ import annotations

import json

import pytest

import backtest.walkforward_strategy_compare as wf_compare


def _dummy_strategy_fn(window_df, info, code):
    raise AssertionError("strategy_fnが実際に呼ばれるべきではありません。")


def _runner_result_ok(strategy_name: str) -> dict:
    return {
        "runner_schema_version": "1.0",
        "run_id": f"run-{strategy_name}",
        "status": "SUCCESS",
        "summary": {"health_check": {"level": "Good", "score": 80.0}},
        "benchmark": {"best_transition": {"improvement_score": 70.0}},
    }


@pytest.fixture
def mock_runner_success(monkeypatch):
    calls = []

    def _fake_runner(*, code, strategy_fn, strategy_name, period, **kwargs):
        calls.append({"code": code, "strategy_fn": strategy_fn, "strategy_name": strategy_name,
                       "period": period, "kwargs": kwargs})
        return _runner_result_ok(strategy_name)

    monkeypatch.setattr(wf_compare, "run_walkforward_runner", _fake_runner)
    return calls


def test_calls_runner_once_per_strategy(mock_runner_success):
    """strategies辞書のエントリ数だけrun_walkforward_runner()が呼ばれる。"""
    strategies = {"v8": _dummy_strategy_fn, "v9": _dummy_strategy_fn}
    wf_compare.run_walkforward_strategy_compare(code="7203", strategies=strategies, period="1y")

    assert len(mock_runner_success) == 2
    assert {c["strategy_name"] for c in mock_runner_success} == {"v8", "v9"}


def test_result_contains_one_entry_per_strategy(mock_runner_success):
    """戻り値のstrategiesに、指定した戦略名をキーとする結果が1つずつ格納される。"""
    strategies = {"v8": _dummy_strategy_fn, "v9": _dummy_strategy_fn}
    result = wf_compare.run_walkforward_strategy_compare(code="7203", strategies=strategies, period="1y")

    assert set(result["strategies"].keys()) == {"v8", "v9"}
    assert result["strategies"]["v8"]["status"] == "SUCCESS"
    assert result["errors"] == []
    # H-1対応: Runnerファミリーと揃えたトップレベル構造の検証
    assert result["status"] == "SUCCESS"
    assert result["run_id"] is not None
    assert result["warnings"] == []


def test_extra_kwargs_are_forwarded_to_every_runner_call(mock_runner_success):
    """dry_run等の追加kwargsが、すべてのRunner呼び出しへ共通で転送される。"""
    strategies = {"v8": _dummy_strategy_fn}
    wf_compare.run_walkforward_strategy_compare(
        code="7203", strategies=strategies, period="1y", dry_run=True, run_id="fixed-id"
    )

    assert mock_runner_success[0]["kwargs"].get("dry_run") is True
    assert mock_runner_success[0]["kwargs"].get("run_id") == "fixed-id"


def test_one_strategy_failure_does_not_stop_others(monkeypatch):
    """1つの戦略でRunnerが例外を送出しても、他の戦略の実行は継続される。"""
    def _fake_runner(*, code, strategy_fn, strategy_name, period, **kwargs):
        if strategy_name == "v8":
            raise RuntimeError("boom")
        return _runner_result_ok(strategy_name)

    monkeypatch.setattr(wf_compare, "run_walkforward_runner", _fake_runner)

    strategies = {"v8": _dummy_strategy_fn, "v9": _dummy_strategy_fn}
    result = wf_compare.run_walkforward_strategy_compare(code="7203", strategies=strategies, period="1y")

    assert "v8" not in result["strategies"]
    assert "v9" in result["strategies"]
    assert len(result["errors"]) == 1
    assert result["errors"][0]["strategy"] == "v8"
    # H-1対応: 一部戦略が失敗した場合はPARTIAL_SUCCESSになる
    # （新しい状態は作らず、既存3値のみを使用）
    assert result["status"] == "PARTIAL_SUCCESS"


def test_result_is_json_serializable(mock_runner_success):
    strategies = {"v8": _dummy_strategy_fn, "v9": _dummy_strategy_fn}
    result = wf_compare.run_walkforward_strategy_compare(code="7203", strategies=strategies, period="1y")
    assert isinstance(json.dumps(result), str)


def test_required_keys_present(mock_runner_success):
    strategies = {"v8": _dummy_strategy_fn}
    result = wf_compare.run_walkforward_strategy_compare(code="7203", strategies=strategies, period="1y")
    for key in ("strategy_compare_schema_version", "run_id", "status", "warnings",
                "code", "period", "strategies", "errors"):
        assert key in result
