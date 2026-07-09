"""
backtest/scoring_v9.py (v9研究開発ブランチ スコアリングエンジン Phase1)
====================================================================
v9で新規に追加する加点・減点ロジックを、既存v8ロジックとは
完全に独立した小さな関数群として実装するモジュール。

【設計方針】
  各関数は「window_dfの直近の状態から、1つの観点についての
  加点・減点（float）を1つ返す」という単純な責務のみを持つ。
  複数の関数の合算・重み付け・ON/OFF制御は strategy_v9.py
  （呼び出し側）が行い、このファイルは純粋な計算ロジックのみを持つ。

【Look Ahead Bias（未来情報リーク）に関する設計上の注意】
  すべての関数は引数 window_df のみを参照する。
  window_df は backtest_runner.run_backtest() が
  df.iloc[:i+1]（判定対象日までの行のみ）に絞り込んだ状態で
  strategy_fn経由で渡されることが前提であり、本モジュールの
  各関数はその前提を信頼し、window_df自身に対して
  .rolling() / .tail() 等の「window_df内で完結する」計算のみを行う。
  window_dfの外（未来の行）を一切参照しないため、新たなリークは発生しない。

【既存指標の再利用について】
  RSI・MACD・MACD_signal・MA25・MA75は
  technical_analysis.add_indicators() で既に計算済みの列を
  window_dfからそのまま参照する（重複実装を避ける）。
  MA5・25日乖離率・ボリンジャーバンド・上ヒゲ比率・ギャップ率・
  出来高比率は既存コードに列が存在しないため、本モジュール内で
  window_dfから都度計算する。
"""

import pandas as pd

from backtest import v9_config as cfg


def _last_valid(series: pd.Series):
    """seriesの末尾がNaNでなければfloatで返す。NaN/データ不足はNoneを返す。"""
    if series is None or len(series) == 0:
        return None
    v = series.iloc[-1]
    if pd.isna(v):
        return None
    return float(v)


# ── ① 移動平均線の傾き（地合判定） ──────────────────────
def calc_ma_score(window_df: pd.DataFrame) -> float:
    """
    MA5・MA25・MA75の並び順と傾きから地合（相場の地力）を判定する。

    加点条件: MA5 > MA25 > MA75（短期>中期>長期のパーフェクトオーダー）
              かつ MA25がMA_SLOPE_LOOKBACK日前より上向き
    減点条件: 逆順（MA5 < MA25 < MA75）かつMA25が下向き
    それ以外: 0点
    """
    close = window_df["Close"]
    if len(close) < max(cfg.MA_SHORT_WINDOW, cfg.MA_SLOPE_LOOKBACK) + 1:
        return 0.0

    ma5 = close.rolling(cfg.MA_SHORT_WINDOW).mean()
    ma25 = window_df["MA25"]
    ma75 = window_df["MA75"]

    ma5_now = _last_valid(ma5)
    ma25_now = _last_valid(ma25)
    ma75_now = _last_valid(ma75)

    if ma5_now is None or ma25_now is None or ma75_now is None:
        return 0.0
    if len(ma25.dropna()) <= cfg.MA_SLOPE_LOOKBACK:
        return 0.0

    ma25_past = ma25.iloc[-1 - cfg.MA_SLOPE_LOOKBACK]
    if pd.isna(ma25_past):
        return 0.0
    ma25_slope_up = ma25_now > float(ma25_past)

    if ma5_now > ma25_now > ma75_now and ma25_slope_up:
        return float(cfg.MA_TREND_BONUS)
    if ma5_now < ma25_now < ma75_now and not ma25_slope_up:
        return -float(cfg.MA_TREND_PENALTY)
    return 0.0


# ── ② 25日移動平均乖離率 ────────────────────────────
def calc_deviation_score(window_df: pd.DataFrame) -> float:
    """(終値 - MA25) / MA25 * 100 の乖離率から、売られすぎ／過熱を判定する。"""
    close_now = _last_valid(window_df["Close"])
    ma25_now = _last_valid(window_df["MA25"])
    if close_now is None or ma25_now is None or ma25_now == 0:
        return 0.0

    deviation_pct = (close_now - ma25_now) / ma25_now * 100

    if deviation_pct <= cfg.DEVIATION_OVERSOLD_PCT:
        return float(cfg.DEVIATION_BONUS)
    if deviation_pct >= cfg.DEVIATION_OVERHEATED_PCT:
        return -float(cfg.DEVIATION_PENALTY)
    return 0.0


# ── ③ 上ヒゲ判定 ────────────────────────────────────
def calc_upper_shadow_penalty(window_df: pd.DataFrame) -> float:
    """直近1日の上ヒゲが値幅に対して大きい場合、戻り売り警戒として減点する。"""
    row = window_df.iloc[-1]
    try:
        o, h, l, c = float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"])
    except (KeyError, ValueError, TypeError):
        return 0.0

    price_range = h - l
    if price_range <= 0:
        return 0.0

    upper_shadow = h - max(o, c)
    ratio = upper_shadow / price_range

    if ratio >= cfg.UPPER_SHADOW_RATIO_THRESHOLD:
        return -float(cfg.UPPER_SHADOW_PENALTY)
    return 0.0


# ── ④ ギャップアップ判定 ────────────────────────────
def calc_gap_penalty(window_df: pd.DataFrame) -> float:
    """前日終値に対して当日始値が大きく上に窓を開けた場合、高値掴み防止のため減点する。"""
    if len(window_df) < 2:
        return 0.0
    try:
        prev_close = float(window_df["Close"].iloc[-2])
        today_open = float(window_df["Open"].iloc[-1])
    except (KeyError, ValueError, TypeError):
        return 0.0

    if prev_close <= 0:
        return 0.0

    gap_pct = (today_open - prev_close) / prev_close * 100
    if gap_pct >= cfg.GAP_UP_PCT_THRESHOLD:
        return -float(cfg.GAP_UP_PENALTY)
    return 0.0


# ── ⑤ 出来高急増 ────────────────────────────────────
def calc_volume_score(window_df: pd.DataFrame) -> float:
    """直近20日平均出来高（当日を除く）に対する当日出来高の比率から「動意付き」を判定する。"""
    if len(window_df) < 21:
        return 0.0
    try:
        vol_today = float(window_df["Volume"].iloc[-1])
        vol_avg20 = float(window_df["Volume"].iloc[-21:-1].mean())
    except (KeyError, ValueError, TypeError):
        return 0.0

    if vol_avg20 <= 0:
        return 0.0

    ratio = vol_today / vol_avg20
    if ratio >= cfg.VOLUME_SURGE_RATIO:
        return float(cfg.VOLUME_SURGE_BONUS)
    return 0.0


# ── ⑥ RSI ───────────────────────────────────────────
def calc_rsi_score(window_df: pd.DataFrame) -> float:
    """
    既存のadd_indicators()で計算済みのRSI列をそのまま参照する（重複実装を避ける）。
    v9独自の閾値（v9_config.RSI_V9_*）で判定する。
    """
    if "RSI" not in window_df.columns:
        return 0.0
    rsi_now = _last_valid(window_df["RSI"])
    if rsi_now is None:
        return 0.0

    if rsi_now <= cfg.RSI_V9_OVERSOLD:
        return float(cfg.RSI_OVERSOLD_BONUS)
    if rsi_now >= cfg.RSI_V9_OVERBOUGHT:
        return -float(cfg.RSI_OVERBOUGHT_PENALTY)
    return 0.0


# ── ⑦ MACDゴールデンクロス ──────────────────────────
def calc_macd_score(window_df: pd.DataFrame) -> float:
    """
    既存のadd_indicators()で計算済みのMACD/MACD_signal列を参照し、
    直近1日で「MACDがシグナルを下から上に抜けた」場合のみを
    ゴールデンクロスとして加点する（MACD>signalが継続しているだけでは加点しない）。
    """
    if "MACD" not in window_df.columns or "MACD_signal" not in window_df.columns:
        return 0.0
    if len(window_df) < 2:
        return 0.0

    macd = window_df["MACD"]
    signal = window_df["MACD_signal"]
    macd_now, macd_prev = macd.iloc[-1], macd.iloc[-2]
    signal_now, signal_prev = signal.iloc[-1], signal.iloc[-2]

    if pd.isna(macd_now) or pd.isna(macd_prev) or pd.isna(signal_now) or pd.isna(signal_prev):
        return 0.0

    crossed_up = float(macd_prev) <= float(signal_prev) and float(macd_now) > float(signal_now)
    return float(cfg.MACD_GOLDEN_CROSS_BONUS) if crossed_up else 0.0


# ── ⑧ ボリンジャーバンド ────────────────────────────
def calc_bb_score(window_df: pd.DataFrame) -> float:
    """
    ボリンジャーバンド（BB_WINDOW日・BB_NUM_STDσ）を都度計算し、
    -2σ到達からの反発期待を加点する。
    スクイーズ／エクスパンションの判定はv9.1以降の拡張ポイントとし、
    Phase1では-2σ反発のみをスコア化する。
    """
    close = window_df["Close"]
    if len(close) < cfg.BB_WINDOW:
        return 0.0

    ma = close.rolling(cfg.BB_WINDOW).mean()
    std = close.rolling(cfg.BB_WINDOW).std()

    ma_now = _last_valid(ma)
    std_now = _last_valid(std)
    close_now = _last_valid(close)

    if ma_now is None or std_now is None or close_now is None:
        return 0.0

    lower_band = ma_now - cfg.BB_NUM_STD * std_now

    if close_now <= lower_band:
        return float(cfg.BB_LOWER_TOUCH_BONUS)
    return 0.0


# ── ⑨ 曜日効果（アノマリー補正） ────────────────────
def calc_weekday_score(window_df: pd.DataFrame) -> float:
    """
    判定対象日の曜日に応じたバイアス補正を返す。
    v9_config.WEEKDAY_BIASの値をそのまま返すだけの薄い関数。
    デフォルトはENABLE["weekday"]=Falseのため呼び出されない
    （strategy_v9.py側で制御。関数自体はいつでもテスト・有効化できるよう残す）。
    """
    weekday = window_df.index[-1].weekday()
    return float(cfg.WEEKDAY_BIAS.get(weekday, 0))
