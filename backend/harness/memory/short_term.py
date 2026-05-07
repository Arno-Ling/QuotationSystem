"""
ShortTermMemory - 短期记忆管理
基于列表的当前会话对话历史管理
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


class Message(BaseModel):
    """消息模型"""
    role: str = Field(..., description="角色: system, user, assistant, tool")
    content: str = Field(..., description="消息内容")
    name: Optional[str] = Field(None, description="工具名称（如果是工具消息）")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


class ShortTermMemory:
    """
    短期记忆管理器
    
    管理当前会话的完整对话历史
    支持：
    1. 添加消息
    2. 获取历史
    3. 清空历史
    4. 上下文窗口管理（截断）
    """
    
    def __init__(self, max_messages: int = 20):
        """
        初始化短期记忆
        
        Args:
            max_messages: 最大消息数量
        """
        self.max_messages = max_messages
        self._messages: List[Message] = []
        logger.info(f"ShortTermMemory initialized with max_messages={max_messages}")
    
    def add_message(
        self,
        role: str,
        content: str,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        添加消息到历史
        
        Args:
            role: 角色 (system, user, assistant, tool)
            content: 消息内容
            name: 工具名称（可选）
            metadata: 元数据（可选）
        """
        message = Message(
            role=role,
            content=content,
            name=name,
            metadata=metadata or {}
        )
        
        self._messages.append(message)
        logger.debug(f"Added message: role={role}, content_length={len(content)}")
        
        # 如果超过最大消息数，进行截断（保留系统消息）
        if len(self._messages) > self.max_messages:
            self._truncate()
    
    def get_messages(self, last_n: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取消息历史
        
        Args:
            last_n: 获取最后 n 条消息（可选）
            
        Returns:
            List[Dict]: 消息列表
        """
        messages = self._messages if last_n is None else self._messages[-last_n:]
        return [msg.dict(exclude_none=True) for msg in messages]
    
    def get_messages_for_llm(self) -> List[Dict[str, str]]:
        """
        获取适合传递给 LLM 的消息格式
        
        Returns:
            List[Dict]: 简化的消息列表
        """
        result = []
        for msg in self._messages:
            message_dict = {"role": msg.role, "content": msg.content}
            if msg.name:
                message_dict["name"] = msg.name
            result.append(message_dict)
        return result
    
    def clear(self) -> None:
        """清空所有消息"""
        self._messages.clear()
        logger.info("Short-term memory cleared")
    
    def _truncate(self) -> None:
        """
        截断消息历史
        
        策略：
        1. 保留第一条系统消息
        2. 删除最旧的用户/助手消息
        3. 保持最近的消息
        """
        # 找到系统消息
        system_messages = [msg for msg in self._messages if msg.role == "system"]
        other_messages = [msg for msg in self._messages if msg.role != "system"]
        
        # 保留系统消息 + 最近的消息
        keep_count = self.max_messages - len(system_messages)
        if keep_count > 0:
            self._messages = system_messages + other_messages[-keep_count:]
        else:
            self._messages = system_messages[:self.max_messages]
        
        logger.info(f"Truncated messages to {len(self._messages)}")
    
    def get_context_summary(self) -> str:
        """
        获取上下文摘要
        
        Returns:
            str: 对话历史的简要摘要
        """
        if not self._messages:
            return "No conversation history."
        
        summary = f"Conversation history ({len(self._messages)} messages):\n"
        for i, msg in enumerate(self._messages[-5:], 1):  # 只显示最后5条
            content_preview = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
            summary += f"{i}. [{msg.role}] {content_preview}\n"
        
        return summary
    
    def __len__(self) -> int:
        """返回消息数量"""
        return len(self._messages)
    
    def __repr__(self) -> str:
        return f"<ShortTermMemory(messages={len(self._messages)}, max={self.max_messages})>"
