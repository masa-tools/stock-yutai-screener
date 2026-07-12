"""tests/test_walkforward_runner.py
====================================================================
backtest.walkforward_runner.run_walkforward_runner() の自動テスト。

【テスト方針】
  run_walkforward_pipeline / run_walkforward_benchmark /
  build_walkforward_summary / build_walkforward_context の4関数は
  すべてmonkeypatchでモックする。実際のバックテスト（yfinance呼び出し・
  スコア計算・Decision/Rating/Confidence/Statistics/Benchmark/Summaryの
  計算）は一切実行しない。

  本テストが検証するのはrun_walkforward_runner()自身の制御フロー
  （各段階の成功/失敗に応じたstatus決定・errorsへの記録・後続段階への
  継続可否・戻り値の構造）のみである。Benchmarkロジック・Decision
  ロジック・Rating・Confidence・Summary計算の正しさは、それぞれ
  test_benchmark.py・test_decision.py等、別モジュールの責務であり
  本テストの対象外とする。

  本番コード（backtest/ 配下の実装ファイル）は一切変更していない。
"""

from __future__ import annotations

import json

import pytest

import backtest.walkforward_runner as wf_runner


# ════════════════════════════════════════════════
# ダミーのstrategy_fn（実際には呼ばれない想定だが、シグネチャを
# 満たすために用意するプレースホルダー）
# ════════════════════════════════════════════════
def _dummy_strategy_fn(window_df, info, code):
    """テスト内でrun_walkforward_pipelineがモック済みのため、実際には呼ばれない。"""
    raise AssertionError(
        "strategy_fnが実際に呼ばれています。"
        "run_walkforward_pipelineが正しくモックされているか確認してください。"
    )


# ════════════════════════════════════════════════
# モック戻り値を組み立てるヘルパー
# （「このテストが何を意図しているか」が分かるよう、
#  成功/失敗パターンごとに小さな関数として用意する）
# ════════════════════════════════════════════════
def _pipeline_result_ok() -> dict:
    """walkforward_pipeline.run_walkforward_pipeline() の正常系ダミー戻り値。"""
    return {
        "pipeline_version": "1.0",
        "run_id": "dummy-run-id",
        "strategy": "v9",
        "code": "7203",
        "period": "1y",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "windows": {"windows": [{"window_index": 0, "decision_report_result": {}}]},
        "errors": [],
        "warnings": [],
    }


def _benchmark_result_ok() -> dict:
    """walkforward_benchmark.run_walkforward_benchmark() の正常系ダミー戻り値。"""
    return {
        "benchmark_schema_version": "1.0",
        "run_id": "dummy-run-id",
        "code": "7203",
        "strategy_name": "v9",
        "period": "1y",
        "total_windows": 1,
        "total_transitions": 0,
        "windows": [],
        "transitions": [],
        "improvement_rank": [],
        "best_transition": None,
        "worst_transition": None,
        "benchmark_summary": {
            "improved_count": 0, "declined_count": 0, "unchanged_count": 0,
            "comparison_success_count": 0, "comparison_failure_count": 0,
            "total_transitions": 0,
        },
    }


def _summary_result_ok() -> dict:
    """walkforward_summary.build_walkforward_summary() の正常系ダミー戻り値。"""
    return {
        "summary_schema_version": "1.0",
        "metadata": {"run_id": "dummy-run-id", "window_count": 1},
        "health_check": {"level": "Good", "score": 80.0, "reason": "dummy"},
        "stability_score": {"score": 70.0, "per_metric": {}},
        "improvement_trend": {"trend": "flat", "reason": "dummy",
                               "first_score": None, "last_score": None},
        "benchmark_improvement_rate": {"rate_pct": None, "sample_size": 0, "reason": None},
        "metric_statistics": {},
        "decision_distribution": {},
        "best_window": None,
        "worst_window": None,
        "window_metrics": [],
    }


def _context_result_ok() -> dict:
    """walkforward_context.build_walkforward_context() の正常系ダミー戻り値。"""
    return {
        "context_schema_version": "1.0",
        "execution_metadata": {"run_id": "dummy-run-id"},
        "module_versions": {"pipeline": "1.0", "benchmark": "1.0", "summary": "1.0", "context": "1.0"},
        "data_availability": {
            "pipeline": True, "benchmark": True, "summary": True,
            "windows": True, "health_check": True, "improvement_trend": False,
        },
        "context_summary": {
            "available_modules": ["pipeline", "benchmark", "summary"],
            "window_count": 1, "benchmark_transition_count": 0,
            "has_summary": True, "has_health_check": True, "has_improvement_trend": False,
        },
        "navigation": {"sections": ["pipeline", "benchmark", "summary", "windows", "metadata"]},
        "pipeline": _pipeline_result_ok(),
        "benchmark": _benchmark_result_ok(),
        "summary": _summary_result_ok(),
    }


# ════════════════════════════════════════════════
# fixture: 4関数をすべて正常系でモックした状態
# ════════════════════════════════════════════════
@pytest.fixture
def mock_all_success(monkeypatch):
    """run_walkforward_pipeline / run_walkforward_benchmark /
    build_walkforward_summary / build_walkforward_context の4つすべてを、
    正常終了するダミー実装へ差し替える。
    """
    monkeypatch.setattr(wf_runner, "run_walkforward_pipeline",
                         lambda *args, **kwargs: _pipeline_result_ok())
    monkeypatch.setattr(wf_runner, "run_walkforward_benchmark",
                         lambda *args, **kwargs: _benchmark_result_ok())
    monkeypatch.setattr(wf_runner, "build_walkforward_summary",
                         lambda *args, **kwargs: _summary_result_ok())
    monkeypatch.setattr(wf_runner, "build_walkforward_context",
                         lambda *args, **kwargs: _context_result_ok())


def _run(dry_run: bool = False) -> dict:
    """run_walkforward_runner() をテスト用の共通引数で実行する。"""
    return wf_runner.run_walkforward_runner(
        code="7203",
        strategy_fn=_dummy_strategy_fn,
        strategy_name="v9",
        period="1y",
        dry_run=dry_run,
    )


# ════════════════════════════════════════════════
# ① 正常終了
# ════════════════════════════════════════════════
def test_success_status_is_success(mock_all_success):
    """4段階すべてが正常に完了した場合、statusは'SUCCESS'になる。"""
    result = _run(dry_run=False)
    assert result["status"] == "SUCCESS"
    assert result["errors"] == []


# ════════════════════════════════════════════════
# ② Dry Run
# ════════════════════════════════════════════════
def test_dry_run_skips_benchmark_summary_context(monkeypatch):
    """dry_run=True の場合、Benchmark/Summary/ContextはSKIPPEDとなり、
    それらの生成関数（run_walkforward_benchmark等）は一切呼ばれない。
    """
    monkeypatch.setattr(wf_runner, "run_walkforward_pipeline",
                         lambda *args, **kwargs: _pipeline_result_ok())

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("Dry Run時にこの関数が呼ばれるべきではありません。")

    monkeypatch.setattr(wf_runner, "run_walkforward_benchmark", _fail_if_called)
    monkeypatch.setattr(wf_runner, "build_walkforward_summary", _fail_if_called)
    monkeypatch.setattr(wf_runner, "build_walkforward_context", _fail_if_called)

    result = _run(dry_run=True)

    assert result["dry_run"] is True
    assert result["stage_status"]["benchmark"] == "SKIPPED"
    assert result["stage_status"]["summary"] == "SKIPPED"
    assert result["stage_status"]["context"] == "SKIPPED"
    assert result["benchmark"] is None
    assert result["summary"] is None
    assert result["context"] is None


# ════════════════════════════════════════════════
# ③ Pipeline失敗
# ════════════════════════════════════════════════
def test_pipeline_failure_records_error_and_stops(monkeypatch):
    """Pipelineが例外を送出した場合、status は 'FAILED' または
    'PARTIAL_SUCCESS' のいずれかになり、errorsに記録される。
    後続のBenchmark/Summary/Contextは実行されない
    （Pipelineの結果が無ければ以降の段階を実行できないため）。
    """
    def _raise(*args, **kwargs):
        raise RuntimeError("pipeline boom")

    monkeypatch.setattr(wf_runner, "run_walkforward_pipeline", _raise)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("Pipeline失敗後にこの関数が呼ばれるべきではありません。")

    monkeypatch.setattr(wf_runner, "run_walkforward_benchmark", _fail_if_called)
    monkeypatch.setattr(wf_runner, "build_walkforward_summary", _fail_if_called)
    monkeypatch.setattr(wf_runner, "build_walkforward_context", _fail_if_called)

    result = _run(dry_run=False)

    assert result["status"] in ("FAILED", "PARTIAL_SUCCESS")
    assert len(result["errors"]) >= 1
    assert any("pipeline" in str(e).lower() for e in result["errors"])
    assert result["pipeline"] is None


# ════════════════════════════════════════════════
# ④ Benchmark失敗
# ════════════════════════════════════════════════
def test_benchmark_failure_allows_summary_and_context_to_continue(monkeypatch):
    """Pipelineは成功、Benchmarkのみ失敗した場合、
    可能であればSummary/Contextの生成は継続される。
    """
    monkeypatch.setattr(wf_runner, "run_walkforward_pipeline",
                         lambda *args, **kwargs: _pipeline_result_ok())

    def _raise(*args, **kwargs):
        raise RuntimeError("benchmark boom")

    monkeypatch.setattr(wf_runner, "run_walkforward_benchmark", _raise)
    monkeypatch.setattr(wf_runner, "build_walkforward_summary",
                         lambda *args, **kwargs: _summary_result_ok())
    monkeypatch.setattr(wf_runner, "build_walkforward_context",
                         lambda *args, **kwargs: _context_result_ok())

    result = _run(dry_run=False)

    assert result["status"] in ("PARTIAL_SUCCESS", "FAILED")
    assert any("benchmark" in str(e).lower() for e in result["errors"])
    assert result["pipeline"] is not None
    # Summary/Contextは、Benchmark失敗後も実行を試みられていること
    # （モックが正常応答するため、ここでは結果が入っていることを確認する）。
    assert result["summary"] is not None
    assert result["context"] is not None


# ════════════════════════════════════════════════
# ⑤ Summary失敗
# ════════════════════════════════════════════════
def test_summary_failure_allows_context_to_continue(monkeypatch):
    """Pipeline/Benchmarkは成功、Summaryのみ失敗した場合、
    Contextの生成まで継続される。
    """
    monkeypatch.setattr(wf_runner, "run_walkforward_pipeline",
                         lambda *args, **kwargs: _pipeline_result_ok())
    monkeypatch.setattr(wf_runner, "run_walkforward_benchmark",
                         lambda *args, **kwargs: _benchmark_result_ok())

    def _raise(*args, **kwargs):
        raise RuntimeError("summary boom")

    monkeypatch.setattr(wf_runner, "build_walkforward_summary", _raise)
    monkeypatch.setattr(wf_runner, "build_walkforward_context",
                         lambda *args, **kwargs: _context_result_ok())

    result = _run(dry_run=False)

    assert result["status"] in ("PARTIAL_SUCCESS", "FAILED")
    assert any("summary" in str(e).lower() for e in result["errors"])
    assert result["pipeline"] is not None
    assert result["benchmark"] is not None
    assert result["summary"] is None
    assert result["context"] is not None


# ════════════════════════════════════════════════
# ⑥ Context失敗
# ════════════════════════════════════════════════
def test_context_failure_still_returns_result(monkeypatch):
    """Pipeline/Benchmark/Summaryは成功、Contextのみ失敗しても、
    Runner自体は例外を送出せず戻り値（dict）を返す。
    """
    monkeypatch.setattr(wf_runner, "run_walkforward_pipeline",
                         lambda *args, **kwargs: _pipeline_result_ok())
    monkeypatch.setattr(wf_runner, "run_walkforward_benchmark",
                         lambda *args, **kwargs: _benchmark_result_ok())
    monkeypatch.setattr(wf_runner, "build_walkforward_summary",
                         lambda *args, **kwargs: _summary_result_ok())

    def _raise(*args, **kwargs):
        raise RuntimeError("context boom")

    monkeypatch.setattr(wf_runner, "build_walkforward_context", _raise)

    result = _run(dry_run=False)

    assert isinstance(result, dict)
    assert result["status"] in ("PARTIAL_SUCCESS", "FAILED")
    assert any("context" in str(e).lower() for e in result["errors"])
    assert result["context"] is None
    assert result["pipeline"] is not None
    assert result["benchmark"] is not None
    assert result["summary"] is not None


# ════════════════════════════════════════════════
# ⑦ JSON互換性
# ════════════════════════════════════════════════
def test_result_is_json_serializable_on_success(mock_all_success):
    """正常終了時、戻り値全体がjson.dumps()可能である。"""
    result = _run(dry_run=False)
    serialized = json.dumps(result)
    assert isinstance(serialized, str)


def test_result_is_json_serializable_on_dry_run(monkeypatch):
    """Dry Run時（Benchmark/Summary/ContextがNone）でも戻り値がjson.dumps()可能である。"""
    monkeypatch.setattr(wf_runner, "run_walkforward_pipeline",
                         lambda *args, **kwargs: _pipeline_result_ok())
    monkeypatch.setattr(wf_runner, "run_walkforward_benchmark",
                         lambda *args, **kwargs: pytest.fail("呼ばれるべきではありません"))
    monkeypatch.setattr(wf_runner, "build_walkforward_summary",
                         lambda *args, **kwargs: pytest.fail("呼ばれるべきではありません"))
    monkeypatch.setattr(wf_runner, "build_walkforward_context",
                         lambda *args, **kwargs: pytest.fail("呼ばれるべきではありません"))

    result = _run(dry_run=True)
    serialized = json.dumps(result)
    assert isinstance(serialized, str)


def test_result_is_json_serializable_on_failure(monkeypatch):
    """Pipeline失敗時（大半のフィールドがNone）でも戻り値がjson.dumps()可能である。"""
    def _raise(*args, **kwargs):
        raise RuntimeError("pipeline boom")

    monkeypatch.setattr(wf_runner, "run_walkforward_pipeline", _raise)
    monkeypatch.setattr(wf_runner, "run_walkforward_benchmark",
                         lambda *args, **kwargs: pytest.fail("呼ばれるべきではありません"))
    monkeypatch.setattr(wf_runner, "build_walkforward_summary",
                         lambda *args, **kwargs: pytest.fail("呼ばれるべきではありません"))
    monkeypatch.setattr(wf_runner, "build_walkforward_context",
                         lambda *args, **kwargs: pytest.fail("呼ばれるべきではありません"))

    result = _run(dry_run=False)
    serialized = json.dumps(result)
    assert isinstance(serialized, str)


# ════════════════════════════════════════════════
# ⑧ 必須キー
# ════════════════════════════════════════════════
_REQUIRED_KEYS = (
    "run_id", "status", "stage_status", "stage_elapsed",
    "pipeline", "benchmark", "summary", "context", "errors", "warnings",
)


@pytest.mark.parametrize("dry_run", [False, True])
def test_required_keys_present_on_success(mock_all_success, dry_run):
    """正常系・Dry Runいずれの場合も、必須キーがすべて戻り値に存在する。"""
    result = _run(dry_run=dry_run)
    for key in _REQUIRED_KEYS:
        assert key in result, f"必須キー '{key}' が戻り値に存在しません。"


def test_required_keys_present_on_pipeline_failure(monkeypatch):
    """Pipeline失敗時も、必須キーはすべて戻り値に存在する（値がNoneになるだけ）。"""
    def _raise(*args, **kwargs):
        raise RuntimeError("pipeline boom")

    monkeypatch.setattr(wf_runner, "run_walkforward_pipeline", _raise)
    monkeypatch.setattr(wf_runner, "run_walkforward_benchmark",
                         lambda *args, **kwargs: pytest.fail("呼ばれるべきではありません"))
    monkeypatch.setattr(wf_runner, "build_walkforward_summary",
                         lambda *args, **kwargs: pytest.fail("呼ばれるべきではありません"))
    monkeypatch.setattr(wf_runner, "build_walkforward_context",
                         lambda *args, **kwargs: pytest.fail("呼ばれるべきではありません"))

    result = _run(dry_run=False)
    for key in _REQUIRED_KEYS:
        assert key in result, f"必須キー '{key}' が戻り値に存在しません。"
