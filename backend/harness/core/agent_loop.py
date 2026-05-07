"""
AgentLoop - 核心 ReAct 循环
实现 Think -> Act -> Observe 的智能体执行循环
"""
from typing import Optional, Dict, Any, List
import logging
import asyncio
from datetime import datetime

try:
    import litellm
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    logging.warning("litellm not installed. LLM calls will be disabled.")

from ..config.agent_config import AgentConfig
from .parser import OutputParser, ParsedOutput
from ..tools.registry import ToolRegistry
from ..memory.short_term import ShortTermMemory
from ..memory.long_term import LongTermMemory

logger = logging.getLogger(__name__)


class AgentLoop:
    """
    Agent 核心执行循环
    
    实现 ReAct 模式：
    1. Think: LLM 思考下一步行动
    2. Act: 执行工具调用
    3. Observe: 观察工具执行结果
    4. Repeat: 重复直到得到最终答案或达到最大步数
    """
    
    def __init__(
        self,
        config: AgentConfig,
        tool_registry: ToolRegistry,
        short_term_memory: Optional[ShortTermMemory] = None,
        long_term_memory: Optional[LongTermMemory] = None
    ):
        """
        初始化 AgentLoop
        
        Args:
            config: Agent 配置
            tool_registry: 工具注册表
            short_term_memory: 短期记忆（可选）
            long_term_memory: 长期记忆（可选）
        """
        self.config = config
        self.tool_registry = tool_registry
        self.parser = OutputParser()
        
        # 初始化记忆
        self.short_term_memory = short_term_memory or ShortTermMemory(
            max_messages=config.max_short_term_messages
        )
        self.long_term_memory = long_term_memory
        
        # 执行状态
        self.current_step = 0
        self.is_running = False
        
        # 检查 LLM 可用性
        if not LITELLM_AVAILABLE:
            logger.error("litellm not available. Agent cannot run.")
        
        logger.info(f"AgentLoop initialized with model: {config.model_name}")
    
    async def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        运行 Agent 执行任务
        
        Args:
            task: 用户任务描述
            context: 额外上下文信息（可选）
            
        Returns:
            str: 最终答案
        """
        if not LITELLM_AVAILABLE:
            return "Error: litellm not installed. Cannot run agent."
        
        if self.is_running:
            return "Error: Agent is already running."
        
        try:
            self.is_running = True
            self.current_step = 0
            
            logger.info(f"Starting agent task: {task[:100]}...")
            
            # 初始化对话历史
            self._initialize_conversation(task, context)
            
            # ReAct 循环
            for step in range(1, self.config.max_steps + 1):
                self.current_step = step
                logger.info(f"Step {step}/{self.config.max_steps}")
                
                # 1. Think: 调用 LLM 思考
                llm_output = await self._call_llm()
                
                # 2. Parse: 解析 LLM 输出
                parsed = self.parser.parse(llm_output)
                
                # 3. Act & Observe
                if parsed.type == "final_answer":
                    # 得到最终答案，结束循环
                    final_answer = parsed.final_answer.answer
                    logger.info(f"Final answer received at step {step}")
                    
                    # 保存到长期记忆
                    if self.long_term_memory and self.config.enable_long_term_memory:
                        await self._save_to_long_term_memory(task, final_answer)
                    
                    return final_answer
                
                elif parsed.type == "tool_call":
                    # 执行工具调用
                    tool_result = await self._execute_tool(parsed.tool_call)
                    
                    # 将工具结果添加到记忆
                    result_message = self.parser.format_tool_result(
                        parsed.tool_call.name,
                        tool_result
                    )
                    self.short_term_memory.add_message(
                        role="tool",
                        content=result_message,
                        name=parsed.tool_call.name
                    )
                
                # 检查是否需要反思
                if self.config.enable_planning and step % self.config.reflection_interval == 0:
                    await self._reflect(step)
            
            # 达到最大步数仍未完成
            logger.warning(f"Reached max steps ({self.config.max_steps}) without final answer")
            return f"Task incomplete after {self.config.max_steps} steps. Please try again with a simpler task or increase max_steps."
        
        except Exception as e:
            logger.error(f"Error in agent loop: {e}", exc_info=True)
            return f"Error: {str(e)}"
        
        finally:
            self.is_running = False
    
    def _initialize_conversation(self, task: str, context: Optional[Dict[str, Any]] = None):
        """
        初始化对话历史
        
        Args:
            task: 用户任务
            context: 额外上下文
        """
        # 清空短期记忆
        self.short_term_memory.clear()
        
        # 添加系统提示
        system_prompt = self.config.system_prompt
        
        # 添加工具信息
        tools_info = self.tool_registry.get_tool_schemas_for_llm()
        system_prompt += f"\n\n{tools_info}"
        
        self.short_term_memory.add_message(
            role="system",
            content=system_prompt
        )
        
        # 添加长期记忆上下文（如果启用）
        if self.long_term_memory and self.config.enable_long_term_memory:
            relevant_context = self.long_term_memory.get_relevant_context(
                query=task,
                top_k=self.config.long_term_memory_top_k
            )
            if relevant_context and relevant_context != "No relevant historical context found.":
                self.short_term_memory.add_message(
                    role="system",
                    content=relevant_context
                )
        
        # 添加额外上下文（如果提供）
        if context:
            context_str = f"Additional Context:\n{context}"
            self.short_term_memory.add_message(
                role="system",
                content=context_str
            )
        
        # 添加用户任务
        self.short_term_memory.add_message(
            role="user",
            content=task
        )
        
        logger.debug(f"Conversation initialized with {len(self.short_term_memory)} messages")
    
    async def _call_llm(self) -> str:
        """
        调用 LLM 生成响应
        
        Returns:
            str: LLM 输出
        """
        try:
            messages = self.short_term_memory.get_messages_for_llm()
            
            logger.debug(f"Calling LLM with {len(messages)} messages")
            
            # 准备 litellm 调用参数
            import os
            
            # 处理模型名称：如果没有provider前缀，且是Anthropic兼容接口，添加anthropic前缀
            model_name = self.config.model_name
            api_base = os.getenv("OPENAI_BASE_URL", "")
            
            # 如果是Anthropic兼容接口（如MiMo），需要添加anthropic/前缀让litellm识别
            if "anthropic" in api_base.lower() and not model_name.startswith(("anthropic/", "openai/", "azure/")):
                model_name = f"anthropic/{model_name}"
                logger.debug(f"Using Anthropic-compatible API, model: {model_name}")
            
            llm_params = {
                "model": model_name,
                "messages": messages,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens
            }
            
            # 添加 API base URL（如果配置了）
            if api_base:
                llm_params["api_base"] = api_base
            
            # 添加 API key（如果配置了）
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                llm_params["api_key"] = api_key
            
            # 使用 litellm 调用 LLM
            response = await asyncio.to_thread(
                litellm.completion,
                **llm_params
            )
            
            # 提取响应内容
            llm_output = response.choices[0].message.content
            
            # 添加到短期记忆
            self.short_term_memory.add_message(
                role="assistant",
                content=llm_output
            )
            
            logger.debug(f"LLM response: {llm_output[:200]}...")
            
            return llm_output
        
        except Exception as e:
            logger.error(f"Error calling LLM: {e}", exc_info=True)
            raise
    
    async def _execute_tool(self, tool_call) -> Dict[str, Any]:
        """
        执行工具调用
        
        Args:
            tool_call: 工具调用对象
            
        Returns:
            Dict: 工具执行结果
        """
        tool_name = tool_call.name
        arguments = tool_call.arguments
        
        logger.info(f"Executing tool: {tool_name} with args: {arguments}")
        
        try:
            # 执行工具
            result = await asyncio.to_thread(
                self.tool_registry.execute,
                tool_name,
                arguments
            )
            
            logger.info(f"Tool {tool_name} executed: success={result.get('success')}")
            
            return result
        
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _reflect(self, current_step: int):
        """
        反思当前进度和计划
        
        Args:
            current_step: 当前步数
        """
        logger.info(f"Reflecting at step {current_step}")
        
        reflection_prompt = f"""
You have completed {current_step} steps. Please reflect on:
1. What progress have you made so far?
2. Are you on the right track to solve the task?
3. What should you do next?

Provide a brief reflection and continue with your next action.
"""
        
        self.short_term_memory.add_message(
            role="user",
            content=reflection_prompt
        )
    
    async def _save_to_long_term_memory(self, task: str, answer: str):
        """
        保存任务和答案到长期记忆
        
        Args:
            task: 任务描述
            answer: 最终答案
        """
        if not self.long_term_memory:
            return
        
        try:
            content = f"Task: {task}\nAnswer: {answer}"
            metadata = {
                "timestamp": datetime.now().isoformat(),
                "model": self.config.model_name,
                "steps": self.current_step
            }
            
            await asyncio.to_thread(
                self.long_term_memory.add,
                content,
                metadata
            )
            
            logger.debug("Saved to long-term memory")
        
        except Exception as e:
            logger.error(f"Error saving to long-term memory: {e}")
    
    def get_state(self) -> Dict[str, Any]:
        """
        获取当前状态
        
        Returns:
            Dict: 状态信息
        """
        return {
            "is_running": self.is_running,
            "current_step": self.current_step,
            "max_steps": self.config.max_steps,
            "model": self.config.model_name,
            "messages_count": len(self.short_term_memory),
            "tools_available": len(self.tool_registry)
        }
    
    def stop(self):
        """停止执行"""
        logger.info("Stopping agent loop")
        self.is_running = False
    
    def __repr__(self) -> str:
        return f"<AgentLoop(model={self.config.model_name}, step={self.current_step}/{self.config.max_steps})>"
