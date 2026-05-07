"""
Production decision rules — hardcoded for MVP (no LLM).

遵循 design.md §决策 6 的简化策略：
  - 热处理 / 表面处理 / 线割  → 强制委外（公司不具备能力）
  - 磨 / 铣 / 车 / 钻 / 镗     → 内部可完成
  - 其他工序                   → 默认建议委外（保守策略）

Future upgrade path: swap `suggest_decision` with an LLM call or
integrate with Harness AgentRunner; function signature unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass

# 强制委外：公司工艺能力外，不允许改为自制
FORCE_OUTSOURCE_PROCESSES: set[str] = {
    "热处理", "表面处理", "线割",
}

# 内部可完成：默认建议自制
PREFER_INTERNAL_PROCESSES: set[str] = {
    "磨", "铣", "车", "钻", "镗",
}


@dataclass
class DecisionSuggestion:
    decision: str   # "self_made" | "outsource"
    reason: str
    is_forced: bool = False


def suggest_decision(process_name: str) -> DecisionSuggestion:
    """Return hardcoded AI suggestion for a single process."""
    if not process_name:
        return DecisionSuggestion(
            decision="outsource",
            reason="工序名为空，建议人工确认",
        )

    name = process_name.strip()

    if name in FORCE_OUTSOURCE_PROCESSES:
        return DecisionSuggestion(
            decision="outsource",
            reason=f"公司不具备「{name}」工艺能力，强制委外",
            is_forced=True,
        )

    if name in PREFER_INTERNAL_PROCESSES:
        return DecisionSuggestion(
            decision="self_made",
            reason=f"「{name}」为常规工序，内部可完成",
        )

    # Fuzzy match: 包含关键词的情况
    for keyword in PREFER_INTERNAL_PROCESSES:
        if keyword in name:
            return DecisionSuggestion(
                decision="self_made",
                reason=f"「{name}」属于常规加工类（匹配关键词「{keyword}」），内部可完成",
            )

    for keyword in FORCE_OUTSOURCE_PROCESSES:
        if keyword in name:
            return DecisionSuggestion(
                decision="outsource",
                reason=f"「{name}」包含强制委外工艺（「{keyword}」），委外",
                is_forced=True,
            )

    # 兜底：保守策略，建议委外让人工判断
    return DecisionSuggestion(
        decision="outsource",
        reason=f"「{name}」未在能力清单中，保守建议委外（人工可改）",
    )
