"""
phase9_step0b_check.py  Phase9 Step0B 一時データ確認ページ
============================================================
【本ファイルの位置付け（重要）】
  Phase9「PER Sector研究」のStep0Bとして、candidate_stocks.py・
  get_candidates() が返す279銘柄について、yfinanceからの
  sector / PER（trailingPE・forwardPE）データの取得状況・分布を
  確認するためだけの、一時的なStreamlit診断ページである。

  確認完了後は削除予定であり、恒久的な機能として組み込むことは
  想定していない。

【やらないこと（禁止事項の遵守）】
  - v8.1側の既存ファイル（app.py・strategy_v8.py等）は一切import・
    変更しない
  - strategy_v9_*.py・backtest配下・Composite関連は一切変更しない
    （strategy_v9_per_sector.py からは SECTOR_PER_RANGES 定数を
    参照するのみで、評価ロジック（compute_score等）は一切呼び出さない）
  - 新しい評価・スコアリング・戦略判定ロジックは実装しない。本ファイルが
    行う計算は、取得成功率・分布（中央値・四分位・最大最小・負値件数）
    といった「データ品質の記述統計」のみであり、投資判断ロジックには
    一切踏み込まない

【やること】
  - candidate_stocks.get_candidates() で279銘柄（重複除去後）を取得する
  - 既存の stock_data.get_stock_info() をそのまま再利用してyfinance
    info を取得する（新しい取得処理は実装しない）
  - sector・trailingPE・forwardPE・dividendYield の取得状況を集計し、
    画面へ表示するのみ

【エラー処理方針】
  1銘柄の取得失敗（例外・タイムアウト・空dict）が全体の処理を止めない
  よう、銘柄ごとにtry/exceptで保護し、失敗銘柄は一覧として画面末尾に
  表示する。
"""

import importlib
import os
import sys
import time

import pandas as pd
import streamlit as st

# ── 実行場所の違いを吸収するための最小限のパス調整 ────────────────
# candidate_stocks.py・stock_data.py は本ファイルと同じ階層（リポジトリ
# ルート）に置かれている想定。念のため本ファイル自身のディレクトリを
# sys.path へ追加し、配置場所による import 失敗を避ける。
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from candidate_stocks import get_candidates  # 既存処理をそのまま再利用
from stock_data import get_stock_info  # 既存処理をそのまま再利用（st.cache_data付き）

# strategy_v9_per_sector.py の配置場所（research/strategy/ 配下 等）が
# 環境によって異なる可能性があるため、複数の import 経路を順に試す。
# いずれも読み込み専用（SECTOR_PER_RANGES定数の参照のみ）であり、
# compute_score() 等の評価ロジックは一切呼び出さない。
_SECTOR_PER_RANGES = None
_sector_ranges_import_errors: list[str] = []
for _candidate_module in (
    "research.strategy.strategy_v9_per_sector",
    "strategy.strategy_v9_per_sector",
    "strategy_v9_per_sector",
):
    try:
        _mod = importlib.import_module(_candidate_module)
        _SECTOR_PER_RANGES = _mod.SECTOR_PER_RANGES
        break
    except ImportError as exc:
        _sector_ranges_import_errors.append(f"{_candidate_module}: {exc}")

_SS_KEY_RESULTS = "phase9_step0b_results"


def _extract_per(info: dict) -> tuple[float | None, str]:
    """info辞書からPERを抽出する（trailingPE優先、forwardPEへフォールバック）。
    strategy_v9_per_sector.py の_extract_per()と同じ優先順位のみを踏襲し、
    評価（スコアリング）は一切行わない、単なるデータ抽出処理。
    """
    for key in ("trailingPE", "forwardPE"):
        raw = info.get(key)
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value != value:  # NaN チェック（pandas非依存で行う）
            continue
        return value, key
    return None, ""


def _fetch_all(codes_with_names: list[tuple[str, str]]) -> list[dict]:
    """全銘柄についてyfinance情報を取得し、銘柄ごとの生データ辞書リストを返す。
    1銘柄の失敗が全体を止めないよう、try/exceptで保護する。
    """
    rows: list[dict] = []
    progress = st.progress(0.0, text="取得準備中...")
    total = len(codes_with_names)

    for i, (code, name) in enumerate(codes_with_names, start=1):
        row = {
            "code": code, "name": name,
            "fetch_ok": False, "error": None,
            "sector": None, "sector_supported": False,
            "per_value": None, "per_source": "",
            "dividend_yield": None,
        }
        try:
            info = get_stock_info(code)
            if not info:
                row["error"] = "空のinfoが返却されました（銘柄コード不正・データ無し等）"
            else:
                row["fetch_ok"] = True
                sector = info.get("sector")
                row["sector"] = sector if isinstance(sector, str) and sector else None
                if row["sector"] is not None and _SECTOR_PER_RANGES is not None:
                    row["sector_supported"] = row["sector"] in _SECTOR_PER_RANGES

                per_value, per_source = _extract_per(info)
                row["per_value"] = per_value
                row["per_source"] = per_source

                row["dividend_yield"] = info.get("dividendYield")
        except Exception as exc:  # noqa: BLE001 - 1銘柄の失敗で全体を止めないための防御的捕捉
            row["error"] = f"{type(exc).__name__}: {exc}"

        rows.append(row)
        progress.progress(i / total, text=f"取得中... {i}/{total}（{code} {name}）")
        time.sleep(0.2)  # yfinanceへの連続リクエストを緩和するための簡易ウェイト

    progress.empty()
    return rows


def main() -> None:
    st.set_page_config(page_title="Phase9 Step0B Data Report", page_icon="🔍", layout="wide")
    st.title("Phase9 Step0B Data Report")
    st.warning(
        "これはPhase9研究のためのデータ品質確認専用の一時ページです。"
        "確認完了後は削除予定であり、評価ロジック・スコアリングの変更は一切行っていません。"
    )

    if _SECTOR_PER_RANGES is None:
        st.error(
            "SECTOR_PER_RANGESの読み込みに失敗しました。以下のimport経路を試しましたが"
            "いずれも失敗しています。B項の対応率確認はスキップされます。\n\n"
            + "\n".join(f"- {e}" for e in _sector_ranges_import_errors)
        )

    # ── A. 母集団 ─────────────────────────────────────────
    st.header("A. 母集団")
    candidates = get_candidates()
    st.metric("get_candidates() 取得件数", len(candidates))

    st.divider()
    st.caption(
        "以下のB〜Eは、下のボタンを押すとyfinanceへ279銘柄分の実通信を行います"
        "（数分かかる場合があります）。ボタンを押すまでは実行されません。"
    )

    if st.button("yfinance取得を実行する", key="phase9_step0b_run"):
        st.session_state[_SS_KEY_RESULTS] = _fetch_all(candidates)

    results = st.session_state.get(_SS_KEY_RESULTS)
    if results is None:
        st.info("上のボタンを押すと、B〜Eの集計結果がここに表示されます。")
        return

    df = pd.DataFrame(results)

    # ── B. sector確認 ─────────────────────────────────────
    st.header("B. sector確認")
    total = len(df)
    fetch_ok = df["fetch_ok"].sum()
    fetch_fail = total - fetch_ok
    sector_ok = df["sector"].notna().sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("取得成功数", int(fetch_ok))
    col2.metric("取得失敗数", int(fetch_fail))
    col3.metric("取得率", f"{fetch_ok / total * 100:.1f}%" if total else "―")

    st.subheader("SECTOR_PER_RANGES 対応状況（sectorが取得できた銘柄のうち）")
    if _SECTOR_PER_RANGES is not None and sector_ok > 0:
        supported = df.loc[df["sector"].notna(), "sector_supported"].sum()
        unsupported = sector_ok - supported
        c1, c2, c3 = st.columns(3)
        c1.metric("対応数", int(supported))
        c2.metric("非対応数", int(unsupported))
        c3.metric("対応率", f"{supported / sector_ok * 100:.1f}%" if sector_ok else "―")
    else:
        st.info("sector取得件数が0件、またはSECTOR_PER_RANGES未読込のため対応率は算出していません。")

    st.subheader("sector別 銘柄数分布")
    if sector_ok > 0:
        sector_counts = (
            df.loc[df["sector"].notna(), "sector"]
            .value_counts()
            .rename_axis("sector")
            .reset_index(name="銘柄数")
        )
        if _SECTOR_PER_RANGES is not None:
            sector_counts["SECTOR_PER_RANGES対応"] = sector_counts["sector"].isin(_SECTOR_PER_RANGES)
        st.dataframe(sector_counts, use_container_width=True)
    else:
        st.info("sectorが取得できた銘柄がありません。")

    # ── C. PER確認 ────────────────────────────────────────
    st.header("C. PER確認")
    per_ok = df["per_value"].notna().sum()
    per_fail = total - per_ok
    c1, c2, c3 = st.columns(3)
    c1.metric("PER取得可能数", int(per_ok))
    c2.metric("欠損数", int(per_fail))
    c3.metric("取得率", f"{per_ok / total * 100:.1f}%" if total else "―")

    st.subheader("PER分布（形状確認のみ・最適化目的ではありません）")
    if per_ok > 0:
        per_series = df.loc[df["per_value"].notna(), "per_value"]
        neg_count = int((per_series < 0).sum())
        d1, d2, d3, d4, d5, d6 = st.columns(6)
        d1.metric("最小", f"{per_series.min():.1f}")
        d2.metric("25%", f"{per_series.quantile(0.25):.1f}")
        d3.metric("中央値", f"{per_series.median():.1f}")
        d4.metric("75%", f"{per_series.quantile(0.75):.1f}")
        d5.metric("最大", f"{per_series.max():.1f}")
        d6.metric("負PER件数", neg_count)
    else:
        st.info("PERが取得できた銘柄がありません。")

    # ── D. 補助確認（dividendYield） ─────────────────────────
    st.header("D. 補助確認（dividendYield）")
    st.caption("評価ルールの変更は行っていません。参考としての分布表示のみです。")
    div_ok = df["dividend_yield"].notna().sum()
    if div_ok > 0:
        div_series = df.loc[df["dividend_yield"].notna(), "dividend_yield"]
        e1, e2, e3 = st.columns(3)
        e1.metric("取得可能数", int(div_ok))
        e2.metric("中央値（生値）", f"{div_series.median():.4f}")
        e3.metric("最大（生値）", f"{div_series.max():.4f}")
        st.caption(
            "yfinanceのdividendYieldは0.03（小数）形式と3.0（%）形式が混在することが"
            "既存コード（stock_data.fmt_dividend_pct）で確認されています。本ページでは"
            "正規化を行わず生値のまま表示しています（評価ロジックへの変更を避けるため）。"
        )
    else:
        st.info("dividendYieldが取得できた銘柄がありません。")

    # ── E. エラー処理（失敗銘柄一覧） ─────────────────────────
    st.header("E. 取得失敗銘柄一覧")
    failed_df = df.loc[~df["fetch_ok"], ["code", "name", "error"]]
    if failed_df.empty:
        st.success("取得失敗銘柄はありませんでした。")
    else:
        st.dataframe(failed_df, use_container_width=True)


if __name__ == "__main__":
    main()
