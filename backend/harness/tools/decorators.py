"""
Tool Decorators - 工具装饰器
使用装饰器将普通函数注册为工具
"""
from typing import Callable, Optional, Dict, Any
from functools import wraps
from .registry import registry
import logging

logger = logging.getLogger(__name__)


def tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
    permission: str = "read_only"
):
    """
    工具装饰器
    
    将普通函数注册为工具，自动提取函数签名生成 JSON Schema
    
    Args:
        name: 工具名称（默认使用函数名）
        description: 工具描述（默认使用函数 docstring）
        parameters: 参数 JSON Schema（默认从函数签名提取）
        permission: 权限级别 (read_only, read_write, sensitive)
    
    Example:
        @tool(description="计算两个数的和")
        def add(a: int, b: int) -> int:
            return a + b
    """
    def decorator(func: Callable) -> Callable:
        # 确定工具名称
        tool_name = name or func.__name__
        
        # 确定工具描述
        tool_desc = description or func.__doc__ or f"Tool: {tool_name}"
        tool_desc = tool_desc.strip()
        
        # 注册工具
        registry.register(
            name=tool_name,
            function=func,
            description=tool_desc,
            parameters=parameters,
            permission=permission
        )
        
        # 返回原函数（保持函数可以正常调用）
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def sensitive_tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None
):
    """
    敏感工具装饰器
    
    标记为敏感工具，执行前需要人工确认
    
    Example:
        @sensitive_tool(description="删除文件")
        def delete_file(path: str) -> str:
            os.remove(path)
            return f"Deleted {path}"
    """
    return tool(
        name=name,
        description=description,
        parameters=parameters,
        permission="sensitive"
    )


def readonly_tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None
):
    """
    只读工具装饰器
    
    标记为只读工具，不会修改系统状态
    
    Example:
        @readonly_tool(description="搜索信息")
        def search(query: str) -> str:
            return f"Search results for: {query}"
    """
    return tool(
        name=name,
        description=description,
        parameters=parameters,
        permission="read_only"
    )
