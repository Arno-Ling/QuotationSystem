"""
Quotation Skills - 报价相关技能
"""

# 导入所有 Skills（它们会通过 @tool 装饰器自动注册到全局 registry）
from . import quotation_analysis
from . import historical_comparison
from . import price_negotiation
from . import rag_skill

__all__ = [
    "quotation_analysis",
    "historical_comparison",
    "price_negotiation",
    "rag_skill",
]
