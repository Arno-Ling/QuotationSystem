"""
Observability Logger - 可观测性日志
提供结构化日志记录和跟踪
"""
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path


class StructuredLogger:
    """
    结构化日志记录器
    
    生成 JSON 格式的结构化日志，方便发送至 ELK 等系统
    """
    
    def __init__(
        self,
        name: str = "agent_harness",
        log_file: Optional[str] = None,
        log_level: str = "INFO"
    ):
        """
        初始化结构化日志记录器
        
        Args:
            name: 日志记录器名称
            log_file: 日志文件路径（可选）
            log_level: 日志级别
        """
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # 清除现有处理器
        self.logger.handlers.clear()
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # 文件处理器（如果指定）
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(console_formatter)
            self.logger.addHandler(file_handler)
        
        self.logger.info(f"StructuredLogger initialized: {name}")
    
    def log_agent_start(
        self,
        task: str,
        config: Dict[str, Any],
        session_id: Optional[str] = None
    ):
        """
        记录 Agent 启动
        
        Args:
            task: 任务描述
            config: 配置信息
            session_id: 会话 ID
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "agent_start",
            "session_id": session_id,
            "task": task,
            "config": config
        }
        self.logger.info(json.dumps(log_entry, ensure_ascii=False))
    
    def log_step(
        self,
        step: int,
        action: str,
        details: Dict[str, Any],
        session_id: Optional[str] = None
    ):
        """
        记录执行步骤
        
        Args:
            step: 步骤编号
            action: 动作类型 (think, act, observe)
            details: 详细信息
            session_id: 会话 ID
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "step",
            "session_id": session_id,
            "step": step,
            "action": action,
            "details": details
        }
        self.logger.info(json.dumps(log_entry, ensure_ascii=False))
    
    def log_llm_call(
        self,
        step: int,
        model: str,
        input_messages: list,
        output: str,
        tokens_used: Optional[int] = None,
        session_id: Optional[str] = None
    ):
        """
        记录 LLM 调用
        
        Args:
            step: 步骤编号
            model: 模型名称
            input_messages: 输入消息
            output: 输出内容
            tokens_used: 使用的 token 数
            session_id: 会话 ID
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "llm_call",
            "session_id": session_id,
            "step": step,
            "model": model,
            "input_messages_count": len(input_messages),
            "output_length": len(output),
            "tokens_used": tokens_used
        }
        self.logger.info(json.dumps(log_entry, ensure_ascii=False))
    
    def log_tool_call(
        self,
        step: int,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Dict[str, Any],
        execution_time: Optional[float] = None,
        session_id: Optional[str] = None
    ):
        """
        记录工具调用
        
        Args:
            step: 步骤编号
            tool_name: 工具名称
            arguments: 工具参数
            result: 执行结果
            execution_time: 执行时间（秒）
            session_id: 会话 ID
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "tool_call",
            "session_id": session_id,
            "step": step,
            "tool_name": tool_name,
            "arguments": arguments,
            "success": result.get("success", False),
            "execution_time": execution_time
        }
        self.logger.info(json.dumps(log_entry, ensure_ascii=False))
    
    def log_agent_complete(
        self,
        final_answer: str,
        total_steps: int,
        total_time: Optional[float] = None,
        session_id: Optional[str] = None
    ):
        """
        记录 Agent 完成
        
        Args:
            final_answer: 最终答案
            total_steps: 总步数
            total_time: 总时间（秒）
            session_id: 会话 ID
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "agent_complete",
            "session_id": session_id,
            "final_answer_length": len(final_answer),
            "total_steps": total_steps,
            "total_time": total_time
        }
        self.logger.info(json.dumps(log_entry, ensure_ascii=False))
    
    def log_error(
        self,
        error_type: str,
        error_message: str,
        step: Optional[int] = None,
        session_id: Optional[str] = None
    ):
        """
        记录错误
        
        Args:
            error_type: 错误类型
            error_message: 错误消息
            step: 步骤编号
            session_id: 会话 ID
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "error",
            "session_id": session_id,
            "step": step,
            "error_type": error_type,
            "error_message": error_message
        }
        self.logger.error(json.dumps(log_entry, ensure_ascii=False))
    
    def log_custom(
        self,
        event: str,
        data: Dict[str, Any],
        level: str = "INFO",
        session_id: Optional[str] = None
    ):
        """
        记录自定义事件
        
        Args:
            event: 事件名称
            data: 事件数据
            level: 日志级别
            session_id: 会话 ID
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "session_id": session_id,
            **data
        }
        
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(json.dumps(log_entry, ensure_ascii=False))


# 全局日志记录器实例
structured_logger = StructuredLogger()
