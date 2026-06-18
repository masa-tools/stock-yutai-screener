"""
scoring_config.py  v8.0
=======================
スコアリング・判定で使用する閾値定数の一元管理

【管理対象】
  ユーザーに表示・説明される判定文言の根拠となる閾値のみ管理する。
  各スコアリング系統の内部計算ロジック（配点比率等）はそれぞれのファイルで管理。

【スコアリング系統】
  calc_simple_score   : technical_analysis.py（100点満点）
  _calc_scores        : recommend.py（100点満点）
  _judge              : buy_timing.py（50点満点）
  _investment_judge   : app.py（13点満点）
"""

# ── RSI 判定閾値 ──────────────────────────────────────────
# ユーザーに表示する「売られすぎ」「買われすぎ」の定義を統一する

RSI_OVERSOLD         = 30   # 売られすぎ（強い買いシグナル）
RSI_SLIGHTLY_OVERSOLD = 40  # やや売られすぎ
RSI_NEUTRAL_LOW      = 55   # 適正下限（過熱感なし）
RSI_NEUTRAL_HIGH     = 65   # 適正上限
RSI_OVERBOUGHT       = 75   # 買われすぎ（注意）

# ── 配当利回り 判定閾値（%） ──────────────────────────────
DIV_HIGH             = 3.0  # 高配当の下限
DIV_ATTRACTIVE       = 3.5  # 魅力的な高配当
DIV_CAUTION          = 8.0  # 高すぎ・持続性注意の上限

# ── PER 判定閾値 ──────────────────────────────────────────
PER_UNDERVALUE       = 10   # 割安水準の上限
PER_FAIR             = 20   # 適正水準の上限
PER_SLIGHTLY_HIGH    = 25   # やや割高の上限
