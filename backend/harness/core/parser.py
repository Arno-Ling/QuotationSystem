"""
Parser - LLM 输出解析器
解析 LLM 输出，区分 Final Answer 和 Tool Call
"""
from typing import Optional, Dict, Any, Union
from pydantic import BaseModel, Field
import re
import json
import logging

logger = logging.getLogger(__name__)


class ToolCall(BaseModel):
    """工具调用模型"""
    name: str = Field(..., description="工具名称")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="工具参数")


class FinalAnswer(BaseModel):
    """最终答案模型"""
    answer: str = Field(..., description="最终答案内容")


class ParsedOutput(BaseModel):
    """解析后的输出"""
    type: str = Field(..., description="输出类型: 'tool_call' 或 'final_answer'")
    tool_call: Optional[ToolCall] = Field(None, description="工具调用（如果是工具调用）")
    final_answer: Optional[FinalAnswer] = Field(None, description="最终答案（如果是最终答案）")
    raw_output: str = Field(..., description="原始输出")


class OutputParser:
    """
    LLM 输出解析器
    
    支持两种格式：
    1. Final Answer: [答案内容]
    2. Tool Call: {"name": "tool_name", "arguments": {...}}
    """
    
    def __init__(self):
        """初始化解析器"""
        # 最终答案模式
        self.final_answer_pattern = re.compile(
            r'Final\s+Answer\s*:\s*(.+)',
            re.IGNORECASE | re.DOTALL
        )
        
        # 工具调用模式
        self.tool_call_pattern = re.compile(
            r'Tool\s+Call\s*:\s*(\{.+?\})',
            re.IGNORECASE | re.DOTALL
        )
    
    def parse(self, output: str) -> ParsedOutput:
        """
        解析 LLM 输出
        
        Args:
            output: LLM 的原始输出
            
        Returns:
            ParsedOutput: 解析后的结构化输出
        """
        output = output.strip()
        
        # 尝试解析最终答案
        final_answer = self._parse_final_answer(output)
        if final_answer:
            logger.info("Parsed as Final Answer")
            return ParsedOutput(
                type="final_answer",
                final_answer=final_answer,
                raw_output=output
            )
        
        # 尝试解析工具调用
        tool_call = self._parse_tool_call(output)
        if tool_call:
            logger.info(f"Parsed as Tool Call: {tool_call.name}")
            return ParsedOutput(
                type="tool_call",
                tool_call=tool_call,
                raw_output=output
            )
        
        # 如果都不匹配，尝试作为 JSON 解析（OpenAI function calling 格式）
        tool_call = self._parse_json_tool_call(output)
        if tool_call:
            logger.info(f"Parsed as JSON Tool Call: {tool_call.name}")
            return ParsedOutput(
                type="tool_call",
                tool_call=tool_call,
                raw_output=output
            )
        
        # 默认作为最终答案处理
        logger.warning("Could not parse output format, treating as final answer")
        return ParsedOutput(
            type="final_answer",
            final_answer=FinalAnswer(answer=output),
            raw_output=output
        )
    
    def _parse_final_answer(self, output: str) -> Optional[FinalAnswer]:
        """
        解析最终答案格式
        
        格式: Final Answer: [答案内容]
        """
        match = self.final_answer_pattern.search(output)
        if match:
            answer = match.group(1).strip()
            return FinalAnswer(answer=answer)
        return None
    
    def _parse_tool_call(self, output: str) -> Optional[ToolCall]:
        """
        解析工具调用格式
        
        格式: Tool Call: {"name": "tool_name", "arguments": {...}}
        """
        match = self.tool_call_pattern.search(output)
        if match:
            try:
                json_str = match.group(1)
                data = json.loads(json_str)
                return ToolCall(
                    name=data.get("name", ""),
                    arguments=data.get("arguments", {})
                )
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse tool call JSON: {e}")
                return None
        return None
    
    def _parse_json_tool_call(self, output: str) -> Optional[ToolCall]:
        """
        尝试将整个输出作为 JSON 解析（OpenAI function calling 格式）
        
        格式: {"name": "tool_name", "arguments": {...}}
        """
        try:
            data = json.loads(output)
            if isinstance(data, dict) and "name" in data:
                return ToolCall(
                    name=data.get("name", ""),
                    arguments=data.get("arguments", {})
                )
        except json.JSONDecodeError:
            pass
        return None
    
    def format_tool_result(self, tool_name: str, result: Any) -> str:
        """
        格式化工具执行结果，返回给 LLM
        
        Args:
            tool_name: 工具名称
            result: 工具执行结果
            
        Returns:
            str: 格式化后的结果字符串
        """
        return f"Tool Result ({tool_name}): {json.dumps(result, ensure_ascii=False, indent=2)}"


# 全局解析器实例
parser = OutputParser()
