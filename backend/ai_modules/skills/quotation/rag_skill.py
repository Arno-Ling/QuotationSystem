"""
QuotationRAGSkill - RAG 知识检索技能
使用 ChromaDB 检索历史报价案例和市场行情数据
"""
from typing import Dict, Any, List
import logging

import sys
sys.path.append('../../..')
from harness.tools import tool
from harness.memory import LongTermMemory

logger = logging.getLogger(__name__)


# 初始化长期记忆（ChromaDB）
quotation_memory = LongTermMemory(
    collection_name="quotation_knowledge",
    persist_directory="./chroma_db/quotation"
)


@tool(
    description="从知识库检索历史报价案例、市场行情和供应商评价信息",
    permission="read_only"
)
def search_quotation_knowledge(
    query: str,
    top_k: int = 5,
    filter_type: str = None
) -> Dict[str, Any]:
    """
    检索报价相关知识
    
    Args:
        query: 查询文本
        top_k: 返回结果数量
        filter_type: 过滤类型 ("historical_price", "market_trend", "supplier_review")
        
    Returns:
        Dict: 检索结果
        {
            "results": List[Dict],  # 检索到的知识条目
            "summary": str,  # 结果摘要
            "relevance_scores": List[float]  # 相关性分数
        }
    """
    logger.info(f"Searching quotation knowledge: query='{query}', top_k={top_k}")
    
    try:
        # 构建过滤条件
        filter_metadata = None
        if filter_type:
            filter_metadata = {"type": filter_type}
        
        # 从 ChromaDB 检索
        search_results = quotation_memory.search(
            query=query,
            top_k=top_k,
            filter_metadata=filter_metadata
        )
        
        if not search_results:
            return {
                "results": [],
                "summary": "未找到相关知识",
                "relevance_scores": []
            }
        
        # 格式化结果
        formatted_results = []
        relevance_scores = []
        
        for result in search_results:
            formatted_results.append({
                "content": result['content'],
                "metadata": result.get('metadata', {}),
                "relevance": 1 - result.get('distance', 0)  # 距离越小，相关性越高
            })
            relevance_scores.append(1 - result.get('distance', 0))
        
        # 生成摘要
        summary = _generate_knowledge_summary(formatted_results, query)
        
        result = {
            "results": formatted_results,
            "summary": summary,
            "relevance_scores": relevance_scores,
            "total_found": len(formatted_results)
        }
        
        logger.info(f"Found {len(formatted_results)} relevant knowledge entries")
        return result
    
    except Exception as e:
        logger.error(f"Error searching knowledge: {e}", exc_info=True)
        return {
            "error": str(e),
            "results": [],
            "summary": f"检索失败: {str(e)}"
        }


@tool(
    description="添加新的报价知识到知识库",
    permission="read_write"
)
def add_quotation_knowledge(
    content: str,
    knowledge_type: str,
    metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    添加报价知识
    
    Args:
        content: 知识内容
        knowledge_type: 知识类型 ("historical_price", "market_trend", "supplier_review", "case_study")
        metadata: 元数据
        
    Returns:
        Dict: 添加结果
    """
    logger.info(f"Adding quotation knowledge: type={knowledge_type}")
    
    try:
        # 准备元数据
        full_metadata = metadata or {}
        full_metadata['type'] = knowledge_type
        
        # 添加到 ChromaDB
        doc_id = quotation_memory.add(
            content=content,
            metadata=full_metadata
        )
        
        if doc_id:
            logger.info(f"Knowledge added successfully: id={doc_id}")
            return {
                "success": True,
                "doc_id": doc_id,
                "message": "知识添加成功"
            }
        else:
            return {
                "success": False,
                "message": "知识添加失败"
            }
    
    except Exception as e:
        logger.error(f"Error adding knowledge: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "message": f"添加失败: {str(e)}"
        }


def _generate_knowledge_summary(results: List[Dict], query: str) -> str:
    """
    生成知识检索摘要
    
    Args:
        results: 检索结果列表
        query: 查询文本
        
    Returns:
        str: 摘要文本
    """
    if not results:
        return "未找到相关知识"
    
    summary = f"针对查询「{query}」，找到 {len(results)} 条相关知识：\n\n"
    
    for i, result in enumerate(results[:3], 1):  # 只摘要前3条
        content_preview = result['content'][:100] + "..." if len(result['content']) > 100 else result['content']
        relevance = result.get('relevance', 0)
        summary += f"{i}. (相关度: {relevance:.2f}) {content_preview}\n"
    
    if len(results) > 3:
        summary += f"\n...以及其他 {len(results) - 3} 条相关知识"
    
    return summary


def initialize_quotation_knowledge_base():
    """
    初始化报价知识库（添加示例数据）
    
    这个函数应该在系统初始化时调用一次
    """
    logger.info("Initializing quotation knowledge base...")
    
    # 示例知识条目
    sample_knowledge = [
        {
            "content": "钢材零件数控加工，历史平均价格 50-60 元/件，市场价格相对稳定。精密加工会增加 30-50% 成本。",
            "type": "historical_price",
            "metadata": {"material": "钢", "process": "数控加工", "date": "2024-01"}
        },
        {
            "content": "铝合金零件加工价格近期呈上涨趋势，主要原因是原材料价格上涨。建议锁定长期供应商以稳定价格。",
            "type": "market_trend",
            "metadata": {"material": "铝合金", "trend": "上涨", "date": "2024-02"}
        },
        {
            "content": "精密机械厂：质量稳定，交期准时，但价格略高于市场平均 5-10%。适合高精度零件加工。",
            "type": "supplier_review",
            "metadata": {"supplier": "精密机械厂", "rating": "优秀"}
        },
        {
            "content": "案例：某项目采购 1000 件轴承座，初始报价 65 元/件，经过谈判降至 55 元/件，节省成本 10000 元。谈判关键：强调批量优势和长期合作。",
            "type": "case_study",
            "metadata": {"part": "轴承座", "quantity": 1000, "savings": 10000}
        },
        {
            "content": "大批量订单（>500件）通常可获得 5-15% 的批量折扣。建议在谈判时明确提出批量折扣要求。",
            "type": "negotiation_tip",
            "metadata": {"topic": "批量折扣"}
        },
        {
            "content": "供应商利润率通常在 15-25% 之间。如果利润率超过 30%，存在较大议价空间。",
            "type": "market_insight",
            "metadata": {"topic": "利润率"}
        }
    ]
    
    # 添加到知识库
    for knowledge in sample_knowledge:
        add_quotation_knowledge(
            content=knowledge['content'],
            knowledge_type=knowledge['type'],
            metadata=knowledge.get('metadata', {})
        )
    
    logger.info(f"Added {len(sample_knowledge)} sample knowledge entries")


# 测试代码
if __name__ == "__main__":
    # 初始化知识库
    print("初始化知识库...")
    initialize_quotation_knowledge_base()
    
    # 测试检索
    print("\n测试检索:")
    result = search_quotation_knowledge(
        query="钢材零件的历史价格",
        top_k=3
    )
    
    print(f"找到 {result['total_found']} 条结果")
    print(f"\n摘要:\n{result['summary']}")
    
    # 测试添加知识
    print("\n测试添加知识:")
    add_result = add_quotation_knowledge(
        content="塑料零件注塑成型，市场价格 20-30 元/件，交期通常 7-10 天。",
        knowledge_type="historical_price",
        metadata={"material": "塑料", "process": "注塑"}
    )
    print(f"添加结果: {add_result['message']}")
