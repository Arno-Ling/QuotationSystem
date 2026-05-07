"""
Callback System - 回调系统
提供实时回调接口，允许前端可视化当前执行步骤
"""
from typing import Dict, Any, List, Callable, Optional
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class BaseCallback(ABC):
    """
    回调基类
    
    定义回调接口
    """
    
    @abstractmethod
    def on_agent_start(self, task: str, config: Dict[str, Any]):
        """Agent 启动时调用"""
        pass
    
    @abstractmethod
    def on_step_start(self, step: int):
        """步骤开始时调用"""
        pass
    
    @abstractmethod
    def on_llm_call(self, step: int, input_messages: List[Dict], output: str):
        """LLM 调用时调用"""
        pass
    
    @abstractmethod
    def on_tool_call(self, step: int, tool_name: str, arguments: Dict[str, Any], result: Dict[str, Any]):
        """工具调用时调用"""
        pass
    
    @abstractmethod
    def on_step_end(self, step: int):
        """步骤结束时调用"""
        pass
    
    @abstractmethod
    def on_agent_complete(self, final_answer: str, total_steps: int):
        """Agent 完成时调用"""
        pass
    
    @abstractmethod
    def on_error(self, error: Exception, step: Optional[int] = None):
        """发生错误时调用"""
        pass


class ConsoleCallback(BaseCallback):
    """
    控制台回调
    
    将事件打印到控制台
    """
    
    def __init__(self, verbose: bool = True):
        """
        初始化控制台回调
        
        Args:
            verbose: 是否详细输出
        """
        self.verbose = verbose
    
    def on_agent_start(self, task: str, config: Dict[str, Any]):
        """Agent 启动"""
        print(f"\n{'='*60}")
        print(f"🚀 Agent Started")
        print(f"{'='*60}")
        print(f"Task: {task}")
        if self.verbose:
            print(f"Config: {config}")
        print(f"{'='*60}\n")
    
    def on_step_start(self, step: int):
        """步骤开始"""
        print(f"\n--- Step {step} ---")
    
    def on_llm_call(self, step: int, input_messages: List[Dict], output: str):
        """LLM 调用"""
        print(f"🤖 LLM Call (Step {step})")
        if self.verbose:
            print(f"   Input messages: {len(input_messages)}")
        print(f"   Output: {output[:200]}{'...' if len(output) > 200 else ''}")
    
    def on_tool_call(self, step: int, tool_name: str, arguments: Dict[str, Any], result: Dict[str, Any]):
        """工具调用"""
        success = result.get("success", False)
        status = "✅" if success else "❌"
        print(f"{status} Tool Call (Step {step}): {tool_name}")
        if self.verbose:
            print(f"   Arguments: {arguments}")
        print(f"   Result: {result}")
    
    def on_step_end(self, step: int):
        """步骤结束"""
        if self.verbose:
            print(f"--- Step {step} Complete ---\n")
    
    def on_agent_complete(self, final_answer: str, total_steps: int):
        """Agent 完成"""
        print(f"\n{'='*60}")
        print(f"✨ Agent Complete")
        print(f"{'='*60}")
        print(f"Total Steps: {total_steps}")
        print(f"Final Answer: {final_answer}")
        print(f"{'='*60}\n")
    
    def on_error(self, error: Exception, step: Optional[int] = None):
        """错误"""
        step_info = f" (Step {step})" if step else ""
        print(f"\n❌ Error{step_info}: {str(error)}\n")


class WebSocketCallback(BaseCallback):
    """
    WebSocket 回调
    
    通过 WebSocket 发送事件到前端
    """
    
    def __init__(self, websocket_handler: Optional[Callable] = None):
        """
        初始化 WebSocket 回调
        
        Args:
            websocket_handler: WebSocket 处理函数
        """
        self.websocket_handler = websocket_handler
    
    def _send(self, event_type: str, data: Dict[str, Any]):
        """
        发送事件
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
        if self.websocket_handler:
            try:
                self.websocket_handler({
                    "type": event_type,
                    "data": data
                })
            except Exception as e:
                logger.error(f"Error sending websocket event: {e}")
    
    def on_agent_start(self, task: str, config: Dict[str, Any]):
        """Agent 启动"""
        self._send("agent_start", {"task": task, "config": config})
    
    def on_step_start(self, step: int):
        """步骤开始"""
        self._send("step_start", {"step": step})
    
    def on_llm_call(self, step: int, input_messages: List[Dict], output: str):
        """LLM 调用"""
        self._send("llm_call", {
            "step": step,
            "input_messages_count": len(input_messages),
            "output": output
        })
    
    def on_tool_call(self, step: int, tool_name: str, arguments: Dict[str, Any], result: Dict[str, Any]):
        """工具调用"""
        self._send("tool_call", {
            "step": step,
            "tool_name": tool_name,
            "arguments": arguments,
            "result": result
        })
    
    def on_step_end(self, step: int):
        """步骤结束"""
        self._send("step_end", {"step": step})
    
    def on_agent_complete(self, final_answer: str, total_steps: int):
        """Agent 完成"""
        self._send("agent_complete", {
            "final_answer": final_answer,
            "total_steps": total_steps
        })
    
    def on_error(self, error: Exception, step: Optional[int] = None):
        """错误"""
        self._send("error", {
            "error": str(error),
            "step": step
        })


class CallbackManager:
    """
    回调管理器
    
    管理多个回调
    """
    
    def __init__(self):
        """初始化回调管理器"""
        self.callbacks: List[BaseCallback] = []
        logger.info("CallbackManager initialized")
    
    def add_callback(self, callback: BaseCallback):
        """
        添加回调
        
        Args:
            callback: 回调对象
        """
        self.callbacks.append(callback)
        logger.debug(f"Added callback: {callback.__class__.__name__}")
    
    def remove_callback(self, callback: BaseCallback):
        """
        移除回调
        
        Args:
            callback: 回调对象
        """
        if callback in self.callbacks:
            self.callbacks.remove(callback)
            logger.debug(f"Removed callback: {callback.__class__.__name__}")
    
    def clear_callbacks(self):
        """清空所有回调"""
        self.callbacks.clear()
        logger.debug("Cleared all callbacks")
    
    def on_agent_start(self, task: str, config: Dict[str, Any]):
        """触发 Agent 启动事件"""
        for callback in self.callbacks:
            try:
                callback.on_agent_start(task, config)
            except Exception as e:
                logger.error(f"Error in callback on_agent_start: {e}")
    
    def on_step_start(self, step: int):
        """触发步骤开始事件"""
        for callback in self.callbacks:
            try:
                callback.on_step_start(step)
            except Exception as e:
                logger.error(f"Error in callback on_step_start: {e}")
    
    def on_llm_call(self, step: int, input_messages: List[Dict], output: str):
        """触发 LLM 调用事件"""
        for callback in self.callbacks:
            try:
                callback.on_llm_call(step, input_messages, output)
            except Exception as e:
                logger.error(f"Error in callback on_llm_call: {e}")
    
    def on_tool_call(self, step: int, tool_name: str, arguments: Dict[str, Any], result: Dict[str, Any]):
        """触发工具调用事件"""
        for callback in self.callbacks:
            try:
                callback.on_tool_call(step, tool_name, arguments, result)
            except Exception as e:
                logger.error(f"Error in callback on_tool_call: {e}")
    
    def on_step_end(self, step: int):
        """触发步骤结束事件"""
        for callback in self.callbacks:
            try:
                callback.on_step_end(step)
            except Exception as e:
                logger.error(f"Error in callback on_step_end: {e}")
    
    def on_agent_complete(self, final_answer: str, total_steps: int):
        """触发 Agent 完成事件"""
        for callback in self.callbacks:
            try:
                callback.on_agent_complete(final_answer, total_steps)
            except Exception as e:
                logger.error(f"Error in callback on_agent_complete: {e}")
    
    def on_error(self, error: Exception, step: Optional[int] = None):
        """触发错误事件"""
        for callback in self.callbacks:
            try:
                callback.on_error(error, step)
            except Exception as e:
                logger.error(f"Error in callback on_error: {e}")
    
    def __len__(self) -> int:
        """返回回调数量"""
        return len(self.callbacks)
    
    def __repr__(self) -> str:
        return f"<CallbackManager(callbacks={len(self.callbacks)})>"
