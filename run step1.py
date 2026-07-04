"""
backtest/run_step1.py  (v9研究開発ブランチ Step1)
====================================================
Step1専用の実行エントリポイント。

対象: トヨタ（7203）1銘柄・過去1年・v8のみ・全営業日判定方式。

data_loader / strategy_v8 / backtest_runner / metrics の各関数を
順番に呼び出すだけの「台本」であり、それ自体にロジックは持たない。

Streamlitに依存しない素のPythonスクリプトとして実行できる。

実行方法:
    python run_step1.py
"""

from data_loader import fetch_stock_data
from strategy_v8 import compute_score_at
from backtest_runner import run_backtest
from metrics import (
    filter_by_threshold,
    calc_max_drawdown,
    calc_down10_rate,
    describe_score_distribution,
)

# Step1固定パラメータ
TARGET_CODE = "7203"   # トヨタ
TARGET_PERIOD = "1y"   # 過去1年


def main():
    print(f"=== Step1バックテスト: {TARGET_CODE}（過去{TARGET_PERIOD}）v8のみ ===\n")

    # Phase A: データ取得
    df, info = fetch_stock_data(TARGET_CODE, period=TARGET_PERIOD)
    if df is None or df.empty:
        print("データ取得に失敗しました。処理を中断します。")
        return

    print(f"取得データ: {len(df)}営業日分")
    print(f"期間: {df.index[0].date()} 〜 {df.index[-1].date()}\n")

    # Phase B + C: 全営業日スコア計算 + 将来リターン付与（統合済み）
    result_df = run_backtest(df, info, TARGET_CODE, compute_score_at)

    if result_df.empty:
        print("バックテスト結果が空です。データ期間が短すぎる可能性があります。")
        return

    print(f"判定対象日数: {len(result_df)}日"
          f"（先頭{result_df.index[0]}〜末尾、"
          f"REQUIRED_HISTORY_DAYS分はスキップ済み）\n")

    # スコア分布の確認（閾値を決めるための土台データ）
    dist = describe_score_distribution(result_df, score_col="total")
    print("--- スコア分布（total列） ---")
    for k, v in dist.items():
        print(f"  {k}: {v}")
    print()

    # 参考: 閾値を仮に70点として集計してみる（本格的な閾値検討はStep1完了後）
    tentative_threshold = 70
    filtered = filter_by_threshold(result_df, tentative_threshold, score_col="total")
    print(f"--- 参考集計（閾値={tentative_threshold}点で仮フィルタ） ---")
    print(f"  該当日数: {len(filtered)}日")

    max_dd = calc_max_drawdown(filtered)
    down10 = calc_down10_rate(filtered)
    print(f"  最大ドローダウン: {max_dd}")
    print(f"  -10%以上下落した割合: {down10}")

    # CSV出力（Step1では可視化まで作り込まず、生データの保存に留める）
    output_path = "step1_result.csv"
    result_df.to_csv(output_path, index=False)
    print(f"\n結果をCSVに保存しました: {output_path}")


if __name__ == "__main__":
    main()
