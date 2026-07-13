"""backtest/types.py (v9研究開発ブランチ Walk Forward 共通型定義)
====================================================================
Walk Forward関連モジュール（walkforward.py・walkforward_decision.py・
walkforward_evaluation.py・walkforward_pipeline.py・
walkforward_benchmark.py・walkforward_summary.py・walkforward_context.py）
が受け渡しするJSON互換dictの構造を、TypedDictとして集約したモジュール。

【設計方針】
  このファイルは他のbacktest.walkforward_*モジュールに一切依存しない
  （importしない）。型定義のみの末端（リーフ）モジュールとすることで、
  各walkforward_*モジュールがこのファイルをimportしても循環参照が
  発生しない構造にしている。

  計算ロジック・戻り値の実際の構造（キー名・ネスト・値）は一切変更
  していない。ここで定義するTypedDictは、既存の実装が既に返している
  dictの「形」をそのまま型として明文化したものに過ぎない。

【動的キーを持つ構造について（重要な設計判断）】
  以下の構造は、strategyやDecisionラベルの種類によってキー集合が
  実行時に変わるため、TypedDictでは静的に表現できない。これらは
  意図的にMapping[str, Any]の型エイリアスとして残している：
    - ValidationRecord / DecisionRecord: res_df・decision_pipeline.py
      出力の1行分。列はstrategy_v8/v9/将来のv10で異なりうる。
    - DecisionReportResult: "report_info"キー + Decisionラベルごとの
      キー（"Strong Buy"等）という、ラベルの種類が可変な構造。
    - DecisionValidationResult: 同様にDecisionラベルをキーとする構造。
  これらの「値側」の形（1件分のレコード）は DecisionReportEntry・
  DecisionValidationEntry としてTypedDict化している。
"""

from __future__ import annotations

from typing import Any, Literal, Mapping, Optional, TypedDict

__all__ = [
    # 汎用
    "StageErrorEntry",
    "ValidationRecord",
    "DecisionRecord",
    # walkforward.py
    "SplitterDescription",
    "WindowRecord",
    "WalkForwardValidationResult",
    # walkforward_decision.py
    "DecisionWindowRecord",
    "WalkForwardDecisionResult",
    # walkforward_evaluation.py（decision_report.py / decision_validation.py 由来の型を含む）
    "ReportInfo",
    "DecisionReportEntry",
    "DecisionReportResult",
    "DecisionValidationEntry",
    "DecisionValidationResult",
    "EvaluationWindowRecord",
    "WalkForwardEvaluationResult",
    # walkforward_pipeline.py
    "WalkForwardPipelineResult",
    # walkforward_benchmark.py（benchmark.py 由来の型を含む）
    "MetricJudgement",
    "BenchmarkResult",
    "ComparisonMetadata",
    "TransitionRecord",
    "ImprovementRankEntry",
    "BenchmarkSummary",
    "BenchmarkWindowRecord",
    "WalkForwardBenchmarkResult",
    # walkforward_summary.py
    "WindowMetric",
    "MetricStatEntry",
    "StabilityMetricEntry",
    "StabilityScore",
    "HealthCheck",
    "ImprovementTrend",
    "BenchmarkImprovementRate",
    "BestWorstEntry",
    "SummaryMetadata",
    "WalkForwardSummaryResult",
    # walkforward_context.py
    "ExecutionMetadata",
    "ModuleVersions",
    "DataAvailability",
    "ContextSummary",
    "Navigation",
    "WalkForwardContextResult",
    # walkforward_runner.py
    "RunnerStatus",
    "RunnerStageName",
    "RunnerStageStatusValue",
    "RunnerStageStatusMap",
    "RunnerStageElapsedMap",
    "WalkForwardRunnerResult",
]


# ════════════════════════════════════════════════
# 汎用
# ════════════════════════════════════════════════
class StageErrorEntry(TypedDict):
    """walkforward_pipeline.py の errors / warnings 配列の1要素。"""
    stage: str
    message: str


#: res_df・decision_pipeline.py出力の1行分。列はstrategyごとに異なりうる
#: ため、キー集合を静的に固定しない（TypedDict化しない）。
ValidationRecord = Mapping[str, Any]

#: decision_pipeline.attach_decision_columns() 適用後の1行分。
#: ValidationRecordと同様、列はstrategyごとに異なりうる。
DecisionRecord = Mapping[str, Any]


# ════════════════════════════════════════════════
# walkforward.py
# ════════════════════════════════════════════════
class _SplitterDescriptionRequired(TypedDict):
    type: str


class SplitterDescription(_SplitterDescriptionRequired, total=False):
    """WindowSplitterの設定内容を記述するdict（デバッグ・再現性確認用）。

    n_splits/train_ratio/min_validation_sizeはFixedWindowSplitter
    使用時のみ含まれる（将来のRolling/ExpandingWindowSplitterでは
    別のフィールドが入りうるため、typeのみ必須としている）。
    """
    n_splits: int
    train_ratio: float
    min_validation_size: int


class WindowRecord(TypedDict):
    """walkforward.run_walkforward_validation() が生成する1Window分の構造。"""
    validation_period_id: str
    code: str
    strategy_name: str
    window_index: int
    train_start: str
    train_end: str
    train_count: int
    validation_start: str
    validation_end: str
    validation_count: int
    validation_records: list[ValidationRecord]


class WalkForwardValidationResult(TypedDict):
    """walkforward.run_walkforward_validation() の戻り値。"""
    walkforward_schema_version: str
    code: str
    strategy_name: str
    period: str
    splitter: SplitterDescription
    total_days: int
    windows: list[WindowRecord]


# ════════════════════════════════════════════════
# walkforward_decision.py
# ════════════════════════════════════════════════
class DecisionWindowRecord(TypedDict):
    """walkforward_decision.run_walkforward_decision_validation() が生成する1Window分の構造。"""
    validation_period_id: Optional[str]
    run_id: Optional[str]
    code: Optional[str]
    strategy_name: Optional[str]
    window_index: Optional[int]
    train_start: Optional[str]
    train_end: Optional[str]
    train_count: Optional[int]
    validation_start: Optional[str]
    validation_end: Optional[str]
    validation_count: Optional[int]
    decision_count: int
    decision_records: list[DecisionRecord]
    error: Optional[str]


class WalkForwardDecisionResult(TypedDict):
    """walkforward_decision.run_walkforward_decision_validation() の戻り値。"""
    walkforward_decision_schema_version: str
    run_id: Optional[str]
    code: Optional[str]
    strategy_name: Optional[str]
    period: Optional[str]
    total_windows: int
    windows: list[DecisionWindowRecord]


# ════════════════════════════════════════════════
# walkforward_evaluation.py
# （decision_report.py / decision_validation.py が返す構造も含む）
# ════════════════════════════════════════════════
class ReportInfo(TypedDict):
    """decision_report.build_decision_report() の "report_info" キー。"""
    strategy_name: Optional[str]
    code: Optional[str]
    period_start: Optional[str]
    period_end: Optional[str]
    total_days: int
    total_decisions: int


class DecisionReportEntry(TypedDict):
    """decision_report.build_decision_report() のDecisionラベル1件分の集計結果。"""
    count: int
    ratio_pct: Optional[float]
    avg_return: Optional[float]
    win_rate: Optional[float]
    max_dd: Optional[float]
    down10_rate: Optional[float]
    avg_score: Optional[float]
    avg_confidence: Optional[float]
    avg_risk: Optional[float]
    confidence_sample_size: int


#: decision_report.build_decision_report() の戻り値。
#: "report_info"キー（ReportInfo）とDecisionラベルごとのキー
#: （DecisionReportEntry）を持つが、ラベルの種類は可変なため
#: TypedDict化せずMapping[str, Any]のエイリアスとする。
DecisionReportResult = Mapping[str, Any]


class DecisionValidationEntry(TypedDict):
    """decision_validation.build_decision_validation_summary() のDecisionラベル1件分の集計結果。"""
    count: int
    avg_return: Optional[float]
    avg_return_1w: Optional[float]
    avg_return_3m: Optional[float]
    win_rate: Optional[float]
    max_dd: Optional[float]
    down10_rate: Optional[float]


#: decision_validation.build_decision_validation_summary() の戻り値。
#: Decisionラベルをキーとするため（種類が可変）、TypedDict化せず
#: Mapping[str, Any]のエイリアスとする（値の形はDecisionValidationEntry）。
DecisionValidationResult = Mapping[str, Any]


class EvaluationWindowRecord(TypedDict):
    """walkforward_evaluation.run_walkforward_evaluation() が生成する1Window分の構造。"""
    validation_period_id: Optional[str]
    run_id: Optional[str]
    report_hash: Optional[str]
    code: Optional[str]
    strategy_name: Optional[str]
    window_index: Optional[int]
    train_start: Optional[str]
    train_end: Optional[str]
    train_count: Optional[int]
    validation_start: Optional[str]
    validation_end: Optional[str]
    validation_count: Optional[int]
    decision_validation_result: Optional[DecisionValidationResult]
    decision_report_result: Optional[DecisionReportResult]
    error: Optional[str]


class WalkForwardEvaluationResult(TypedDict):
    """walkforward_evaluation.run_walkforward_evaluation() の戻り値。"""
    walkforward_evaluation_schema_version: str
    run_id: Optional[str]
    code: Optional[str]
    strategy_name: Optional[str]
    period: Optional[str]
    total_windows: int
    windows: list[EvaluationWindowRecord]


# ════════════════════════════════════════════════
# walkforward_pipeline.py
# ════════════════════════════════════════════════
class _WalkForwardPipelineResultRequired(TypedDict):
    pipeline_version: str
    run_id: str
    strategy: str
    code: str
    period: str
    generated_at: str
    # 正常時は WalkForwardEvaluationResult 相当、途中失敗時は
    # {"windows": [...]} という縮退構造になるため、単一のTypedDictでは
    # 表現しきれずMapping[str, Any]としている。
    windows: Mapping[str, Any]
    errors: list[StageErrorEntry]
    warnings: list[StageErrorEntry]


class WalkForwardPipelineResult(_WalkForwardPipelineResultRequired, total=False):
    """walkforward_pipeline.run_walkforward_pipeline() の戻り値。"""
    extensions: Mapping[str, Any]


# ════════════════════════════════════════════════
# walkforward_benchmark.py（benchmark.py が返す構造も含む）
# ════════════════════════════════════════════════
class MetricJudgement(TypedDict):
    """benchmark.build_benchmark() の "metrics" 配下、1指標分の判定結果。"""
    before: Optional[float]
    after: Optional[float]
    diff: Optional[float]
    diff_pct: Optional[float]
    status: str


class BenchmarkResult(TypedDict):
    """benchmark.build_benchmark() の戻り値。"""
    overall: str
    improvement_score: float
    metrics: dict[str, MetricJudgement]
    summary: str


class ComparisonMetadata(TypedDict):
    """walkforward_benchmark.py が組み立てる、1つのWindow遷移の比較メタ情報。"""
    before_window: Optional[int]
    after_window: Optional[int]
    validation_period_id: Optional[str]
    run_id: Optional[str]
    strategy: Optional[str]
    code: Optional[str]


class TransitionRecord(TypedDict):
    """walkforward_benchmark.py の "transitions" 配列の1要素。"""
    comparison_metadata: ComparisonMetadata
    benchmark_result: Optional[BenchmarkResult]
    error: Optional[str]


class ImprovementRankEntry(TypedDict):
    """walkforward_benchmark.py の "improvement_rank" 配列の1要素。"""
    rank: int
    improvement_score: float
    overall: Optional[str]
    comparison_metadata: ComparisonMetadata


class BenchmarkSummary(TypedDict):
    """walkforward_benchmark.py の "benchmark_summary" キー。"""
    improved_count: int
    declined_count: int
    unchanged_count: int
    comparison_success_count: int
    comparison_failure_count: int
    total_transitions: int


class BenchmarkWindowRecord(EvaluationWindowRecord):
    """walkforward_benchmark.py が EvaluationWindowRecord に
    benchmark_result を1つ追加したコピー。
    """
    benchmark_result: Optional[BenchmarkResult]


class _WalkForwardBenchmarkResultRequired(TypedDict):
    benchmark_schema_version: str
    run_id: Optional[str]
    code: Optional[str]
    strategy_name: Optional[str]
    period: Optional[str]
    total_windows: int
    total_transitions: int
    windows: list[BenchmarkWindowRecord]
    transitions: list[TransitionRecord]
    improvement_rank: list[ImprovementRankEntry]
    best_transition: Optional[ImprovementRankEntry]
    worst_transition: Optional[ImprovementRankEntry]
    benchmark_summary: BenchmarkSummary


class WalkForwardBenchmarkResult(_WalkForwardBenchmarkResultRequired, total=False):
    """walkforward_benchmark.run_walkforward_benchmark() の戻り値。"""
    context: Mapping[str, Any]
    extensions: Mapping[str, Any]


# ════════════════════════════════════════════════
# walkforward_summary.py
# ════════════════════════════════════════════════
class WindowMetric(TypedDict):
    """walkforward_summary.py がWindow単位で集約した1レコード。"""
    validation_period_id: Optional[str]
    run_id: Optional[str]
    code: Optional[str]
    strategy_name: Optional[str]
    window_index: Optional[int]
    train_start: Optional[str]
    train_end: Optional[str]
    train_count: Optional[int]
    validation_start: Optional[str]
    validation_end: Optional[str]
    validation_count: Optional[int]
    success: bool
    decision_count: Optional[int]
    avg_return: Optional[float]
    win_rate: Optional[float]
    max_dd: Optional[float]
    down10_rate: Optional[float]
    avg_score: Optional[float]
    avg_confidence: Optional[float]
    avg_risk: Optional[float]


class MetricStatEntry(TypedDict):
    """build_metric_statistics() が指標ごとに返す平均・中央値・標準偏差。"""
    mean: Optional[float]
    median: Optional[float]
    stdev: Optional[float]


class StabilityMetricEntry(TypedDict):
    """build_stability_score() が指標ごとに返す標準偏差とスコア。"""
    stdev: Optional[float]
    score: Optional[float]


class StabilityScore(TypedDict):
    """build_stability_score() の戻り値。"""
    score: Optional[float]
    per_metric: dict[str, StabilityMetricEntry]


class HealthCheck(TypedDict):
    """build_health_check() の戻り値。"""
    level: str
    score: Optional[float]
    reason: str


class ImprovementTrend(TypedDict):
    """build_improvement_trend() の戻り値。"""
    trend: str
    reason: str
    first_score: Optional[float]
    last_score: Optional[float]


class BenchmarkImprovementRate(TypedDict):
    """build_benchmark_improvement_rate() の戻り値。"""
    rate_pct: Optional[float]
    sample_size: int
    reason: Optional[str]


class BestWorstEntry(TypedDict):
    """build_best_worst_window() が返す best/worst の1件分。"""
    run_id: Optional[str]
    validation_period_id: Optional[str]
    strategy_name: Optional[str]
    code: Optional[str]
    window_index: Optional[int]
    metric: str
    value: float


class SummaryMetadata(TypedDict):
    """build_summary_metadata() の戻り値（+ validation_success_rate_pctを追加したもの）。"""
    generated_at: str
    run_id: Optional[str]
    schema_version: str
    window_count: int
    successful_windows: int
    failed_windows: int
    strategy: Optional[str]
    code: Optional[str]
    period: Optional[str]
    validation_success_rate_pct: Optional[float]


class _WalkForwardSummaryResultRequired(TypedDict):
    summary_schema_version: str
    metadata: SummaryMetadata
    health_check: HealthCheck
    stability_score: StabilityScore
    improvement_trend: ImprovementTrend
    benchmark_improvement_rate: BenchmarkImprovementRate
    metric_statistics: dict[str, MetricStatEntry]
    decision_distribution: dict[str, int]
    best_window: Optional[BestWorstEntry]
    worst_window: Optional[BestWorstEntry]
    window_metrics: list[WindowMetric]


class WalkForwardSummaryResult(_WalkForwardSummaryResultRequired, total=False):
    """walkforward_summary.build_walkforward_summary() の戻り値。"""
    context: Mapping[str, Any]
    extensions: Mapping[str, Any]


# ════════════════════════════════════════════════
# walkforward_context.py
# ════════════════════════════════════════════════
class ExecutionMetadata(TypedDict):
    """walkforward_context.py の "execution_metadata" キー。"""
    run_id: Optional[str]
    created_at: str
    strategy: Optional[str]
    code: Optional[str]
    period: Optional[str]
    window_count: Optional[int]
    pipeline_version: Optional[str]
    summary_version: Optional[str]
    benchmark_version: Optional[str]


class ModuleVersions(TypedDict):
    """walkforward_context.py の "module_versions" キー。"""
    pipeline: Optional[str]
    benchmark: Optional[str]
    summary: Optional[str]
    context: str


class DataAvailability(TypedDict):
    """walkforward_context.py の "data_availability" キー。"""
    pipeline: bool
    benchmark: bool
    summary: bool
    windows: bool
    health_check: bool
    improvement_trend: bool


class ContextSummary(TypedDict):
    """walkforward_context.py の "context_summary" キー。"""
    available_modules: list[str]
    window_count: Optional[int]
    benchmark_transition_count: Optional[int]
    has_summary: bool
    has_health_check: bool
    has_improvement_trend: bool


class Navigation(TypedDict):
    """walkforward_context.py の "navigation" キー。"""
    sections: list[str]


class _WalkForwardContextResultRequired(TypedDict):
    context_schema_version: str
    execution_metadata: ExecutionMetadata
    module_versions: ModuleVersions
    data_availability: DataAvailability
    context_summary: ContextSummary
    navigation: Navigation
    # 入力（WalkForwardPipelineResult/WalkForwardBenchmarkResult/
    # WalkForwardSummaryResult）をそのまま保持するキー。呼び出し側の
    # 実引数型と厳密に一致させると三者三様のUnionが必要になり可読性が
    # 落ちるため、ここではMapping[str, Any]としている
    # （中身は加工されず入力値そのままである点はモジュール側docstringで保証）。
    pipeline: Mapping[str, Any]
    benchmark: Mapping[str, Any]
    summary: Mapping[str, Any]


class WalkForwardContextResult(_WalkForwardContextResultRequired, total=False):
    """walkforward_context.build_walkforward_context() の戻り値。"""
    context: Mapping[str, Any]
    extensions: Mapping[str, Any]
    ai_context: Mapping[str, Any]
    fundamental_context: Mapping[str, Any]
    dividend_context: Mapping[str, Any]
    market_context: Mapping[str, Any]


# ════════════════════════════════════════════════
# walkforward_runner.py
# ════════════════════════════════════════════════
# 【重要】この節は backtest/walkforward_runner.py の実ソースを直接確認した
# うえで、その戻り値構造（_build_result()）と完全に一致させて定義している。
# 特に以下2点は実装との整合性上、重要な注意点である：
#   1. run_walkforward_runner() の戻り値に "dry_run" キーは存在しない。
#      Dry Runの実施有無は stage_status（benchmark/summary/contextが
#      "SKIPPED"かどうか）から判断する。
#   2. 戻り値の "context" キーは Stage4（build_walkforward_context()）の
#      実行結果である。Runnerの引数として渡された context（将来拡張用の
#      予約dict）が指定された場合は、別キー "context_input" へ格納される
#      （"context"と"context_input"は意味が異なる）。

RunnerStatus = Literal["SUCCESS", "PARTIAL_SUCCESS", "FAILED"]

RunnerStageName = Literal["pipeline", "benchmark", "summary", "context"]

RunnerStageStatusValue = Literal["SUCCESS", "FAILED", "SKIPPED"]

#: run_walkforward_runner() の "stage_status" キー。
#: 実装上はdict[str, str]だが、キー・値の取りうる範囲を
#: RunnerStageName / RunnerStageStatusValue として明示するための別名。
RunnerStageStatusMap = Mapping[RunnerStageName, RunnerStageStatusValue]

#: run_walkforward_runner() の "stage_elapsed" キー（各Stageの所要秒数）。
RunnerStageElapsedMap = Mapping[RunnerStageName, float]


class _WalkForwardRunnerResultRequired(TypedDict):
    runner_schema_version: str
    run_id: str
    started_at: str
    finished_at: str
    elapsed_seconds: float
    status: RunnerStatus
    pipeline: Optional[WalkForwardPipelineResult]
    benchmark: Optional[WalkForwardBenchmarkResult]
    summary: Optional[WalkForwardSummaryResult]
    # Stage4（build_walkforward_context()）の実行結果。
    # Runner引数の"context"（予約入力）とは異なる（後述のcontext_input参照）。
    context: Optional[WalkForwardContextResult]
    stage_status: RunnerStageStatusMap
    stage_elapsed: RunnerStageElapsedMap
    errors: list[StageErrorEntry]
    warnings: list[StageErrorEntry]


class WalkForwardRunnerResult(_WalkForwardRunnerResultRequired, total=False):
    """walkforward_runner.run_walkforward_runner() の戻り値。

    以下のキーは、対応する予約引数が呼び出し時に指定された場合のみ
    含まれる（Noneの場合はキー自体が戻り値に存在しない）。
    """
    #: Runner引数の"context"（将来拡張用の予約dict）がそのまま格納される。
    #: 戻り値の"context"キー（Stage4結果）とは意味が異なる点に注意。
    context_input: Mapping[str, Any]
    extensions: Mapping[str, Any]
    ai_context: Mapping[str, Any]
    fundamental_context: Mapping[str, Any]
    dividend_context: Mapping[str, Any]
    market_context: Mapping[str, Any]
