"""
backtest/v9_config.py (v9研究開発ブランチ スコアリングエンジン Phase1)
====================================================================
v9スコアリングエンジンの重み・ON/OFF・パラメータを一元管理する設定ファイル。

【設計目的】
  v9.1・v9.2...と改善を重ねる際、strategy_v9.py / scoring_v9.py本体を
  変更せずに、この設定ファイルの値を書き換えるだけで
    - 各コンポーネントのON/OFF
    - 重み（配点）の調整
    - 閾値パラメータの調整
    - 将来のA/Bテスト（設定セットを複数持つ）
  を行えるようにすることを目的とする。

【既存v8との関係】
  ここで定義する定数はv9の加点・減点ロジック専用であり、
  scoring_config.py（v8・既存4系統が参照する共通閾値）とは
  独立して管理する。v8側の閾値・配点には一切影響を与えない。
"""

# ── コンポーネントごとのON/OFFスイッチ ──────────────────
# Falseにすると、そのcalc_*_score関数は呼び出されず加減点0として扱われる。
ENABLE = {
    "ma_trend":     True,   # ① 移動平均線の傾き（地合判定）
    "deviation":    True,   # ② 25日移動平均乖離率
    "upper_shadow": True,   # ③ 上ヒゲ判定
    "gap":          True,   # ④ ギャップアップ判定
    "volume_surge": True,   # ⑤ 出来高急増
    "rsi":          True,   # ⑥ RSI
    "macd_cross":   True,   # ⑦ MACDゴールデンクロス
    "bollinger":    True,   # ⑧ ボリンジャーバンド
    "weekday":      False,  # ⑨ 曜日効果（デフォルトOFF。根拠データ未検証のため）
}

# ── 重み（各コンポーネントのスコアに掛ける係数） ──────────
# 1.0 = calc_*_score() の返り値をそのまま加減点に使う。
# 将来的にA/Bテストで重みだけ変えたバリエーションを試す際、
# ここを変更するだけで済む。
WEIGHT = {
    "ma_trend":     1.0,
    "deviation":    1.0,
    "upper_shadow": 1.0,
    "gap":          1.0,
    "volume_surge": 1.0,
    "rsi":          1.0,
    "macd_cross":   1.0,
    "bollinger":    1.0,
    "weekday":      1.0,
}

# ── ① 移動平均線の傾き ──────────────────────────
MA_SHORT_WINDOW = 5     # 短期線（MA5、window_df内で都度計算。MA25/MA75は既存列を利用）
MA_SLOPE_LOOKBACK = 5   # 傾き判定に使う「何日前と比較するか」
MA_TREND_BONUS = 5      # 短期>中期>長期＆上向きの場合の加点
MA_TREND_PENALTY = 3    # 逆順＆下向きの場合の減点

# ── ② 25日移動平均乖離率 ────────────────────────
DEVIATION_OVERSOLD_PCT = -8.0     # これより下に乖離 → 売られすぎ（加点）
DEVIATION_OVERHEATED_PCT = 8.0    # これより上に乖離 → 過熱（減点）
DEVIATION_BONUS = 4
DEVIATION_PENALTY = 4

# ── ③ 上ヒゲ判定 ────────────────────────────────
UPPER_SHADOW_RATIO_THRESHOLD = 0.5  # (高値-実体上端)/値幅 がこの比率以上で警戒
UPPER_SHADOW_PENALTY = 3

# ── ④ ギャップアップ判定 ────────────────────────
GAP_UP_PCT_THRESHOLD = 3.0   # 前日終値比+3%以上の寄り付きを窓開けとみなす
GAP_UP_PENALTY = 3

# ── ⑤ 出来高急増 ────────────────────────────────
VOLUME_SURGE_RATIO = 2.0     # 20日平均（当日除く）比でこの倍率以上を急増とみなす
VOLUME_SURGE_BONUS = 4

# ── ⑥ RSI ───────────────────────────────────────
# 既存scoring_config.pyのRSI_OVERSOLD/RSI_OVERBOUGHT（v8共通・30/75）とは
# 独立して、依頼書指定の30/70をv9独自閾値としてここで管理する。
RSI_V9_OVERSOLD = 30
RSI_V9_OVERBOUGHT = 70
RSI_OVERSOLD_BONUS = 4
RSI_OVERBOUGHT_PENALTY = 4

# ── ⑦ MACDゴールデンクロス ──────────────────────
MACD_GOLDEN_CROSS_BONUS = 5

# ── ⑧ ボリンジャーバンド ────────────────────────
BB_WINDOW = 20
BB_NUM_STD = 2.0
BB_LOWER_TOUCH_BONUS = 4      # -2σ到達からの反発期待（Phase1はこれのみ実装）
# スクイーズ／エクスパンションの数値化はv9.1以降の拡張ポイント（下記コメント参照）

# ── ⑨ 曜日効果（デフォルトOFF） ─────────────────
# 0=月曜 … 4=金曜。根拠となるアノマリーデータが未検証のため
# デフォルトは全て0点（ENABLE["weekday"]=Falseで無効化済み）。
# v9.1以降、統計的に有意な効果が確認できた曜日のみ値を入れる想定。
WEEKDAY_BIAS = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
