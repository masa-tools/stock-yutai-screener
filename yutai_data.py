"""
yutai_data.py  v7.0
====================
株主優待マスターデータ（④詳細表示対応版）

【v7.0 追加フィールド】
  long_hold_bonus: 長期保有優遇内容
  share_tiers    : 株数別優待内容リスト
  notes          : 補足・注意事項
"""

YUTAI_DATA: dict[str, dict] = {

    # ── 通信 ──────────────────────────────────────────────
    "9432": {
        "yutai"          : "dポイント（最大3,000ポイント）",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 3000,
        "share_tiers"    : [
            {"shares": 100,   "benefit": "dポイント 1,000pt"},
            {"shares": 1000,  "benefit": "dポイント 3,000pt"},
        ],
        "long_hold_bonus": "なし",
        "notes"          : "dポイント加盟店・d払いで利用可",
    },
    "9433": {
        "yutai"          : "カタログギフト（3,000〜5,000円相当）",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 4000,
        "share_tiers"    : [
            {"shares": 100,  "benefit": "カタログギフト 3,000円相当"},
            {"shares": 1000, "benefit": "カタログギフト 5,000円相当"},
        ],
        "long_hold_bonus": "5年以上保有でグレードアップ",
        "notes"          : "食品・日用品など豊富な選択肢",
    },
    "9434": {
        "yutai"          : "PayPayポイント（最大5,000円相当）",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 3000,
        "share_tiers"    : [
            {"shares": 100,   "benefit": "PayPayポイント 1,500pt"},
            {"shares": 1000,  "benefit": "PayPayポイント 5,000pt"},
        ],
        "long_hold_bonus": "なし",
        "notes"          : "PayPay加盟店・スマホ決済で利用可",
    },

    # ── 金融・保険 ────────────────────────────────────────
    "8591": {
        "yutai"          : "カタログギフト（3,000〜10,000円相当）",
        "kenri_month"    : "3月・9月",
        "min_shares"     : 100,
        "yutai_value"    : 5000,
        "share_tiers"    : [
            {"shares": 100,  "benefit": "カタログギフト 3,000円相当（3月）"},
            {"shares": 100,  "benefit": "カタログギフト 5,000円相当（9月/3年以上）"},
        ],
        "long_hold_bonus": "3年以上でグレードアップ（最大10,000円相当）",
        "notes"          : "年2回受け取り可。長期保有でさらにお得",
    },
    "8316": {
        "yutai"          : "なし（高配当重視型）",
        "kenri_month"    : "3月・9月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "配当金での株主還元に注力",
    },
    "8058": {
        "yutai"          : "なし（高配当重視型）",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "配当金での株主還元に注力",
    },
    "8766": {
        "yutai"          : "なし（高配当重視型）",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "配当利回りが高く長期保有向き",
    },
    "8725": {
        "yutai"          : "なし（高配当重視型）",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "",
    },

    # ── 食品・飲料 ────────────────────────────────────────
    "2914": {
        "yutai"          : "自社製品詰め合わせ（2,500〜5,000円相当）",
        "kenri_month"    : "6月・12月",
        "min_shares"     : 100,
        "yutai_value"    : 3000,
        "share_tiers"    : [
            {"shares": 100,  "benefit": "自社製品 2,500円相当（年2回）"},
            {"shares": 200,  "benefit": "自社製品 5,000円相当（年2回）"},
        ],
        "long_hold_bonus": "なし",
        "notes"          : "年2回（6月・12月）受け取り。たばこ以外も選択可",
    },
    "2502": {
        "yutai"          : "自社飲料詰め合わせ（1,000円相当）",
        "kenri_month"    : "12月",
        "min_shares"     : 100,
        "yutai_value"    : 1000,
        "share_tiers"    : [
            {"shares": 100, "benefit": "アサヒ飲料 1,000円相当"},
        ],
        "long_hold_bonus": "なし",
        "notes"          : "",
    },
    "2503": {
        "yutai"          : "自社製品詰め合わせ（1,000円相当）",
        "kenri_month"    : "12月",
        "min_shares"     : 100,
        "yutai_value"    : 1000,
        "share_tiers"    : [
            {"shares": 100, "benefit": "キリン製品 1,000円相当"},
        ],
        "long_hold_bonus": "なし",
        "notes"          : "",
    },
    "2897": {
        "yutai"          : "自社製品詰め合わせ（1,500円相当）",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 1500,
        "share_tiers"    : [
            {"shares": 100, "benefit": "日清食品製品 1,500円相当"},
        ],
        "long_hold_bonus": "なし",
        "notes"          : "カップ麺・即席めん等の詰め合わせ",
    },
    "2801": {
        "yutai"          : "自社製品詰め合わせ（1,500円相当）",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 1500,
        "share_tiers"    : [
            {"shares": 100, "benefit": "キッコーマン製品 1,500円相当"},
        ],
        "long_hold_bonus": "なし",
        "notes"          : "しょうゆ・食品詰め合わせ",
    },
    "2802": {
        "yutai"          : "自社製品詰め合わせ（1,000円相当）",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 1000,
        "share_tiers"    : [
            {"shares": 100, "benefit": "味の素製品 1,000円相当"},
        ],
        "long_hold_bonus": "なし",
        "notes"          : "",
    },

    # ── 小売・流通 ────────────────────────────────────────
    "8267": {
        "yutai"          : "オーナーズカード（3〜7%キャッシュバック）",
        "kenri_month"    : "2月・8月",
        "min_shares"     : 100,
        "yutai_value"    : 3000,
        "share_tiers"    : [
            {"shares": 100,  "benefit": "オーナーズカード（3%返金）"},
            {"shares": 500,  "benefit": "オーナーズカード（4%返金）"},
            {"shares": 1000, "benefit": "オーナーズカード（5%返金）"},
            {"shares": 3000, "benefit": "オーナーズカード（7%返金）"},
        ],
        "long_hold_bonus": "なし",
        "notes"          : "イオン・マックスバリュ等での買い物が割引",
    },
    "3382": {
        "yutai"          : "グループ商品券（1,000円分）",
        "kenri_month"    : "2月・8月",
        "min_shares"     : 100,
        "yutai_value"    : 1000,
        "share_tiers"    : [
            {"shares": 100, "benefit": "グループ商品券 500円×2枚"},
        ],
        "long_hold_bonus": "なし",
        "notes"          : "セブン-イレブン・イトーヨーカドーで利用可",
    },
    "9843": {
        "yutai"          : "株主優待券（500円×複数枚）",
        "kenri_month"    : "2月",
        "min_shares"     : 100,
        "yutai_value"    : 1000,
        "share_tiers"    : [
            {"shares": 100, "benefit": "株主優待券 1,000円相当"},
        ],
        "long_hold_bonus": "なし",
        "notes"          : "ニトリ・デコホーム店舗で利用可",
    },

    # ── 製造・その他 ─────────────────────────────────────
    "7203": {
        "yutai"          : "なし（配当重視型）",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "配当金での還元が中心",
    },
    "6758": {
        "yutai"          : "なし（成長株型）",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "",
    },
    "4502": {
        "yutai"          : "なし（グローバル型）",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "",
    },
    "4661": {
        "yutai"          : "株主優待パスポート（1デー入園券）",
        "kenri_month"    : "3月・9月",
        "min_shares"     : 100,
        "yutai_value"    : 9400,
        "share_tiers"    : [
            {"shares": 100, "benefit": "1デーパスポート×1枚（年2回）"},
        ],
        "long_hold_bonus": "なし",
        "notes"          : "東京ディズニーランド/シー入園券。定価9,400円相当",
    },
    "1928": {
        "yutai"          : "クオカード（1,000円）",
        "kenri_month"    : "1月",
        "min_shares"     : 100,
        "yutai_value"    : 1000,
        "share_tiers"    : [
            {"shares": 100, "benefit": "クオカード 1,000円"},
        ],
        "long_hold_bonus": "なし",
        "notes"          : "",
    },
    "1925": {
        "yutai"          : "クオカード（500円）",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 500,
        "share_tiers"    : [
            {"shares": 100, "benefit": "クオカード 500円"},
        ],
        "long_hold_bonus": "なし",
        "notes"          : "",
    },
    "3003": {
        "yutai"          : "クオカード（1,000円）",
        "kenri_month"    : "12月",
        "min_shares"     : 100,
        "yutai_value"    : 1000,
        "share_tiers"    : [
            {"shares": 100,  "benefit": "クオカード 1,000円"},
            {"shares": 1000, "benefit": "クオカード 3,000円"},
        ],
        "long_hold_bonus": "3年以上でグレードアップ",
        "notes"          : "",
    },
  KENRI_MAP = {
    "1821": "3月",  "1929": "3月",  "1941": "3月",  "1944": "3月",
    "1945": "3月",  "1951": "3月",  "2207": "3月",  "2208": "3月",
    "2216": "12月", "2411": "3月",  "2432": "3月",  "2492": "9月",
    "2659": "2月",  "2698": "2月",  "2768": "3月",  "2910": "3月",
    "2936": "3月",  "3048": "8月",  "3240": "1月・7月", "3283": "2月・8月",
    "3333": "3月",  "3577": "3月",  "3659": "12月", "3697": "8月",
    "3865": "3月",  "3994": "11月", "4041": "3月",  "4091": "3月",
    "4151": "12月", "4159": "3月",  "4206": "3月",  "4217": "3月",
    "4462": "3月",  "4471": "3月",  "4480": "12月", "4506": "3月",
    "4512": "3月",  "4541": "3月",  "4549": "3月",  "4555": "3月",
    "4560": "12月", "4563": "12月", "4566": "12月", "4812": "3月",
    "6146": "6月",  "6674": "3月",  "6724": "3月",  "6727": "3月",
    "6740": "3月",  "6745": "3月",  "6753": "3月",  "6770": "3月",
    "6794": "3月",  "6807": "3月",  "7282": "3月",  "7296": "3月",
    "7312": "3月",  "7315": "3月",  "7321": "3月",  "8016": "2月",
    "8025": "3月",  "8036": "3月",  "8242": "3月",  "8248": "3月",
    "8951": "2月・8月", "9024": "3月", "9025": "3月",
}

# 追加ブロックを生成
lines = []
lines.append("")
lines.append("    # ══ Phase1追加（P3-2）: 権利確定月のみ登録。優待内容はPhase2で拡充予定 ══")
for code in sorted(KENRI_MAP.keys()):
    month = KENRI_MAP[code]
    lines.append(f"    # Phase2で優待内容を拡充予定")
    lines.append(f'    "{code}": {{')
    lines.append(f'        "yutai"          : "調査中",')
    lines.append(f'        "kenri_month"    : "{month}",')
    lines.append(f'        "min_shares"     : 100,')
    lines.append(f'        "yutai_value"    : 0,')
    lines.append(f'        "share_tiers"    : [],')
    lines.append(f'        "long_hold_bonus": "なし",')
    lines.append(f'        "notes"          : "",')
    lines.append(f'    }},')

insert_block = "\n".join(lines)

with open("/home/claude/yutai_data_p32.py") as f:
    content = f.read()

# YUTAI_DATA の閉じ括弧直前に挿入
old = "\n}\n\n\ndef get_yutai"
new = insert_block + "\n}\n\n\ndef get_yutai"
result = content.replace(old, new, 1)

if result == content:
    print("ERROR: 挿入位置が見つかりませんでした")
else:
    with open("/home/claude/yutai_data_p32.py", "w") as f:
        f.write(result)
    print("追加完了")
}


def get_yutai(code: str) -> dict:
    """証券コードに対応する優待情報を返す"""
    return YUTAI_DATA.get(code, {
        "yutai"          : "データなし（公式サイトでご確認ください）",
        "kenri_month"    : "―",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "―",
        "notes"          : "",
    })


def yutai_score(code: str) -> float:
    """優待の充実度を0〜10点で返す（スコアリング用）"""
    val = get_yutai(code).get("yutai_value", 0)
    if   val >= 5000: return 10.0
    elif val >= 3000: return 8.0
    elif val >= 1500: return 6.5
    elif val >= 1000: return 5.0
    elif val >  0   : return 3.5
    else            : return 1.5
