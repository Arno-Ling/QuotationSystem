"""
ToolRegistry - 工具注册表
管理所有可用工具的注册、查找和执行
"""
from typing import Dict, Any, Callable, Optional, List
from pydantic import BaseModel, Field
import logging
import inspect
import json

logger = logging.getLogger(__name__)


class Tool(BaseModel):
    """工具模型"""
    name: str = Field(..., description="工具名称")
    description: str = Field(..., description="工具描述")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="参数 JSON Schema")
    function: Any = Field(None, description="工具函数", exclude=True)
    permission: str = Field(default="read_only", description="权限级别")
    
    class Config:
        arbitrary_types_allowed = True


class ToolRegistry:
    """
    工具注册表
    
    负责：
    1. 注册和注销工具
    2. 查找工具
    3. 执行工具并捕获异常
    """
    
    def __init__(self):
        """初始化工具注册表"""
        self._tools: Dict[str, Tool] = {}
        logger.info("ToolRegistry initialized")
    
    def register(
        self,
        name: str,
        function: Callable,
        description: str,
        parameters: Optional[Dict[str, Any]] = None,
        permission: str = "read_only"
    ) -> None:
        """
        注册工具
        
        Args:
            name: 工具名称
            function: 工具函数
            description: 工具描述
            parameters: 参数 JSON Schema（可选，会自动从函数签名提取）
            permission: 权限级别
        """
        if name in self._tools:
            logger.warning(f"Tool '{name}' already registered. Overwriting.")
        
        # 如果没有提供参数 schema，尝试从函数签名提取
        if parameters is None:
            parameters = self._extract_parameters(function)
        
        tool = Tool(
            name=name,
            description=description,
            parameters=parameters,
            function=function,
            permission=permission
        )
        
        self._tools[name] = tool
        logger.info(f"Tool '{name}' registered with permission '{permission}'")
    
    def unregister(self, name: str) -> bool:
        """
        注销工具
        
        Args:
            name: 工具名称
            
        Returns:
            bool: 是否成功注销
        """
        if name in self._tools:
            del self._tools[name]
            logger.info(f"Tool '{name}' unregistered")
            return True
        else:
            logger.warning(f"Tool '{name}' not found, cannot unregister")
            return False
    
    def get(self, name: str) -> Optional[Tool]:
        """
        获取工具
        
        Args:
            name: 工具名称
            
        Returns:
            Optional[Tool]: 工具对象，如果不存在则返回 None
        """
        return self._tools.get(name)
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """
        列出所有工具（用于传递给 LLM）
        
        Returns:
            List[Dict]: 工具列表，每个工具包含 name, description, parameters
        """
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
            }
            for tool in self._tools.values()
        ]
    
    def execute(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工具
        
        Args:
            name: 工具名称
            arguments: 工具参数
            
        Returns:
            Dict: 执行结果
            {
                "success": bool,
                "result": Any,  # 如果成功
                "error": str    # 如果失败
            }
        """
        tool = self.get(name)
        if not tool:
            error_msg = f"Tool '{name}' not found"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
        
        try:
            logger.info(f"Executing tool '{name}' with arguments: {arguments}")
            
            # 执行工具函数
            result = tool.function(**arguments)
            
            logger.info(f"Tool '{name}' executed successfully")
            return {
                "success": True,
                "result": result
            }
        
        except TypeError as e:
            # 参数错误
            error_msg = f"Invalid arguments for tool '{name}': {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
        
        except Exception as e:
            # 其他执行错误
            error_msg = f"Error executing tool '{name}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "error": error_msg
            }
    
    def _extract_parameters(self, function: Callable) -> Dict[str, Any]:
        """
        从函数签名提取参数 JSON Schema
        
        Args:
            function: 函数对象
            
        Returns:
            Dict: JSON Schema 格式的参数定义
        """
        sig = inspect.signature(function)
        parameters = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        for param_name, param in sig.parameters.items():
            # 跳过 self 和 cls
            if param_name in ('self', 'cls'):
                continue
            
            # 基础类型映射
            param_type = "string"  # 默认类型
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == int:
                    param_type = "integer"
                elif param.annotation == float:
                    param_type = "number"
                elif param.annotation == bool:
                    param_type = "boolean"
                elif param.annotation == list:
                    param_type = "array"
                elif param.annotation == dict:
                    param_type = "object"
            
            parameters["properties"][param_name] = {
                "type": param_type,
                "description": f"Parameter {param_name}"
            }
            
            # 如果没有默认值，则为必需参数
            if param.default == inspect.Parameter.empty:
                parameters["required"].append(param_name)
        
        return parameters
    
    def get_tool_schemas_for_llm(self) -> str:
        """
        获取工具 schema 的字符串表示，用于 LLM 提示
        
        Returns:
            str: 工具列表的格式化字符串
        """
        if not self._tools:
            return "No tools available."
        
        tools_desc = "Available Tools:\n\n"
        for tool in self._tools.values():
            tools_desc += f"- {tool.name}: {tool.description}\n"
            if tool.parameters.get("properties"):
                tools_desc += f"  Parameters: {json.dumps(tool.parameters['properties'], indent=2)}\n"
        
        return tools_desc
    
    def __len__(self) -> int:
        """返回注册的工具数量"""
        return len(self._tools)
    
    def __repr__(self) -> str:
        return f"<ToolRegistry(tools={len(self._tools)})>"


# 全局工具注册表实例
registry = ToolRegistry()
