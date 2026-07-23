# 株ラボ v9 Research Architecture Specification
Version: v9 Research Design Freeze  
Status: Design Frozen  
Scope: Research Environment Only  
Production Impact: ZERO
---
# 1. 目的
本ドキュメントは、株ラボ v9研究環境の正式アーキテクチャを定義する。
v9研究では、v8.1 Stableを完全保護しながら、
- 投資判断ロジック改善
- Walk Forward検証
- パラメータ研究
- 戦略比較
- 長期投資向け評価指標検証
を行う。
本設計は実装前の凍結仕様であり、
コード変更・UI変更・既存ファイル変更を伴わない。
---
# 2. 最重要原則
## v8.1 Stable完全保護
以下は変更禁止。

app.py

strategy_v8.py

既存backtestモジュール

Config Manager

settings.json

既存UI

既存判定ロジック

v9研究は必ず独立環境で実施する。
---
# 3. v9研究環境構成

research/

├── research_app.py

├── views/
│
├── strategy/
│
├── evaluation/
│
├── storage/
│
├── config/
│
└── logs/

---
# 4. 起動方式
本番環境

streamlit run app.py

研究環境

streamlit run research/research_app.py

完全分離する。
research_app.pyはapp.pyをimportしない。
---
# 5. 研究テーマ
## Phase1研究対象
優先順位：

1. RSI改善
2. 出来高改善
3. 配当性向評価
4. PER業種別最適化

---
# 6. 研究テーマ追加ルール
1テーマ = 1責務
例：

strategy/

├── rsi/

├── volume/

├── dividend/

└── per_sector/

テーマ間ロジック混在は禁止。
---
# 7. Walk Forward検証設計
## 基本方式
Rolling Walk Forward方式を採用。
構成：

Training期間

↓

Validation期間

↓

Forward期間

---
## 基本条件
Training:
3年
Validation:
6ヶ月ローリング
Forward:
6ヶ月〜1年
Forwardは最終確認専用。
結果確認後の再調整は禁止。
---
# 8. Baseline管理
Baselineは固定する。
基準：

v8.1 Stable

比較対象：

v8.1 Stable

現在まで採用済みのv9累積版

---
例：
Phase1 RSI
比較：

v8.1

vs

v9_step01_rsi

Phase2 出来高
比較：

v8.1

vs

v9_step01_rsi

vs

v9_step02_rsi_volume

---
# 9. 最終総合検証
全テーマ採用後、
必ず総合Walk Forwardを実施する。
理由：
個別テーマ改善の合計が
全体改善になる保証はないため。
工程：

RSI改善

↓

出来高改善

↓

配当性向改善

↓

PER改善

↓

総合v9検証

---
# 10. RSI研究開始前の必須確認
RSI研究前に対象範囲を固定する。
確認対象：
- ConfigManager管理値
- technical_analysis内部閾値
- buy_timing内部閾値
研究対象外の値を明確化する。
---
# 11. 評価指標
## 必須評価
優先順位：
1.
最大ドローダウン
2.
配当込みトータルリターン
3.
リスクリワード
4.
平均利益
5.
平均損失
6.
勝率
---
## 追加評価候補
研究成熟後に追加。

Calmar Ratio

Sortino Ratio

Time Underwater

平均保有期間

回転率

セクター集中度

---
# 12. 採用基準
研究テーマ採用条件：
## 必須

最大DD悪化なし

AND

トータルリターン改善

---
## 再現性
Rolling期間の70%以上で改善。
---
## 最終確認
Forward期間でも改善。
Forward悪化の場合：
採用不可。
---
# 13. 過学習対策
禁止事項：
- 無制限パラメータ探索
- Forward結果を見た再調整
- 結果が良い期間だけ採用
- 単一銘柄依存
---
研究ルール：
- 候補は3〜5案以内
- 仮説ベースで設定
- Rolling複数期間で確認
- 銘柄横断確認を行う
---
# 14. データ固定ルール
Baseline比較のため、
以下を固定管理する。
- 対象銘柄リスト
- 株価データ期間
- 使用データ取得日時
- 評価条件
同じ条件で再実行できる状態を維持する。
---
# 15. Survivor Bias対策
現行銘柄のみで検証する場合、
結果には生存者バイアスが含まれる可能性がある。
対応：
- 制約を明記
- 結果解釈時に考慮
- 将来的に過去銘柄データ対応を検討
---
# 16. 研究ストレージ
本番保存領域とは分離する。

research/storage/

├── results/

├── experiments/

├── comparisons/

└── adoption_history/

---
# 17. 研究担当分担
## Claude①
担当：
ロジック研究
対象：
- technical_analysis
- buy_timing
- recommend
- scoring
- Walk Forward評価
責務：
研究テーマの妥当性確認
改善案作成
検証結果レビュー
---
## Claude②
担当：
プラットフォーム研究
対象：
- research_app
- UI
- storage
- config分離
- 履歴管理
責務：
研究環境構築
UI管理
データ管理
---
# 18. 実装ロードマップ
## Phase5
### 研究環境基盤構築
担当：
Claude②
目的：
v8.1と完全分離したresearch環境作成
成果物：
- research_app.py
- researchディレクトリ
- storage設計
- config分離
完了条件：
v8.1が無変更で起動確認
---
## Phase6
### RSI研究実装
担当：
Claude①
目的：
最初の研究テーマ検証
成果物：
- RSI候補セット
- Walk Forward結果
- v8比較結果
完了条件：
採用/不採用判断
---
## Phase7
### 出来高研究
担当：
Claude①
目的：
出来高改善検証
完了条件：
採用判断
---
## Phase8
### 配当性向研究
担当：
Claude①
目的：
長期保有適性改善
完了条件：
採用判断
---
## Phase9
### PER業種別研究
担当：
Claude①
目的：
業種補正検証
前提：
業種データ品質確認済み
完了条件：
採用判断
---
## Phase10
### v9総合検証
担当：
Claude① + Claude②
目的：
全改善要素を統合した最終評価
完了条件：
v8.1 Stableとの差分確認
---
# 19. 絶対遵守ルール
重要度順：
## 1位
v8.1 Stableへ影響を与えない。
---
## 2位
研究結果は必ずBaseline比較する。
---
## 3位
Forward期間を守る。
---
## 4位
勝率だけで判断しない。
---
## 5位
個別改善後に必ず総合検証する。
---
## 6位
研究途中で既存backtestを改変しない。
---
# 20. 設計状態
現在状態：

Architecture Design

↓

Frozen

↓

Implementation Ready

次工程：
Phase5 Research Environment Construction
---
End of Specification
