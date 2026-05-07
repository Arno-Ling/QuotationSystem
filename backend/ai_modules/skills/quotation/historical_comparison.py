"""
HistoricalComparisonSkill - 历史对比技能
对比历史报价数据，分析价格趋势
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging

import sys
sys.path.append('../../..')
from harness.tools import tool

logger = logging.getLogger(__name__)


@tool(
    description="对比历史报价数据，分析价格趋势和供应商报价历史",
    permission="read_only"
)
def compare_with_history(
    part_id: str,
    current_price: float,
    supplier_id: str = None,
    time_range_months: int = 12
) -> Dict[str, Any]:
    """
    对比历史报价数据
    
    Args:
        part_id: 零件ID
        current_price: 当前报价
        supplier_id: 供应商ID（可选）
        time_range_months: 时间范围（月）
        
    Returns:
        Dict: 对比结果
        {
            "historical_prices": List[Dict],  # 历史价格列表
            "price_trend": "上涨" | "下降" | "稳定",
            "trend_percentage": float,  # 趋势百分比
            "average_price": float,  # 平均价格
            "min_price": float,  # 最低价格
            "max_price": float,  # 最高价格
            "current_vs_average": float,  # 当前价格 vs 平均价格 (%)
            "supplier_history": Dict,  # 该供应商历史
            "comparison_summary": str
        }
    """
    logger.info(f"Comparing historical prices for part {part_id}")
    
    try:
        # 1. 获取历史报价数据（模拟）
        historical_data = _fetch_historical_quotations(part_id, time_range_months)
        
        if not historical_data:
            return {
                "error": "No historical data found",
                "comparison_summary": f"零件 {part_id} 暂无历史报价数据"
            }
        
        # 2. 计算统计数据
        prices = [item['price'] for item in historical_data]
        average_price = sum(prices) / len(prices)
        min_price = min(prices)
        max_price = max(prices)
        
        # 3. 分析价格趋势
        price_trend, trend_percentage = _analyze_price_trend(historical_data)
        
        # 4. 当前价格 vs 平均价格
        current_vs_average = ((current_price - average_price) / average_price) * 100
        
        # 5. 获取该供应商的历史报价
        supplier_history = _get_supplier_history(historical_data, supplier_id) if supplier_id else {}
        
        # 6. 生成对比摘要
        comparison_summary = _generate_comparison_summary(
            part_id,
            current_price,
            average_price,
            price_trend,
            trend_percentage,
            current_vs_average,
            supplier_history
        )
        
        result = {
            "historical_prices": historical_data[-10:],  # 返回最近10条
            "price_trend": price_trend,
            "trend_percentage": round(trend_percentage, 2),
            "average_price": round(average_price, 2),
            "min_price": round(min_price, 2),
            "max_price": round(max_price, 2),
            "current_vs_average": round(current_vs_average, 2),
            "supplier_history": supplier_history,
            "comparison_summary": comparison_summary,
            "data_points": len(historical_data)
        }
        
        logger.info(f"Historical comparison completed: trend={price_trend}")
        return result
    
    except Exception as e:
        logger.error(f"Error comparing with history: {e}", exc_info=True)
        return {
            "error": str(e),
            "comparison_summary": f"历史对比失败: {str(e)}"
        }


def _fetch_historical_quotations(part_id: str, months: int) -> List[Dict[str, Any]]:
    """
    获取历史报价数据（模拟）
    
    实际应用中应该从数据库查询
    
    Args:
        part_id: 零件ID
        months: 时间范围（月）
        
    Returns:
        List[Dict]: 历史报价列表
    """
    # 模拟历史数据
    import random
    
    historical_data = []
    base_price = 50.0
    
    # 生成过去N个月的模拟数据
    for i in range(months * 2):  # 每月2条数据
        date = datetime.now() - timedelta(days=15 * i)
        
        # 模拟价格波动
        price_variation = random.uniform(-0.1, 0.15)  # -10% 到 +15%
        price = base_price * (1 + price_variation)
        
        # 模拟趋势（最近价格略有上涨）
        if i < months:
            price *= 1.05
        
        historical_data.append({
            "date": date.strftime("%Y-%m-%d"),
            "price": round(price, 2),
            "supplier_id": f"SUP{random.randint(1, 5):03d}",
            "supplier_name": f"供应商{random.randint(1, 5)}",
            "quantity": random.randint(100, 1000)
        })
    
    # 按日期排序
    historical_data.sort(key=lambda x: x['date'])
    
    return historical_data


def _analyze_price_trend(historical_data: List[Dict[str, Any]]) -> tuple:
    """
    分析价格趋势
    
    Args:
        historical_data: 历史数据列表
        
    Returns:
        tuple: (趋势描述, 趋势百分比)
    """
    if len(historical_data) < 2:
        return "稳定", 0.0
    
    # 取最近3个月和之前3个月的平均价格对比
    recent_count = min(6, len(historical_data) // 2)
    
    recent_prices = [item['price'] for item in historical_data[-recent_count:]]
    older_prices = [item['price'] for item in historical_data[:recent_count]]
    
    recent_avg = sum(recent_prices) / len(recent_prices)
    older_avg = sum(older_prices) / len(older_prices)
    
    trend_percentage = ((recent_avg - older_avg) / older_avg) * 100
    
    if trend_percentage > 5:
        trend = "上涨"
    elif trend_percentage < -5:
        trend = "下降"
    else:
        trend = "稳定"
    
    return trend, trend_percentage


def _get_supplier_history(
    historical_data: List[Dict[str, Any]],
    supplier_id: str
) -> Dict[str, Any]:
    """
    获取特定供应商的历史报价
    
    Args:
        historical_data: 历史数据列表
        supplier_id: 供应商ID
        
    Returns:
        Dict: 供应商历史数据
    """
    supplier_data = [
        item for item in historical_data 
        if item.get('supplier_id') == supplier_id
    ]
    
    if not supplier_data:
        return {
            "has_history": False,
            "message": "该供应商无历史报价记录"
        }
    
    prices = [item['price'] for item in supplier_data]
    
    return {
        "has_history": True,
        "quote_count": len(supplier_data),
        "average_price": round(sum(prices) / len(prices), 2),
        "min_price": round(min(prices), 2),
        "max_price": round(max(prices), 2),
        "last_quote_date": supplier_data[-1]['date'],
        "last_quote_price": supplier_data[-1]['price'],
        "recent_quotes": supplier_data[-3:]  # 最近3次报价
    }


def _generate_comparison_summary(
    part_id: str,
    current_price: float,
    average_price: float,
    price_trend: str,
    trend_percentage: float,
    current_vs_average: float,
    supplier_history: Dict
) -> str:
    """
    生成对比摘要
    
    Args:
        part_id: 零件ID
        current_price: 当前价格
        average_price: 平均价格
        price_trend: 价格趋势
        trend_percentage: 趋势百分比
        current_vs_average: 当前价格 vs 平均价格
        supplier_history: 供应商历史
        
    Returns:
        str: 对比摘要
    """
    summary = f"零件【{part_id}】的当前报价为 {current_price} 元/件，"
    summary += f"历史平均价格为 {average_price:.2f} 元/件。"
    
    if abs(current_vs_average) <= 5:
        summary += f"当前报价与历史平均价格基本持平（偏差 {abs(current_vs_average):.1f}%）。"
    elif current_vs_average > 5:
        summary += f"当前报价比历史平均价格高 {current_vs_average:.1f}%。"
    else:
        summary += f"当前报价比历史平均价格低 {abs(current_vs_average):.1f}%。"
    
    summary += f"\n\n价格趋势分析：近期价格呈【{price_trend}】趋势"
    if abs(trend_percentage) > 1:
        summary += f"（{abs(trend_percentage):.1f}%）"
    summary += "。"
    
    if supplier_history.get('has_history'):
        summary += f"\n\n该供应商历史报价：共 {supplier_history['quote_count']} 次报价，"
        summary += f"平均价格 {supplier_history['average_price']} 元/件，"
        summary += f"最近一次报价 {supplier_history['last_quote_price']} 元/件"
        summary += f"（{supplier_history['last_quote_date']}）。"
    else:
        summary += "\n\n该供应商为首次报价，无历史数据可供参考。"
    
    return summary


# 测试代码
if __name__ == "__main__":
    # 测试历史对比
    result = compare_with_history(
        part_id="PART001",
        current_price=55.0,
        supplier_id="SUP001",
        time_range_months=12
    )
    
    print("历史对比结果:")
    print(f"价格趋势: {result['price_trend']} ({result['trend_percentage']}%)")
    print(f"平均价格: {result['average_price']}")
    print(f"当前 vs 平均: {result['current_vs_average']}%")
    print(f"\n对比摘要:\n{result['comparison_summary']}")
