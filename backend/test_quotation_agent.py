"""
测试 QuotationAgent
验证报价智能代理的功能
"""
import asyncio
import sys
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 导入 QuotationAgent
from ai_modules.agents.quotation_agent import QuotationAgent


async def test_basic_analysis():
    """测试基础报价分析"""
    print("\n" + "=" * 80)
    print("测试 1: 基础报价分析")
    print("=" * 80)
    
    # 创建代理
    agent = QuotationAgent(
        model_name="gpt-4",
        enable_callbacks=True,
        enable_long_term_memory=False
    )
    
    # 测试数据
    quotation_data = {
        "part_name": "轴承座",
        "part_id": "PART001",
        "unit_price": 60.0,
        "quantity": 800,
        "material": "钢",
        "process_type": "数控加工",
        "supplier_id": "SUP001",
        "supplier_name": "精密机械厂",
        "target_price": 50.0,
        "supplier_rating": "良好"
    }
    
    print("\n📋 报价信息:")
    print(f"  零件: {quotation_data['part_name']}")
    print(f"  供应商: {quotation_data['supplier_name']}")
    print(f"  单价: {quotation_data['unit_price']} 元/件")
    print(f"  数量: {quotation_data['quantity']} 件")
    print(f"  目标价格: {quotation_data['target_price']} 元/件")
    
    print("\n🤖 开始 AI 分析...")
    
    # 分析报价
    result = await agent.analyze_quotation(quotation_data)
    
    if result['success']:
        print("\n✅ 分析成功!")
        print(f"\n📊 分析报告:")
        print("-" * 80)
        print(result['analysis_report'])
        print("-" * 80)
        print(f"\n⚙️  执行步数: {result['agent_steps']}")
        print(f"⏰ 完成时间: {result['timestamp']}")
    else:
        print(f"\n❌ 分析失败: {result.get('error')}")
    
    return result


async def test_high_price_quotation():
    """测试高价报价分析"""
    print("\n" + "=" * 80)
    print("测试 2: 高价报价分析")
    print("=" * 80)
    
    agent = QuotationAgent(
        model_name="gpt-4",
        enable_callbacks=False,
        enable_long_term_memory=False
    )
    
    # 高价报价数据
    quotation_data = {
        "part_name": "连接件",
        "part_id": "PART002",
        "unit_price": 85.0,  # 明显偏高
        "quantity": 500,
        "material": "铝",
        "process_type": "普通加工",
        "supplier_id": "SUP002",
        "supplier_name": "通用机械厂",
        "target_price": 50.0,
        "supplier_rating": "一般"
    }
    
    print("\n📋 报价信息:")
    print(f"  零件: {quotation_data['part_name']}")
    print(f"  供应商: {quotation_data['supplier_name']}")
    print(f"  单价: {quotation_data['unit_price']} 元/件 (明显偏高)")
    print(f"  数量: {quotation_data['quantity']} 件")
    
    print("\n🤖 开始 AI 分析...")
    
    result = await agent.analyze_quotation(quotation_data)
    
    if result['success']:
        print("\n✅ 分析成功!")
        print(f"\n📊 分析报告:")
        print("-" * 80)
        print(result['analysis_report'])
        print("-" * 80)
    else:
        print(f"\n❌ 分析失败: {result.get('error')}")
    
    return result


async def test_large_quantity_quotation():
    """测试大批量报价分析"""
    print("\n" + "=" * 80)
    print("测试 3: 大批量报价分析")
    print("=" * 80)
    
    agent = QuotationAgent(
        model_name="gpt-4",
        enable_callbacks=False,
        enable_long_term_memory=False
    )
    
    # 大批量报价数据
    quotation_data = {
        "part_name": "标准件",
        "part_id": "PART003",
        "unit_price": 35.0,
        "quantity": 2000,  # 大批量
        "material": "塑料",
        "process_type": "注塑成型",
        "supplier_id": "SUP003",
        "supplier_name": "塑料制品厂",
        "target_price": 30.0,
        "supplier_rating": "优秀"
    }
    
    print("\n📋 报价信息:")
    print(f"  零件: {quotation_data['part_name']}")
    print(f"  供应商: {quotation_data['supplier_name']}")
    print(f"  单价: {quotation_data['unit_price']} 元/件")
    print(f"  数量: {quotation_data['quantity']} 件 (大批量)")
    
    print("\n🤖 开始 AI 分析...")
    
    result = await agent.analyze_quotation(quotation_data)
    
    if result['success']:
        print("\n✅ 分析成功!")
        print(f"\n📊 分析报告:")
        print("-" * 80)
        print(result['analysis_report'])
        print("-" * 80)
    else:
        print(f"\n❌ 分析失败: {result.get('error')}")
    
    return result


async def main():
    """主测试函数"""
    print("\n" + "=" * 80)
    print("QuotationAgent 功能测试")
    print("=" * 80)
    
    print("\n⚠️  注意: 这些测试需要配置 OPENAI_API_KEY 环境变量")
    print("如果没有配置，测试将会失败\n")
    
    try:
        # 测试 1: 基础报价分析
        await test_basic_analysis()
        
        # 测试 2: 高价报价分析
        # await test_high_price_quotation()
        
        # 测试 3: 大批量报价分析
        # await test_large_quantity_quotation()
        
        print("\n" + "=" * 80)
        print("✅ 所有测试完成!")
        print("=" * 80)
    
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
