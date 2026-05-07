"""
PriceNegotiationSkill - 谈判建议技能
生成谈判策略和建议
"""
from typing import Dict, Any, List
import logging

import sys
sys.path.append('../../..')
from harness.tools import tool

logger = logging.getLogger(__name__)


@tool(
    description="生成价格谈判策略和建议，包括降价空间评估和谈判话术",
    permission="read_only"
)
def generate_negotiation_strategy(
    current_price: float,
    target_price: float,
    market_average: float,
    supplier_profit_margin: float,
    quantity: int,
    supplier_rating: str = "良好"
) -> Dict[str, Any]:
    """
    生成谈判策略
    
    Args:
        current_price: 当前报价
        target_price: 目标价格
        market_average: 市场平均价格
        supplier_profit_margin: 供应商利润率
        quantity: 采购数量
        supplier_rating: 供应商评级
        
    Returns:
        Dict: 谈判策略
        {
            "negotiation_potential": float,  # 议价潜力 (%)
            "recommended_target": float,  # 推荐目标价格
            "negotiation_strategy": str,  # 谈判策略
            "key_points": List[str],  # 谈判要点
            "talking_points": List[str],  # 谈判话术
            "concession_plan": Dict,  # 让步计划
            "risk_assessment": str  # 风险评估
        }
    """
    logger.info(f"Generating negotiation strategy: current={current_price}, target={target_price}")
    
    try:
        # 1. 计算议价潜力
        negotiation_potential = _calculate_negotiation_potential(
            current_price,
            market_average,
            supplier_profit_margin,
            quantity
        )
        
        # 2. 推荐目标价格
        recommended_target = _calculate_recommended_target(
            current_price,
            target_price,
            market_average,
            negotiation_potential
        )
        
        # 3. 选择谈判策略
        strategy = _select_negotiation_strategy(
            current_price,
            recommended_target,
            supplier_rating,
            quantity
        )
        
        # 4. 生成谈判要点
        key_points = _generate_key_points(
            current_price,
            market_average,
            supplier_profit_margin,
            quantity
        )
        
        # 5. 生成谈判话术
        talking_points = _generate_talking_points(
            current_price,
            recommended_target,
            market_average,
            quantity,
            strategy
        )
        
        # 6. 制定让步计划
        concession_plan = _create_concession_plan(
            current_price,
            recommended_target,
            negotiation_potential
        )
        
        # 7. 风险评估
        risk_assessment = _assess_negotiation_risk(
            current_price,
            recommended_target,
            supplier_rating,
            negotiation_potential
        )
        
        result = {
            "negotiation_potential": round(negotiation_potential, 2),
            "recommended_target": round(recommended_target, 2),
            "negotiation_strategy": strategy,
            "key_points": key_points,
            "talking_points": talking_points,
            "concession_plan": concession_plan,
            "risk_assessment": risk_assessment,
            "expected_savings": round((current_price - recommended_target) * quantity, 2)
        }
        
        logger.info(f"Negotiation strategy generated: potential={negotiation_potential}%")
        return result
    
    except Exception as e:
        logger.error(f"Error generating negotiation strategy: {e}", exc_info=True)
        return {
            "error": str(e),
            "negotiation_strategy": f"策略生成失败: {str(e)}"
        }


def _calculate_negotiation_potential(
    current_price: float,
    market_average: float,
    profit_margin: float,
    quantity: int
) -> float:
    """
    计算议价潜力
    
    Args:
        current_price: 当前价格
        market_average: 市场平均价格
        profit_margin: 利润率
        quantity: 数量
        
    Returns:
        float: 议价潜力百分比
    """
    potential = 0.0
    
    # 1. 基于市场价格的议价空间
    if current_price > market_average:
        market_gap = ((current_price - market_average) / current_price) * 100
        potential += market_gap * 0.6  # 60%的市场差价可议价
    
    # 2. 基于利润率的议价空间
    if profit_margin > 0.15:  # 利润率超过15%
        profit_gap = (profit_margin - 0.15) * 100
        potential += profit_gap * 0.5  # 50%的超额利润可议价
    
    # 3. 基于数量的议价空间
    if quantity >= 1000:
        potential += 5  # 大批量额外5%议价空间
    elif quantity >= 500:
        potential += 3
    elif quantity >= 100:
        potential += 1
    
    return min(potential, 25)  # 最大25%议价空间


def _calculate_recommended_target(
    current_price: float,
    target_price: float,
    market_average: float,
    negotiation_potential: float
) -> float:
    """
    计算推荐目标价格
    
    Args:
        current_price: 当前价格
        target_price: 期望目标价格
        market_average: 市场平均价格
        negotiation_potential: 议价潜力
        
    Returns:
        float: 推荐目标价格
    """
    # 基于议价潜力计算可达成的目标
    achievable_target = current_price * (1 - negotiation_potential / 100)
    
    # 综合考虑期望目标和市场平均
    if target_price < achievable_target:
        # 期望目标过低，使用可达成目标
        recommended = achievable_target
    elif target_price > market_average:
        # 期望目标过高，使用市场平均
        recommended = market_average
    else:
        # 期望目标合理
        recommended = target_price
    
    return max(recommended, market_average * 0.9)  # 不低于市场价的90%


def _select_negotiation_strategy(
    current_price: float,
    target_price: float,
    supplier_rating: str,
    quantity: int
) -> str:
    """
    选择谈判策略
    
    Args:
        current_price: 当前价格
        target_price: 目标价格
        supplier_rating: 供应商评级
        quantity: 数量
        
    Returns:
        str: 谈判策略描述
    """
    price_gap = ((current_price - target_price) / current_price) * 100
    
    if price_gap < 5:
        strategy = "温和协商策略"
        description = "价格差距较小，采用温和协商方式，强调长期合作价值。"
    elif price_gap < 15:
        strategy = "标准谈判策略"
        description = "价格差距适中，采用标准谈判流程，结合市场数据和批量优势进行议价。"
    else:
        strategy = "强势谈判策略"
        description = "价格差距较大，采用强势谈判姿态，必要时考虑更换供应商。"
    
    # 根据供应商评级调整
    if supplier_rating in ["优秀", "良好"] and price_gap > 10:
        description += " 考虑到供应商评级较高，可适当放宽价格要求以维护关系。"
    
    # 根据数量调整
    if quantity >= 1000:
        description += " 强调大批量订单的价值，要求批量折扣。"
    
    return f"{strategy}: {description}"


def _generate_key_points(
    current_price: float,
    market_average: float,
    profit_margin: float,
    quantity: int
) -> List[str]:
    """
    生成谈判要点
    
    Args:
        current_price: 当前价格
        market_average: 市场平均价格
        profit_margin: 利润率
        quantity: 数量
        
    Returns:
        List[str]: 谈判要点列表
    """
    key_points = []
    
    # 1. 市场价格对比
    if current_price > market_average * 1.1:
        key_points.append(f"当前报价比市场平均价格高 {((current_price/market_average - 1) * 100):.1f}%，存在明显降价空间")
    
    # 2. 利润率分析
    if profit_margin > 0.20:
        key_points.append(f"供应商利润率达 {profit_margin*100:.1f}%，高于行业平均水平，有议价余地")
    
    # 3. 批量优势
    if quantity >= 500:
        key_points.append(f"本次采购数量为 {quantity} 件，属于大批量订单，应享受批量折扣")
    
    # 4. 长期合作
    key_points.append("强调长期合作意向，争取更优惠价格")
    
    # 5. 竞争压力
    key_points.append("提及已向多家供应商询价，存在竞争压力")
    
    return key_points


def _generate_talking_points(
    current_price: float,
    target_price: float,
    market_average: float,
    quantity: int,
    strategy: str
) -> List[str]:
    """
    生成谈判话术
    
    Args:
        current_price: 当前价格
        target_price: 目标价格
        market_average: 市场平均价格
        quantity: 数量
        strategy: 谈判策略
        
    Returns:
        List[str]: 谈判话术列表
    """
    talking_points = []
    
    # 开场白
    talking_points.append(
        f"【开场】感谢贵司的报价。我们对贵司的产品质量和服务一直很认可，"
        f"希望能在价格上达成更有竞争力的合作方案。"
    )
    
    # 市场对比
    if current_price > market_average:
        talking_points.append(
            f"【市场对比】根据我们的市场调研，同类产品的市场平均价格在 {market_average:.2f} 元左右，"
            f"贵司的报价相对偏高。能否考虑调整到更接近市场水平？"
        )
    
    # 批量优势
    if quantity >= 500:
        talking_points.append(
            f"【批量优势】本次我们的采购量达到 {quantity} 件，属于大批量订单，"
            f"希望能获得相应的批量折扣。我们的目标价格是 {target_price:.2f} 元/件。"
        )
    
    # 长期合作
    talking_points.append(
        f"【长期合作】我们非常重视与优质供应商的长期合作关系。"
        f"如果价格合适，我们愿意签订长期供货协议，保证稳定的订单量。"
    )
    
    # 竞争压力
    if "强势" in strategy:
        talking_points.append(
            f"【竞争压力】坦率地说，我们已经收到其他供应商更具竞争力的报价。"
            f"如果价格无法达成一致，我们可能需要考虑其他选择。"
        )
    
    # 结束语
    talking_points.append(
        f"【结束语】希望贵司能重新考虑价格方案。我们期待与贵司建立长期稳定的合作关系，"
        f"实现双赢。请问贵司能否在价格上做出调整？"
    )
    
    return talking_points


def _create_concession_plan(
    current_price: float,
    target_price: float,
    negotiation_potential: float
) -> Dict[str, Any]:
    """
    制定让步计划
    
    Args:
        current_price: 当前价格
        target_price: 目标价格
        negotiation_potential: 议价潜力
        
    Returns:
        Dict: 让步计划
    """
    price_gap = current_price - target_price
    
    # 三步让步计划
    step1_price = current_price - price_gap * 0.3  # 第一步：降30%的差价
    step2_price = current_price - price_gap * 0.6  # 第二步：降60%的差价
    step3_price = target_price  # 第三步：达到目标价格
    
    # 底线价格（不低于目标价格的95%）
    bottom_line = target_price * 0.95
    
    return {
        "step_1": {
            "price": round(step1_price, 2),
            "description": "首轮谈判目标，要求降价30%的差距",
            "condition": "如果供应商态度强硬，可接受此价格"
        },
        "step_2": {
            "price": round(step2_price, 2),
            "description": "第二轮谈判目标，要求降价60%的差距",
            "condition": "如果供应商愿意让步，继续争取更低价格"
        },
        "step_3": {
            "price": round(step3_price, 2),
            "description": "最终目标价格",
            "condition": "理想情况下达成的价格"
        },
        "bottom_line": {
            "price": round(bottom_line, 2),
            "description": "绝对底线，低于此价格不予考虑",
            "condition": "如果无法达成，考虑更换供应商"
        }
    }


def _assess_negotiation_risk(
    current_price: float,
    target_price: float,
    supplier_rating: str,
    negotiation_potential: float
) -> str:
    """
    评估谈判风险
    
    Args:
        current_price: 当前价格
        target_price: 目标价格
        supplier_rating: 供应商评级
        negotiation_potential: 议价潜力
        
    Returns:
        str: 风险评估
    """
    price_reduction = ((current_price - target_price) / current_price) * 100
    
    risk_level = "低"
    risks = []
    
    # 评估价格降幅风险
    if price_reduction > negotiation_potential * 1.5:
        risk_level = "高"
        risks.append("目标降价幅度超过议价潜力，可能导致谈判破裂")
    elif price_reduction > negotiation_potential:
        risk_level = "中"
        risks.append("目标降价幅度略高，需要较强的谈判技巧")
    
    # 评估供应商关系风险
    if supplier_rating in ["优秀", "良好"] and price_reduction > 15:
        risks.append("过度压价可能影响与优质供应商的长期合作关系")
    
    # 评估质量风险
    if price_reduction > 20:
        risks.append("大幅降价可能导致供应商降低质量标准")
    
    if not risks:
        risks.append("谈判风险较低，目标价格合理可行")
    
    assessment = f"风险等级：【{risk_level}】\n"
    assessment += "风险因素：\n"
    for i, risk in enumerate(risks, 1):
        assessment += f"{i}. {risk}\n"
    
    return assessment


# 测试代码
if __name__ == "__main__":
    # 测试谈判策略生成
    result = generate_negotiation_strategy(
        current_price=60.0,
        target_price=50.0,
        market_average=52.0,
        supplier_profit_margin=0.25,
        quantity=800,
        supplier_rating="良好"
    )
    
    print("谈判策略:")
    print(f"议价潜力: {result['negotiation_potential']}%")
    print(f"推荐目标: {result['recommended_target']} 元")
    print(f"策略: {result['negotiation_strategy']}")
    print(f"\n谈判要点:")
    for point in result['key_points']:
        print(f"  - {point}")
    print(f"\n预期节省: {result['expected_savings']} 元")
