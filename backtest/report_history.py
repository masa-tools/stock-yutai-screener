"""backtest/report_history.py (v9研究開発ブランチ Report History)
====================================================================
Decision Report（``backtest.decision_report.build_decision_report()``の
戻り値）を、履歴として保存・読込・比較できるデータ構造へ変換するだけの
責務を持つモジュール。

責務:
    Decision Reportの内容を一切加工せず、run_id・timestamp・
    config_hash等のメタ情報を付与した履歴エントリ（dict）へ変換する
    ``build_history_entry()``と、2つの履歴エントリの差分のみを機械的に
    算出する``compare_history_entry()``を提供する。新しい分析・売買
    判定は一切行わない。

    標準ライブラリのみに依存し、pandas・Streamlit等のUI/データ処理
    ライブラリはimportしない。戻り値はすべてJSON完全互換の型
    （str/int/float/bool/None/list/dict）のみで構成される。
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any


#: compare_history_entry() が比較対象とするトップレベルフィールド。
#: 将来フィールドが増えた場合はこのタプルに追加するだけでよい
#: （compare_history_entry() 本体のロジック変更は不要）。
_COMPARABLE_FIELDS: tuple[str, ...] = (
    "strategy",
    "strategy_version",
    "config_hash",
    "code",
    "period",
)


def _compute_config_hash(config_snapshot: dict[str, Any]) -> str:
    """設定スナップショットからSHA256ハッシュ値を計算する。

    キー順序に依存しない安定したハッシュにするため、``sort_keys=True``
    でJSON文字列化してからハッシュ化する。将来 ``v9_config.py`` の
    設定値が変わった場合、このハッシュ値の変化によって検知できる。

    Args:
        config_snapshot: ハッシュ化対象の設定値（JSON化可能なdict）。

    Returns:
        設定内容から算出したSHA256ハッシュの16進数文字列。
    """
    canonical = json.dumps(config_snapshot, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _fallback_from_report_info(report: dict[str, Any], key: str) -> Any:
    """report["report_info"] から指定キーの値をフォールバック取得する。

    Args:
        report: build_decision_report() の戻り値。
        key: report_info内で探すキー名（"strategy_name"や"code"等）。

    Returns:
        見つかった値。report_info自体が無い、またはキーが無い場合はNone。
    """
    report_info = report.get("report_info") if isinstance(report, dict) else None
    if not isinstance(report_info, dict):
        return None
    return report_info.get(key)


def _resolve_period(
    period: str | None,
    report: dict[str, Any],
) -> str | None:
    """periodが未指定の場合、report_infoのperiod_start/period_endから組み立てる。

    Args:
        period: 呼び出し側が明示的に渡したperiod文字列。
        report: build_decision_report() の戻り値。

    Returns:
        periodが指定されていればそのまま返す。未指定の場合、
        report_infoから "start〜end" 形式の文字列を組み立てて返す。
        いずれの情報も無い場合はNone。
    """
    if period is not None:
        return period

    start = _fallback_from_report_info(report, "period_start")
    end = _fallback_from_report_info(report, "period_end")
    if start is None and end is None:
        return None
    return f"{start}〜{end}"


def build_history_entry(
    report: dict[str, Any],
    config_snapshot: dict[str, Any],
    strategy: str | None = None,
    code: str | None = None,
    period: str | None = None,
    app_version: str | None = None,
    strategy_version: str | None = None,
    created_by: str = "backtest",
    tags: list[str] | None = None,
    memo: str = "",
    run_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Decision Reportを履歴エントリ（JSON完全互換のdict）へ変換する。

    Decision Report（``report``引数）の内容は一切加工せず、そのまま
    ``"report"``キーへ格納する。``strategy``/``code``/``period``が
    明示的に渡されなかった場合のみ、``report["report_info"]``から
    フォールバック抽出する（decision_report.py自身が
    strategy_name/codeを推定する際に用いているのと同じ考え方）。

    Args:
        report: ``backtest.decision_report.build_decision_report()``の
            戻り値。加工せずそのまま保持する。
        config_snapshot: 実行時点の設定値スナップショット（例:
            ``evaluation.get_v9_config_snapshot()``の戻り値）。
            JSON化可能なdictである必要がある。config_hashの算出元となる。
        strategy: 戦略識別子（例: "v9"）。省略時はreport_infoの
            "strategy_name"から取得を試みる。
        code: 対象銘柄コード。省略時はreport_infoの"code"から
            取得を試みる。
        period: 対象期間を表す文字列。省略時はreport_infoの
            period_start/period_endから組み立てる。
        app_version: 株ラボ本体のバージョン識別子（任意）。
        strategy_version: strategy_v8.py/strategy_v9.py等のロジック
            バージョン識別子（任意）。
        created_by: このエントリを生成した主体。デフォルトは"backtest"。
        tags: 任意のタグ一覧。省略時は空リスト。
        memo: 任意のメモ文字列。省略時は空文字列。
        run_id: 実行ID。省略時はUUID4を新規生成する
            （再現性が必要なテスト等のために明示指定も可能にしている）。
        timestamp: ISO8601形式のタイムスタンプ文字列。省略時は
            呼び出し時点のUTC時刻から生成する。

    Returns:
        以下のキーを持つdict（すべてJSON完全互換の値のみ）::

            {
                "run_id": str,
                "timestamp": str (ISO8601),
                "strategy": str | None,
                "strategy_version": str | None,
                "code": str | None,
                "period": str | None,
                "config_hash": str,
                "config_snapshot": dict,
                "app_version": str | None,
                "created_by": str,
                "tags": list[str],
                "memo": str,
                "report": dict,  # 引数reportをそのまま保持（加工なし）
            }
    """
    resolved_strategy = strategy if strategy is not None else _fallback_from_report_info(report, "strategy_name")
    resolved_code = code if code is not None else _fallback_from_report_info(report, "code")
    resolved_period = _resolve_period(period, report)

    return {
        "run_id": run_id if run_id is not None else str(uuid.uuid4()),
        "timestamp": timestamp if timestamp is not None else datetime.now(timezone.utc).isoformat(),
        "strategy": resolved_strategy,
        "strategy_version": strategy_version,
        "code": resolved_code,
        "period": resolved_period,
        "config_hash": _compute_config_hash(config_snapshot),
        "config_snapshot": config_snapshot,
        "app_version": app_version,
        "created_by": created_by,
        "tags": list(tags) if tags is not None else [],
        "memo": memo,
        "report": report,
    }


def compare_history_entry(
    entry_a: dict[str, Any],
    entry_b: dict[str, Any],
    fields: tuple[str, ...] = _COMPARABLE_FIELDS,
) -> dict[str, Any]:
    """2つの履歴エントリの主要フィールドの差分を算出する。

    表示は一切行わない。差分の有無・両エントリの値のみを機械的に
    比較して返す純粋関数であり、どちらが「良い」結果かの判断は
    行わない（それはEvaluation Lab等、呼び出し側の責務とする）。

    Args:
        entry_a: 比較対象1（build_history_entry()の戻り値）。
        entry_b: 比較対象2（build_history_entry()の戻り値）。
        fields: 比較対象とするトップレベルフィールド名のタプル。
            省略時は strategy / strategy_version / config_hash /
            code / period を比較する。将来フィールドが増えた場合は
            呼び出し側でこの引数に追加のフィールド名を渡すか、
            モジュール冒頭の ``_COMPARABLE_FIELDS`` を編集することで
            対応でき、本関数自体のロジック変更は不要。

    Returns:
        以下の構造を持つdict（JSON完全互換）::

            {
                "run_id_a": str,
                "run_id_b": str,
                "fields": {
                    "strategy": {"a": ..., "b": ..., "changed": bool},
                    "strategy_version": {"a": ..., "b": ..., "changed": bool},
                    "config_hash": {"a": ..., "b": ..., "changed": bool},
                    "code": {"a": ..., "b": ..., "changed": bool},
                    "period": {"a": ..., "b": ..., "changed": bool},
                },
                "changed_fields": ["config_hash", ...],  # changed=Trueのフィールド名一覧
                "config_changed": bool,  # config_hashが異なるかどうかの要約フラグ
            }
    """
    field_diffs: dict[str, dict[str, Any]] = {}
    changed_fields: list[str] = []

    for field_name in fields:
        value_a = entry_a.get(field_name)
        value_b = entry_b.get(field_name)
        changed = value_a != value_b

        field_diffs[field_name] = {"a": value_a, "b": value_b, "changed": changed}
        if changed:
            changed_fields.append(field_name)

    return {
        "run_id_a": entry_a.get("run_id"),
        "run_id_b": entry_b.get("run_id"),
        "fields": field_diffs,
        "changed_fields": changed_fields,
        "config_changed": field_diffs.get("config_hash", {}).get("changed", False),
    }
