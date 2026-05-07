"""
SolutionRecommendationSkill - 解决方案推荐技能
推荐异常解决方案并评估成本和时间影响
"""
from typing import Dict, Any, Optional, List
import logging

# 导入 Harness 框架的工具装饰器
import sys
sys.path.append('../../..')
from harness.tools import tool

logger = logging.getLogger(__name__)


@tool(
    description="推荐异常解决方案并评估成本和时间影响",
    permission="read_only"
)
def recommend_solution(
    exception_type: str,
    severity: str,
    root_cause: str,
    responsible_party: str,
    quantity_affected: int = 1
) -> Dict[str, Any]:
    """
    推荐异常解决方案
    
    Args:
        exception_type: 异常类型 (尺寸偏差, 表面缺陷, 材料问题, 组装问题)
        severity: 严重程度 (critical, major, minor)
        root_cause: 根本原因
        responsible_party: 责任方 (internal, supplier, material_vendor)
        quantity_affected: 受影响数量 (默认1)
        
    Returns:
        Dict: 解决方案推荐
        {
            "solutions": List[{
                "solution_type": str,  # rework, replacement, temporary_acceptance, design_modification
                "description": str,
                "cost_impact": float,
                "time_impact": int,  # days
                "feasibility_score": float,  # 0-100
                "implementation_steps": List[str],
                "pros": List[str],
                "cons": List[str]
            }],
            "recommended_solution": str,  # Best solution type
            "recommendation_summary": str
        }
    """
    logger.info(f"Recommending solutions for {exception_type} with severity {severity}")
    
    try:
        solutions = []
        
        # 1. 生成返工方案
        rework_solution = _generate_rework_solution(
            exception_type, severity, root_cause, responsible_party, quantity_affected
        )
        if rework_solution:
            solutions.append(rework_solution)
        
        # 2. 生成更换方案
        replacement_solution = _generate_replacement_solution(
            exception_type, severity, root_cause, responsible_party, quantity_affected
        )
        if replacement_solution:
            solutions.append(replacement_solution)
        
        # 3. 生成临时让步接收方案
        temp_acceptance_solution = _generate_temporary_acceptance_solution(
            exception_type, severity, root_cause, responsible_party, quantity_affected
        )
        if temp_acceptance_solution:
            solutions.append(temp_acceptance_solution)
        
        # 4. 生成修改设计方案
        design_modification_solution = _generate_design_modification_solution(
            exception_type, severity, root_cause, responsible_party, quantity_affected
        )
        if design_modification_solution:
            solutions.append(design_modification_solution)
        
        # 5. 按可行性评分排序
        solutions = _rank_solutions_by_feasibility(solutions)
        
        # 6. 选择推荐方案
        recommended_solution = solutions[0]["solution_type"] if solutions else "none"
        
        # 7. 生成推荐摘要
        recommendation_summary = _generate_recommendation_summary(
            solutions, recommended_solution, severity, quantity_affected
        )
        
        result = {
            "solutions": solutions,
            "recommended_solution": recommended_solution,
            "recommendation_summary": recommendation_summary
        }
        
        logger.info(f"Generated {len(solutions)} solutions, recommended: {recommended_solution}")
        return result
    
    except Exception as e:
        logger.error(f"Error recommending solutions: {e}", exc_info=True)
        return {
            "solutions": [],
            "recommended_solution": "error",
            "recommendation_summary": f"方案推荐失败: {str(e)}"
        }


def _generate_rework_solution(
    exception_type: str,
    severity: str,
    root_cause: str,
    responsible_party: str,
    quantity_affected: int
) -> Optional[Dict[str, Any]]:
    """
    生成返工方案
    
    Args:
        exception_type: 异常类型
        severity: 严重程度
        root_cause: 根本原因
        responsible_party: 责任方
        quantity_affected: 受影响数量
        
    Returns:
        Optional[Dict]: 返工方案，如果不适用则返回None
    """
    # 返工适用性判断
    if severity == "critical" and "无法" in root_cause:
        # 严重缺陷且无法修复，不适用返工
        return None
    
    if exception_type == "材料问题" and "成分" in root_cause:
        # 材料成分问题无法返工
        return None
    
    # 计算成本影响
    base_cost_per_unit = {
        "尺寸偏差": 50.0,
        "表面缺陷": 30.0,
        "材料问题": 80.0,
        "组装问题": 40.0
    }.get(exception_type, 50.0)
    
    # 严重程度调整系数
    severity_multiplier = {
        "critical": 2.0,
        "major": 1.5,
        "minor": 1.0
    }.get(severity, 1.5)
    
    cost_impact = base_cost_per_unit * severity_multiplier * quantity_affected
    
    # 计算时间影响
    base_time = {
        "critical": 7,
        "major": 5,
        "minor": 3
    }.get(severity, 5)
    
    # 数量调整
    if quantity_affected > 100:
        time_impact = base_time + 3
    elif quantity_affected > 50:
        time_impact = base_time + 2
    else:
        time_impact = base_time
    
    # 计算可行性评分
    feasibility_score = 90.0
    
    # 严重程度降低可行性
    if severity == "critical":
        feasibility_score -= 20
    elif severity == "major":
        feasibility_score -= 10
    
    # 数量影响可行性
    if quantity_affected > 200:
        feasibility_score -= 15
    elif quantity_affected > 100:
        feasibility_score -= 10
    
    # 异常类型影响可行性
    if exception_type == "材料问题":
        feasibility_score -= 20
    
    feasibility_score = max(feasibility_score, 0.0)
    
    # 生成实施步骤
    implementation_steps = [
        f"1. 将{quantity_affected}件超差零件退回{_get_party_name(responsible_party)}",
        f"2. {_get_party_name(responsible_party)}重新加工修正缺陷",
        "3. 重新检验确认质量合格",
        "4. 合格后重新交付"
    ]
    
    if severity == "critical":
        implementation_steps.insert(1, "1.5. 制定详细的返工工艺方案")
    
    # 优缺点
    pros = [
        "成本相对较低",
        "可以修复现有零件",
        "不需要重新制造"
    ]
    
    cons = [
        f"需要额外{time_impact}天时间",
        "可能影响交期",
        "返工质量可能不如新件"
    ]
    
    if quantity_affected > 100:
        cons.append("批量返工工作量大")
    
    description = f"对{quantity_affected}件超差零件进行返工处理，修正{exception_type}问题。"
    description += f"预计成本{cost_impact:.2f}元，耗时{time_impact}天。"
    
    return {
        "solution_type": "rework",
        "description": description,
        "cost_impact": round(cost_impact, 2),
        "time_impact": time_impact,
        "feasibility_score": round(feasibility_score, 2),
        "implementation_steps": implementation_steps,
        "pros": pros,
        "cons": cons
    }


def _generate_replacement_solution(
    exception_type: str,
    severity: str,
    root_cause: str,
    responsible_party: str,
    quantity_affected: int
) -> Optional[Dict[str, Any]]:
    """
    生成更换方案
    
    Args:
        exception_type: 异常类型
        severity: 严重程度
        root_cause: 根本原因
        responsible_party: 责任方
        quantity_affected: 受影响数量
        
    Returns:
        Optional[Dict]: 更换方案，如果不适用则返回None
    """
    # 更换适用性判断 - 几乎总是适用
    
    # 计算成本影响 (比返工高)
    base_cost_per_unit = {
        "尺寸偏差": 100.0,
        "表面缺陷": 80.0,
        "材料问题": 150.0,
        "组装问题": 90.0
    }.get(exception_type, 100.0)
    
    # 严重程度调整系数
    severity_multiplier = {
        "critical": 1.5,
        "major": 1.3,
        "minor": 1.0
    }.get(severity, 1.3)
    
    cost_impact = base_cost_per_unit * severity_multiplier * quantity_affected
    
    # 计算时间影响 (比返工长)
    base_time = {
        "critical": 10,
        "major": 8,
        "minor": 7
    }.get(severity, 8)
    
    # 数量调整
    if quantity_affected > 100:
        time_impact = base_time + 4
    elif quantity_affected > 50:
        time_impact = base_time + 2
    else:
        time_impact = base_time
    
    # 计算可行性评分
    feasibility_score = 85.0
    
    # 严重程度提高可行性 (严重问题更适合更换)
    if severity == "critical":
        feasibility_score += 10
    elif severity == "minor":
        feasibility_score -= 15
    
    # 数量影响可行性
    if quantity_affected > 200:
        feasibility_score -= 20
    elif quantity_affected > 100:
        feasibility_score -= 10
    
    # 成本考虑
    if cost_impact > 50000:
        feasibility_score -= 15
    
    feasibility_score = max(feasibility_score, 0.0)
    
    # 生成实施步骤
    implementation_steps = [
        f"1. 向{_get_party_name(responsible_party)}下达新的生产订单",
        f"2. {_get_party_name(responsible_party)}重新生产{quantity_affected}件零件",
        "3. 对新零件进行全面检验",
        "4. 检验合格后交付新零件",
        "5. 处置不合格零件"
    ]
    
    if severity == "critical":
        implementation_steps.insert(1, "1.5. 要求提供详细的质量保证计划")
    
    # 优缺点
    pros = [
        "质量有保证",
        "不影响原零件使用",
        "可以避免返工风险"
    ]
    
    if severity == "critical":
        pros.append("适合严重缺陷")
    
    cons = [
        f"成本较高 ({cost_impact:.2f}元)",
        f"时间较长 ({time_impact}天)",
        "需要处置不合格零件"
    ]
    
    if quantity_affected > 100:
        cons.append("大批量更换成本很高")
    
    description = f"重新制造{quantity_affected}件新零件替换超差零件。"
    description += f"预计成本{cost_impact:.2f}元，耗时{time_impact}天。"
    
    return {
        "solution_type": "replacement",
        "description": description,
        "cost_impact": round(cost_impact, 2),
        "time_impact": time_impact,
        "feasibility_score": round(feasibility_score, 2),
        "implementation_steps": implementation_steps,
        "pros": pros,
        "cons": cons
    }


def _generate_temporary_acceptance_solution(
    exception_type: str,
    severity: str,
    root_cause: str,
    responsible_party: str,
    quantity_affected: int
) -> Optional[Dict[str, Any]]:
    """
    生成临时让步接收方案
    
    Args:
        exception_type: 异常类型
        severity: 严重程度
        root_cause: 根本原因
        responsible_party: 责任方
        quantity_affected: 受影响数量
        
    Returns:
        Optional[Dict]: 临时让步接收方案，如果不适用则返回None
    """
    # 临时让步接收适用性判断 - 仅适用于轻微缺陷
    if severity in ["critical", "major"]:
        # 严重和主要缺陷不适用临时让步
        return None
    
    if exception_type == "材料问题":
        # 材料问题不适用临时让步
        return None
    
    # 计算成本影响 (主要是文档和审批成本)
    base_cost = 500.0  # 基础文档成本
    
    # 数量影响成本
    if quantity_affected > 100:
        cost_impact = base_cost + 300
    elif quantity_affected > 50:
        cost_impact = base_cost + 200
    else:
        cost_impact = base_cost
    
    # 计算时间影响 (主要是审批时间)
    time_impact = 2  # 1-2天审批
    
    if quantity_affected > 100:
        time_impact = 3
    
    # 计算可行性评分
    feasibility_score = 70.0
    
    # 仅轻微缺陷可行
    if severity == "minor":
        feasibility_score += 20
    
    # 表面缺陷更适合临时让步
    if exception_type == "表面缺陷":
        feasibility_score += 10
    
    # 数量影响可行性
    if quantity_affected > 200:
        feasibility_score -= 20
    
    feasibility_score = max(feasibility_score, 0.0)
    
    # 生成实施步骤
    implementation_steps = [
        "1. 评估缺陷对功能和安全的影响",
        "2. 编制临时让步接收申请文件",
        "3. 提交技术部门和质量部门审批",
        "4. 获得客户书面同意",
        "5. 记录让步接收决定和理由",
        "6. 标识让步接收零件"
    ]
    
    # 优缺点
    pros = [
        "成本最低",
        "时间最短",
        "不影响生产进度",
        "适合不影响功能的轻微缺陷"
    ]
    
    cons = [
        "需要客户同意",
        "可能影响产品外观",
        "需要完整的审批流程",
        "仅适用于轻微缺陷"
    ]
    
    description = f"对{quantity_affected}件轻微{exception_type}零件进行临时让步接收。"
    description += f"需要客户书面同意，预计成本{cost_impact:.2f}元，耗时{time_impact}天。"
    
    return {
        "solution_type": "temporary_acceptance",
        "description": description,
        "cost_impact": round(cost_impact, 2),
        "time_impact": time_impact,
        "feasibility_score": round(feasibility_score, 2),
        "implementation_steps": implementation_steps,
        "pros": pros,
        "cons": cons
    }


def _generate_design_modification_solution(
    exception_type: str,
    severity: str,
    root_cause: str,
    responsible_party: str,
    quantity_affected: int
) -> Optional[Dict[str, Any]]:
    """
    生成修改设计方案
    
    Args:
        exception_type: 异常类型
        severity: 严重程度
        root_cause: 根本原因
        responsible_party: 责任方
        quantity_affected: 受影响数量
        
    Returns:
        Optional[Dict]: 修改设计方案，如果不适用则返回None
    """
    # 修改设计适用性判断 - 仅适用于系统性问题或设计缺陷
    if "设计" not in root_cause and "系统" not in root_cause:
        # 非设计问题，不适用修改设计
        return None
    
    # 计算成本影响 (非常高)
    base_cost = 50000.0  # 基础设计修改成本
    
    # 严重程度影响成本
    severity_multiplier = {
        "critical": 2.0,
        "major": 1.5,
        "minor": 1.0
    }.get(severity, 1.5)
    
    # 异常类型影响成本
    type_multiplier = {
        "尺寸偏差": 1.5,
        "表面缺陷": 1.0,
        "材料问题": 1.3,
        "组装问题": 1.8
    }.get(exception_type, 1.5)
    
    cost_impact = base_cost * severity_multiplier * type_multiplier
    
    # 加上重新制造成本
    manufacturing_cost = 100.0 * quantity_affected
    cost_impact += manufacturing_cost
    
    # 计算时间影响 (非常长)
    base_time = 21  # 3周基础时间
    
    # 严重程度影响时间
    if severity == "critical":
        time_impact = base_time + 9  # 额外1.5周
    elif severity == "major":
        time_impact = base_time + 5  # 额外5天
    else:
        time_impact = base_time
    
    # 计算可行性评分 (通常较低)
    feasibility_score = 40.0
    
    # 仅在设计缺陷时可行性较高
    if "设计" in root_cause:
        feasibility_score += 20
    
    # 严重程度提高可行性 (严重问题值得修改设计)
    if severity == "critical":
        feasibility_score += 15
    
    # 成本和时间降低可行性
    if cost_impact > 100000:
        feasibility_score -= 20
    
    if time_impact > 30:
        feasibility_score -= 10
    
    feasibility_score = max(feasibility_score, 0.0)
    
    # 生成实施步骤
    implementation_steps = [
        "1. 组织技术评审会议，确认设计缺陷",
        "2. 制定设计修改方案",
        "3. 进行设计验证和仿真分析",
        "4. 更新技术图纸和工艺文件",
        "5. 重新制造模具或工装",
        "6. 试生产验证修改效果",
        f"7. 批量生产{quantity_affected}件新零件",
        "8. 更新产品文档和BOM"
    ]
    
    # 优缺点
    pros = [
        "从根本上解决设计缺陷",
        "避免未来重复出现问题",
        "提升产品质量",
        "适合系统性问题"
    ]
    
    cons = [
        f"成本非常高 ({cost_impact:.2f}元)",
        f"时间非常长 ({time_impact}天)",
        "需要重新制造模具/工装",
        "影响项目进度",
        "风险较高"
    ]
    
    description = f"修改设计以从根本上解决{exception_type}问题。"
    description += f"需要重新设计、制造模具和生产，预计成本{cost_impact:.2f}元，耗时{time_impact}天。"
    
    return {
        "solution_type": "design_modification",
        "description": description,
        "cost_impact": round(cost_impact, 2),
        "time_impact": time_impact,
        "feasibility_score": round(feasibility_score, 2),
        "implementation_steps": implementation_steps,
        "pros": pros,
        "cons": cons
    }


def _rank_solutions_by_feasibility(solutions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    按可行性评分排序方案
    
    Args:
        solutions: 方案列表
        
    Returns:
        List[Dict]: 排序后的方案列表 (可行性从高到低)
    """
    return sorted(solutions, key=lambda x: x["feasibility_score"], reverse=True)


def _generate_recommendation_summary(
    solutions: List[Dict[str, Any]],
    recommended_solution: str,
    severity: str,
    quantity_affected: int
) -> str:
    """
    生成推荐摘要
    
    Args:
        solutions: 方案列表
        recommended_solution: 推荐方案类型
        severity: 严重程度
        quantity_affected: 受影响数量
        
    Returns:
        str: 推荐摘要
    """
    if not solutions:
        return "未能生成有效的解决方案，建议人工评估。"
    
    solution_type_names = {
        "rework": "返工",
        "replacement": "更换",
        "temporary_acceptance": "临时让步接收",
        "design_modification": "修改设计"
    }
    
    severity_text = {
        "critical": "严重",
        "major": "主要",
        "minor": "轻微"
    }
    
    summary = f"针对{severity_text.get(severity, severity)}程度的异常，"
    summary += f"影响{quantity_affected}件零件，"
    summary += f"共生成{len(solutions)}个解决方案。\n\n"
    
    # 推荐方案
    recommended = next((s for s in solutions if s["solution_type"] == recommended_solution), None)
    if recommended:
        summary += f"【推荐方案】{solution_type_names.get(recommended_solution, recommended_solution)}\n"
        summary += f"可行性评分: {recommended['feasibility_score']:.1f}/100\n"
        summary += f"预计成本: {recommended['cost_impact']:.2f}元\n"
        summary += f"预计时间: {recommended['time_impact']}天\n"
        summary += f"方案描述: {recommended['description']}\n\n"
    
    # 其他方案
    if len(solutions) > 1:
        summary += "【备选方案】\n"
        for i, solution in enumerate(solutions[1:], 1):
            solution_name = solution_type_names.get(solution["solution_type"], solution["solution_type"])
            summary += f"{i}. {solution_name} "
            summary += f"(可行性: {solution['feasibility_score']:.1f}, "
            summary += f"成本: {solution['cost_impact']:.2f}元, "
            summary += f"时间: {solution['time_impact']}天)\n"
    
    # 建议
    summary += "\n【建议】\n"
    if severity == "critical":
        summary += "异常严重程度高，建议优先考虑质量保证，必要时选择更换方案。"
    elif severity == "major":
        summary += "建议综合考虑成本、时间和质量，选择最合适的方案。"
    else:
        summary += "异常程度较轻，可考虑成本较低的方案，如临时让步接收。"
    
    return summary


def _get_party_name(responsible_party: str) -> str:
    """
    获取责任方名称
    
    Args:
        responsible_party: 责任方代码
        
    Returns:
        str: 责任方名称
    """
    party_names = {
        "supplier": "供应商",
        "internal": "内部",
        "material_vendor": "材料供应商"
    }
    return party_names.get(responsible_party, "相关方")


# 测试代码
if __name__ == "__main__":
    # 测试解决方案推荐
    result = recommend_solution(
        exception_type="尺寸偏差",
        severity="major",
        root_cause="加工设备精度不足或刀具磨损导致尺寸超出公差范围",
        responsible_party="supplier",
        quantity_affected=50
    )
    
    print("解决方案推荐结果:")
    print(f"推荐方案: {result['recommended_solution']}")
    print(f"方案数量: {len(result['solutions'])}")
    print(f"\n推荐摘要:\n{result['recommendation_summary']}")
    print(f"\n详细方案:")
    for i, solution in enumerate(result['solutions'], 1):
        print(f"\n{i}. {solution['solution_type']}")
        print(f"   可行性: {solution['feasibility_score']}")
        print(f"   成本: {solution['cost_impact']}")
        print(f"   时间: {solution['time_impact']}天")
