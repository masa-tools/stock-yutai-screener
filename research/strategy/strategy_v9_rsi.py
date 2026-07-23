"""
research/strategy/strategy_v9_rsi.py
=====================================
v9研究 Phase6-2 : RSI研究専用スコアリングエンジン

【目的】
  「RSI条件変更が長期投資成果を改善するか」を検証するための、
  research環境専用の独立したRSI評価エンジン。

【設計方針（重要）】
  本モジュールは v8.1 の buy_timing.py / technical_analysis.py /
  scoring_config.py / investment_judge.py の実装を一切 import しない。
  それらのファイルは仕様として不変（絶対変更禁止）であり、
  研究側が意図せず本番仕様に結合されることを防ぐため、
  評価ロジックはこのファイル内で完結する独立実装とする。

  候補（A〜E）ごとの閾値・仮説は
  research/config/research_settings.json から取得する。
  このJSONも「研究条件の定義」のみを保持し、実験結果・採用判断は
  一切含まない（Phase6-1で確定した設計）。

【本Phaseで実装する範囲】
  ① candidate A〜E の管理
  ② research_settings.json からの候補条件取得
  ③ RSI値からの研究用スコア算出
  ④ candidate 切替機能
  ⑤ 仮説情報の取得

【本Phaseで実装しない範囲（絶対禁止）】
  ・Walk Forward runner との接続
  ・backtest runner との接続
  ・baselineとの比較処理
  ・storageへの保存処理
  ・UI（views/の責務）

【他モジュールとの関係】
  ・v8.1側（app.py, strategy_v8.py, buy_timing.py, technical_analysis.py,
    scoring_config.py, investment_judge.py, settings.json, 既存backtest）
    への import・参照は一切行わない。
  ・保存処理は research/storage/ 側の責務、Walk Forward接続は
    research/evaluation/ または runner呼び出し側の責務であり、
    本ファイルはそれらを呼び出さない（Phase6-1完了報告の責務定義に準拠）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── 定数 ──────────────────────────────────────────────
# research_settings.json のデフォルト配置場所（研究環境内で完結させる）
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "research_settings.json"

# 想定する候補IDの正式リスト（Phase6-1で確定した5案）
VALID_CANDIDATE_IDS = ("A", "B", "C", "D", "E")

# RSIスコアの点数帯ラベル（表示・ログ用。判定文言そのものはUI側の責務）
_TIER_LABELS = (
    "oversold",            # 最も強い買いシグナル水準
    "slightly_oversold",   # やや売られすぎ
    "neutral_low",         # 中立帯（下寄り）
    "neutral_high",        # 中立帯（上寄り）
    "overbought_caution",  # やや過熱
    "overbought",          # 買われすぎ
)

# 各点数帯に対応する研究用スコア（合計50点満点構成の一部・15点上限）
# ※この点数配分自体もPhase6-1で定義した「5段階配点構造」の研究対象であり、
#   buy_timing.py からの値のコピーではなく、研究エンジン独自の定義として持つ。
_TIER_POINTS = (15, 12, 8, 5, 2, 0)


class ResearchSettingsError(Exception):
    """research_settings.json の読み込み・内容不備に関するエラー"""


@dataclass(frozen=True)
class RSIThresholds:
    """1候補分のRSI閾値セット"""
    oversold: float
    slightly_oversold: float
    neutral_low: float
    neutral_high: float
    overbought: float


@dataclass(frozen=True)
class RSICandidate:
    """1候補（A〜E）の完全な定義"""
    id: str
    name: str
    name_ja: str
    thresholds: RSIThresholds
    hypothesis: str
    expected_effect: str
    expected_weakness: str
    threshold_mapping_note: Optional[str] = None


@dataclass(frozen=True)
class RSIScoreResult:
    """score() の戻り値"""
    candidate_id: str
    rsi: float
    points: int
    tier: str


# ── 候補ロード ─────────────────────────────────────────
def load_candidates(config_path: Path | str = DEFAULT_CONFIG_PATH) -> dict[str, RSICandidate]:
    """
    research_settings.json から candidate 定義を読み込み、
    candidate_id -> RSICandidate の辞書として返す。

    v8.1側のファイルには一切依存しない、独立した読み込み処理。
    """
    path = Path(config_path)
    if not path.exists():
        raise ResearchSettingsError(f"research_settings.json が見つかりません: {path}")

    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        raise ResearchSettingsError(f"research_settings.json の解析に失敗しました: {e}") from e

    if raw.get("theme") != "rsi":
        raise ResearchSettingsError(
            f"theme が 'rsi' ではありません（{raw.get('theme')!r}）。"
            "誤って他テーマの設定ファイルを参照している可能性があります。"
        )

    candidates_raw = raw.get("candidates")
    if not candidates_raw:
        raise ResearchSettingsError("candidates が定義されていません。")

    candidates: dict[str, RSICandidate] = {}
    for c in candidates_raw:
        cid = c.get("id")
        if cid not in VALID_CANDIDATE_IDS:
            raise ResearchSettingsError(f"未知のcandidate id です: {cid!r}")

        th = c.get("thresholds", {})
        try:
            thresholds = RSIThresholds(
                oversold=th["oversold"],
                slightly_oversold=th["slightly_oversold"],
                neutral_low=th["neutral_low"],
                neutral_high=th["neutral_high"],
                overbought=th["overbought"],
            )
        except KeyError as e:
            raise ResearchSettingsError(f"candidate {cid} の閾値定義が不完全です: {e}") from e

        candidates[cid] = RSICandidate(
            id=cid,
            name=c.get("name", ""),
            name_ja=c.get("name_ja", ""),
            thresholds=thresholds,
            hypothesis=c.get("hypothesis", ""),
            expected_effect=c.get("expected_effect", ""),
            expected_weakness=c.get("expected_weakness", ""),
            threshold_mapping_note=c.get("threshold_mapping_note"),
        )

    missing = set(VALID_CANDIDATE_IDS) - set(candidates.keys())
    if missing:
        raise ResearchSettingsError(f"候補が不足しています: {sorted(missing)}")

    return candidates


# ── スコア計算（純粋関数） ─────────────────────────────────
def calc_rsi_research_score(rsi: float, thresholds: RSIThresholds) -> tuple[int, str]:
    """
    RSI値と閾値セットから、研究用スコア（点数・帯ラベル）を算出する純粋関数。

    独立した5段階の閾値判定であり、buy_timing.py の実装コードは
    参照していない（Phase6-1で定義した点数配分に基づく独自実装）。

    候補E（教科書型）のように一部閾値が同値の場合でも、
    以下のif-elif連鎖により自然に該当する帯へ畳み込まれる
    （例：oversold == slightly_oversold の場合、12点帯は事実上出現しない）。
    """
    if rsi <= thresholds.oversold:
        return _TIER_POINTS[0], _TIER_LABELS[0]
    if rsi <= thresholds.slightly_oversold:
        return _TIER_POINTS[1], _TIER_LABELS[1]
    if rsi <= thresholds.neutral_low:
        return _TIER_POINTS[2], _TIER_LABELS[2]
    if rsi <= thresholds.neutral_high:
        return _TIER_POINTS[3], _TIER_LABELS[3]
    if rsi <= thresholds.overbought:
        return _TIER_POINTS[4], _TIER_LABELS[4]
    return _TIER_POINTS[5], _TIER_LABELS[5]


# ── 研究エンジン本体 ────────────────────────────────────
class RSIResearchEngine:
    """
    RSI研究専用エンジン。

    candidate の管理・切替、RSIスコア算出、仮説情報の取得のみを担当する。
    Walk Forward接続・baseline比較・保存処理・UIは一切持たない
    （それらはPhase6-3以降、evaluation/・storage/・views/側の責務）。
    """

    def __init__(
        self,
        config_path: Path | str = DEFAULT_CONFIG_PATH,
        initial_candidate_id: str = "A",
    ) -> None:
        self._config_path = Path(config_path)
        self._candidates: dict[str, RSICandidate] = load_candidates(self._config_path)
        self._current_id: str = ""
        self.set_candidate(initial_candidate_id)

    # ④ candidate切替機能 ------------------------------------------------
    def set_candidate(self, candidate_id: str) -> None:
        """研究対象のcandidateを切り替える"""
        if candidate_id not in self._candidates:
            raise ValueError(
                f"存在しないcandidate_idです: {candidate_id!r}"
                f"（利用可能: {sorted(self._candidates.keys())}）"
            )
        self._current_id = candidate_id

    @property
    def current_candidate_id(self) -> str:
        return self._current_id

    # ① candidate A〜E管理 -------------------------------------------------
    def list_candidate_ids(self) -> list[str]:
        return sorted(self._candidates.keys())

    def get_candidate(self, candidate_id: Optional[str] = None) -> RSICandidate:
        """
        指定candidateの完全な定義を返す。
        candidate_id省略時は現在選択中のcandidateを返す。
        """
        cid = candidate_id or self._current_id
        if cid not in self._candidates:
            raise ValueError(f"存在しないcandidate_idです: {cid!r}")
        return self._candidates[cid]

    # ③ RSI値からの研究用スコア算出 -----------------------------------------
    def score(self, rsi: float, candidate_id: Optional[str] = None) -> RSIScoreResult:
        """
        指定（または現在選択中の）candidateの閾値でRSIをスコアリングする。

        Args:
            rsi: RSI値（0〜100想定）
            candidate_id: 省略時は現在のcandidateを使用

        Returns:
            RSIScoreResult(candidate_id, rsi, points, tier)
        """
        candidate = self.get_candidate(candidate_id)
        points, tier = calc_rsi_research_score(rsi, candidate.thresholds)
        return RSIScoreResult(
            candidate_id=candidate.id,
            rsi=rsi,
            points=points,
            tier=tier,
        )

    def score_all_candidates(self, rsi: float) -> list[RSIScoreResult]:
        """
        全candidate（A〜E）に対して同一RSI値でのスコアを算出する。
        Walk Forward接続前の単体動作確認・簡易比較用途を想定。
        """
        return [self.score(rsi, cid) for cid in self.list_candidate_ids()]

    # ⑤ 仮説情報取得 -------------------------------------------------------
    def get_hypothesis(self, candidate_id: Optional[str] = None) -> dict:
        """
        指定（または現在選択中の）candidateの仮説情報を返す。
        """
        candidate = self.get_candidate(candidate_id)
        info = {
            "candidate_id": candidate.id,
            "name_ja": candidate.name_ja,
            "hypothesis": candidate.hypothesis,
            "expected_effect": candidate.expected_effect,
            "expected_weakness": candidate.expected_weakness,
        }
        if candidate.threshold_mapping_note:
            info["threshold_mapping_note"] = candidate.threshold_mapping_note
        return info

    def get_all_hypotheses(self) -> list[dict]:
        """全candidateの仮説情報一覧を返す"""
        return [self.get_hypothesis(cid) for cid in self.list_candidate_ids()]


# ── 動作確認用（このファイル単体で実行した場合のみ動く軽量セルフチェック） ──
# Walk Forward・保存処理などは一切呼び出さない、純粋なロジック確認のみ。
if __name__ == "__main__":
    engine = RSIResearchEngine()
    print("候補一覧:", engine.list_candidate_ids())

    for rsi_value in (20, 32, 50, 68, 78):
        print(f"\n--- RSI={rsi_value} ---")
        for result in engine.score_all_candidates(rsi_value):
            print(f"  candidate={result.candidate_id}: {result.points}pt ({result.tier})")

    print("\n現在のcandidate:", engine.current_candidate_id)
    engine.set_candidate("E")
    print("切替後:", engine.current_candidate_id)
    print("Eの仮説:", engine.get_hypothesis())
