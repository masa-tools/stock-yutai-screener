"""
investment_judge.py  v8.0
=========================
投資判断ロジック専用モジュール（P4-1c: app.py 責務分離）

【移動元】
  app.py の以下を移動:
    - _investment_judge()

【依存モジュール】
  scoring_config : RSI_SLIGHTLY_OVERSOLD / RSI_OVERBOUGHT
  stock_data     : fmt_dividend_pct（P2-1残件解消: インライン変換を統一）
  numpy          : NaN/Inf チェック（_nv ヘルパー）

【P2-1残件解消】
  移動前の _investment_judge 内に残存していた
    dp = dv * 100 if dv <= 1.0 else dv
  を fmt_dividend_pct() に統一。
"""

import numpy as np
from scoring_config import RSI_SLIGHTLY_OVERSOLD, RSI_OVERBOUGHT
from stock_data     import fmt_dividend_pct


def _investment_judge(sc: dict, tv: dict, info: dict) -> dict:
    """
    長期投資向けの総合投資判断を返す。

    評価軸:
      PER・PBR・配当利回り・RSI・移動平均・財務・連続増配傾向
    """
    pts = 0
    reasons: list[str] = []
    cautions: list[str] = []

    def _nv(key):
        v = info.get(key)
        try:
            f = float(v)
            return None if (np.isnan(f) or np.isinf(f)) else f
        except Exception:
            return None

    # --- PER ---
    per = _nv("trailingPE") or _nv("forwardPE")
    if per:
        if 8 <= per <= 18:
            pts += 2; reasons.append(f"PER {per:.1f}倍（割安〜適正）")
        elif per < 8:
            pts += 1; reasons.append(f"PER {per:.1f}倍（超割安、理由に注意）")
        elif per <= 25:
            pts += 1
        else:
            cautions.append(f"PER {per:.1f}倍（割高水準）")

    # --- PBR ---
    pbr = _nv("priceToBook")
    if pbr:
        if pbr < 1.0:
            pts += 2; reasons.append(f"PBR {pbr:.2f}倍（解散価値以下・割安）")
        elif pbr <= 2.0:
            pts += 1; reasons.append(f"PBR {pbr:.2f}倍（適正水準）")
        else:
            cautions.append(f"PBR {pbr:.2f}倍（割高水準）")

    # --- 配当利回り（P2-1残件解消: fmt_dividend_pct に統一） ---
    dp = fmt_dividend_pct(info.get("dividendYield"))
    if dp >= 3.0 and dp <= 6.0:
        pts += 2; reasons.append(f"配当利回り {dp:.2f}%（高配当）")
    elif dp >= 1.5:
        pts += 1; reasons.append(f"配当利回り {dp:.2f}%")
    elif dp > 6.0:
        pts += 1; cautions.append(f"配当利回り {dp:.2f}%（高すぎ・持続性注意）")

    # --- RSI ---
    rsi = tv.get("rsi")
    if rsi:
        if rsi <= RSI_SLIGHTLY_OVERSOLD:
            pts += 2; reasons.append(f"RSI {rsi:.0f}（売られすぎ・買い場の可能性）")
        elif rsi <= 60:
            pts += 1
        elif rsi >= RSI_OVERBOUGHT:
            cautions.append(f"RSI {rsi:.0f}（買われすぎ）")

    # --- 移動平均線 ---
    close = tv.get("close", 0)
    ma25  = tv.get("ma25")
    ma75  = tv.get("ma75")
    if ma25 and ma75 and close:
        if close > ma25 > ma75:
            pts += 2; reasons.append("株価が25日線・75日線を上回る（上昇トレンド）")
        elif close > ma25:
            pts += 1; reasons.append("株価が25日移動平均を上回る")
        elif ma25 < ma75:
            cautions.append("下降トレンド中（25日線が75日線を下回る）")

    # --- 財務スコア ---
    fin = sc.get("finance", 0)
    if fin >= 70:
        pts += 2; reasons.append("財務健全性が高い")
    elif fin >= 50:
        pts += 1

    # 5段階判定（最大13点）
    if   pts >= 11: stars, label = 5, "強く買い 🌟"
    elif pts >= 8 : stars, label = 4, "買い ✨"
    elif pts >= 5 : stars, label = 3, "保有 🌸"
    elif pts >= 3 : stars, label = 2, "利確検討 🍂"
    else          : stars, label = 1, "売却検討 ⚠️"

    return {
        "stars"   : stars,
        "label"   : label,
        "points"  : pts,
        "reasons" : reasons[:4],
        "cautions": cautions[:2],
    }
