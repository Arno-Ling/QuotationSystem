"""
Security Guardrails - 安全防护层
提供输入护栏、输出审计和工具权限管理
"""
from typing import Dict, Any, List, Optional
import re
import logging
from enum import Enum

from ..config.agent_config import AgentConfig, ToolPermission

logger = logging.getLogger(__name__)


class GuardrailViolation(Exception):
    """护栏违规异常"""
    pass


class InputGuardrails:
    """
    输入护栏
    
    在用户输入进入循环前，检查是否包含恶意内容
    """
    
    def __init__(self, config: AgentConfig):
        """
        初始化输入护栏
        
        Args:
            config: Agent 配置
        """
        self.config = config
        self.enabled = config.enable_input_guardrails
        
        # 危险模式列表
        self.dangerous_patterns = [
            # 越狱尝试
            r"ignore\s+(previous|all)\s+instructions",
            r"disregard\s+(previous|all)\s+instructions",
            r"forget\s+(previous|all)\s+instructions",
            
            # 提示注入
            r"system\s*:\s*you\s+are",
            r"new\s+instructions",
            r"override\s+instructions",
            
            # 敏感信息泄露尝试
            r"show\s+me\s+your\s+(prompt|instructions|system\s+message)",
            r"what\s+are\s+your\s+(instructions|rules)",
            
            # 恶意代码执行
            r"exec\s*\(",
            r"eval\s*\(",
            r"__import__\s*\(",
        ]
        
        logger.info(f"InputGuardrails initialized (enabled={self.enabled})")
    
    def check(self, user_input: str) -> Dict[str, Any]:
        """
        检查用户输入
        
        Args:
            user_input: 用户输入
            
        Returns:
            Dict: 检查结果
            {
                "safe": bool,
                "violations": List[str],
                "sanitized_input": str
            }
        """
        if not self.enabled:
            return {
                "safe": True,
                "violations": [],
                "sanitized_input": user_input
            }
        
        violations = []
        
        # 检查危险模式
        for pattern in self.dangerous_patterns:
            if re.search(pattern, user_input, re.IGNORECASE):
                violations.append(f"Matched dangerous pattern: {pattern}")
        
        # 检查输入长度
        if len(user_input) > 10000:
            violations.append("Input too long (>10000 characters)")
        
        is_safe = len(violations) == 0
        
        if not is_safe:
            logger.warning(f"Input guardrail violations detected: {violations}")
        
        return {
            "safe": is_safe,
            "violations": violations,
            "sanitized_input": user_input if is_safe else ""
        }
    
    def validate_or_raise(self, user_input: str) -> str:
        """
        验证输入，如果不安全则抛出异常
        
        Args:
            user_input: 用户输入
            
        Returns:
            str: 清理后的输入
            
        Raises:
            GuardrailViolation: 如果输入不安全
        """
        result = self.check(user_input)
        
        if not result["safe"]:
            raise GuardrailViolation(
                f"Input validation failed: {', '.join(result['violations'])}"
            )
        
        return result["sanitized_input"]


class OutputAudit:
    """
    输出审计
    
    在工具调用执行前，根据配置的规则过滤危险操作
    """
    
    def __init__(self, config: AgentConfig):
        """
        初始化输出审计
        
        Args:
            config: Agent 配置
        """
        self.config = config
        self.enabled = config.enable_output_audit
        
        logger.info(f"OutputAudit initialized (enabled={self.enabled})")
    
    def audit_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        tool_permission: ToolPermission
    ) -> Dict[str, Any]:
        """
        审计工具调用
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            tool_permission: 工具权限级别
            
        Returns:
            Dict: 审计结果
            {
                "allowed": bool,
                "reason": str,
                "requires_confirmation": bool
            }
        """
        if not self.enabled:
            return {
                "allowed": True,
                "reason": "Audit disabled",
                "requires_confirmation": False
            }
        
        # 检查敏感工具
        if tool_permission == ToolPermission.SENSITIVE:
            if self.config.require_human_confirmation:
                logger.warning(f"Sensitive tool '{tool_name}' requires human confirmation")
                return {
                    "allowed": False,
                    "reason": "Sensitive tool requires human confirmation",
                    "requires_confirmation": True
                }
        
        # 检查危险操作模式
        violations = self._check_dangerous_operations(tool_name, arguments)
        
        if violations:
            logger.error(f"Dangerous operation detected in tool '{tool_name}': {violations}")
            return {
                "allowed": False,
                "reason": f"Dangerous operation: {', '.join(violations)}",
                "requires_confirmation": False
            }
        
        # 检查路径白名单（如果工具涉及文件操作）
        if self._is_file_operation(tool_name, arguments):
            path_check = self._check_path_whitelist(arguments)
            if not path_check["allowed"]:
                logger.error(f"Path not in whitelist: {path_check['reason']}")
                return path_check
        
        return {
            "allowed": True,
            "reason": "Audit passed",
            "requires_confirmation": False
        }
    
    def _check_dangerous_operations(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> List[str]:
        """
        检查危险操作
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            List[str]: 违规列表
        """
        violations = []
        
        # 将参数转换为字符串进行检查
        args_str = str(arguments).lower()
        
        # 检查危险模式
        for pattern in self.config.dangerous_patterns:
            if re.search(pattern, args_str, re.IGNORECASE):
                violations.append(f"Matched dangerous pattern: {pattern}")
        
        return violations
    
    def _is_file_operation(self, tool_name: str, arguments: Dict[str, Any]) -> bool:
        """
        判断是否为文件操作
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            bool: 是否为文件操作
        """
        # 检查工具名称
        file_operation_keywords = ['file', 'read', 'write', 'delete', 'path', 'directory']
        if any(keyword in tool_name.lower() for keyword in file_operation_keywords):
            return True
        
        # 检查参数名称
        if any(key in ['path', 'file', 'filename', 'directory'] for key in arguments.keys()):
            return True
        
        return False
    
    def _check_path_whitelist(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查路径是否在白名单中
        
        Args:
            arguments: 工具参数
            
        Returns:
            Dict: 检查结果
        """
        # 提取路径参数
        path = None
        for key in ['path', 'file', 'filename', 'directory']:
            if key in arguments:
                path = str(arguments[key])
                break
        
        if not path:
            return {"allowed": True, "reason": "No path parameter found"}
        
        # 检查是否在白名单中
        allowed = any(
            path.startswith(allowed_path)
            for allowed_path in self.config.allowed_paths
        )
        
        if not allowed:
            return {
                "allowed": False,
                "reason": f"Path '{path}' not in whitelist: {self.config.allowed_paths}",
                "requires_confirmation": False
            }
        
        return {"allowed": True, "reason": "Path in whitelist"}


class SecurityManager:
    """
    安全管理器
    
    统一管理输入护栏和输出审计
    """
    
    def __init__(self, config: AgentConfig):
        """
        初始化安全管理器
        
        Args:
            config: Agent 配置
        """
        self.config = config
        self.input_guardrails = InputGuardrails(config)
        self.output_audit = OutputAudit(config)
        
        logger.info("SecurityManager initialized")
    
    def validate_input(self, user_input: str) -> str:
        """
        验证用户输入
        
        Args:
            user_input: 用户输入
            
        Returns:
            str: 清理后的输入
            
        Raises:
            GuardrailViolation: 如果输入不安全
        """
        return self.input_guardrails.validate_or_raise(user_input)
    
    def audit_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        tool_permission: ToolPermission
    ) -> Dict[str, Any]:
        """
        审计工具调用
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            tool_permission: 工具权限级别
            
        Returns:
            Dict: 审计结果
        """
        return self.output_audit.audit_tool_call(tool_name, arguments, tool_permission)
    
    def __repr__(self) -> str:
        return f"<SecurityManager(input_enabled={self.input_guardrails.enabled}, output_enabled={self.output_audit.enabled})>"
