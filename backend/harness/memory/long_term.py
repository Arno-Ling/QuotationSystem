"""
LongTermMemory - 长期记忆管理
基于 ChromaDB 的向量数据库，支持语义相似性检索
"""
from typing import List, Dict, Any, Optional
import logging
import uuid

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logging.warning("ChromaDB not installed. Long-term memory will be disabled.")

logger = logging.getLogger(__name__)


class LongTermMemory:
    """
    长期记忆管理器
    
    使用 ChromaDB 存储和检索历史会话片段
    支持语义相似性检索
    """
    
    def __init__(
        self,
        collection_name: str = "agent_memory",
        persist_directory: str = "./chroma_db"
    ):
        """
        初始化长期记忆
        
        Args:
            collection_name: 集合名称
            persist_directory: 持久化目录
        """
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self.enabled = CHROMADB_AVAILABLE
        
        if not self.enabled:
            logger.warning("Long-term memory disabled (ChromaDB not available)")
            return
        
        try:
            # 初始化 ChromaDB 客户端
            self.client = chromadb.Client(Settings(
                persist_directory=persist_directory,
                anonymized_telemetry=False
            ))
            
            # 获取或创建集合
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"description": "Agent long-term memory"}
            )
            
            logger.info(f"LongTermMemory initialized: collection='{collection_name}'")
        
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            self.enabled = False
    
    def add(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        doc_id: Optional[str] = None
    ) -> str:
        """
        添加记忆片段
        
        Args:
            content: 记忆内容
            metadata: 元数据
            doc_id: 文档 ID（可选，自动生成）
            
        Returns:
            str: 文档 ID
        """
        if not self.enabled:
            logger.warning("Long-term memory is disabled")
            return ""
        
        try:
            doc_id = doc_id or str(uuid.uuid4())
            
            self.collection.add(
                documents=[content],
                metadatas=[metadata or {}],
                ids=[doc_id]
            )
            
            logger.debug(f"Added memory: id={doc_id}, content_length={len(content)}")
            return doc_id
        
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")
            return ""
    
    def search(
        self,
        query: str,
        top_k: int = 3,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索相关记忆
        
        Args:
            query: 查询文本
            top_k: 返回前 k 个结果
            filter_metadata: 元数据过滤条件
            
        Returns:
            List[Dict]: 搜索结果列表
            [
                {
                    "id": "doc_id",
                    "content": "content",
                    "metadata": {...},
                    "distance": 0.5
                }
            ]
        """
        if not self.enabled:
            logger.warning("Long-term memory is disabled")
            return []
        
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                where=filter_metadata
            )
            
            # 格式化结果
            formatted_results = []
            if results['ids'] and results['ids'][0]:
                for i in range(len(results['ids'][0])):
                    formatted_results.append({
                        "id": results['ids'][0][i],
                        "content": results['documents'][0][i],
                        "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                        "distance": results['distances'][0][i] if results['distances'] else 0.0
                    })
            
            logger.debug(f"Search found {len(formatted_results)} results for query: {query[:50]}...")
            return formatted_results
        
        except Exception as e:
            logger.error(f"Failed to search memory: {e}")
            return []
    
    def delete(self, doc_id: str) -> bool:
        """
        删除记忆片段
        
        Args:
            doc_id: 文档 ID
            
        Returns:
            bool: 是否成功删除
        """
        if not self.enabled:
            return False
        
        try:
            self.collection.delete(ids=[doc_id])
            logger.debug(f"Deleted memory: id={doc_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete memory: {e}")
            return False
    
    def clear(self) -> bool:
        """
        清空所有记忆
        
        Returns:
            bool: 是否成功清空
        """
        if not self.enabled:
            return False
        
        try:
            self.client.delete_collection(name=self.collection_name)
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "Agent long-term memory"}
            )
            logger.info("Long-term memory cleared")
            return True
        except Exception as e:
            logger.error(f"Failed to clear memory: {e}")
            return False
    
    def get_relevant_context(self, query: str, top_k: int = 3) -> str:
        """
        获取与查询相关的上下文
        
        Args:
            query: 查询文本
            top_k: 返回前 k 个结果
            
        Returns:
            str: 格式化的相关上下文
        """
        results = self.search(query, top_k=top_k)
        
        if not results:
            return "No relevant historical context found."
        
        context = "Relevant historical context:\n\n"
        for i, result in enumerate(results, 1):
            context += f"{i}. {result['content']}\n"
            if result.get('metadata'):
                context += f"   Metadata: {result['metadata']}\n"
            context += "\n"
        
        return context
    
    def __repr__(self) -> str:
        status = "enabled" if self.enabled else "disabled"
        return f"<LongTermMemory(status={status}, collection='{self.collection_name}')>"
