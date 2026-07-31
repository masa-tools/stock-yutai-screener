"""
strategy_compare_view.py  v9 Research (緊急復旧・暫定実装)
================================================================
【本ファイルの位置付け（重要・必ずお読みください）】
  本ファイルは、research_app.py が
      from views.strategy_compare_view import render_strategy_compare
  をimportしているにもかかわらず、GitHubリポジトリの research/views/
  配下に本ファイルが存在せず ModuleNotFoundError で研究画面全体が
  起動不能になっていた問題を解消するための、緊急復旧用の新規作成
  ファイルである。

  【重要な限界（正直な申し送り）】
  本ファイルが復旧前に何を表示する設計だったのか（元の実装内容・
  仕様）は、今回の調査時点でClaude②が参照できる資料
  （research_app.py・strategy_registry.py・theme_switcher_view.py・
  walkforward_result_view.py 等、これまでのやり取りで共有された
  ファイル群）の中には一切残っていなかった。git blame・過去コミット
  履歴・削除前のバージョン等、直接の証拠は本調査では確認できて
  いない。そのため、本ファイルの中身は「欠落前の実装の復元」では
  なく、「投資ロジック・スコアリングに一切踏み込まない、安全な
  最小暫定実装」として新規に用意したものである。

  render_strategy_compare() の本来の目的が、例えば
    - 単一銘柄に対する複数戦略のスコアをWalk Forwardなしで
      即時比較するプレビュー機能
    - 戦略ごとのパラメータ設定の見比べ機能
  等であった可能性は排除できない。元の仕様が判明次第、本ファイルは
  差し替えられることを前提とした「起動を止めないための最小実装」
  である旨を明記する。

【本ファイルが行うこと（暫定実装の範囲）】
  strategy_registry.list_themes() が返す登録済みテーマ一覧
  （id・label・status）を、表形式で参照表示するだけの機能。
  スコア計算・Walk Forward実行・戦略の呼び出し（resolve_strategy_fn）
  は一切行わない。

【本ファイルが行わないこと】
  - 投資ロジック・スコアリングロジックへの関与
  - strategy_v9_*.py の compute_score() の呼び出し
  - Walk Forward実行（この責務は walkforward_result_view.py 側）
  - v8.1側コードの参照
"""

import streamlit as st

from strategy.strategy_registry import list_themes


def render_strategy_compare() -> None:
    st.subheader("🧪 戦略比較（暫定実装）")
    st.warning(
        "本タブは、research_app.pyが参照するviews/strategy_compare_view.pyが"
        "GitHubリポジトリに存在せずResearch画面全体が起動不能になっていた問題への"
        "緊急復旧対応として、暫定的に新規作成したものです。元の実装内容は"
        "確認できていないため、現時点では登録済みテーマの一覧参照のみを表示します。"
        "本来の仕様が判明次第、差し替えを想定しています。"
    )

    themes = list_themes()
    st.dataframe(
        [
            {"テーマID": t["id"], "表示名": t["label"], "状態": t["status"]}
            for t in themes
        ]
    )

    st.caption(
        "戦略ごとの実際の比較結果（Total Return等）はWalk Forward結果タブの"
        "比較機能をご利用ください。"
    )
