"""
Orchestrator - 多智能体编排层
支持定义多个 Agent，并根据任务分派给合适的 Agent
"""
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class AgentInfo:
    """Agent 信息模型"""
    
    def __init__(
        self,
        agent_id: str,
        name: str,
        description: str,
        capabilities: List[str],
        agent_instance: Any
    ):
        """
        初始化 Agent 信息
        
        Args:
            agent_id: Agent ID
            name: Agent 名称
            description: Agent 描述
            capabilities: Agent 能力列表
            agent_instance: Agent 实例
        """
        self.agent_id = agent_id
        self.name = name
        self.description = description
        self.capabilities = capabilities
        self.agent_instance = agent_instance
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "capabilities": self.capabilities
        }
    
    def __repr__(self) -> str:
        return f"<AgentInfo(id={self.agent_id}, name={self.name})>"


class Orchestrator:
    """
    多智能体编排器
    
    功能：
    1. 注册多个 Agent
    2. 根据任务选择合适的 Agent
    3. 协调 Agent 之间的协作
    4. 传递上下文和结果
    """
    
    def __init__(self):
        """初始化编排器"""
        self.agents: Dict[str, AgentInfo] = {}
        logger.info("Orchestrator initialized")
    
    def register_agent(
        self,
        agent_id: str,
        name: str,
        description: str,
        capabilities: List[str],
        agent_instance: Any
    ):
        """
        注册 Agent
        
        Args:
            agent_id: Agent ID
            name: Agent 名称
            description: Agent 描述
            capabilities: Agent 能力列表
            agent_instance: Agent 实例
        """
        agent_info = AgentInfo(
            agent_id=agent_id,
            name=name,
            description=description,
            capabilities=capabilities,
            agent_instance=agent_instance
        )
        
        self.agents[agent_id] = agent_info
        logger.info(f"Registered agent: {name} (id={agent_id})")
    
    def unregister_agent(self, agent_id: str) -> bool:
        """
        注销 Agent
        
        Args:
            agent_id: Agent ID
            
        Returns:
            bool: 是否成功注销
        """
        if agent_id in self.agents:
            agent_name = self.agents[agent_id].name
            del self.agents[agent_id]
            logger.info(f"Unregistered agent: {agent_name} (id={agent_id})")
            return True
        else:
            logger.warning(f"Agent not found: {agent_id}")
            return False
    
    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """
        获取 Agent 信息
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Optional[AgentInfo]: Agent 信息，如果不存在则返回 None
        """
        return self.agents.get(agent_id)
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """
        列出所有 Agent
        
        Returns:
            List[Dict]: Agent 列表
        """
        return [agent.to_dict() for agent in self.agents.values()]
    
    async def route_task(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        路由任务到合适的 Agent
        
        Args:
            task: 任务描述
            context: 额外上下文
            
        Returns:
            Dict: 执行结果
            {
                "agent_id": str,
                "agent_name": str,
                "result": Any,
                "success": bool
            }
        """
        logger.info(f"Routing task: {task[:100]}...")
        
        # 选择合适的 Agent
        selected_agent = self._select_agent(task, context)
        
        if not selected_agent:
            logger.error("No suitable agent found for task")
            return {
                "agent_id": None,
                "agent_name": None,
                "result": "Error: No suitable agent found",
                "success": False
            }
        
        logger.info(f"Selected agent: {selected_agent.name}")
        
        # 执行任务
        try:
            result = await self._execute_with_agent(selected_agent, task, context)
            
            return {
                "agent_id": selected_agent.agent_id,
                "agent_name": selected_agent.name,
                "result": result,
                "success": True
            }
        
        except Exception as e:
            logger.error(f"Error executing task with agent {selected_agent.name}: {e}")
            return {
                "agent_id": selected_agent.agent_id,
                "agent_name": selected_agent.name,
                "result": f"Error: {str(e)}",
                "success": False
            }
    
    def _select_agent(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[AgentInfo]:
        """
        选择合适的 Agent
        
        Args:
            task: 任务描述
            context: 额外上下文
            
        Returns:
            Optional[AgentInfo]: 选中的 Agent，如果没有则返回 None
        """
        if not self.agents:
            return None
        
        # 简单策略：基于关键词匹配能力
        task_lower = task.lower()
        
        # 计算每个 Agent 的匹配分数
        scores = {}
        for agent_id, agent_info in self.agents.items():
            score = 0
            for capability in agent_info.capabilities:
                if capability.lower() in task_lower:
                    score += 1
            scores[agent_id] = score
        
        # 选择分数最高的 Agent
        if scores:
            best_agent_id = max(scores, key=scores.get)
            if scores[best_agent_id] > 0:
                return self.agents[best_agent_id]
        
        # 如果没有匹配，返回第一个 Agent
        return list(self.agents.values())[0] if self.agents else None
    
    async def _execute_with_agent(
        self,
        agent_info: AgentInfo,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        使用指定 Agent 执行任务
        
        Args:
            agent_info: Agent 信息
            task: 任务描述
            context: 额外上下文
            
        Returns:
            Any: 执行结果
        """
        agent = agent_info.agent_instance
        
        # 检查 Agent 是否有 run 方法
        if hasattr(agent, 'run'):
            if hasattr(agent.run, '__call__'):
                # 异步方法
                import asyncio
                if asyncio.iscoroutinefunction(agent.run):
                    return await agent.run(task, context)
                else:
                    # 同步方法，转换为异步
                    return await asyncio.to_thread(agent.run, task, context)
        
        # 降级：直接返回任务
        logger.warning(f"Agent {agent_info.name} does not have a run method")
        return f"Agent {agent_info.name} received task: {task}"
    
    async def collaborate(
        self,
        task: str,
        agent_ids: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        多个 Agent 协作完成任务
        
        Args:
            task: 任务描述
            agent_ids: 参与的 Agent ID 列表
            context: 额外上下文
            
        Returns:
            Dict: 协作结果
            {
                "results": List[Dict],
                "final_result": Any,
                "success": bool
            }
        """
        logger.info(f"Collaborating with {len(agent_ids)} agents")
        
        results = []
        shared_context = context or {}
        
        # 依次执行每个 Agent
        for agent_id in agent_ids:
            agent_info = self.get_agent(agent_id)
            
            if not agent_info:
                logger.warning(f"Agent not found: {agent_id}")
                continue
            
            try:
                result = await self._execute_with_agent(agent_info, task, shared_context)
                
                results.append({
                    "agent_id": agent_id,
                    "agent_name": agent_info.name,
                    "result": result,
                    "success": True
                })
                
                # 更新共享上下文
                shared_context[f"result_from_{agent_id}"] = result
            
            except Exception as e:
                logger.error(f"Error in agent {agent_info.name}: {e}")
                results.append({
                    "agent_id": agent_id,
                    "agent_name": agent_info.name,
                    "result": f"Error: {str(e)}",
                    "success": False
                })
        
        # 汇总结果
        final_result = self._aggregate_results(results)
        
        return {
            "results": results,
            "final_result": final_result,
            "success": all(r["success"] for r in results)
        }
    
    def _aggregate_results(self, results: List[Dict[str, Any]]) -> str:
        """
        汇总多个 Agent 的结果
        
        Args:
            results: 结果列表
            
        Returns:
            str: 汇总结果
        """
        if not results:
            return "No results"
        
        aggregated = "Collaboration Results:\n\n"
        for i, result in enumerate(results, 1):
            status = "✅" if result["success"] else "❌"
            aggregated += f"{i}. {status} {result['agent_name']}: {result['result']}\n"
        
        return aggregated
    
    def get_state(self) -> Dict[str, Any]:
        """
        获取编排器状态
        
        Returns:
            Dict: 状态信息
        """
        return {
            "total_agents": len(self.agents),
            "agents": self.list_agents()
        }
    
    def __len__(self) -> int:
        """返回 Agent 数量"""
        return len(self.agents)
    
    def __repr__(self) -> str:
        return f"<Orchestrator(agents={len(self.agents)})>"
