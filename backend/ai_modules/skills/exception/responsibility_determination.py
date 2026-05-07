"""
ResponsibilityDeterminationSkill - 责任判定技能
判定质量异常的责任方（内部、供应商、材料商）
"""
from typing import Dict, Any, Optional, List
import logging

# 导入 Harness 框架的工具装饰器
import sys
sys.path.append('../../..')
from harness.tools import tool

logger = logging.getLogger(__name__)


@tool(
    description="判定质量异常的责任方（内部、供应商、材料商）",
    permission="read_only"
)
def determine_responsibility(
    exception_type: str,
    root_cause: str,
    supplier_id: str,
    material: Optional[str] = None,
    historical_cases: Optional[List[Dict]] = None
) -> Dict[str, Any]:
    """
    判定异常责任方
    
    Args:
        exception_type: 异常类型 (尺寸偏差, 表面缺陷, 材料问题, 组装问题)
        root_cause: 根本原因
        supplier_id: 供应商ID
        material: 材料类型 (可选)
        historical_cases: 历史案例列表 (可选)
        
    Returns:
        Dict: 责任判定结果
        {
            "responsible_party": str,  # internal, supplier, material_vendor
            "confidence_score": float,  # 0-100
            "evidence": List[str],  # 证据列表
            "requires_review": bool,  # 是否需要人工审核
            "reasoning": str  # 判定理由
        }
    """
    logger.info(f"Determining responsibility for {exception_type}")
    
    try:
        # 1. 基于异常类型的初步判定
        base_responsibility = _map_exception_type_to_responsibility(exception_type)
        
        # 2. 收集证据
        evidence = _collect_evidence(
            exception_type, root_cause, material, historical_cases
        )
        
        # 3. 计算置信度分数
        confidence_score = _calculate_confidence_score(
            exception_type, root_cause, evidence, historical_cases
        )
        
        # 4. 基于证据调整责任判定
        final_responsibility = _adjust_responsibility_based_on_evidence(
            base_responsibility, root_cause, evidence
        )
        
        # 5. 判断是否需要人工审核
        requires_review = _check_requires_review(
            confidence_score, evidence, final_responsibility
        )
        
        # 6. 生成判定理由
        reasoning = _generate_reasoning(
            exception_type, final_responsibility, evidence, confidence_score
        )
        
        result = {
            "responsible_party": final_responsibility,
            "confidence_score": round(confidence_score, 2),
            "evidence": evidence,
            "requires_review": requires_review,
            "reasoning": reasoning
        }
        
        logger.info(
            f"Responsibility determined: {final_responsibility}, "
            f"confidence: {confidence_score:.2f}"
        )
        return result
    
    except Exception as e:
        logger.error(f"Error determining responsibility: {e}", exc_info=True)
        return {
            "responsible_party": "unknown",
            "confidence_score": 0.0,
            "evidence": [],
            "requires_review": True,
            "reasoning": f"责任判定失败: {str(e)}"
        }


def _map_exception_type_to_responsibility(exception_type: str) -> str:
    """
    将异常类型映射到责任方
    
    Args:
        exception_type: 异常类型
        
    Returns:
        str: 责任方 (internal, supplier, material_vendor)
    """
    # 异常类型到责任方的映射规则
    type_responsibility_mapping = {
        "尺寸偏差": "supplier",        # 通常是供应商加工问题
        "表面缺陷": "supplier",        # 可能是供应商或材料商
        "材料问题": "material_vendor",  # 通常是材料商问题
        "组装问题": "internal"         # 可能是内部或供应商
    }
    
    return type_responsibility_mapping.get(exception_type, "supplier")


def _collect_evidence(
    exception_type: str,
    root_cause: str,
    material: Optional[str],
    historical_cases: Optional[List[Dict]]
) -> List[str]:
    """
    收集责任判定的证据
    
    Args:
        exception_type: 异常类型
        root_cause: 根本原因
        material: 材料类型
        historical_cases: 历史案例
        
    Returns:
        List[str]: 证据列表
    """
    evidence = []
    
    # 1. 基于异常类型的证据
    if exception_type == "尺寸偏差":
        evidence.append("异常类型为尺寸偏差，通常由加工方（供应商）负责")
    elif exception_type == "表面缺陷":
        evidence.append("异常类型为表面缺陷，可能是加工或材料问题")
    elif exception_type == "材料问题":
        evidence.append("异常类型为材料问题，通常由材料供应商负责")
    elif exception_type == "组装问题":
        evidence.append("异常类型为组装问题，可能是内部装配或零件配合问题")
    
    # 2. 基于根本原因的证据
    root_cause_lower = root_cause.lower()
    
    if "加工" in root_cause_lower or "设备" in root_cause_lower or "刀具" in root_cause_lower:
        evidence.append("根本原因涉及加工设备或工艺，指向供应商责任")
    
    if "材料" in root_cause_lower and "成分" in root_cause_lower:
        evidence.append("根本原因涉及材料成分，指向材料供应商责任")
    
    if "材料" in root_cause_lower and ("质量" in root_cause_lower or "硬度" in root_cause_lower):
        evidence.append("根本原因涉及材料质量，指向材料供应商责任")
    
    if "组装" in root_cause_lower or "装配" in root_cause_lower:
        evidence.append("根本原因涉及组装工艺，指向内部责任")
    
    if "操作" in root_cause_lower or "人为" in root_cause_lower:
        evidence.append("根本原因涉及操作失误，需确认操作方")
    
    if "设计" in root_cause_lower or "图纸" in root_cause_lower:
        evidence.append("根本原因涉及设计问题，可能是内部设计责任")
    
    if "测量" in root_cause_lower or "检验" in root_cause_lower:
        evidence.append("根本原因涉及测量或检验方法，需确认检验方")
    
    # 3. 基于材料的证据
    if material:
        if exception_type == "材料问题":
            evidence.append(f"材料为{material}，材料相关问题应由材料供应商负责")
        elif exception_type == "表面缺陷" and "氧化" in root_cause_lower:
            evidence.append(f"{material}材料的表面氧化问题，可能是材料存储或质量问题")
    
    # 4. 基于历史案例的证据
    if historical_cases and len(historical_cases) > 0:
        # 统计历史案例中的责任方分布
        responsibility_counts = {}
        for case in historical_cases:
            if "responsible_party" in case:
                party = case["responsible_party"]
                responsibility_counts[party] = responsibility_counts.get(party, 0) + 1
        
        if responsibility_counts:
            most_common = max(responsibility_counts, key=responsibility_counts.get)
            count = responsibility_counts[most_common]
            total = len(historical_cases)
            percentage = (count / total) * 100
            
            evidence.append(
                f"历史案例显示，类似异常中{percentage:.0f}%由{_translate_party(most_common)}负责"
            )
    
    # 5. 如果证据不足
    if len(evidence) < 2:
        evidence.append("证据不足，建议进行详细调查")
    
    return evidence


def _calculate_confidence_score(
    exception_type: str,
    root_cause: str,
    evidence: List[str],
    historical_cases: Optional[List[Dict]]
) -> float:
    """
    计算置信度分数
    
    Args:
        exception_type: 异常类型
        root_cause: 根本原因
        evidence: 证据列表
        historical_cases: 历史案例
        
    Returns:
        float: 置信度分数 (0-100)
    """
    # 基础置信度
    base_confidence = 60.0
    
    # 1. 基于异常类型的置信度调整
    type_confidence_boost = {
        "材料问题": 20.0,  # 材料问题责任明确
        "尺寸偏差": 15.0,  # 尺寸问题通常责任明确
        "表面缺陷": 10.0,  # 表面问题可能有多种原因
        "组装问题": 5.0    # 组装问题责任可能不明确
    }
    
    base_confidence += type_confidence_boost.get(exception_type, 0)
    
    # 2. 基于证据数量的调整
    evidence_count = len(evidence)
    if evidence_count >= 4:
        base_confidence += 15.0
    elif evidence_count >= 3:
        base_confidence += 10.0
    elif evidence_count >= 2:
        base_confidence += 5.0
    else:
        base_confidence -= 10.0  # 证据不足
    
    # 3. 基于根本原因明确性的调整
    root_cause_lower = root_cause.lower()
    
    # 明确指向某一方的关键词
    if any(keyword in root_cause_lower for keyword in ["明确", "确定", "显然"]):
        base_confidence += 10.0
    
    # 不确定的关键词
    if any(keyword in root_cause_lower for keyword in ["可能", "或", "不确定", "需调查"]):
        base_confidence -= 15.0
    
    # 4. 基于历史案例的调整
    if historical_cases and len(historical_cases) > 0:
        # 如果有3个以上相似案例，增加置信度
        if len(historical_cases) >= 3:
            base_confidence += 10.0
        elif len(historical_cases) >= 1:
            base_confidence += 5.0
    else:
        # 没有历史案例参考，降低置信度
        base_confidence -= 5.0
    
    # 5. 确保置信度在0-100范围内
    confidence_score = max(0.0, min(100.0, base_confidence))
    
    return confidence_score


def _adjust_responsibility_based_on_evidence(
    base_responsibility: str,
    root_cause: str,
    evidence: List[str]
) -> str:
    """
    基于证据调整责任判定
    
    Args:
        base_responsibility: 基础责任判定
        root_cause: 根本原因
        evidence: 证据列表
        
    Returns:
        str: 调整后的责任方
    """
    root_cause_lower = root_cause.lower()
    
    # 强证据：材料成分或质量问题
    if "材料" in root_cause_lower and ("成分" in root_cause_lower or "质量" in root_cause_lower):
        return "material_vendor"
    
    # 强证据：组装或装配问题
    if "组装" in root_cause_lower or "装配" in root_cause_lower:
        return "internal"
    
    # 强证据：设计问题
    if "设计" in root_cause_lower or "图纸" in root_cause_lower:
        return "internal"
    
    # 强证据：加工设备或工艺问题
    if "加工" in root_cause_lower or "设备" in root_cause_lower or "工艺" in root_cause_lower:
        return "supplier"
    
    # 如果没有强证据，保持基础判定
    return base_responsibility


def _check_requires_review(
    confidence_score: float,
    evidence: List[str],
    responsible_party: str
) -> bool:
    """
    检查是否需要人工审核
    
    Args:
        confidence_score: 置信度分数
        evidence: 证据列表
        responsible_party: 责任方
        
    Returns:
        bool: 是否需要人工审核
    """
    # 1. 置信度低于70需要审核
    if confidence_score < 70:
        return True
    
    # 2. 证据不足需要审核
    if len(evidence) < 2:
        return True
    
    # 3. 证据中包含"证据不足"或"需调查"
    for ev in evidence:
        if "证据不足" in ev or "需调查" in ev or "不确定" in ev:
            return True
    
    # 4. 责任方为unknown需要审核
    if responsible_party == "unknown":
        return True
    
    return False


def _generate_reasoning(
    exception_type: str,
    responsible_party: str,
    evidence: List[str],
    confidence_score: float
) -> str:
    """
    生成判定理由
    
    Args:
        exception_type: 异常类型
        responsible_party: 责任方
        evidence: 证据列表
        confidence_score: 置信度分数
        
    Returns:
        str: 判定理由
    """
    party_text = _translate_party(responsible_party)
    
    reasoning = f"基于异常类型【{exception_type}】和相关证据分析，"
    reasoning += f"判定责任方为【{party_text}】，置信度为 {confidence_score:.1f}%。"
    
    # 添加主要证据
    if evidence:
        reasoning += "\n\n主要证据："
        for i, ev in enumerate(evidence[:3], 1):  # 只列出前3条主要证据
            reasoning += f"\n{i}. {ev}"
    
    # 添加建议
    if confidence_score >= 80:
        reasoning += "\n\n建议：置信度较高，可直接按此判定处理。"
    elif confidence_score >= 70:
        reasoning += "\n\n建议：置信度中等，建议确认后处理。"
    else:
        reasoning += "\n\n建议：置信度较低，强烈建议人工审核确认。"
    
    return reasoning


def _translate_party(party: str) -> str:
    """
    翻译责任方代码为中文
    
    Args:
        party: 责任方代码
        
    Returns:
        str: 中文描述
    """
    translations = {
        "internal": "内部",
        "supplier": "供应商",
        "material_vendor": "材料供应商",
        "unknown": "未知"
    }
    
    return translations.get(party, party)


# 测试代码
if __name__ == "__main__":
    # 测试责任判定
    result = determine_responsibility(
        exception_type="尺寸偏差",
        root_cause="加工设备精度不足或刀具磨损导致尺寸超出公差范围",
        supplier_id="SUP001",
        material="钢",
        historical_cases=[
            {"responsible_party": "supplier", "outcome": "成功解决"},
            {"responsible_party": "supplier", "outcome": "成功解决"}
        ]
    )
    
    print("责任判定结果:")
    print(f"责任方: {result['responsible_party']}")
    print(f"置信度: {result['confidence_score']}%")
    print(f"需要审核: {result['requires_review']}")
    print(f"证据: {result['evidence']}")
    print(f"理由: {result['reasoning']}")
