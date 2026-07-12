"""backtest/walkforward.py (v9研究開発ブランチ Walk Forward Validation基盤)
====================================================================
「未来データを見て最適化してしまっていないか」を確認するための、
時系列検証（Walk Forward Validation）基盤。

責務:
    既存のバックテスト（backtest.data_loader.fetch_stock_data() +
    backtest.backtest_runner.run_backtest()）を1回実行した結果
    （res_df）を、期間で分割してValidation区間だけを取り出し、
    JSON互換のdict/listへ整理するだけ。新しい売買判定・新しい統計・
    新しいDecision・新しいConfidenceは一切実装しない。
    Evaluation Lab・Decision Report・Historyが担う分析・集計処理とは
    責務を重複させず、それらへ渡すための「期間ごとに整理された素材」を
    提供することに限定する。

    戻り値はJSON完全互換のdict/listのみで構成される
    （pandas.DataFrame・numpy型・pandas.Timestampは含まない）。
    内部処理では既存モジュールが返すpandas.DataFrameを扱うが、
    それは既存バックテスト基盤の出力形式を再利用するために
    避けられないためであり、外部への戻り値・公開インターフェースは
    JSON互換dict/listに統一している。Streamlitへの依存は持たない。

【WindowSplitterについて】
    将来のRolling Window・Expanding Windowへの拡張を見据え、
    「日付のリストを受け取り、(train_dates, validation_dates)の
    組を複数生成する」という責務を WindowSplitter という抽象基底
    クラスに切り出している。今回実装するのは固定期間分割
    （FixedWindowSplitter）のみだが、将来
        - RollingWindowSplitter（一定幅の窓をスライドさせる）
        - ExpandingWindowSplitter（trainの開始点を固定し終了点だけ伸ばす）
    を追加する場合も、WindowSplitterを継承した新しいクラスを追加する
    だけでよく、run_walkforward_validation() 本体は変更不要な設計に
    している。

Public API:
    WindowSplit, WindowSplitter, FixedWindowSplitter,
    run_walkforward_validation
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

import pandas as pd

from backtest.data_loader import fetch_stock_data
from backtest.backtest_runner import run_backtest

__all__ = [
    "WALKFORWARD_SCHEMA_VERSION",
    "WindowSplit",
    "WindowSplitter",
    "FixedWindowSplitter",
    "run_walkforward_validation",
]

#: このモジュールの戻り値スキーマのバージョン。消費側が互換性を判断する。
WALKFORWARD_SCHEMA_VERSION = "1.0"

#: run_walkforward_validation() に渡すスコアリング関数の型。
StrategyFn = Callable[[pd.DataFrame, Mapping[str, Any], str], Mapping[str, Any]]


@dataclass(frozen=True)
class WindowSplit:
    """1つのtrain/validation区間の境界情報。

    Attributes:
        window_index: このウィンドウの通し番号（0始まり）。
        train_dates: trainに属する日付のリスト（昇順）。
        validation_dates: validationに属する日付のリスト（昇順）。
    """

    window_index: int
    train_dates: list[pd.Timestamp]
    validation_dates: list[pd.Timestamp]


class WindowSplitter(ABC):
    """日付のリストをtrain/validationの複数ウィンドウへ分割する責務の抽象基底クラス。

    将来のRolling Window・Expanding Window等はこのクラスを継承した
    サブクラスとして追加する想定。generate_windows() のシグネチャを
    守れば run_walkforward_validation() 側は変更不要。
    """

    @abstractmethod
    def generate_windows(self, dates: Sequence[pd.Timestamp]) -> list[WindowSplit]:
        """日付のリストから、train/validationのウィンドウ群を生成する。

        Args:
            dates: 対象期間の全判定日（昇順ソート済みであることを前提とする）。

        Returns:
            WindowSplitのリスト（window_index昇順）。
        """
        raise NotImplementedError


class FixedWindowSplitter(WindowSplitter):
    """対象期間を固定サイズの連続ブロックへ分割し、各ブロック内を
    train_ratioでtrain/validationへ分ける、最も単純な分割方式。

    Rolling Window・Expanding Windowとは異なり、各ブロックは重複せず
    対象期間全体を過不足なくカバーする。
    """

    def __init__(self, n_splits: int = 4, train_ratio: float = 0.7,
                 min_validation_size: int = 5) -> None:
        """
        Args:
            n_splits: 対象期間を分割するブロック数。
            train_ratio: 各ブロック内でtrain区間に割り当てる比率（0〜1）。
            min_validation_size: validation区間がこの日数未満のブロックはスキップする。

        Raises:
            ValueError: n_splitsが1未満、またはtrain_ratioが(0, 1)の範囲外の場合。
        """
        if n_splits < 1:
            raise ValueError("n_splits は1以上である必要があります。")
        if not (0.0 < train_ratio < 1.0):
            raise ValueError("train_ratio は0より大きく1未満である必要があります。")
        self.n_splits = n_splits
        self.train_ratio = train_ratio
        self.min_validation_size = min_validation_size

    def generate_windows(self, dates: Sequence[pd.Timestamp]) -> list[WindowSplit]:
        """対象期間をn_splits個の連続ブロックに分割し、各ブロックをtrain/validationへ分ける。

        Args:
            dates: 対象期間の全判定日（昇順ソート済み）。

        Returns:
            WindowSplitのリスト。validation区間がmin_validation_size未満に
            なるブロックは除外されるため、要求したn_splits件より少なく
            なる場合がある。
        """
        n = len(dates)
        if n == 0:
            return []

        block_size = n // self.n_splits
        if block_size < 2:
            return []

        windows: list[WindowSplit] = []
        for i in range(self.n_splits):
            block_start = i * block_size
            block_end = n if i == self.n_splits - 1 else (i + 1) * block_size
            block = list(dates[block_start:block_end])
            if len(block) < 2:
                continue

            split_idx = max(1, int(math.floor(len(block) * self.train_ratio)))
            train_dates = block[:split_idx]
            validation_dates = block[split_idx:]

            if len(validation_dates) < self.min_validation_size or not train_dates:
                continue

            windows.append(WindowSplit(
                window_index=len(windows),
                train_dates=train_dates,
                validation_dates=validation_dates,
            ))

        return windows


def _to_json_safe(value: Any) -> Any:
    """pandas/numpyの値をJSON互換のプリミティブ型へ変換する（日時はISO8601、NaNはNone）。"""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(v) for v in value]
    try:
        if isinstance(value, float) and math.isnan(value):
            return None
    except TypeError:
        pass
    if isinstance(value, (int, float, str, bool)):
        return value
    try:
        f = float(value)
        if math.isnan(f):
            return None
        if f.is_integer() and not isinstance(value, float):
            return int(f)
        return f
    except (TypeError, ValueError):
        return str(value)


def _row_to_record(row: pd.Series) -> dict[str, Any]:
    """DataFrameの1行をJSON互換dictへ変換する。"""
    return {col: _to_json_safe(row[col]) for col in row.index}


def _describe_splitter(splitter: WindowSplitter) -> dict[str, Any]:
    """splitterの設定内容をJSON互換dictとして記述する（デバッグ・再現性確認用）。"""
    info: dict[str, Any] = {"type": type(splitter).__name__}
    if isinstance(splitter, FixedWindowSplitter):
        info["n_splits"] = splitter.n_splits
        info["train_ratio"] = splitter.train_ratio
        info["min_validation_size"] = splitter.min_validation_size
    return info


def run_walkforward_validation(
    code: str,
    strategy_fn: StrategyFn,
    strategy_name: str,
    period: str = "1y",
    splitter: WindowSplitter | None = None,
    date_col: str = "date",
) -> dict[str, Any]:
    """既存バックテストを1回実行し、その結果を期間で分割してValidation
    区間だけを収集する、Walk Forward Validationの実行エントリポイント。

    data_loader.fetch_stock_data() と backtest_runner.run_backtest()
    （いずれも無変更）をそのまま呼び出すのみで、新しい売買判定・
    テクニカル指標・スコア計算は一切行わない。res_dfはbacktest_runner
    の設計上、各判定日についてその日までのデータのみを用いて計算
    されている（Look Ahead Biasの無いウォークフォワード形式）ため、
    本関数はその結果を「期間ブロックに区切って整理する」処理のみを
    担う。

    Args:
        code: 対象銘柄コード（例: "7203"）。
        strategy_fn: backtest_runner.run_backtest() にそのまま渡す
            スコアリング関数（例: strategy_v9.compute_score_at_v9）。
        strategy_name: レポート上の戦略識別子（例: "v9"）。
        period: data_loader.fetch_stock_data() にそのまま渡す
            yfinance期間文字列（例: "1y"）。
        splitter: 期間分割方式。省略時は FixedWindowSplitter() の
            デフォルト設定を用いる。
        date_col: res_df内の判定日列名。

    Returns:
        walkforward_schema_version・code・strategy_name・period・
        splitter・total_days・windows（各windowはvalidation_period_id・
        train/validation境界情報・validation_recordsを持つJSON互換dict）
        を持つdict。データ取得失敗・res_dfが空・分割不能の場合、
        "windows" は空リストになる（例外は送出しない）。
    """
    if splitter is None:
        splitter = FixedWindowSplitter()

    result: dict[str, Any] = {
        "walkforward_schema_version": WALKFORWARD_SCHEMA_VERSION,
        "code": code,
        "strategy_name": strategy_name,
        "period": period,
        "splitter": _describe_splitter(splitter),
        "total_days": 0,
        "windows": [],
    }

    df, info = fetch_stock_data(code, period=period)
    if df is None or df.empty:
        return result

    res_df = run_backtest(df, info, code, strategy_fn)
    if res_df.empty or date_col not in res_df.columns:
        return result

    res_df = res_df.sort_values(date_col).reset_index(drop=True)
    dates = list(res_df[date_col])
    result["total_days"] = len(dates)

    window_splits = splitter.generate_windows(dates)
    if not window_splits:
        return result

    windows_out: list[dict[str, Any]] = []
    for split in window_splits:
        validation_rows = res_df[res_df[date_col].isin(split.validation_dates)]
        if validation_rows.empty:
            continue

        windows_out.append({
            "validation_period_id": f"{code}_{strategy_name}_w{split.window_index}",
            "code": code,
            "strategy_name": strategy_name,
            "window_index": split.window_index,
            "train_start": _to_json_safe(split.train_dates[0]),
            "train_end": _to_json_safe(split.train_dates[-1]),
            "train_count": len(split.train_dates),
            "validation_start": _to_json_safe(split.validation_dates[0]),
            "validation_end": _to_json_safe(split.validation_dates[-1]),
            "validation_count": len(split.validation_dates),
            "validation_records": [
                _row_to_record(row) for _, row in validation_rows.iterrows()
            ],
        })

    result["windows"] = windows_out
    return result
