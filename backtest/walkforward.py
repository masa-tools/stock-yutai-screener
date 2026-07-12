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
    責務を重複させず、それらへ渡すための「期間ごとに整理された素材
    （res_dfの部分集合をJSON化したもの）」を提供することに限定する。

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
    だけでよく、run_walkforward_validation() 本体（バックテスト実行・
    JSON変換のロジック）は変更不要な設計にしている。
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Sequence

import pandas as pd

from backtest.data_loader import fetch_stock_data
from backtest.backtest_runner import run_backtest


#: このモジュールの戻り値スキーマのバージョン。
#: 戻り値の構造（トップレベルキー構成）を変更する場合はこの値を更新し、
#: 消費側（validation_dashboard.py・本番画面・CSV/SQLite保存等）が
#: 互換性を判断できるようにする。
WALKFORWARD_SCHEMA_VERSION = "1.0"


# ════════════════════════════════════════════════
# WindowSplitter: 期間分割の責務のみを切り出した抽象基底クラス
# ════════════════════════════════════════════════
@dataclass(frozen=True)
class WindowSplit:
    """1つのtrain/validation区間の境界情報。

    Attributes:
        window_index: このウィンドウの通し番号（0始まり）。
        train_dates: このウィンドウのtrain区間に属する日付のリスト
            （昇順、pandas.Timestampのリスト）。
        validation_dates: このウィンドウのvalidation区間に属する
            日付のリスト（昇順、pandas.Timestampのリスト）。
    """

    window_index: int
    train_dates: list[pd.Timestamp]
    validation_dates: list[pd.Timestamp]


class WindowSplitter(ABC):
    """日付のリストをtrain/validationの複数ウィンドウへ分割する責務の抽象基底クラス。

    将来のRolling Window・Expanding Window等はこのクラスを継承した
    サブクラスとして追加する想定。generate_windows() のシグネチャ
    （日付のリストを受け取りWindowSplitのリストを返す）を守れば、
    run_walkforward_validation() 側は変更不要で新しい分割方式を
    利用できる。
    """

    @abstractmethod
    def generate_windows(self, dates: Sequence[pd.Timestamp]) -> list[WindowSplit]:
        """日付のリストから、train/validationのウィンドウ群を生成する。

        Args:
            dates: 対象期間の全判定日（昇順にソート済みであることを前提とする）。

        Returns:
            WindowSplitのリスト（window_index昇順）。
        """
        raise NotImplementedError


class FixedWindowSplitter(WindowSplitter):
    """対象期間を固定サイズの連続したブロックへ分割し、各ブロック内を
    train_ratioでtrain/validationへ分ける、最も単純な分割方式。

    Rolling Window（窓をスライドさせる）・Expanding Window
    （trainの開始点を固定して終了点だけ伸ばす）とは異なり、各ブロックは
    重複せず対象期間全体を過不足なくカバーする。今回のPM要件
    「今回はシンプルな固定期間分割のみ実装」に対応する実装。
    """

    def __init__(self, n_splits: int = 4, train_ratio: float = 0.7,
                 min_validation_size: int = 5) -> None:
        """
        Args:
            n_splits: 対象期間を分割するブロック数。
            train_ratio: 各ブロック内でtrain区間に割り当てる比率
                （0〜1）。残りがvalidation区間になる。
            min_validation_size: validation区間がこの日数未満になる
                ブロックはスキップする（意味のある検証にならないため）。
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
            # 1ブロックあたりの日数が少なすぎて train/validation に
            # 分けられない場合は、分割を試みずに空リストを返す。
            return []

        windows: list[WindowSplit] = []
        for i in range(self.n_splits):
            block_start = i * block_size
            # 最後のブロックは割り切れなかった余りも含めて末尾まで取る。
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


# ════════════════════════════════════════════════
# JSON変換ヘルパー
# ════════════════════════════════════════════════
def _to_json_safe(value: Any) -> Any:
    """pandas/numpyの値をJSON互換のプリミティブ型へ変換する。

    Args:
        value: 変換対象の値（pandas.Timestamp・numpy数値型・dict・
            None・NaN等を想定）。

    Returns:
        str（日時はISO8601） / float / int / bool / None / dict / list
        のいずれか。NaNはNoneに変換する。
    """
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
    # numpy.float64 / numpy.int64 等はfloat/intへのキャストで
    # JSON互換のPythonネイティブ型になる。
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
    """res_dfの1行（pandas.Series）を、JSON互換dictへ変換する。

    Args:
        row: res_df.iloc[i] 等で取得した1行。

    Returns:
        列名をキーとし、値をすべてJSON互換型へ変換したdict。
    """
    return {col: _to_json_safe(row[col]) for col in row.index}


# ════════════════════════════════════════════════
# 入口となるAPI
# ════════════════════════════════════════════════
def run_walkforward_validation(
    code: str,
    strategy_fn: Callable[[pd.DataFrame, dict, str], dict],
    strategy_name: str,
    period: str = "1y",
    splitter: WindowSplitter | None = None,
    date_col: str = "date",
) -> dict[str, Any]:
    """既存バックテストを1回実行し、その結果を期間で分割してValidation
    区間だけを収集する、Walk Forward Validationの実行エントリポイント。

    data_loader.fetch_stock_data() と backtest_runner.run_backtest()
    （いずれも無変更）をそのまま呼び出すのみで、新しい売買判定・
    テクニカル指標・スコア計算は一切行わない。res_dfはすでに
    backtest_runner.run_backtest() の設計上、各判定日についてその日
    までのデータのみを用いて計算されている（Look Ahead Biasの無い
    ウォークフォワード形式）ため、本関数はその結果を「期間ブロックに
    区切って整理する」処理のみを担う。

    Args:
        code: 対象銘柄コード（例: "7203"）。将来複数銘柄をまとめて
            検証できるよう、常に文字列として保持する。
        strategy_fn: backtest_runner.run_backtest() にそのまま渡す
            スコアリング関数（例: strategy_v9.compute_score_at_v9）。
            本関数はこの関数の中身には一切関与しない。
        strategy_name: レポート上の戦略識別子（例: "v9"）。
            strategy_fn自体から名前を推定することはせず、呼び出し側が
            明示的に渡す。
        period: data_loader.fetch_stock_data() にそのまま渡す
            yfinance期間文字列（例: "1y"）。
        splitter: 期間分割方式。省略時は FixedWindowSplitter() の
            デフォルト設定（4分割・train比率0.7）を用いる。
        date_col: res_df内の判定日列名。

    Returns:
        以下の構造を持つJSON互換dict::

            {
                "walkforward_schema_version": "1.0",
                "code": "7203",
                "strategy_name": "v9",
                "period": "1y",
                "splitter": {"type": "FixedWindowSplitter", "n_splits": 4, "train_ratio": 0.7},
                "total_days": 判定対象営業日数の総数,
                "windows": [
                    {
                        "validation_period_id": "7203_v9_w0",
                        "code": "7203",
                        "strategy_name": "v9",
                        "window_index": 0,
                        "train_start": "2025-01-06", "train_end": "2025-03-10",
                        "train_count": 45,
                        "validation_start": "2025-03-11", "validation_end": "2025-04-01",
                        "validation_count": 15,
                        "validation_records": [
                            {"date": "2025-03-11", "total": 78.0, ...},
                            ...
                        ],
                    },
                    ...
                ],
            }

        データ取得失敗・res_dfが空・分割不能（対象日数が少なすぎる等）の
        場合、"windows" は空リストになる（例外は送出しない）。
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

    date_to_index = {d: i for i, d in enumerate(dates)}

    windows_out: list[dict[str, Any]] = []
    for split in window_splits:
        validation_rows = res_df[res_df[date_col].isin(split.validation_dates)]
        if validation_rows.empty:
            continue

        train_start = split.train_dates[0]
        train_end = split.train_dates[-1]
        validation_start = split.validation_dates[0]
        validation_end = split.validation_dates[-1]

        windows_out.append({
            "validation_period_id": f"{code}_{strategy_name}_w{split.window_index}",
            "code": code,
            "strategy_name": strategy_name,
            "window_index": split.window_index,
            "train_start": _to_json_safe(train_start),
            "train_end": _to_json_safe(train_end),
            "train_count": len(split.train_dates),
            "validation_start": _to_json_safe(validation_start),
            "validation_end": _to_json_safe(validation_end),
            "validation_count": len(split.validation_dates),
            "validation_records": [
                _row_to_record(row) for _, row in validation_rows.iterrows()
            ],
        })

    result["windows"] = windows_out
    return result


def _describe_splitter(splitter: WindowSplitter) -> dict[str, Any]:
    """splitterの設定内容をJSON互換dictとして記述する（デバッグ・再現性確認用）。

    Args:
        splitter: run_walkforward_validation()に渡されたWindowSplitter。

    Returns:
        {"type": クラス名, ...splitter固有の設定値} を持つdict。
        FixedWindowSplitter以外の未知のsplitterでも、typeキーのみは
        必ず含まれる。
    """
    info: dict[str, Any] = {"type": type(splitter).__name__}
    if isinstance(splitter, FixedWindowSplitter):
        info["n_splits"] = splitter.n_splits
        info["train_ratio"] = splitter.train_ratio
        info["min_validation_size"] = splitter.min_validation_size
    return info
