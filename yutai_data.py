"""
yutai_data.py
=============
株主優待マスターデータ

【なぜ手動管理？】
  yfinance では優待情報が取得できないため、
  主要銘柄のみここに手動で登録しています。
  新しい銘柄を追加したいときは YUTAI_DATA に
  同じ形式で追記するだけでOKです。

【追加方法】
  "証券コード": {
      "yutai"      : "優待内容（具体的に）",
      "kenri_month": "確定月（例: 3月・9月）",
      "min_shares" : 最低単元株数（通常100）,
      "yutai_value": 優待の概算金額（スコア計算に使用）,
  }
"""

# ────────────────────────────────
# 株主優待マスター（主要銘柄）
# ────────────────────────────────
YUTAI_DATA: dict[str, dict] = {

    # ── 通信 ──────────────────────
    "9432": {
        "yutai"      : "dポイント（最大3,000ポイント）",
        "kenri_month": "3月",
        "min_shares" : 100,
        "yutai_value": 3000,
    },
    "9433": {
        "yutai"      : "カタログギフト（3,000〜5,000円相当）",
        "kenri_month": "3月",
        "min_shares" : 100,
        "yutai_value": 4000,
    },
    "9434": {
        "yutai"      : "PayPayポイント（最大5,000円相当）",
        "kenri_month": "3月",
        "min_shares" : 100,
        "yutai_value": 3000,
    },

    # ── 金融・保険 ────────────────
    "8591": {
        "yutai"      : "カタログギフト（3,000〜10,000円相当）",
        "kenri_month": "3月・9月",
        "min_shares" : 100,
        "yutai_value": 5000,
    },
    "8316": {
        "yutai"      : "なし（高配当型）",
        "kenri_month": "3月・9月",
        "min_shares" : 100,
        "yutai_value": 0,
    },
    "8058": {
        "yutai"      : "なし（高配当型）",
        "kenri_month": "3月",
        "min_shares" : 100,
        "yutai_value": 0,
    },

    # ── 食品・飲料 ────────────────
    "2914": {
        "yutai"      : "自社製品詰め合わせ（2,500〜5,000円相当）",
        "kenri_month": "6月・12月",
        "min_shares" : 100,
        "yutai_value": 3000,
    },
    "2502": {
        "yutai"      : "自社飲料詰め合わせ（1,000円相当）",
        "kenri_month": "12月",
        "min_shares" : 100,
        "yutai_value": 1000,
    },
    "2503": {
        "yutai"      : "自社製品詰め合わせ（1,000円相当）",
        "kenri_month": "12月",
        "min_shares" : 100,
        "yutai_value": 1000,
    },
    "2897": {
        "yutai"      : "自社製品詰め合わせ（1,500円相当）",
        "kenri_month": "3月",
        "min_shares" : 100,
        "yutai_value": 1500,
    },

    # ── 小売・流通 ────────────────
    "8267": {
        "yutai"      : "オーナーズカード（3〜7%キャッシュバック）",
        "kenri_month": "2月・8月",
        "min_shares" : 100,
        "yutai_value": 3000,
    },
    "3382": {
        "yutai"      : "グループ商品券（1,000円分）",
        "kenri_month": "2月・8月",
        "min_shares" : 100,
        "yutai_value": 1000,
    },

    # ── 製造・その他 ──────────────
    "7203": {
        "yutai"      : "なし（配当重視型）",
        "kenri_month": "3月",
        "min_shares" : 100,
        "yutai_value": 0,
    },
    "6758": {
        "yutai"      : "なし（成長株型）",
        "kenri_month": "3月",
        "min_shares" : 100,
        "yutai_value": 0,
    },
    "4502": {
        "yutai"      : "なし（グローバル型）",
        "kenri_month": "3月",
        "min_shares" : 100,
        "yutai_value": 0,
    },
    "4661": {
        "yutai"      : "株主優待パスポート（1デー入園券）",
        "kenri_month": "3月・9月",
        "min_shares" : 100,
        "yutai_value": 9400,
    },
}


def get_yutai(code: str) -> dict:
    """
    証券コードに対応する優待情報を返す。
    マスターにない場合はデフォルト値を返す。
    """
    return YUTAI_DATA.get(code, {
        "yutai"      : "データなし（公式サイトでご確認ください）",
        "kenri_month": "―",
        "min_shares" : 100,
        "yutai_value": 0,
    })


def yutai_score(code: str) -> float:
    """優待の充実度を0〜10点で返す（スコアリング用）"""
    val = get_yutai(code).get("yutai_value", 0)
    if   val >= 5000: return 10.0
    elif val >= 3000: return 8.0
    elif val >= 1500: return 6.5
    elif val >= 1000: return 5.0
    elif val >  0   : return 3.5
    else            : return 1.5   # 優待なしでも配当重視型として最低点
