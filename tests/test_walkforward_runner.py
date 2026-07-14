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

【今回の修正について】
  Dry Runテストが参照していた result["dry_run"] は、実際の
  run_walkforward_runner() の戻り値には存在しないキーであることが
  実ファイル監査で判明したため、実在するキー（stage_status["benchmark"]
  等）を用いた検証へ差し替えた。Runner本体・他のテスト項目は変更して
  いない。
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
    """
    dry_run=True の場合、Benchmark/Summary/ContextはSKIPPEDとなり、
    それらの生成関数（run_walkforward_benchmark等）は一切呼ばれない。

    【修正メモ】run_walkforward_runner()の戻り値には"dry_run"キーは
    存在しないため（実ファイル監査で判明）、代わりに実在する
    stage_status（"pipeline"/"benchmark"/"summary"/"context"の各値）と
    pipeline/benchmark/summary/contextの値（None/非None）を用いて
    Dry Runの効果を検証する。
    """
    monkeypatch.setattr(wf_runner, "run_walkforward_pipeline",
                         lambda *args, **kwargs: _pipeline_result_ok())

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("Dry Run時にこの関数が呼ばれるべきではありません。")

    monkeypatch.setattr(wf_runner, "run_walkforward_benchmark", _fail_if_called)
    monkeypatch.setattr(wf_runner, "build_walkforward_summary", _fail_if_called)
    monkeypatch.setattr(wf_runner, "build_walkforward_context", _fail_if_called)

    result = _run(dry_run=True)

    assert result["status"] == "SUCCESS"
    assert result["stage_status"]["pipeline"] == "SUCCESS"
    assert result["stage_status"]["benchmark"] == "SKIPPED"
    assert result["stage_status"]["summary"] == "SKIPPED"
    assert result["stage_status"]["context"] == "SKIPPED"
    assert result["pipeline"] is not None
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


# ════════════════════════════════════════════════
# H-1対応: 予約引数（context/extensions/ai_context/fundamental_context/
# dividend_context/market_context）とrun_idの伝播テスト
# ════════════════════════════════════════════════
#
# ここから追加分。既存のテスト・フィクスチャ・ヘルパー関数は変更していない。
# 4つのStage関数をすべて「呼び出し時のargs/kwargsを記録するだけ」の
# スパイへ差し替え、Runner自身が各Stageへ何を渡しているかを直接検証する。
# 新しい計算ロジックは検証せず、Runnerの配線（引数の受け渡し）のみを対象とする。

@pytest.fixture
def capture_calls(monkeypatch):
    """
    run_walkforward_pipeline / run_walkforward_benchmark /
    build_walkforward_summary / build_walkforward_context の4関数を、
    正常系のダミー戻り値を返しつつ呼び出し時のargs/kwargsを記録する
    スパイ関数へ差し替える。

    Returns:
        {"pipeline": {"args":..., "kwargs":...}, "benchmark": {...},
         "summary": {...}, "context": {...}} という形のdict
        （run_walkforward_runner()実行後に各キーへ記録される）。
    """
    calls: dict[str, dict] = {}

    def _pipeline(*args, **kwargs):
        calls["pipeline"] = {"args": args, "kwargs": kwargs}
        return _pipeline_result_ok()

    def _benchmark(*args, **kwargs):
        calls["benchmark"] = {"args": args, "kwargs": kwargs}
        return _benchmark_result_ok()

    def _summary(*args, **kwargs):
        calls["summary"] = {"args": args, "kwargs": kwargs}
        return _summary_result_ok()

    def _context(*args, **kwargs):
        calls["context"] = {"args": args, "kwargs": kwargs}
        return _context_result_ok()

    monkeypatch.setattr(wf_runner, "run_walkforward_pipeline", _pipeline)
    monkeypatch.setattr(wf_runner, "run_walkforward_benchmark", _benchmark)
    monkeypatch.setattr(wf_runner, "build_walkforward_summary", _summary)
    monkeypatch.setattr(wf_runner, "build_walkforward_context", _context)

    return calls


def _run_with(**overrides) -> dict:
    """
    run_walkforward_runner() を任意の追加引数付きで実行するテスト用ヘルパー。

    既存の _run(dry_run) はそのまま残し、本テスト群専用の別ヘルパーとして
    追加する（context/extensions/run_id等、_run()が持たない引数を
    柔軟に指定できるようにするため）。
    """
    kwargs = dict(
        code="7203",
        strategy_fn=_dummy_strategy_fn,
        strategy_name="v9",
        period="1y",
        dry_run=False,
    )
    kwargs.update(overrides)
    return wf_runner.run_walkforward_runner(**kwargs)


# ── ① context の伝播 ────────────────────────────────
def test_context_argument_propagates_to_benchmark_summary_context_stages(capture_calls):
    """
    context引数は Benchmark / Summary / Context の3Stageへ
    "同一オブジェクト" としてそのまま転送される。
    Pipeline（Stage1）はcontextを受け取らない設計であることも合わせて確認する
    （実ファイル監査で確認済みの仕様）。
    """
    sentinel_context = {"test": "value"}
    result = _run_with(context=sentinel_context)

    assert capture_calls["benchmark"]["kwargs"].get("context") is sentinel_context
    assert capture_calls["summary"]["kwargs"].get("context") is sentinel_context
    assert capture_calls["context"]["kwargs"].get("context") is sentinel_context

    assert "context" not in capture_calls["pipeline"]["kwargs"], (
        "Pipeline StageはcontextをRunnerから受け取らない設計です。"
        "受け取るようになった場合は配線が変更されたことを意味します。"
    )

    assert result["context_input"] is sentinel_context


# ── ② extensions の伝播 ──────────────────────────────
def test_extensions_argument_propagates_to_all_four_stages(capture_calls):
    """extensions引数は Pipeline / Benchmark / Summary / Context の全4Stageへ同一オブジェクトとして転送される。"""
    sentinel_extensions = {"feature": "x"}
    result = _run_with(extensions=sentinel_extensions)

    assert capture_calls["pipeline"]["kwargs"].get("extensions") is sentinel_extensions
    assert capture_calls["benchmark"]["kwargs"].get("extensions") is sentinel_extensions
    assert capture_calls["summary"]["kwargs"].get("extensions") is sentinel_extensions
    assert capture_calls["context"]["kwargs"].get("extensions") is sentinel_extensions

    assert result.get("extensions") is sentinel_extensions


# ── ③ AI系予約引数はContext Stageのみに渡ること ──────
def test_ai_and_domain_context_arguments_only_reach_context_stage(capture_calls):
    """
    ai_context / fundamental_context / dividend_context / market_context は
    Context Stageのみへ渡され、Pipeline / Benchmark / Summaryへは渡らない。
    """
    ai_ctx = {"ai": 1}
    fundamental_ctx = {"fundamental": 1}
    dividend_ctx = {"dividend": 1}
    market_ctx = {"market": 1}

    result = _run_with(
        ai_context=ai_ctx,
        fundamental_context=fundamental_ctx,
        dividend_context=dividend_ctx,
        market_context=market_ctx,
    )

    ctx_kwargs = capture_calls["context"]["kwargs"]
    assert ctx_kwargs.get("ai_context") is ai_ctx
    assert ctx_kwargs.get("fundamental_context") is fundamental_ctx
    assert ctx_kwargs.get("dividend_context") is dividend_ctx
    assert ctx_kwargs.get("market_context") is market_ctx

    reserved_keys = ("ai_context", "fundamental_context", "dividend_context", "market_context")
    for stage in ("pipeline", "benchmark", "summary"):
        stage_kwargs = capture_calls[stage]["kwargs"]
        for key in reserved_keys:
            assert key not in stage_kwargs, f"{stage} Stageが{key}を受け取るべきではありません。"

    assert result.get("ai_context") is ai_ctx
    assert result.get("fundamental_context") is fundamental_ctx
    assert result.get("dividend_context") is dividend_ctx
    assert result.get("market_context") is market_ctx


# ── ④ result["context"] と result["context_input"] は別物 ──
def test_result_context_and_context_input_are_distinct(capture_calls):
    """
    result["context"]（Stage4=build_walkforward_context()の実行結果）と
    result["context_input"]（Runner呼び出し時に渡したcontext引数そのもの）は、
    同じ"context"という名前でも中身が完全に異なる別物であることを確認する
    （README_walkforward.md §⑦で説明している仕様）。
    """
    sentinel_context = {"test": "value"}
    result = _run_with(context=sentinel_context)

    assert result["context"] == _context_result_ok()
    assert "context_schema_version" in result["context"]

    assert result["context_input"] is sentinel_context

    assert result["context"] is not result["context_input"]
    assert result["context"] != result["context_input"]


# ── ⑤ run_id の伝播 ──────────────────────────────────
def test_explicit_run_id_is_passed_to_pipeline_stage_only(capture_calls):
    """
    明示的に指定したrun_idはPipeline Stageへそのまま渡り、result["run_id"]にも反映される。
    Benchmark/Summary/Context Stageはrun_idを明示引数として受け取らない設計であること
    （各Windowのrun_idは既にPipeline内部で埋め込まれており、後続Stageはそのデータ構造
    から読み取るのみ）も合わせて確認する。
    """
    result = _run_with(run_id="fixed-run-id-123")

    assert capture_calls["pipeline"]["kwargs"].get("run_id") == "fixed-run-id-123"
    assert result["run_id"] == "fixed-run-id-123"

    for stage in ("benchmark", "summary", "context"):
        assert "run_id" not in capture_calls[stage]["kwargs"], (
            f"{stage} Stageは現行実装ではrun_idを明示引数として受け取りません。"
            "受け取るようになった場合はRunnerの配線が変更されたことを意味するため、"
            "本テストが検知します。"
        )


def test_auto_generated_run_id_is_consistent_with_pipeline_call(capture_calls):
    """run_id省略時、自動生成されたUUIDがPipeline呼び出しとresult["run_id"]で一致する。"""
    result = _run_with()

    generated_run_id = capture_calls["pipeline"]["kwargs"].get("run_id")
    assert generated_run_id is not None
    assert result["run_id"] == generated_run_id


# ── ⑥ Dry Run時も伝播仕様が変わらないこと ──────────────
def test_dry_run_preserves_context_extensions_run_id_wiring_to_pipeline(monkeypatch):
    """
    dry_run=True でも、Pipeline呼び出しへのcontext/extensions/run_id伝播仕様は
    変わらない（dry_runはBenchmark以降をスキップするだけで、Pipeline呼び出し
    自体の引数構成には影響しない）。Benchmark以降がSKIPPEDになる従来仕様も
    合わせて確認する。
    """
    calls: dict[str, dict] = {}

    def _pipeline(*args, **kwargs):
        calls["pipeline"] = kwargs
        return _pipeline_result_ok()

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("dry_run=True の場合、この関数は呼ばれるべきではありません。")

    monkeypatch.setattr(wf_runner, "run_walkforward_pipeline", _pipeline)
    monkeypatch.setattr(wf_runner, "run_walkforward_benchmark", _fail_if_called)
    monkeypatch.setattr(wf_runner, "build_walkforward_summary", _fail_if_called)
    monkeypatch.setattr(wf_runner, "build_walkforward_context", _fail_if_called)

    sentinel_extensions = {"e": 1}
    result = _run_with(dry_run=True, run_id="dry-run-id", extensions=sentinel_extensions)

    assert calls["pipeline"].get("run_id") == "dry-run-id"
    assert calls["pipeline"].get("extensions") is sentinel_extensions
    assert result["run_id"] == "dry-run-id"
    assert result.get("extensions") is sentinel_extensions

    assert result["stage_status"]["benchmark"] == "SKIPPED"
    assert result["stage_status"]["summary"] == "SKIPPED"
    assert result["stage_status"]["context"] == "SKIPPED"
    assert result["benchmark"] is None
    assert result["summary"] is None
    assert result["context"] is None

    # 今回contextは未指定のため、context_inputキー自体が結果に含まれないことも確認する
    # （Noneの場合はキーごと省略される設計）。
    assert "context_input" not in result
