"""
RAGSkill - 知识检索技能（异常案例）
从知识库检索相似的历史异常案例
使用 ChromaDB 检索历史异常案例
"""
from typing import Dict, Any, Optional, List
import logging

import sys
sys.path.append('../../..')
from harness.tools import tool
from harness.memory import LongTermMemory

logger = logging.getLogger(__name__)


# 初始化长期记忆（ChromaDB）
exception_memory = LongTermMemory(
    collection_name="exception_cases",
    persist_directory="./chroma_db/exception_agent"
)


@tool(
    description="从知识库检索相似的历史异常案例",
    permission="read_only"
)
def search_exception_cases(
    query: str,
    exception_type: str = None,
    top_k: int = 5
) -> Dict[str, Any]:
    """
    检索历史异常案例
    
    Args:
        query: 查询文本（异常描述）
        exception_type: 异常类型过滤 ("尺寸偏差", "表面缺陷", "材料问题", "组装问题")
        top_k: 返回结果数量（默认5，最多5）
        
    Returns:
        Dict: 检索结果
        {
            "cases": List[Dict],  # 检索到的历史案例
            "summary": str,  # 结果摘要
            "total_found": int  # 找到的案例数量
        }
    """
    logger.info(f"Searching exception cases: query='{query}', exception_type={exception_type}, top_k={top_k}")
    
    # 限制 top_k 最多为 5
    top_k = min(top_k, 5)
    
    try:
        # 构建过滤条件
        filter_metadata = None
        if exception_type:
            filter_metadata = {"exception_type": exception_type}
        
        # 从 ChromaDB 检索
        search_results = exception_memory.search(
            query=query,
            top_k=top_k,
            filter_metadata=filter_metadata
        )
        
        if not search_results:
            return {
                "cases": [],
                "summary": "未找到相关历史案例",
                "total_found": 0
            }
        
        # 格式化结果并提取元数据
        formatted_cases = []
        all_low_similarity = True
        
        for result in search_results:
            # 计算相似度分数（距离越小，相似度越高）
            similarity_score = 1 - result.get('distance', 0)
            
            # 检查是否有高相似度案例
            if similarity_score >= 0.6:
                all_low_similarity = False
            
            # 提取案例元数据
            metadata = result.get('metadata', {})
            case = {
                "case_id": metadata.get('case_id', 'N/A'),
                "exception_type": metadata.get('exception_type', 'N/A'),
                "description": result['content'],
                "responsible_party": metadata.get('responsible_party', 'N/A'),
                "resolution": metadata.get('resolution_plan', 'N/A'),
                "outcome": metadata.get('outcome', 'N/A'),
                "resolution_date": metadata.get('resolution_date', 'N/A'),
                "similarity_score": round(similarity_score, 3)
            }
            formatted_cases.append(case)
        
        # 处理低相似度情况
        if all_low_similarity:
            summary = "未找到相关性足够高的历史案例（所有案例相似度 < 0.6）"
        else:
            # 生成摘要
            summary = _generate_case_summary(formatted_cases, query)
        
        result = {
            "cases": formatted_cases,
            "summary": summary,
            "total_found": len(formatted_cases)
        }
        
        logger.info(f"Found {len(formatted_cases)} historical cases")
        return result
    
    except Exception as e:
        logger.error(f"Error searching exception cases: {e}", exc_info=True)
        return {
            "error": str(e),
            "cases": [],
            "summary": f"检索失败: {str(e)}",
            "total_found": 0
        }


@tool(
    description="添加新的异常案例到知识库",
    permission="read_write"
)
def add_exception_case(
    description: str,
    exception_type: str,
    responsible_party: str,
    resolution_plan: str,
    outcome: str,
    metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    添加已解决的异常案例到知识库
    
    Args:
        description: 异常描述
        exception_type: 异常类型
        responsible_party: 责任方 (internal, supplier, material_vendor)
        resolution_plan: 解决方案
        outcome: 解决结果
        metadata: 额外元数据（可选）
        
    Returns:
        Dict: 添加结果
    """
    logger.info(f"Adding exception case: type={exception_type}, responsible_party={responsible_party}")
    
    try:
        # 准备完整元数据
        full_metadata = metadata or {}
        full_metadata.update({
            'exception_type': exception_type,
            'responsible_party': responsible_party,
            'resolution_plan': resolution_plan,
            'outcome': outcome
        })
        
        # 生成嵌入内容（描述 + 解决方案）
        content = f"{description}\n解决方案: {resolution_plan}\n结果: {outcome}"
        
        # 添加到 ChromaDB
        doc_id = exception_memory.add(
            content=content,
            metadata=full_metadata
        )
        
        if doc_id:
            logger.info(f"Exception case added successfully: id={doc_id}")
            return {
                "success": True,
                "doc_id": doc_id,
                "message": "异常案例添加成功"
            }
        else:
            return {
                "success": False,
                "message": "异常案例添加失败"
            }
    
    except Exception as e:
        logger.error(f"Error adding exception case: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "message": f"添加失败: {str(e)}"
        }


def _generate_case_summary(cases: List[Dict], query: str) -> str:
    """
    生成案例检索摘要
    
    Args:
        cases: 检索结果列表
        query: 查询文本
        
    Returns:
        str: 摘要文本
    """
    if not cases:
        return "未找到相关历史案例"
    
    summary = f"针对查询「{query}」，找到 {len(cases)} 条相关历史案例：\n\n"
    
    for i, case in enumerate(cases[:3], 1):  # 只摘要前3条
        desc_preview = case['description'][:80] + "..." if len(case['description']) > 80 else case['description']
        similarity = case.get('similarity_score', 0)
        responsible = case.get('responsible_party', 'N/A')
        resolution = case.get('resolution', 'N/A')
        
        summary += f"{i}. (相似度: {similarity:.2f}) {desc_preview}\n"
        summary += f"   责任方: {responsible}, 解决方案: {resolution[:50]}...\n"
    
    if len(cases) > 3:
        summary += f"\n...以及其他 {len(cases) - 3} 条相关案例"
    
    return summary


def initialize_exception_knowledge_base():
    """
    初始化异常案例知识库（添加示例数据）
    
    这个函数应该在系统初始化时调用一次
    """
    logger.info("Initializing exception knowledge base...")
    
    # 示例异常案例
    sample_cases = [
        {
            "description": "轴承座内径尺寸超差0.5mm，超出公差范围±0.2mm，导致轴承无法正常安装",
            "exception_type": "尺寸偏差",
            "responsible_party": "supplier",
            "resolution_plan": "返工处理，重新加工修正内径尺寸",
            "outcome": "成功解决，重新加工后尺寸合格",
            "metadata": {
                "case_id": "CASE001",
                "resolution_date": "2024-01-10",
                "cost": 2500.0,
                "time_days": 5
            }
        },
        {
            "description": "零件表面有明显划痕和氧化痕迹，影响外观质量",
            "exception_type": "表面缺陷",
            "responsible_party": "supplier",
            "resolution_plan": "表面重新处理，抛光并重新镀层",
            "outcome": "成功解决，表面质量达标",
            "metadata": {
                "case_id": "CASE002",
                "resolution_date": "2024-01-12",
                "cost": 1500.0,
                "time_days": 3
            }
        },
        {
            "description": "材料硬度不足，检测发现硬度值低于规格要求HRC45",
            "exception_type": "材料问题",
            "responsible_party": "material_vendor",
            "resolution_plan": "更换材料，重新采购符合规格的材料",
            "outcome": "成功解决，新材料硬度合格",
            "metadata": {
                "case_id": "CASE003",
                "resolution_date": "2024-01-15",
                "cost": 8000.0,
                "time_days": 10
            }
        },
        {
            "description": "组装时发现螺纹孔位置偏移2mm，导致无法正常组装",
            "exception_type": "尺寸偏差",
            "responsible_party": "supplier",
            "resolution_plan": "重新制造新零件，原零件报废",
            "outcome": "成功解决，新零件组装正常",
            "metadata": {
                "case_id": "CASE004",
                "resolution_date": "2024-01-18",
                "cost": 5000.0,
                "time_days": 8
            }
        },
        {
            "description": "零件在组装过程中发现配合间隙过大，影响装配精度",
            "exception_type": "组装问题",
            "responsible_party": "internal",
            "resolution_plan": "调整装配工艺，增加垫片补偿间隙",
            "outcome": "成功解决，装配精度满足要求",
            "metadata": {
                "case_id": "CASE005",
                "resolution_date": "2024-01-20",
                "cost": 800.0,
                "time_days": 2
            }
        },
        {
            "description": "材料成分分析发现碳含量超标，不符合材料规格要求",
            "exception_type": "材料问题",
            "responsible_party": "material_vendor",
            "resolution_plan": "退回材料，要求供应商更换符合规格的材料",
            "outcome": "成功解决，新材料成分合格",
            "metadata": {
                "case_id": "CASE006",
                "resolution_date": "2024-01-22",
                "cost": 6000.0,
                "time_days": 7
            }
        }
    ]
    
    # 添加到知识库
    for case in sample_cases:
        add_exception_case(
            description=case['description'],
            exception_type=case['exception_type'],
            responsible_party=case['responsible_party'],
            resolution_plan=case['resolution_plan'],
            outcome=case['outcome'],
            metadata=case.get('metadata', {})
        )
    
    logger.info(f"Added {len(sample_cases)} sample exception cases")


# 测试代码
if __name__ == "__main__":
    # 初始化知识库
    print("初始化异常案例知识库...")
    initialize_exception_knowledge_base()
    
    # 测试检索
    print("\n测试检索 - 尺寸偏差案例:")
    result = search_exception_cases(
        query="内径尺寸超差，无法安装",
        exception_type="尺寸偏差",
        top_k=3
    )
    
    print(f"找到 {result['total_found']} 条结果")
    print(f"\n摘要:\n{result['summary']}")
    
    if result['cases']:
        print("\n详细案例:")
        for case in result['cases']:
            print(f"- 案例ID: {case['case_id']}, 相似度: {case['similarity_score']}")
            print(f"  责任方: {case['responsible_party']}, 解决方案: {case['resolution']}")
    
    # 测试低相似度情况
    print("\n\n测试检索 - 不相关查询:")
    result2 = search_exception_cases(
        query="完全不相关的查询内容测试",
        top_k=3
    )
    print(f"摘要: {result2['summary']}")
