"""
Production decision rules — 数据驱动版（MVP 不调 LLM）

决策依据：
  - 读 process_methods.is_internal_capable
      * FALSE → 强制委外（我方不具备该能力，is_forced=True）
      * TRUE  → 建议自制（人工可改为委外）
  - 找不到匹配 → 保守策略：建议委外（未知工艺让人工判断）

之前是硬编码 FORCE_OUTSOURCE_PROCESSES = {"热处理","表面处理","线割"}；
现在和"系统管理 → 加工方式 → 我方可自制"勾选联动，改字典立即生效，
不用改代码、不用重启。

接口稳定：suggest_decision(process_name) -> DecisionSuggestion 签名不变，
调用方无需修改。
"""
from __future__ import annotations

from dataclasses import dataclass

from mvp import db


@dataclass
class DecisionSuggestion:
    decision: str                # "self_made" | "outsource"
    reason: str
    is_forced: bool = False      # True = 强制委外，不允许人工改自制


# 软性兜底：当数据库字典里没录入该工艺时，匹配这些关键词也视为强制委外
# 只是保护：正常流程应该通过 admin 页面维护 process_methods
_LEGACY_FORCE_HINTS: tuple[str, ...] = ("热处理", "表面处理", "线割", "阳极")


def _lookup_method(process_name: str) -> dict | None:
    """精确名称匹配，找不到则按关键词模糊匹配。"""
    name = (process_name or "").strip()
    if not name:
        return None

    # 精确匹配
    row = db.fetch_one(
        "SELECT name, category, is_internal_capable, remark FROM process_methods WHERE name = %s",
        (name,),
    )
    if row:
        return row

    # 模糊：先看工艺字典里有没有"被工序名字包含"的（例 "P1-精铣-A" 包含 "精铣"）
    all_rows = db.fetch_all(
        "SELECT name, category, is_internal_capable, remark FROM process_methods"
    )
    for r in all_rows:
        if r["name"] and r["name"] in name:
            return r

    return None


def suggest_decision(process_name: str) -> DecisionSuggestion:
    """从 process_methods 表动态决定建议。"""
    if not process_name or not process_name.strip():
        return DecisionSuggestion(
            decision="outsource",
            reason="工序名为空，建议人工确认",
        )

    name = process_name.strip()
    method = _lookup_method(name)

    # 情况 1：数据库里有这个工艺
    if method is not None:
        if not method["is_internal_capable"]:
            return DecisionSuggestion(
                decision="outsource",
                reason=f"我方不具备「{method['name']}」能力（系统字典标记为强制委外），必须委外",
                is_forced=True,
            )
        else:
            return DecisionSuggestion(
                decision="self_made",
                reason=f"「{method['name']}」在我方能力范围内（可改为委外）",
            )

    # 情况 2：数据库里找不到，降级到关键词兜底
    for hint in _LEGACY_FORCE_HINTS:
        if hint in name:
            return DecisionSuggestion(
                decision="outsource",
                reason=f"工艺「{name}」未录入字典，但包含关键词「{hint}」，按强制委外类处理",
                is_forced=True,
            )

    # 情况 3：完全未知工艺 → 保守建议委外
    return DecisionSuggestion(
        decision="outsource",
        reason=f"工艺「{name}」未录入系统字典，建议委外交人工判断（请去【系统管理→加工方式】补录）",
    )
