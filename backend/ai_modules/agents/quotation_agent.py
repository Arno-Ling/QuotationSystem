"""
QuotationAgent - 报价智能代理
整合所有报价相关的 Skills，提供智能报价分析服务
"""
import asyncio
import logging
from typing import Dict, Any, Optional

import sys
sys.path.append('../..')
from harness import AgentLoop, AgentConfig, ToolRegistry
from harness.memory import ShortTermMemory, LongTermMemory
from harness.observability import ConsoleCallback, CallbackManager

# 导入报价相关的 Skills（它们已经通过 @tool 装饰器自动注册）
sys.path.append('..')
from ai_modules.skills.quotation import quotation_analysis
from ai_modules.skills.quotation import historical_comparison
from ai_modules.skills.quotation import price_negotiation
from ai_modules.skills.quotation import rag_skill

logger = logging.getLogger(__name__)


class QuotationAgent:
    """
    报价智能代理
    
    功能：
    1. 分析供应商报价的合理性
    2. 对比历史报价数据
    3. 识别异常报价
    4. 生成谈判建议和策略
    """
    
    def __init__(
        self,
        model_name: str = "gpt-4",
        enable_callbacks: bool = True,
        enable_long_term_memory: bool = True
    ):
        """
        初始化报价代理
        
        Args:
            model_name: LLM 模型名称
            enable_callbacks: 是否启用回调
            enable_long_term_memory: 是否启用长期记忆
        """
        logger.info("Initializing QuotationAgent...")
        
        # 1. 创建专用配置
        self.config = AgentConfig(
            model_name=model_name,
            temperature=0.3,  # 报价分析需要较低温度，保证结果稳定
            max_steps=15,
            max_tokens=3000,
            enable_long_term_memory=enable_long_term_memory,
            system_prompt=self._create_system_prompt()
        )
        
        # 2. 获取全局工具注册表（Skills 已自动注册）
        from harness.tools import registry
        self.tool_registry = registry
        
        # 3. 创建记忆
        self.short_term_memory = ShortTermMemory(
            max_messages=self.config.max_short_term_messages
        )
        
        self.long_term_memory = None
        if enable_long_term_memory:
            self.long_term_memory = LongTermMemory(
                collection_name="quotation_agent_memory",
                persist_directory="./chroma_db/quotation_agent"
            )
        
        # 4. 创建回调管理器
        self.callback_manager = None
        if enable_callbacks:
            self.callback_manager = CallbackManager()
            console_callback = ConsoleCallback(verbose=False)
            self.callback_manager.add_callback(console_callback)
        
        # 5. 创建 AgentLoop
        self.agent_loop = AgentLoop(
            config=self.config,
            tool_registry=self.tool_registry,
            short_term_memory=self.short_term_memory,
            long_term_memory=self.long_term_memory
        )
        
        logger.info("QuotationAgent initialized successfully")
    
    def _create_system_prompt(self) -> str:
        """
        创建报价代理的系统提示词
        
        Returns:
            str: 系统提示词
        """
        return """你是一个专业的采购报价分析助手，擅长分析供应商报价、识别价格异常、提供谈判建议。

你的职责：
1. 分析供应商报价的合理性，包括价格水平、成本结构、利润空间
2. 对比历史报价数据，识别价格趋势和异常
3. 从知识库检索相关的历史案例和市场信息
4. 生成专业的谈判策略和建议

可用工具：
- analyze_quotation: 分析报价的合理性和成本结构
- compare_with_history: 对比历史报价数据
- generate_negotiation_strategy: 生成谈判策略
- search_quotation_knowledge: 从知识库检索相关信息

工作流程：
1. 首先使用 analyze_quotation 分析当前报价
2. 然后使用 compare_with_history 对比历史数据
3. 使用 search_quotation_knowledge 检索相关知识
4. 最后使用 generate_negotiation_strategy 生成谈判建议
5. 综合所有信息，给出最终分析报告

输出格式：
当完成分析后，使用以下格式输出：

Final Answer: 
【报价分析报告】

一、基本信息
- 零件名称：XXX
- 供应商：XXX
- 报价：XXX 元/件
- 数量：XXX 件

二、价格分析
- 价格水平：XXX
- 价格偏离度：XXX%
- 合理性评分：XXX 分
- 成本结构：材料成本 XXX，加工成本 XXX，利润 XXX

三、历史对比
- 历史平均价格：XXX 元/件
- 价格趋势：XXX
- 当前价格 vs 平均价格：XXX%

四、谈判建议
- 议价潜力：XXX%
- 推荐目标价格：XXX 元/件
- 谈判策略：XXX
- 预期节省：XXX 元

五、综合建议
XXX

请严格按照工作流程使用工具，确保分析全面准确。
"""
    
    async def analyze_quotation(
        self,
        quotation_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        分析供应商报价
        
        Args:
            quotation_data: 报价数据
            {
                "part_name": str,  # 零件名称
                "part_id": str,  # 零件ID
                "unit_price": float,  # 单价
                "quantity": int,  # 数量
                "material": str,  # 材料
                "process_type": str,  # 工艺类型
                "supplier_id": str,  # 供应商ID
                "supplier_name": str,  # 供应商名称
                "target_price": float,  # 目标价格（可选）
                "supplier_rating": str  # 供应商评级（可选）
            }
            
        Returns:
            Dict: 分析结果
        """
        logger.info(f"Analyzing quotation for {quotation_data.get('part_name')}")
        
        try:
            # 构建分析任务
            task = self._build_analysis_task(quotation_data)
            
            # 触发回调
            if self.callback_manager:
                self.callback_manager.on_agent_start(task, self.config.dict())
            
            # 运行 Agent
            result = await self.agent_loop.run(task)
            
            # 触发回调
            if self.callback_manager:
                self.callback_manager.on_agent_complete(
                    result,
                    self.agent_loop.current_step
                )
            
            # 解析结果
            parsed_result = self._parse_analysis_result(result, quotation_data)
            
            logger.info("Quotation analysis completed successfully")
            return parsed_result
        
        except Exception as e:
            logger.error(f"Error analyzing quotation: {e}", exc_info=True)
            if self.callback_manager:
                self.callback_manager.on_error(e)
            
            return {
                "success": False,
                "error": str(e),
                "message": f"报价分析失败: {str(e)}"
            }
    
    def _build_analysis_task(self, quotation_data: Dict[str, Any]) -> str:
        """
        构建分析任务描述
        
        Args:
            quotation_data: 报价数据
            
        Returns:
            str: 任务描述
        """
        task = f"""请分析以下供应商报价：

零件信息：
- 零件名称：{quotation_data.get('part_name', '未知')}
- 零件ID：{quotation_data.get('part_id', '未知')}
- 材料：{quotation_data.get('material', '未知')}
- 工艺类型：{quotation_data.get('process_type', '未知')}

报价信息：
- 供应商：{quotation_data.get('supplier_name', '未知')}
- 供应商ID：{quotation_data.get('supplier_id', '未知')}
- 单价：{quotation_data.get('unit_price', 0)} 元/件
- 数量：{quotation_data.get('quantity', 0)} 件
- 总金额：{quotation_data.get('unit_price', 0) * quotation_data.get('quantity', 0)} 元
"""
        
        if quotation_data.get('target_price'):
            task += f"- 目标价格：{quotation_data['target_price']} 元/件\n"
        
        if quotation_data.get('supplier_rating'):
            task += f"- 供应商评级：{quotation_data['supplier_rating']}\n"
        
        task += """
请按照以下步骤进行分析：
1. 使用 analyze_quotation 工具分析报价合理性
2. 使用 compare_with_history 工具对比历史数据
3. 使用 search_quotation_knowledge 工具检索相关知识
4. 使用 generate_negotiation_strategy 工具生成谈判建议
5. 综合所有信息，生成完整的分析报告

请确保分析全面、准确，并给出明确的建议。
"""
        
        return task
    
    def _parse_analysis_result(
        self,
        result: str,
        quotation_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        解析分析结果
        
        Args:
            result: Agent 返回的结果
            quotation_data: 原始报价数据
            
        Returns:
            Dict: 结构化的分析结果
        """
        return {
            "success": True,
            "quotation_data": quotation_data,
            "analysis_report": result,
            "timestamp": self._get_timestamp(),
            "agent_steps": self.agent_loop.current_step
        }
    
    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def get_state(self) -> Dict[str, Any]:
        """
        获取 Agent 状态
        
        Returns:
            Dict: 状态信息
        """
        return {
            "agent_type": "QuotationAgent",
            "model": self.config.model_name,
            "tools_available": len(self.tool_registry),
            "agent_loop_state": self.agent_loop.get_state()
        }


# 测试代码
async def test_quotation_agent():
    """测试报价代理"""
    print("=" * 80)
    print("测试 QuotationAgent")
    print("=" * 80)
    
    # 创建代理
    agent = QuotationAgent(
        model_name="gpt-4",
        enable_callbacks=True,
        enable_long_term_memory=False  # 测试时禁用长期记忆
    )
    
    # 测试报价数据
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
    
    # 分析报价
    print("\n开始分析报价...")
    result = await agent.analyze_quotation(quotation_data)
    
    if result['success']:
        print("\n✅ 分析成功!")
        print(f"\n分析报告:\n{result['analysis_report']}")
        print(f"\n执行步数: {result['agent_steps']}")
    else:
        print(f"\n❌ 分析失败: {result.get('error')}")


if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_quotation_agent())
