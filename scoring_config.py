"""
scoring_config.py  v8.1
=======================
スコアリング・判定で使用する閾値定数の一元管理

【管理対象】
  ユーザーに表示・説明される判定文言の根拠となる閾値のみ管理する。
  各スコアリング系統の内部計算ロジック（配点比率等）はそれぞれのファイルで管理。

【スコアリング系統】
  calc_simple_score   : technical_analysis.py（100点満点）
  _calc_scores        : recommend.py（100点満点）
  _judge              : buy_timing.py（50点満点）
  _investment_judge   : investment_judge.py（13点満点）

【Phase2-4: RSI設定のみ Config Manager 接続】
  RSI_* の5定数のみ、config_manager.py 経由で config/settings.json から
  値を取得するように変更した（Phase2-4）。
  値そのものは変更していない（従来と完全に同じ 30/40/55/65/75）。

  ConfigManager経由の取得に何らかの問題が生じた場合でも、
  既存(v8.1)と完全に同じ値へフォールバックし、判定結果に
  一切の影響を与えないようにしている。

  DIV_*・PER_* は今回のPhaseでは対象外。従来通りこのファイル内の
  ハードコード値のまま変更していない。
"""

# ── RSI 判定閾値 ──────────────────────────────────────────
# ユーザーに表示する「売られすぎ」「買われすぎ」の定義を統一する
#
# Phase2-4: ConfigManager（config/settings.json）経由で取得する。
# 取得できない場合は、従来と同じ値へフォールバックする
# （既存出力への影響を絶対に発生させないため）。

_RSI_FALLBACK = {
    "oversold": 30,            # 売られすぎ（強い買いシグナル）
    "slightly_oversold": 40,   # やや売られすぎ
    "neutral_low": 55,         # 適正下限（過熱感なし）
    "neutral_high": 65,        # 適正上限
    "overbought": 75,          # 買われすぎ（注意）
}

try:
    from config_manager import ConfigManager

    _cm = ConfigManager()

    RSI_OVERSOLD          = _cm.get("scoring.rsi.oversold",          _RSI_FALLBACK["oversold"])
    RSI_SLIGHTLY_OVERSOLD = _cm.get("scoring.rsi.slightly_oversold", _RSI_FALLBACK["slightly_oversold"])
    RSI_NEUTRAL_LOW       = _cm.get("scoring.rsi.neutral_low",       _RSI_FALLBACK["neutral_low"])
    RSI_NEUTRAL_HIGH      = _cm.get("scoring.rsi.neutral_high",      _RSI_FALLBACK["neutral_high"])
    RSI_OVERBOUGHT        = _cm.get("scoring.rsi.overbought",        _RSI_FALLBACK["overbought"])
except Exception:
    # config_manager.py の import失敗／settings.json不備など、
    # いかなる理由であっても既存(v8.1)と同じ値で動作させる。
    RSI_OVERSOLD          = _RSI_FALLBACK["oversold"]
    RSI_SLIGHTLY_OVERSOLD = _RSI_FALLBACK["slightly_oversold"]
    RSI_NEUTRAL_LOW       = _RSI_FALLBACK["neutral_low"]
    RSI_NEUTRAL_HIGH      = _RSI_FALLBACK["neutral_high"]
    RSI_OVERBOUGHT        = _RSI_FALLBACK["overbought"]

# ── 配当利回り 判定閾値（%） ──────────────────────────────
# Phase2-4では対象外。従来通りこのファイル内のハードコード値のまま。
DIV_HIGH             = 3.0  # 高配当の下限
DIV_ATTRACTIVE       = 3.5  # 魅力的な高配当
DIV_CAUTION          = 8.0  # 高すぎ・持続性注意の上限

# ── PER 判定閾値 ──────────────────────────────────────────
# Phase2-4では対象外。従来通りこのファイル内のハードコード値のまま。
PER_UNDERVALUE       = 10   # 割安水準の上限
PER_FAIR             = 20   # 適正水準の上限
PER_SLIGHTLY_HIGH    = 25   # やや割高の上限
