"""
ExceptionAnalysisSkill - 异常分析技能
分析质量异常的根本原因、严重程度和影响范围
"""
from typing import Dict, Any, Optional, List
import logging

# 导入 Harness 框架的工具装饰器
import sys
sys.path.append('../../..')
from harness.tools import tool

logger = logging.getLogger(__name__)


@tool(
    description="分析质量异常的根本原因、严重程度和影响范围",
    permission="read_only"
)
def analyze_exception(
    exception_type: str,
    description: str,
    entity_type: str,
    material: Optional[str] = None,
    process_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    分析质量异常
    
    Args:
        exception_type: 异常类型 (尺寸偏差, 表面缺陷, 材料问题, 组装问题)
        description: 异常描述
        entity_type: 实体类型 (part, order)
        material: 材料类型 (可选)
        process_type: 工艺类型 (可选)
        
    Returns:
        Dict: 分析结果
        {
            "root_cause": str,  # 根本原因
            "severity": str,  # critical, major, minor
            "impact_scope": str,  # single_part, batch, entire_order
            "contributing_factors": List[str],  # 贡献因素
            "analysis_summary": str  # 分析摘要
        }
    """
    logger.info(f"Analyzing exception: {exception_type}")
    
    try:
        # 1. 根本原因分析
        root_cause = _analyze_root_cause(exception_type, description, material, process_type)
        
        # 2. 严重程度评估
        severity = _assess_severity(exception_type, description)
        
        # 3. 影响范围评估
        impact_scope = _evaluate_impact_scope(exception_type, description, entity_type)
        
        # 4. 识别贡献因素
        contributing_factors = _identify_contributing_factors(
            exception_type, description, material, process_type
        )
        
        # 5. 生成分析摘要
        analysis_summary = _generate_analysis_summary(
            exception_type, root_cause, severity, impact_scope
        )
        
        result = {
            "root_cause": root_cause,
            "severity": severity,
            "impact_scope": impact_scope,
            "contributing_factors": contributing_factors,
            "analysis_summary": analysis_summary
        }
        
        logger.info(f"Analysis completed: severity={severity}, impact={impact_scope}")
        return result
    
    except Exception as e:
        logger.error(f"Error analyzing exception: {e}", exc_info=True)
        return {
            "root_cause": f"分析失败: {str(e)}",
            "severity": "unknown",
            "impact_scope": "unknown",
            "contributing_factors": [],
            "analysis_summary": f"异常分析失败: {str(e)}"
        }


def _analyze_root_cause(
    exception_type: str,
    description: str,
    material: Optional[str],
    process_type: Optional[str]
) -> str:
    """
    分析根本原因
    
    Args:
        exception_type: 异常类型
        description: 异常描述
        material: 材料类型
        process_type: 工艺类型
        
    Returns:
        str: 根本原因
    """
    # 异常类型到常见原因的映射
    type_cause_mapping = {
        "尺寸偏差": "加工设备精度不足、刀具磨损、工艺参数设置不当或测量误差",
        "表面缺陷": "加工过程中的划伤、氧化、材料表面质量问题或操作不当",
        "材料问题": "材料成分不符、材料质量不达标或材料存储不当",
        "组装问题": "零件配合不当、组装工艺问题、零件尺寸累积误差或操作失误"
    }
    
    # 获取基础原因
    base_cause = type_cause_mapping.get(exception_type, "未知原因，需进一步调查")
    
    # 根据描述关键词细化原因
    description_lower = description.lower()
    
    if exception_type == "尺寸偏差":
        if "超差" in description or "公差" in description:
            base_cause = "加工设备精度不足或刀具磨损导致尺寸超出公差范围"
        elif "测量" in description:
            base_cause = "测量方法不当或测量设备精度问题"
    
    elif exception_type == "表面缺陷":
        if "划痕" in description:
            base_cause = "加工或搬运过程中造成的表面划伤"
        elif "氧化" in description or "锈蚀" in description:
            base_cause = "材料表面氧化或存储环境不当"
        elif "毛刺" in description:
            base_cause = "加工后未进行充分的去毛刺处理"
    
    elif exception_type == "材料问题":
        if "硬度" in description:
            base_cause = "材料硬度不符合要求，可能是材料成分或热处理问题"
        elif "成分" in description:
            base_cause = "材料化学成分不符合规格要求"
    
    elif exception_type == "组装问题":
        if "配合" in description or "间隙" in description:
            base_cause = "零件配合尺寸不当，导致装配困难或间隙过大"
        elif "顺序" in description:
            base_cause = "组装顺序错误或组装工艺不当"
    
    # 考虑材料和工艺因素
    if material and "材料" not in base_cause:
        if material in ["钢", "不锈钢", "合金"]:
            base_cause += f"，{material}材料特性可能是影响因素之一"
    
    if process_type and "工艺" not in base_cause:
        base_cause += f"，{process_type}工艺控制可能存在问题"
    
    return base_cause


def _assess_severity(exception_type: str, description: str) -> str:
    """
    评估严重程度
    
    Args:
        exception_type: 异常类型
        description: 异常描述
        
    Returns:
        str: 严重程度 (critical, major, minor)
    """
    description_lower = description.lower()
    
    # 关键词判断
    critical_keywords = ["安全", "失效", "无法使用", "完全", "严重", "报废", "危险"]
    major_keywords = ["超差", "缺陷", "影响功能", "需返工", "不合格"]
    minor_keywords = ["轻微", "表面", "外观", "不影响", "可接受"]
    
    # 检查关键词
    for keyword in critical_keywords:
        if keyword in description_lower:
            return "critical"
    
    for keyword in minor_keywords:
        if keyword in description_lower:
            return "minor"
    
    for keyword in major_keywords:
        if keyword in description_lower:
            return "major"
    
    # 基于异常类型的默认严重程度
    type_severity_mapping = {
        "材料问题": "critical",  # 材料问题通常较严重
        "尺寸偏差": "major",     # 尺寸问题通常是主要缺陷
        "组装问题": "major",     # 组装问题影响功能
        "表面缺陷": "minor"      # 表面问题通常较轻微
    }
    
    return type_severity_mapping.get(exception_type, "major")


def _evaluate_impact_scope(
    exception_type: str,
    description: str,
    entity_type: str
) -> str:
    """
    评估影响范围
    
    Args:
        exception_type: 异常类型
        description: 异常描述
        entity_type: 实体类型
        
    Returns:
        str: 影响范围 (single_part, batch, entire_order)
    """
    description_lower = description.lower()
    
    # 关键词判断
    if any(keyword in description_lower for keyword in ["批次", "批量", "多个", "所有", "整批"]):
        return "batch"
    
    if any(keyword in description_lower for keyword in ["订单", "全部", "系统性", "普遍"]):
        return "entire_order"
    
    if any(keyword in description_lower for keyword in ["单个", "个别", "偶发", "一件"]):
        return "single_part"
    
    # 基于异常类型判断
    if exception_type in ["材料问题", "工艺问题"]:
        # 材料和工艺问题通常影响批次
        return "batch"
    elif exception_type == "组装问题":
        # 组装问题可能影响整个订单
        return "entire_order" if "系统" in description_lower else "batch"
    else:
        # 默认为单个零件
        return "single_part"


def _identify_contributing_factors(
    exception_type: str,
    description: str,
    material: Optional[str],
    process_type: Optional[str]
) -> List[str]:
    """
    识别贡献因素
    
    Args:
        exception_type: 异常类型
        description: 异常描述
        material: 材料类型
        process_type: 工艺类型
        
    Returns:
        List[str]: 贡献因素列表
    """
    factors = []
    
    # 1. 材料因素
    if material:
        factors.append(f"材料质量 ({material})")
    
    # 2. 工艺因素
    if process_type:
        factors.append(f"工艺控制 ({process_type})")
    
    # 3. 基于异常类型的因素
    type_factors = {
        "尺寸偏差": ["设备精度", "刀具状态", "工艺参数", "测量方法"],
        "表面缺陷": ["加工环境", "操作规范", "材料表面质量", "搬运方式"],
        "材料问题": ["材料供应商", "材料检验", "存储条件", "材料规格"],
        "组装问题": ["装配工艺", "零件配合", "操作技能", "工装夹具"]
    }
    
    if exception_type in type_factors:
        factors.extend(type_factors[exception_type])
    
    # 4. 基于描述的额外因素
    description_lower = description.lower()
    
    if "环境" in description_lower or "温度" in description_lower:
        factors.append("环境条件")
    
    if "人员" in description_lower or "操作" in description_lower:
        factors.append("人为因素")
    
    if "设备" in description_lower or "机器" in description_lower:
        factors.append("设备状态")
    
    if "设计" in description_lower or "图纸" in description_lower:
        factors.append("设计规格")
    
    # 去重
    factors = list(dict.fromkeys(factors))
    
    return factors if factors else ["需进一步调查"]


def _generate_analysis_summary(
    exception_type: str,
    root_cause: str,
    severity: str,
    impact_scope: str
) -> str:
    """
    生成分析摘要
    
    Args:
        exception_type: 异常类型
        root_cause: 根本原因
        severity: 严重程度
        impact_scope: 影响范围
        
    Returns:
        str: 分析摘要
    """
    severity_text = {
        "critical": "严重",
        "major": "主要",
        "minor": "轻微"
    }
    
    impact_text = {
        "single_part": "单个零件",
        "batch": "批次",
        "entire_order": "整个订单"
    }
    
    summary = f"异常类型为【{exception_type}】，严重程度评估为【{severity_text.get(severity, severity)}】，"
    summary += f"影响范围为【{impact_text.get(impact_scope, impact_scope)}】。"
    summary += f"根本原因分析：{root_cause}。"
    
    # 添加建议
    if severity == "critical":
        summary += "建议立即停止生产并进行全面检查。"
    elif severity == "major":
        summary += "建议尽快采取纠正措施，防止问题扩大。"
    else:
        summary += "建议记录并监控，必要时采取预防措施。"
    
    return summary


# 测试代码
if __name__ == "__main__":
    # 测试异常分析
    result = analyze_exception(
        exception_type="尺寸偏差",
        description="轴承座内径尺寸超差0.5mm，超出公差范围",
        entity_type="part",
        material="钢",
        process_type="数控加工"
    )
    
    print("异常分析结果:")
    print(f"根本原因: {result['root_cause']}")
    print(f"严重程度: {result['severity']}")
    print(f"影响范围: {result['impact_scope']}")
    print(f"贡献因素: {result['contributing_factors']}")
    print(f"分析摘要: {result['analysis_summary']}")
