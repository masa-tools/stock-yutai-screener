"""
ai_analysis.py
==============
Gemini 2.5 Flash Lite を使ったAI分析コメント生成

【モデル】
  gemini-2.5-flash-lite-preview-06-17（最新・無料枠対応）

【節約設計】
  - st.session_state でセッション内キャッシュ
  - 同じコードは1セッション1回だけAPI呼び出し
  - APIキー未設定なら簡易コメントで代替

【APIキー設定方法】
  .streamlit/secrets.toml に以下を記載：
  GEMINI_API_KEY = "AIzaSy..."
"""

import streamlit as st
import requests
import json

# ────────────────────────────────
# 使用モデル（ここだけ変えれば切り替え可）
# ────────────────────────────────
MODEL = "gemini-2.5-flash-lite-preview-06-17"
API_URL = (
    "https://generativelanguage.googleapis.com/v1beta"
    "/models/{model}:generateContent?key={key}"
)


def get_ai_analysis(
    name: str,
    code: str,
    score: dict,
    info: dict,
    tv: dict,
    yutai: dict,
) -> dict:
    """
    Gemini APIにデータを送りAI分析コメントを受け取る。
    APIキー未設定・エラー時は簡易コメントで代替。

    Returns:
        {
          "strengths": ["強み1", ...],
          "risks"    : ["リスク1", ...],
          "comment"  : "まとめコメント",
          "source"   : "ai" or "fallback",
        }
    """
    # ── セッションキャッシュ確認 ────
    # 同じ銘柄は1セッション1回だけAPIを呼ぶ（節約）
    cache_key = f"ai_{code}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]

    # ── APIキー確認 ─────────────────
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if not api_key or api_key == "your_api_key_here":
        result = _fallback(name, score, tv, info, code, yutai)
        st.session_state[cache_key] = result
        return result

    # ── プロンプト組み立て ──────────
    prompt = _build_prompt(name, code, score, info, tv, yutai)

    # ── API呼び出し ─────────────────
    try:
        url = API_URL.format(model=MODEL, key=api_key)
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature"    : 0.7,
                "maxOutputTokens": 900,
                "topP"           : 0.9,
            },
            "safetySettings": [
                {"category": c, "threshold": "BLOCK_NONE"}
                for c in [
                    "HARM_CATEGORY_HARASSMENT",
                    "HARM_CATEGORY_HATE_SPEECH",
                    "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "HARM_CATEGORY_DANGEROUS_CONTENT",
                ]
            ],
        }
        res = requests.post(url, json=payload, timeout=25,
                            headers={"Content-Type": "application/json"})
        res.raise_for_status()

        raw = _extract(res.json())
        result = _parse(raw, score, code)
        result["source"] = "ai"

    except requests.exceptions.HTTPError as e:
        code_num = e.response.status_code if e.response else 0
        if code_num == 429:
            st.warning("⚠️ Gemini APIのレート制限に達しました。簡易コメントを表示します。")
        elif code_num == 400:
            st.warning("⚠️ APIキーが正しくない可能性があります。secrets.toml を確認してください。")
        else:
            st.warning(f"⚠️ Gemini APIエラー（{code_num}）。簡易コメントを表示します。")
        result = _fallback(name, score, tv, info, code, yutai)

    except requests.exceptions.Timeout:
        st.warning("⚠️ AI分析がタイムアウトしました。簡易コメントを表示します。")
        result = _fallback(name, score, tv, info, code, yutai)

    except Exception as e:
        st.warning(f"⚠️ エラー: {str(e)[:60]}。簡易コメントを表示します。")
        result = _fallback(name, score, tv, info, code, yutai)

    # セッションキャッシュに保存
    st.session_state[cache_key] = result
    return result


# ────────────────────────────────
# プロンプト構築
# ────────────────────────────────
def _build_prompt(name, code, score, info, tv, yutai) -> str:
    """Geminiに渡すプロンプトを組み立てる"""

    def _f(v, d=2, s=""):
        # 数値を安全にフォーマット
        try:
            return f"{float(v):.{d}f}{s}" if v is not None else "不明"
        except Exception:
            return "不明"

    per  = info.get("trailingPE") or info.get("forwardPE")
    pbr  = info.get("priceToBook")
    dy   = info.get("dividendYield")
    dy_s = f"{float(dy)*100:.2f}%" if dy else "無配当"

    return f"""あなたは日本株の長期投資アドバイザーです。
投資初心者（20〜30代女性）に向けて、やさしく正直な分析を行ってください。

【銘柄データ】
- 銘柄名: {name}（{code}）
- 総合スコア: {score.get('total')}点 / 100点
- PER: {_f(per,1,'倍')} / PBR: {_f(pbr,2,'倍')}
- 配当利回り: {dy_s}
- トレンド: {tv.get('trend','不明')}
- RSI: {_f(tv.get('rsi'),0)} （{tv.get('rsi_note','').split('—')[-1].strip() if tv.get('rsi_note') else '不明'}）
- MACD: {tv.get('macd_note','不明')}
- 株主優待: {yutai.get('yutai','なし')}
- 権利確定月: {yutai.get('kenri_month','―')}

【出力形式】
以下のJSON形式のみで出力してください。他のテキストは不要です。

{{
  "strengths": ["強み1（具体的に）", "強み2", "強み3"],
  "risks"    : ["リスク1", "リスク2"],
  "comment"  : "初心者向けの総括コメント（120字以内・前向きかつ正直・断定禁止）"
}}

【禁止事項】
- 「絶対上がります」「確実に儲かります」などの断定表現
- JSON以外の出力・マークダウン記法"""


# ────────────────────────────────
# レスポンス解析
# ────────────────────────────────
def _extract(data: dict) -> str:
    """Gemini APIのレスポンスからテキストを取り出す"""
    try:
        return (data["candidates"][0]["content"]["parts"][0]["text"].strip())
    except (KeyError, IndexError):
        return ""


def _parse(raw: str, score: dict, code: str) -> dict:
    """
    GeminiのJSON出力をパースする。
    失敗時は _fallback() の結果を返す。
    """
    # ```json ... ``` ブロックがあれば除去
    text = raw.strip()
    if "```" in text:
        lines = [l for l in text.splitlines() if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        d = json.loads(text)
        return {
            "strengths": d.get("strengths", ["―"])[:3],
            "risks"    : d.get("risks",     ["―"])[:2],
            "comment"  : d.get("comment",   "コメントを取得できませんでした"),
        }
    except json.JSONDecodeError:
        # パース失敗時はテキストをそのままコメントに
        return {
            "strengths": ["AI分析を取得しました"],
            "risks"    : ["株式投資にはリスクが伴います"],
            "comment"  : raw[:200],
        }


# ────────────────────────────────
# フォールバック（APIなし時）
# ────────────────────────────────
def _fallback(name, score, tv, info, code, yutai) -> dict:
    """
    APIキー未設定・エラー時のフォールバック。
    Pythonの条件分岐だけでコメントを生成する。
    """
    total  = score.get("total", 50)
    dy     = info.get("dividendYield")
    trend  = tv.get("trend", "")
    rsi    = tv.get("rsi")

    strengths = []
    risks     = []

    # 強み
    if "上昇" in trend:
        strengths.append("中長期の上昇トレンドが継続しています")
    if dy and dy * 100 >= 3:
        strengths.append(f"配当利回り{dy*100:.1f}%と魅力的な水準です")
    if yutai.get("yutai_value", 0) >= 1000:
        strengths.append("株主優待が充実しており生活でもお得に活かせます")
    if score.get("finance", 0) >= 65:
        strengths.append("財務安定性が高く、長期保有向きの特徴があります")
    if not strengths:
        strengths.append("スクリーニング条件を一定数クリアしています")

    # リスク
    if rsi and rsi >= 70:
        risks.append(f"RSI {rsi:.0f}と過熱感があります。短期的な調整に注意")
    if "下降" in trend:
        risks.append("中期トレンドが下向きです。慎重な判断が必要です")
    if not risks:
        risks.append("株式投資は元本保証がありません。余裕資金で運用しましょう")

    # まとめコメント
    if total >= 70:
        comment = f"総合スコア{total}点と高水準です。長期保有の候補として検討できます 🌸"
    elif total >= 55:
        comment = f"総合スコア{total}点。バランスよくまとまった銘柄です。四半期決算も定期チェックを 📋"
    else:
        comment = f"総合スコア{total}点。他の候補と比較しながら慎重に検討しましょう 🌼"

    comment += (
        "\n\n💡 Gemini APIキーを `.streamlit/secrets.toml` に設定すると"
        "より詳細なAI分析コメントが使えます。"
    )

    return {
        "strengths": strengths[:3],
        "risks"    : risks[:2],
        "comment"  : comment,
        "source"   : "fallback",
    }
