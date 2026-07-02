"""
yutai_data.py  v8.0
====================
株主優待マスターデータ（④詳細表示対応版）

【v7.0 追加フィールド】
  long_hold_bonus: 長期保有優遇内容
  share_tiers    : 株数別優待内容リスト
  notes          : 補足・注意事項

【v8.0 P3-2 Phase1追加】
  フォールバック3月固定だった67銘柄の権利確定月を登録
  yutai="調査中" で最小構成。Phase2で優待内容を拡充予定。
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

    # ══ Phase1追加（P3-2）: 権利確定月のみ登録。優待内容はPhase2で拡充予定 ══
    # P3-2 Phase2 グループC調査済み
    "1821": {
        "yutai"          : "なし",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "Yahoo!ファイナンスで「株主優待情報はありません」と明記",
    },
    # P3-2 Phase2 グループC調査済み
    "1929": {
        "yutai"          : "なし",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "情報サイトで「株主優待がありません」と明記。麻生グループ傘下の特殊土木大手",
    },
    # P3-2 Phase2 グループC調査済み（権利月を3月→6月・12月に訂正）
    "1941": {
        "yutai"          : "優待ポイント（5,000種類以上の商品と交換可能）",
        "kenri_month"    : "6月・12月",
        "min_shares"     : 100,
        "yutai_value"    : 3000,
        "share_tiers"    : [],
        "long_hold_bonus": "継続保有期間に応じてデジタルギフトの内容が変動",
        "notes"          : "年2回（6月末・12月末）権利確定。保有株式数に応じて優待ポイントを贈呈し5,000種類以上の商品と交換可能",
    },
    # P3-2 Phase2 グループC調査済み
    "1944": {
        "yutai"          : "なし",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "Yahoo!ファイナンスで「株主優待情報はありません」と明記。関西電力系電気工事大手",
    },
    # P3-2 Phase2 グループC調査済み（重要：コード対応関係に疑義あり）
    "1945": {
        "yutai"          : "カタログギフト（食品・雑貨等・自然保護団体への寄付選択可）",
        "kenri_month"    : "6月",
        "min_shares"     : 200,
        "yutai_value"    : 2000,
        "share_tiers"    : [],
        "long_hold_bonus": "1年以上かつ200株以上、または3年以上かつ500株以上で対象",
        "notes"          : "【要確認】candidate_stocks.py記載名「東京電力EP」だが証券コード1945の実企業は「東京エネシス」（東京電力グループの設備工事会社）。東京電力EPは非上場・東京電力HDはコード9501",
    },
    # P3-2 Phase2 グループC調査済み
    "1951": {
        "yutai"          : "なし（優待制度廃止）",
        "kenri_month"    : "3月・12月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "2025年3月権利分をもって株主優待制度を廃止。株主平等性の観点から配当による利益還元に集約する方針",
    },
    # P3-2 Phase2 グループB調査済み（権利月を3月→3月・9月に訂正）
    "2207": {
        "yutai"          : "自社グループ商品詰め合わせ（お菓子）",
        "kenri_month"    : "3月・9月",
        "min_shares"     : 100,
        "yutai_value"    : 1500,
        "share_tiers"    : [
            {"shares": 100,  "benefit": "自社グループ商品 1,500円相当（9月）"},
            {"shares": 200,  "benefit": "自社グループ商品 2,000円相当（3月・9月）"},
        ],
        "long_hold_bonus": "なし",
        "notes"          : "アルファベットチョコレート等で知られる菓子メーカー。2021年に200株以上の株主への3月優待を新設し年2回化",
    },
    # P3-2 Phase2 グループB調査済み（権利月を3月→9月に訂正・要再確認）
    "2208": {
        "yutai"          : "自社グループ商品詰め合わせ（菓子・飲料・食品等）",
        "kenri_month"    : "9月",
        "min_shares"     : 100,
        "yutai_value"    : 1200,
        "share_tiers"    : [
            {"shares": 100,  "benefit": "商品詰め合わせ 1,200円相当（6ヶ月以上保有）"},
            {"shares": 200,  "benefit": "商品詰め合わせ 3,000円相当"},
            {"shares": 1000, "benefit": "詰め合わせ3,000円+オンラインクーポン3,000円"},
        ],
        "long_hold_bonus": "3年以上継続保有で優待価額が200〜1,000円相当増額",
        "notes"          : "アルフォート・ルマンド等で有名な菓子メーカー。6ヶ月以上の継続保有が条件。3月権利の有無は要再確認",
    },
    # P3-2 Phase2 グループB調査済み（権利月12月→6月に訂正）
    "2216": {
        "yutai"          : "クオカード（1,000円分）",
        "kenri_month"    : "6月",
        "min_shares"     : 100,
        "yutai_value"    : 1000,
        "share_tiers"    : [
            {"shares": 100,  "benefit": "クオカード 1,000円分"},
            {"shares": 1000, "benefit": "クオカード+プレミアム優待倶楽部ポイント（四半期毎）"},
        ],
        "long_hold_bonus": "なし",
        "notes"          : "カンロ飴・ピュレグミ等の菓子メーカー。権利確定は6月末（Phase1の12月から訂正）",
    },
    # P3-2 Phase2 グループC調査済み
    "2411": {
        "yutai"          : "なし",
        "kenri_month"    : "3月・9月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "株主掲示板にて優待新設を求める投稿が複数見られ、現時点では優待未実施と判断",
    },
    # P3-2 Phase2 グループB調査済み（権利月を3月→9月に訂正）
    "2432": {
        "yutai"          : "川崎ブレイブサンダース観戦チケット引換証・横浜DeNAベイスターズ関連クーポン",
        "kenri_month"    : "9月",
        "min_shares"     : 100,
        "yutai_value"    : 3900,
        "share_tiers"    : [
            {"shares": 100, "benefit": "観戦チケット引換証1枚+ファンクラブクーポン+グッズ10%オフ+施設入館券"},
            {"shares": 300, "benefit": "観戦チケット引換証3枚+ファンクラブクーポン3,000円オフ+グッズ10%オフ+施設入館券"},
        ],
        "long_hold_bonus": "なし",
        "notes"          : "横浜DeNAベイスターズ・川崎ブレイブサンダースのオーナー企業。権利確定は9月末（Phase1の3月から訂正）",
    },
    # P3-2 Phase2 グループC調査済み（権利月3月→12月に訂正）
    "2492": {
        "yutai"          : "なし",
        "kenri_month"    : "12月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "Yahoo!ファイナンスで「株主優待情報はありません」と明記。決算日は12月31日",
    },
    # P3-2 Phase2 グループA調査済み
    "2659": {
        "yutai"          : "自社商品券・VJAギフトカード（2,000円相当〜）",
        "kenri_month"    : "2月",
        "min_shares"     : 100,
        "yutai_value"    : 2000,
        "share_tiers"    : [
            {"shares": 200,  "benefit": "商品券 2,000円相当"},
            {"shares": 500,  "benefit": "商品券 3,000円相当"},
            {"shares": 1000, "benefit": "商品券 5,000円相当"},
        ],
        "long_hold_bonus": "なし",
        "notes"          : "沖縄県在住者は自社商品券、県外は三井住友VJAギフトカード。優待は200株以上から",
    },
    # P3-2 Phase2 グループA調査済み
    "2698": {
        "yutai"          : "自社店舗優待券（100円＋税相当・2,000円〜）",
        "kenri_month"    : "2月・8月",
        "min_shares"     : 100,
        "yutai_value"    : 2000,
        "share_tiers"    : [
            {"shares": 100,  "benefit": "優待券20枚（2,000円相当）"},
            {"shares": 300,  "benefit": "優待券40枚（4,000円相当）"},
            {"shares": 500,  "benefit": "優待券60枚（6,000円相当）"},
            {"shares": 1000, "benefit": "優待券100枚（10,000円相当）"},
        ],
        "long_hold_bonus": "3年以上継続保有（300株以上）で優待券追加進呈",
        "notes"          : "100円ショップキャンドゥの店舗で使える優待券。権利確定日は8月末",
    },
    # P3-2 Phase2 グループC調査済み
    "2768": {
        "yutai"          : "なし",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "Yahoo!ファイナンスで「株主優待情報はありません」と明記",
    },
    # P3-2 Phase2 グループB調査済み（権利月3月→4月・10月に訂正）
    "2910": {
        "yutai"          : "自社店舗お惣菜券",
        "kenri_month"    : "4月・10月",
        "min_shares"     : 100,
        "yutai_value"    : 2000,
        "share_tiers"    : [
            {"shares": 100,  "benefit": "おそうざい券1,000円分（年2回・合計2,000円）"},
            {"shares": 1000, "benefit": "おそうざい券10,000円分（年2回・合計20,000円・5年未満）"},
        ],
        "long_hold_bonus": "5年以上の継続保有で優待額が変動",
        "notes"          : "RF1等のデパ地下サラダ店を展開。年2回（4月末・10月末）権利確定。近隣店舗がない場合は電子クーポンに交換可",
    },
    # P3-2 Phase2 グループB調査済み（重要：コード重複の可能性あり）
    "2936": {
        "yutai"          : "自社サービス優待クーポン（1,500円相当）",
        "kenri_month"    : "2月・8月",
        "min_shares"     : 100,
        "yutai_value"    : 1500,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "【要確認】Web検索結果ではコード2936は「ベースフード」として表示され、candidate_stocks.py記載の「すぎたホールディングス」と一致しない。2025年1月に優待制度新設。コード対応関係の確認が必要",
    },
    # P3-2 Phase2 グループA調査済み
    "3048": {
        "yutai"          : "グループ店舗優待買物割引券（1,000円相当〜）",
        "kenri_month"    : "8月",
        "min_shares"     : 100,
        "yutai_value"    : 1000,
        "share_tiers"    : [],
        "long_hold_bonus": "1年以上かつ200株以上、または3年以上かつ500株以上でカタログギフトを追加贈呈",
        "notes"          : "ビックカメラ・コジマ・ソフマップ等グループ店舗及び通販で利用可。年2回権利確定（2月・8月）",
    },
    # P3-2 Phase2 グループB調査済み
    "3240": {
        "yutai"          : "なし（REITのため制度上対象外）",
        "kenri_month"    : "1月・7月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "野村不動産マスターファンド投資法人。REITのため一般的に株主優待制度を実施しない",
    },
    # P3-2 Phase2 グループB調査済み
    "3283": {
        "yutai"          : "なし（REITのため制度上対象外）",
        "kenri_month"    : "2月・8月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "日本プロロジスリート投資法人。物流施設特化型REIT。REITのため一般的に株主優待制度を実施しない",
    },
    # P3-2 Phase2 グループA調査済み
    "3333": {
        "yutai"          : "なし（優待制度廃止）",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "2023年2月権利分をもって株主優待制度を廃止済み",
    },
    # P3-2 Phase2 グループC調査済み
    "3577": {
        "yutai"          : "自社オンラインストア利用クーポン",
        "kenri_month"    : "6月・12月",
        "min_shares"     : 300,
        "yutai_value"    : 1000,
        "share_tiers"    : [],
        "long_hold_bonus": "1年以上継続保有が条件",
        "notes"          : "6月20日・12月20日基準日、300株以上保有株主が対象",
    },
    # P3-2 Phase2 グループB調査済み
    "3659": {
        "yutai"          : "なし",
        "kenri_month"    : "12月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "Yahoo!ファイナンス・kabuyutai.com双方で優待制度の実施情報なしと確認。オンラインゲーム大手",
    },
    # P3-2 Phase2 グループC調査済み
    "3697": {
        "yutai"          : "QUOカード（3月）・さぬきうどん・無洗米等（9月）",
        "kenri_month"    : "3月・9月",
        "min_shares"     : 100,
        "yutai_value"    : 1500,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "3月末株主にQUOカード、9月末株主に地元特産品を贈呈",
    },
    # P3-2 Phase2 グループC調査済み
    "3865": {
        "yutai"          : "QUOカードPay・QUOカード",
        "kenri_month"    : "3月・9月",
        "min_shares"     : 100,
        "yutai_value"    : 1000,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "3月末200株以上、9月末100株以上保有株主が対象",
    },
    # P3-2 Phase2 グループC調査済み（権利月11月→5月・11月に訂正）
    "3994": {
        "yutai"          : "自社サービス利用クーポン・イベント特典",
        "kenri_month"    : "5月・11月",
        "min_shares"     : 100,
        "yutai_value"    : 1000,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "5月末・11月末時点で100株以上・半年以上継続保有が条件",
    },
    # P3-2 Phase2 グループC調査済み
    "4041": {
        "yutai"          : "なし",
        "kenri_month"    : "3月・9月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "日経で「株主優待 無」と明記。精密化学・農薬大手",
    },
    # P3-2 Phase2 グループC調査済み
    "4091": {
        "yutai"          : "優待商品（1,000株以上で温泉旅館利用券も）",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 1500,
        "share_tiers"    : [
            {"shares": 100,   "benefit": "優待商品"},
            {"shares": 1000,  "benefit": "優待商品+自社グループ温泉旅館利用券"},
        ],
        "long_hold_bonus": "長期保有株主向けにグレードの高いカタログギフトあり",
        "notes"          : "産業ガス最大手。長期保有優遇制度あり",
    },
    # P3-2 Phase2 グループC調査済み（優待有無を明確化できず・要再確認）
    "4151": {
        "yutai"          : "なし",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "コード対応確認済み（irbank.net・Yahoo!ファイナンス）。Yahoo!ファイナンス公式ページで「株主優待情報はありません」と明記",
    },
    # P3-2 Phase2 グループC調査済み（重要：コード対応関係に疑義あり）
    "4159": {
        "yutai"          : "調査中",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "【要確認】ジェイ・エム・エス（JMS）の正しい証券コードは7702（irbank.net・みんかぶ・Wikipedia等の複数独立ソースで確認）。4159の実企業を複数ソースで検索したが特定できず。candidate_stocks.py修正タスクへの追加候補",
    },
    # P3-2 Phase2 グループC調査済み
    "4206": {
        "yutai"          : "なし",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "Yahoo!ファイナンスで「株主優待情報はありません」と明記。化粧板・接着剤製造大手",
    },
    # P3-2 Phase2 グループC調査済み（要再確認）
    "4217": {
        "yutai"          : "なし（上場廃止）",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "【要確認】日立化成は昭和電工（現レゾナック）によるTOBで完全子会社化され、2020年6月19日付で東証一部上場廃止確定（適時開示で確認）。candidate_stocks.pyからの削除を推奨",
    },
    # P3-2 Phase2 グループC調査済み（重要：コード対応関係に疑義あり）
    "4462": {
        "yutai"          : "自社商品・QUOカード・寄付から選択",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 1000,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "【要確認】candidate_stocks.py記載名「石原産業」だが証券コード4462の実企業は「石原ケミカル」。石原産業の実際の証券コードは4028",
    },
    # P3-2 Phase2 グループC調査済み（権利月3月→3月・9月に訂正）
    "4471": {
        "yutai"          : "QUOカード（年2回贈呈）",
        "kenri_month"    : "3月・9月",
        "min_shares"     : 100,
        "yutai_value"    : 1000,
        "share_tiers"    : [],
        "long_hold_bonus": "長期保有優待制度あり",
        "notes"          : "所有株式数に応じてQUOカードを年2回贈呈。京都拠点の化学品メーカー",
    },
    # P3-2 Phase2 グループC調査済み（権利月3月→12月に訂正）
    "4480": {
        "yutai"          : "なし",
        "kenri_month"    : "12月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "Yahoo!ファイナンスで「株主優待情報はありません」と明記。決算期12月のため権利月を訂正",
    },
    # P3-2 Phase2 グループC調査済み（権利月3月→9月に訂正）
    "4506": {
        "yutai"          : "QUOカード（保有株数・継続年数に応じて）",
        "kenri_month"    : "9月",
        "min_shares"     : 100,
        "yutai_value"    : 1000,
        "share_tiers"    : [],
        "long_hold_bonus": "継続保有年数に応じてQUOカード金額が変動",
        "notes"          : "毎年9月末時点の100株以上保有株主が対象",
    },
    # P3-2 Phase2 グループC調査済み
    "4512": {
        "yutai"          : "なし",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "Yahoo!ファイナンスで「株主優待情報はありません」と明記",
    },
    # P3-2 Phase2 グループC調査済み
    "4541": {
        "yutai"          : "なし",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "Yahoo!ファイナンスで優待情報の記載なし。後発医薬品メーカー",
    },
    # P3-2 Phase2 グループC調査済み（権利月を3月→5月・11月に訂正）
    "4549": {
        "yutai"          : "なし",
        "kenri_month"    : "5月・11月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "Yahoo!ファイナンスで「株主優待情報はありません」と明記。権利確定日は5月20日・11月20日",
    },
    # P3-2 Phase2 グループC調査済み
    "4555": {
        "yutai"          : "なし",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "Yahoo!ファイナンスで「株主優待情報はありません」と明記。後発医薬品最大手",
    },
    # P3-2 Phase2 グループC調査済み（重要：コード対応関係に疑義あり）
    "4560": {
        "yutai"          : "なし",
        "kenri_month"    : "12月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "【要確認】candidate_stocks.py記載名「そーせいグループ」の実際の証券コードは4565（現ネクセラファーマ）。4565は「株主優待がありません」と確認",
    },
    # P3-2 Phase2 グループC調査済み
    "4563": {
        "yutai"          : "なし",
        "kenri_month"    : "12月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "遺伝子医薬品開発の創薬ベンチャー。優待情報の記載を確認できず",
    },
    # P3-2 Phase2 グループC調査済み（重要：コード対応関係に疑義あり）
    "4566": {
        "yutai"          : "なし",
        "kenri_month"    : "12月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "【要確認】candidate_stocks.py記載名「ラクオリア創薬」の実際の証券コードは4579",
    },
    # P3-2 Phase2 グループC調査済み
    "4812": {
        "yutai"          : "なし",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "Yahoo!ファイナンスで「株主優待情報はありません」と明記。電通グループのシステム開発会社",
    },
    # P3-2 Phase2 グループC調査済み（権利月3月→9月に訂正）
    "6146": {
        "yutai"          : "自社製品（食品詰め合わせ選択制）",
        "kenri_month"    : "9月",
        "min_shares"     : 500,
        "yutai_value"    : 1500,
        "share_tiers"    : [],
        "long_hold_bonus": "長期保有株主向け優待あり",
        "notes"          : "9月30日現在500株以上保有株主が対象。半導体製造装置大手",
    },
    # P3-2 Phase2 グループC調査済み（他社情報混在・要再確認）
    "6674": {
        "yutai"          : "なし",
        "kenri_month"    : "3月・9月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "コード対応確認済み（irbank.net）。Yahoo!ファイナンスで「株主優待情報はありません」と明記",
    },
    # P3-2 Phase2 グループC調査済み（権利月3月→12月に訂正）
    "6724": {
        "yutai"          : "優待ポイント（オークネット・プレミアム優待倶楽部）",
        "kenri_month"    : "12月",
        "min_shares"     : 300,
        "yutai_value"    : 1500,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "12月末日時点で300株以上保有株主が対象。プリンター大手",
    },
    # P3-2 Phase2 グループC調査済み（要再確認）
    "6727": {
        "yutai"          : "なし",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "コード対応確認済み（irbank.net）。複数の優待紹介サイトで具体的な優待内容の記載が確認できず、優待なしと判定",
    },
    # P3-2 Phase2 グループC調査済み
    "6740": {
        "yutai"          : "なし",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "Yahoo!ファイナンスで「株主優待情報はありません」と明記",
    },
    # P3-2 Phase2 グループB調査済み
    "6745": {
        "yutai"          : "なし",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "Yahoo!ファイナンスで「株主優待情報はありません」と明記。火災報知機・消火設備大手メーカー",
    },
    # P3-2 Phase2 グループC調査済み（要再確認）
    "6753": {
        "yutai"          : "なし",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "コード対応確認済み（irbank.net）。Yahoo!ファイナンス公式ページで「株主優待情報はありません」と明記",
    },
    # P3-2 Phase2 グループC調査済み
    "6770": {
        "yutai"          : "なし",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "Yahoo!ファイナンスで「株主優待情報はありません」と明記",
    },
    # P3-2 Phase2 グループC調査済み（優待廃止済み）
    "6794": {
        "yutai"          : "なし（優待制度廃止）",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "2023年3月権利分をもって株主優待制度を廃止",
    },
    # P3-2 Phase2 グループC調査済み
    "6807": {
        "yutai"          : "なし",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "Yahoo!ファイナンスで「株主優待情報はありません」と明記",
    },
    # P3-2 Phase2 グループC調査済み
    "7282": {
        "yutai"          : "QUOカード（年2回贈呈）",
        "kenri_month"    : "3月・9月",
        "min_shares"     : 100,
        "yutai_value"    : 1000,
        "share_tiers"    : [],
        "long_hold_bonus": "長期保有優待制度あり",
        "notes"          : "所有株式数に応じてQUOカードを年2回贈呈",
    },
    # P3-2 Phase2 グループC調査済み
    "7296": {
        "yutai"          : "地元特産品（2,500円相当）",
        "kenri_month"    : "3月・9月",
        "min_shares"     : 200,
        "yutai_value"    : 2500,
        "share_tiers"    : [],
        "long_hold_bonus": "継続保有期間1年以上で条件あり",
        "notes"          : "200株保有から優待対象",
    },
    # P3-2 Phase2 グループC調査済み
    "7312": {
        "yutai"          : "なし",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "Yahoo!ファイナンスで「株主優待情報はありません」と明記",
    },
    # P3-2 Phase2 グループC調査済み
    "7315": {
        "yutai"          : "なし",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "優待情報の記載が確認できず優待なしと推定",
    },
    # P3-2 Phase2 グループC調査済み（要再確認）
    "7321": {
        "yutai"          : "なし（非上場企業）",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "【要確認】日本自動車部品総合研究所（現SOKEN株式会社）はデンソーとトヨタ自動車の出資による会社であり、有価証券報告書上「連結子会社」の扱いのため上場企業ではない。証券コード7321自体が誤りの可能性が高い。candidate_stocks.pyからの削除を推奨",
    },
    # P3-2 Phase2 グループA調査済み
    "8016": {
        "yutai"          : "自社ECサイト割引クーポン（20%割引）・ギフトカタログ",
        "kenri_month"    : "2月",
        "min_shares"     : 100,
        "yutai_value"    : 1000,
        "share_tiers"    : [
            {"shares": 100,  "benefit": "ECサイト20%割引クーポン（6回分）"},
            {"shares": 1000, "benefit": "クーポン+ギフトカタログ3,000円相当（1年以上保有）"},
        ],
        "long_hold_bonus": "1年以上保有でギフトカタログ進呈・3年以上でさらに増額",
        "notes"          : "ECサイト「オンワード・クローゼット」で使える割引クーポン。権利確定は2月末",
    },
    # P3-2 Phase2 グループA調査済み（一部未確認）
    "8025": {
        "yutai"          : "自社特別企画品（詳細調査中）",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "優待制度自体は存在するが金額・内容の詳細出典が不十分。次回追加調査が必要",
    },
    # P3-2 Phase2 グループC調査済み（重要：上場廃止企業）
    "8036": {
        "yutai"          : "なし（上場廃止）",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "【要確認】日立ハイテクは2020年5月に日立製作所によるTOB・株式売渡請求により上場廃止済み。candidate_stocks.pyからの削除を推奨",
    },
    # P3-2 Phase2 グループA調査済み
    "8242": {
        "yutai"          : "株主優待券（自社グループ百貨店・食品スーパー等で利用可）",
        "kenri_month"    : "3月・9月",
        "min_shares"     : 100,
        "yutai_value"    : 1000,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "阪急阪神百貨店等グループ店舗で利用可能な優待券。年2回（3月・9月）権利確定",
    },
    # P3-2 Phase2 グループC調査済み（要再確認）
    "8248": {
        "yutai"          : "なし（上場廃止）",
        "kenri_month"    : "3月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "【要確認】candidate_stocks.py記載名「ジュニア」だが証券コード8248の実企業は「ニッセンホールディングス」（irbank.net確認）。ニッセンHDは2016年10月27日にセブン&アイHD傘下で東証一部上場廃止済み。candidate_stocks.pyからの削除を推奨",
    },
    # P3-2 Phase2 グループB調査済み
    "8951": {
        "yutai"          : "なし（REITのため制度上対象外）",
        "kenri_month"    : "2月・8月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "J-REIT最古参の一つ。REITは投資法人のため一般的に株主優待制度を実施しない",
    },
    # P3-2 Phase2 グループA調査済み
    "9024": {
        "yutai"          : "株主優待乗車証（西武線・西武バス全線片道きっぷ）",
        "kenri_month"    : "3月・9月",
        "min_shares"     : 100,
        "yutai_value"    : 320,
        "share_tiers"    : [
            {"shares": 100,   "benefit": "片道きっぷ2枚（3月のみ）"},
            {"shares": 1000,  "benefit": "片道きっぷ10枚"},
            {"shares": 10000, "benefit": "電車全線パス1枚"},
        ],
        "long_hold_bonus": "3年以上継続保有（3,000株以上）で片道きっぷ5枚追加",
        "notes"          : "西武鉄道・西武バス全線で利用可能な乗車証。施設利用優待券（レストラン・ゴルフ割引等）も付帯",
    },
    # P3-2 Phase2 グループC調査済み
    "9025": {
        "yutai"          : "なし",
        "kenri_month"    : "3月・9月",
        "min_shares"     : 100,
        "yutai_value"    : 0,
        "share_tiers"    : [],
        "long_hold_bonus": "なし",
        "notes"          : "ダイヤモンド・ザイ記事で「株主優待を実施していない」と明記",
    },
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
