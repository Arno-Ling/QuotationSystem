"""
ExceptionAgent - 异常分析智能代理
整合所有异常分析相关的 Skills，提供智能异常分析服务
"""
import asyncio
import logging
from typing import Dict, Any, Optional
import time
import os
import sys

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(os.path.dirname(current_dir))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from harness import AgentLoop, AgentConfig, ToolRegistry
from harness.memory import ShortTermMemory, LongTermMemory
from harness.observability import ConsoleCallback, CallbackManager

# 导入异常分析相关的 Skills（它们已经通过 @tool 装饰器自动注册）
from ai_modules.skills.exception import exception_analysis
from ai_modules.skills.exception import responsibility_determination
from ai_modules.skills.exception import solution_recommendation
from ai_modules.skills.exception import rag_skill

logger = logging.getLogger(__name__)


class ExceptionAgent:
    """
    异常分析智能代理
    
    功能：
    1. 分析质量异常的根本原因、严重程度和影响范围
    2. 从知识库检索相似的历史异常案例
    3. 判定责任方（内部、供应商、材料商）
    4. 推荐解决方案并评估成本和时间影响
    """
    
    def __init__(
        self,
        model_name: str = "gpt-4",
        enable_callbacks: bool = True,
        enable_long_term_memory: bool = True
    ):
        """
        初始化异常分析代理
        
        Args:
            model_name: LLM 模型名称
            enable_callbacks: 是否启用回调
            enable_long_term_memory: 是否启用长期记忆
        """
        logger.info("Initializing ExceptionAgent...")
        
        # 1. 创建专用配置
        self.config = AgentConfig(
            model_name=model_name,
            temperature=0.2,  # 异常分析需要更低温度，保证结果一致性
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
                collection_name="exception_agent_memory",
                persist_directory="./chroma_db/exception_agent"
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
        
        # 6. 配置重试参数
        self.max_retries = 3
        self.retry_backoff_base = 1  # 指数退避基数（秒）
        self.timeout = 120  # 超时时间（秒）
        
        logger.info("ExceptionAgent initialized successfully")
    
    def _create_system_prompt(self) -> str:
        """
        创建异常分析代理的系统提示词
        
        Returns:
            str: 系统提示词
        """
        return """你是一个专业的质量异常分析助手，擅长分析异常原因、判定责任方、推荐解决方案。

你的职责：
1. 分析异常的根本原因、严重程度和影响范围
2. 从知识库检索相似的历史案例
3. 判定责任方（内部、供应商、材料商）并提供证据
4. 推荐解决方案并评估成本和时间影响

可用工具：
- analyze_exception: 分析异常原因和影响
- search_exception_cases: 检索历史案例
- determine_responsibility: 判定责任方
- recommend_solution: 推荐解决方案

工作流程：
1. 使用 analyze_exception 分析异常
2. 使用 search_exception_cases 检索历史案例
3. 使用 determine_responsibility 判定责任
4. 使用 recommend_solution 推荐方案
5. 综合所有信息，生成完整分析报告

输出格式：
当完成分析后，使用以下格式输出：

Final Answer:
【异常分析报告】

一、基本信息
- 异常类型：XXX
- 异常描述：XXX
- 相关实体：XXX

二、异常分析
- 根本原因：XXX
- 严重程度：XXX
- 影响范围：XXX
- 贡献因素：XXX

三、历史案例
- 找到 X 条相似案例
- 案例1：XXX
- 案例2：XXX

四、责任判定
- 责任方：XXX
- 置信度：XXX%
- 证据：XXX
- 是否需要审核：XXX

五、解决方案
- 推荐方案：XXX
- 成本影响：XXX 元
- 时间影响：XXX 天
- 实施步骤：XXX
- 备选方案：XXX

六、综合建议
XXX

请严格按照工作流程使用工具，确保分析全面准确。如果置信度低于70%，请明确标注需要人工审核。
"""
    
    async def analyze_exception(
        self,
        exception_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        分析质量异常
        
        Args:
            exception_data: 异常数据
            {
                "exception_id": str,
                "exception_type": str,  # 尺寸偏差, 表面缺陷, 材料问题, 组装问题
                "description": str,
                "related_entity_id": str,  # part_id or order_id
                "entity_type": str,  # part or order
                "project_id": str,
                "supplier_id": str (optional),
                "material": str (optional),
                "process_type": str (optional),
                "severity": str (optional),  # critical, major, minor
                "quantity_affected": int (optional)
            }
            
        Returns:
            Dict: 分析结果
            {
                "success": bool,
                "exception_data": Dict,
                "analysis": {
                    "root_cause": str,
                    "severity": str,
                    "impact_scope": str,
                    "contributing_factors": List[str]
                },
                "historical_cases": List[Dict],
                "responsibility": {
                    "responsible_party": str,
                    "confidence_score": float,
                    "evidence": List[str],
                    "requires_review": bool
                },
                "solutions": List[Dict],
                "recommended_solution": str,
                "analysis_report": str,
                "timestamp": str,
                "agent_steps": int
            }
        """
        logger.info(f"Analyzing exception {exception_data.get('exception_id')}")
        
        # 记录开始时间
        start_time = time.time()
        
        try:
            # 构建分析任务
            task = self._build_analysis_task(exception_data)
            
            # 触发回调
            if self.callback_manager:
                self.callback_manager.on_agent_start(task, self.config.dict())
            
            # 运行 Agent（带重试和超时）
            result = await self._run_with_retry_and_timeout(task)
            
            # 检查超时
            elapsed_time = time.time() - start_time
            if elapsed_time >= self.timeout:
                logger.warning(f"Analysis timeout after {elapsed_time:.2f}s")
                # 返回部分结果
                return self._create_timeout_response(exception_data, elapsed_time)
            
            # 触发回调
            if self.callback_manager:
                self.callback_manager.on_agent_complete(
                    result,
                    self.agent_loop.current_step
                )
            
            # 解析结果
            parsed_result = self._parse_analysis_result(result, exception_data)
            
            logger.info(f"Exception analysis completed successfully in {elapsed_time:.2f}s")
            return parsed_result
        
        except asyncio.TimeoutError:
            elapsed_time = time.time() - start_time
            logger.error(f"Analysis timeout after {elapsed_time:.2f}s")
            return self._create_timeout_response(exception_data, elapsed_time)
        
        except Exception as e:
            logger.error(f"Error analyzing exception: {e}", exc_info=True)
            if self.callback_manager:
                self.callback_manager.on_error(e)
            
            return {
                "success": False,
                "error": str(e),
                "error_type": "ANALYSIS_ERROR",
                "exception_data": exception_data,
                "message": f"异常分析失败: {str(e)}",
                "timestamp": self._get_timestamp()
            }
    
    async def _run_with_retry_and_timeout(self, task: str) -> str:
        """
        运行 Agent，带重试和超时机制
        
        Args:
            task: 任务描述
            
        Returns:
            str: Agent 返回结果
            
        Raises:
            asyncio.TimeoutError: 超时
            Exception: 其他错误
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                # 设置超时
                result = await asyncio.wait_for(
                    self.agent_loop.run(task),
                    timeout=self.timeout
                )
                return result
            
            except asyncio.TimeoutError:
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries} timed out")
                raise  # 超时不重试，直接抛出
            
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Attempt {attempt + 1}/{self.max_retries} failed: {e}",
                    exc_info=True
                )
                
                # 如果不是最后一次尝试，等待后重试
                if attempt < self.max_retries - 1:
                    backoff_time = self.retry_backoff_base * (2 ** attempt)
                    logger.info(f"Retrying in {backoff_time}s...")
                    await asyncio.sleep(backoff_time)
        
        # 所有重试都失败
        logger.error(f"All {self.max_retries} retry attempts failed")
        raise last_error
    
    def _build_analysis_task(self, exception_data: Dict[str, Any]) -> str:
        """
        构建分析任务描述
        
        Args:
            exception_data: 异常数据
            
        Returns:
            str: 任务描述
        """
        task = f"""请分析以下质量异常：

异常信息：
- 异常ID：{exception_data.get('exception_id', '未知')}
- 异常类型：{exception_data.get('exception_type', '未知')}
- 异常描述：{exception_data.get('description', '未知')}

相关信息：
- 相关实体ID：{exception_data.get('related_entity_id', '未知')}
- 实体类型：{exception_data.get('entity_type', '未知')}
- 项目ID：{exception_data.get('project_id', '未知')}
"""
        
        if exception_data.get('supplier_id'):
            task += f"- 供应商ID：{exception_data['supplier_id']}\n"
        
        if exception_data.get('material'):
            task += f"- 材料：{exception_data['material']}\n"
        
        if exception_data.get('process_type'):
            task += f"- 工艺类型：{exception_data['process_type']}\n"
        
        if exception_data.get('quantity_affected'):
            task += f"- 受影响数量：{exception_data['quantity_affected']} 件\n"
        
        task += """
请按照以下步骤进行分析：
1. 使用 analyze_exception 工具分析异常的根本原因、严重程度和影响范围
2. 使用 search_exception_cases 工具检索相似的历史案例
3. 使用 determine_responsibility 工具判定责任方
4. 使用 recommend_solution 工具推荐解决方案
5. 综合所有信息，生成完整的分析报告

请确保分析全面、准确，并给出明确的建议。如果置信度低于70%，请明确标注需要人工审核。
"""
        
        return task
    
    def _parse_analysis_result(
        self,
        result: str,
        exception_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        解析分析结果
        
        Args:
            result: Agent 返回的结果
            exception_data: 原始异常数据
            
        Returns:
            Dict: 结构化的分析结果
        """
        # 基础结构化结果
        parsed_result = {
            "success": True,
            "exception_data": exception_data,
            "analysis_report": result,
            "timestamp": self._get_timestamp(),
            "agent_steps": self.agent_loop.current_step
        }
        
        # 尝试从结果中提取结构化信息
        # 这里可以添加更复杂的解析逻辑，从 result 文本中提取各个部分
        # 目前返回基础结构
        
        return parsed_result
    
    def _create_timeout_response(
        self,
        exception_data: Dict[str, Any],
        elapsed_time: float
    ) -> Dict[str, Any]:
        """
        创建超时响应
        
        Args:
            exception_data: 异常数据
            elapsed_time: 已用时间
            
        Returns:
            Dict: 超时响应
        """
        return {
            "success": False,
            "error": "Analysis timeout",
            "error_type": "TIMEOUT_ERROR",
            "exception_data": exception_data,
            "message": f"异常分析超时（{elapsed_time:.2f}秒），请稍后重试",
            "partial_results": {
                "agent_steps": self.agent_loop.current_step,
                "elapsed_time": elapsed_time
            },
            "timestamp": self._get_timestamp()
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
            "agent_type": "ExceptionAgent",
            "model": self.config.model_name,
            "temperature": self.config.temperature,
            "max_steps": self.config.max_steps,
            "tools_available": len(self.tool_registry),
            "agent_loop_state": self.agent_loop.get_state(),
            "retry_config": {
                "max_retries": self.max_retries,
                "backoff_base": self.retry_backoff_base,
                "timeout": self.timeout
            }
        }


# 测试代码
async def test_exception_agent():
    """测试异常分析代理"""
    print("=" * 80)
    print("测试 ExceptionAgent")
    print("=" * 80)
    
    # 创建代理
    agent = ExceptionAgent(
        model_name="gpt-4",
        enable_callbacks=True,
        enable_long_term_memory=False  # 测试时禁用长期记忆
    )
    
    # 测试异常数据
    exception_data = {
        "exception_id": "EXC001",
        "exception_type": "尺寸偏差",
        "description": "轴承座内径尺寸超差0.5mm，超出公差范围±0.2mm，导致轴承无法正常安装",
        "related_entity_id": "PART001",
        "entity_type": "part",
        "project_id": "PROJ001",
        "supplier_id": "SUP001",
        "material": "钢",
        "process_type": "数控加工",
        "quantity_affected": 50
    }
    
    # 分析异常
    print("\n开始分析异常...")
    result = await agent.analyze_exception(exception_data)
    
    if result['success']:
        print("\n✅ 分析成功!")
        print(f"\n分析报告:\n{result['analysis_report']}")
        print(f"\n执行步数: {result['agent_steps']}")
        print(f"\n时间戳: {result['timestamp']}")
    else:
        print(f"\n❌ 分析失败: {result.get('error')}")
        print(f"错误类型: {result.get('error_type')}")
        print(f"消息: {result.get('message')}")
    
    # 获取状态
    print("\n" + "=" * 80)
    print("Agent 状态:")
    print("=" * 80)
    state = agent.get_state()
    for key, value in state.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_exception_agent())
