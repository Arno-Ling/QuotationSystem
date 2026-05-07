"""
QuotationAnalysisSkill - 报价分析技能
分析供应商报价的合理性、成本结构和利润空间
"""
from typing import Dict, Any
import logging

# 导入 Harness 框架的工具装饰器
import sys
sys.path.append('../../..')
from harness.tools import tool

logger = logging.getLogger(__name__)


@tool(
    description="分析供应商报价的合理性，包括价格分析、成本拆解和利润评估",
    permission="read_only"
)
def analyze_quotation(
    part_name: str,
    unit_price: float,
    quantity: int,
    material: str,
    process_type: str,
    supplier_name: str
) -> Dict[str, Any]:
    """
    分析供应商报价
    
    Args:
        part_name: 零件名称
        unit_price: 单价
        quantity: 数量
        material: 材料
        process_type: 工艺类型
        supplier_name: 供应商名称
        
    Returns:
        Dict: 分析结果
        {
            "price_level": "合理" | "偏高" | "偏低",
            "price_deviation": float,  # 价格偏离度 (%)
            "cost_breakdown": {
                "material_cost": float,
                "processing_cost": float,
                "profit_margin": float
            },
            "reasonableness_score": float,  # 合理性评分 0-100
            "analysis_summary": str,
            "risk_factors": List[str]
        }
    """
    logger.info(f"Analyzing quotation for {part_name} from {supplier_name}")
    
    try:
        # 1. 计算总价
        total_amount = unit_price * quantity
        
        # 2. 估算成本结构（基于经验公式）
        material_cost_ratio = _estimate_material_cost_ratio(material, process_type)
        processing_cost_ratio = _estimate_processing_cost_ratio(process_type)
        
        estimated_material_cost = unit_price * material_cost_ratio
        estimated_processing_cost = unit_price * processing_cost_ratio
        estimated_profit_margin = unit_price * (1 - material_cost_ratio - processing_cost_ratio)
        
        # 3. 价格合理性评估
        market_reference_price = _get_market_reference_price(material, process_type)
        price_deviation = ((unit_price - market_reference_price) / market_reference_price) * 100
        
        # 4. 判断价格水平
        if abs(price_deviation) <= 10:
            price_level = "合理"
        elif price_deviation > 10:
            price_level = "偏高"
        else:
            price_level = "偏低"
        
        # 5. 计算合理性评分
        reasonableness_score = _calculate_reasonableness_score(
            price_deviation, 
            estimated_profit_margin / unit_price if unit_price > 0 else 0,
            quantity
        )
        
        # 6. 识别风险因素
        risk_factors = _identify_risk_factors(
            price_level, 
            price_deviation, 
            estimated_profit_margin / unit_price if unit_price > 0 else 0,
            quantity
        )
        
        # 7. 生成分析摘要
        analysis_summary = _generate_analysis_summary(
            part_name,
            supplier_name,
            unit_price,
            price_level,
            price_deviation,
            reasonableness_score
        )
        
        result = {
            "price_level": price_level,
            "price_deviation": round(price_deviation, 2),
            "cost_breakdown": {
                "material_cost": round(estimated_material_cost, 2),
                "processing_cost": round(estimated_processing_cost, 2),
                "profit_margin": round(estimated_profit_margin, 2)
            },
            "reasonableness_score": round(reasonableness_score, 2),
            "analysis_summary": analysis_summary,
            "risk_factors": risk_factors,
            "total_amount": round(total_amount, 2)
        }
        
        logger.info(f"Analysis completed: {price_level}, score: {reasonableness_score}")
        return result
    
    except Exception as e:
        logger.error(f"Error analyzing quotation: {e}", exc_info=True)
        return {
            "error": str(e),
            "price_level": "未知",
            "analysis_summary": f"分析失败: {str(e)}"
        }


def _estimate_material_cost_ratio(material: str, process_type: str) -> float:
    """
    估算材料成本占比
    
    Args:
        material: 材料类型
        process_type: 工艺类型
        
    Returns:
        float: 材料成本占比 (0-1)
    """
    # 基础材料成本占比
    material_ratios = {
        "钢": 0.35,
        "铝": 0.30,
        "铜": 0.40,
        "塑料": 0.25,
        "不锈钢": 0.38,
        "合金": 0.42
    }
    
    base_ratio = material_ratios.get(material, 0.30)
    
    # 根据工艺类型调整
    if "精密" in process_type or "高精度" in process_type:
        base_ratio *= 0.9  # 精密加工材料占比相对降低
    
    return base_ratio


def _estimate_processing_cost_ratio(process_type: str) -> float:
    """
    估算加工成本占比
    
    Args:
        process_type: 工艺类型
        
    Returns:
        float: 加工成本占比 (0-1)
    """
    # 不同工艺的加工成本占比
    process_ratios = {
        "车削": 0.25,
        "铣削": 0.30,
        "磨削": 0.35,
        "钻孔": 0.20,
        "精密加工": 0.40,
        "数控加工": 0.35,
        "普通加工": 0.25
    }
    
    for key, ratio in process_ratios.items():
        if key in process_type:
            return ratio
    
    return 0.30  # 默认值


def _get_market_reference_price(material: str, process_type: str) -> float:
    """
    获取市场参考价格（模拟）
    
    实际应用中应该从数据库或外部API获取
    
    Args:
        material: 材料类型
        process_type: 工艺类型
        
    Returns:
        float: 市场参考价格
    """
    # 基础价格（元/件）
    base_prices = {
        "钢": 50,
        "铝": 45,
        "铜": 80,
        "塑料": 30,
        "不锈钢": 70,
        "合金": 90
    }
    
    base_price = base_prices.get(material, 50)
    
    # 根据工艺类型调整
    if "精密" in process_type:
        base_price *= 1.5
    elif "数控" in process_type:
        base_price *= 1.3
    
    return base_price


def _calculate_reasonableness_score(
    price_deviation: float,
    profit_margin_ratio: float,
    quantity: int
) -> float:
    """
    计算合理性评分
    
    Args:
        price_deviation: 价格偏离度 (%)
        profit_margin_ratio: 利润率
        quantity: 数量
        
    Returns:
        float: 合理性评分 (0-100)
    """
    score = 100.0
    
    # 1. 价格偏离度扣分
    if abs(price_deviation) > 30:
        score -= 40
    elif abs(price_deviation) > 20:
        score -= 25
    elif abs(price_deviation) > 10:
        score -= 10
    
    # 2. 利润率合理性
    if profit_margin_ratio < 0.05:  # 利润率过低
        score -= 20
    elif profit_margin_ratio > 0.40:  # 利润率过高
        score -= 15
    
    # 3. 数量因素（大批量应该有折扣）
    if quantity > 1000 and price_deviation > 0:
        score -= 10  # 大批量但价格偏高
    
    return max(0, min(100, score))


def _identify_risk_factors(
    price_level: str,
    price_deviation: float,
    profit_margin_ratio: float,
    quantity: int
) -> list:
    """
    识别风险因素
    
    Args:
        price_level: 价格水平
        price_deviation: 价格偏离度
        profit_margin_ratio: 利润率
        quantity: 数量
        
    Returns:
        List[str]: 风险因素列表
    """
    risks = []
    
    if price_level == "偏高":
        if price_deviation > 30:
            risks.append("价格严重偏高，建议重新询价")
        elif price_deviation > 20:
            risks.append("价格明显偏高，建议谈判降价")
        else:
            risks.append("价格略高，可尝试议价")
    
    if price_level == "偏低":
        if price_deviation < -20:
            risks.append("价格异常偏低，可能存在质量风险")
        else:
            risks.append("价格偏低，需确认质量标准")
    
    if profit_margin_ratio < 0.05:
        risks.append("供应商利润空间极小，可能影响质量或交期")
    
    if profit_margin_ratio > 0.40:
        risks.append("供应商利润率过高，存在较大议价空间")
    
    if quantity > 1000 and price_deviation > 5:
        risks.append("大批量订单未享受批量折扣")
    
    if not risks:
        risks.append("暂无明显风险")
    
    return risks


def _generate_analysis_summary(
    part_name: str,
    supplier_name: str,
    unit_price: float,
    price_level: str,
    price_deviation: float,
    reasonableness_score: float
) -> str:
    """
    生成分析摘要
    
    Args:
        part_name: 零件名称
        supplier_name: 供应商名称
        unit_price: 单价
        price_level: 价格水平
        price_deviation: 价格偏离度
        reasonableness_score: 合理性评分
        
    Returns:
        str: 分析摘要
    """
    summary = f"供应商【{supplier_name}】对零件【{part_name}】的报价为 {unit_price} 元/件，"
    summary += f"价格水平评估为【{price_level}】，"
    summary += f"相对市场参考价格偏离 {abs(price_deviation):.1f}%。"
    summary += f"综合合理性评分为 {reasonableness_score:.1f} 分。"
    
    if reasonableness_score >= 80:
        summary += "该报价整体合理，建议接受。"
    elif reasonableness_score >= 60:
        summary += "该报价基本合理，可考虑适当议价。"
    else:
        summary += "该报价存在较大问题，建议谨慎处理或重新询价。"
    
    return summary


# 测试代码
if __name__ == "__main__":
    # 测试报价分析
    result = analyze_quotation(
        part_name="轴承座",
        unit_price=55.0,
        quantity=500,
        material="钢",
        process_type="数控加工",
        supplier_name="精密机械厂"
    )
    
    print("报价分析结果:")
    print(f"价格水平: {result['price_level']}")
    print(f"价格偏离度: {result['price_deviation']}%")
    print(f"合理性评分: {result['reasonableness_score']}")
    print(f"分析摘要: {result['analysis_summary']}")
    print(f"风险因素: {result['risk_factors']}")
