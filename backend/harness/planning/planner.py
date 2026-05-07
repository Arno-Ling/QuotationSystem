"""
Planner - 规划与任务分解层
支持 Plan-and-Execute 模式和反思步骤
"""
from typing import List, Dict, Any, Optional
import logging
import json

logger = logging.getLogger(__name__)


class Task:
    """任务模型"""
    
    def __init__(
        self,
        task_id: str,
        description: str,
        status: str = "pending",
        result: Optional[Any] = None
    ):
        """
        初始化任务
        
        Args:
            task_id: 任务 ID
            description: 任务描述
            status: 任务状态 (pending, in_progress, completed, failed)
            result: 任务结果
        """
        self.task_id = task_id
        self.description = description
        self.status = status
        self.result = result
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "description": self.description,
            "status": self.status,
            "result": self.result
        }
    
    def __repr__(self) -> str:
        return f"<Task(id={self.task_id}, status={self.status})>"


class Plan:
    """计划模型"""
    
    def __init__(self, goal: str):
        """
        初始化计划
        
        Args:
            goal: 目标描述
        """
        self.goal = goal
        self.tasks: List[Task] = []
        self.current_task_index = 0
    
    def add_task(self, task: Task):
        """
        添加任务
        
        Args:
            task: 任务对象
        """
        self.tasks.append(task)
    
    def get_current_task(self) -> Optional[Task]:
        """
        获取当前任务
        
        Returns:
            Optional[Task]: 当前任务，如果没有则返回 None
        """
        if self.current_task_index < len(self.tasks):
            return self.tasks[self.current_task_index]
        return None
    
    def mark_current_task_completed(self, result: Any):
        """
        标记当前任务为完成
        
        Args:
            result: 任务结果
        """
        if self.current_task_index < len(self.tasks):
            self.tasks[self.current_task_index].status = "completed"
            self.tasks[self.current_task_index].result = result
            self.current_task_index += 1
    
    def mark_current_task_failed(self, error: str):
        """
        标记当前任务为失败
        
        Args:
            error: 错误信息
        """
        if self.current_task_index < len(self.tasks):
            self.tasks[self.current_task_index].status = "failed"
            self.tasks[self.current_task_index].result = {"error": error}
    
    def is_complete(self) -> bool:
        """
        检查计划是否完成
        
        Returns:
            bool: 是否完成
        """
        return self.current_task_index >= len(self.tasks)
    
    def get_progress(self) -> Dict[str, Any]:
        """
        获取进度信息
        
        Returns:
            Dict: 进度信息
        """
        completed = sum(1 for task in self.tasks if task.status == "completed")
        failed = sum(1 for task in self.tasks if task.status == "failed")
        
        return {
            "total": len(self.tasks),
            "completed": completed,
            "failed": failed,
            "current": self.current_task_index,
            "progress_percentage": (completed / len(self.tasks) * 100) if self.tasks else 0
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "goal": self.goal,
            "tasks": [task.to_dict() for task in self.tasks],
            "current_task_index": self.current_task_index,
            "progress": self.get_progress()
        }
    
    def __repr__(self) -> str:
        progress = self.get_progress()
        return f"<Plan(tasks={progress['total']}, completed={progress['completed']})>"


class Planner:
    """
    规划器
    
    支持 Plan-and-Execute 模式：
    1. 生成计划
    2. 逐步执行
    3. 反思和调整
    """
    
    def __init__(self, llm_caller: Optional[Any] = None):
        """
        初始化规划器
        
        Args:
            llm_caller: LLM 调用器（可选）
        """
        self.llm_caller = llm_caller
        logger.info("Planner initialized")
    
    async def generate_plan(self, goal: str, context: Optional[str] = None) -> Plan:
        """
        生成计划
        
        Args:
            goal: 目标描述
            context: 额外上下文
            
        Returns:
            Plan: 生成的计划
        """
        logger.info(f"Generating plan for goal: {goal}")
        
        # 构建提示
        prompt = self._build_planning_prompt(goal, context)
        
        # 调用 LLM 生成计划
        if self.llm_caller:
            try:
                plan_text = await self.llm_caller(prompt)
                plan = self._parse_plan(goal, plan_text)
            except Exception as e:
                logger.error(f"Error generating plan with LLM: {e}")
                # 降级：生成简单计划
                plan = self._generate_simple_plan(goal)
        else:
            # 没有 LLM，生成简单计划
            plan = self._generate_simple_plan(goal)
        
        logger.info(f"Plan generated with {len(plan.tasks)} tasks")
        return plan
    
    def _build_planning_prompt(self, goal: str, context: Optional[str] = None) -> str:
        """
        构建规划提示
        
        Args:
            goal: 目标描述
            context: 额外上下文
            
        Returns:
            str: 提示文本
        """
        prompt = f"""You are a task planner. Break down the following goal into a sequence of concrete, actionable sub-tasks.

Goal: {goal}
"""
        
        if context:
            prompt += f"\nContext: {context}\n"
        
        prompt += """
Please provide a plan as a numbered list of tasks. Each task should be:
1. Specific and actionable
2. Achievable with available tools
3. Ordered logically

Format your response as:
1. [Task description]
2. [Task description]
3. [Task description]
...

Plan:
"""
        
        return prompt
    
    def _parse_plan(self, goal: str, plan_text: str) -> Plan:
        """
        解析计划文本
        
        Args:
            goal: 目标描述
            plan_text: 计划文本
            
        Returns:
            Plan: 解析后的计划
        """
        plan = Plan(goal)
        
        # 解析任务列表
        lines = plan_text.strip().split('\n')
        task_counter = 1
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 匹配编号任务格式: "1. Task description" 或 "1) Task description"
            import re
            match = re.match(r'^\d+[\.\)]\s*(.+)$', line)
            if match:
                task_description = match.group(1).strip()
                task = Task(
                    task_id=f"task_{task_counter}",
                    description=task_description
                )
                plan.add_task(task)
                task_counter += 1
        
        # 如果没有解析到任务，创建一个默认任务
        if not plan.tasks:
            plan.add_task(Task(
                task_id="task_1",
                description=goal
            ))
        
        return plan
    
    def _generate_simple_plan(self, goal: str) -> Plan:
        """
        生成简单计划（降级方案）
        
        Args:
            goal: 目标描述
            
        Returns:
            Plan: 简单计划
        """
        plan = Plan(goal)
        plan.add_task(Task(
            task_id="task_1",
            description=goal
        ))
        return plan
    
    async def reflect_on_progress(
        self,
        plan: Plan,
        execution_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        反思执行进度
        
        Args:
            plan: 当前计划
            execution_history: 执行历史
            
        Returns:
            Dict: 反思结果
            {
                "should_continue": bool,
                "should_revise_plan": bool,
                "reflection": str,
                "suggestions": List[str]
            }
        """
        logger.info("Reflecting on progress")
        
        progress = plan.get_progress()
        
        # 构建反思提示
        prompt = self._build_reflection_prompt(plan, execution_history, progress)
        
        # 调用 LLM 进行反思
        if self.llm_caller:
            try:
                reflection_text = await self.llm_caller(prompt)
                reflection_result = self._parse_reflection(reflection_text)
            except Exception as e:
                logger.error(f"Error during reflection: {e}")
                reflection_result = self._default_reflection(progress)
        else:
            reflection_result = self._default_reflection(progress)
        
        logger.info(f"Reflection complete: should_continue={reflection_result['should_continue']}")
        return reflection_result
    
    def _build_reflection_prompt(
        self,
        plan: Plan,
        execution_history: List[Dict[str, Any]],
        progress: Dict[str, Any]
    ) -> str:
        """
        构建反思提示
        
        Args:
            plan: 当前计划
            execution_history: 执行历史
            progress: 进度信息
            
        Returns:
            str: 提示文本
        """
        prompt = f"""You are reflecting on the progress of a task execution.

Goal: {plan.goal}

Progress:
- Total tasks: {progress['total']}
- Completed: {progress['completed']}
- Failed: {progress['failed']}
- Current task: {progress['current'] + 1}

Execution History:
"""
        
        for i, entry in enumerate(execution_history[-5:], 1):  # 最后5条
            prompt += f"{i}. {entry}\n"
        
        prompt += """
Please reflect on:
1. Is the current approach working?
2. Should we continue with the current plan?
3. Should we revise the plan?
4. Any suggestions for improvement?

Provide your reflection and answer:
- Should continue: yes/no
- Should revise plan: yes/no
- Reflection: [your thoughts]
- Suggestions: [list of suggestions]
"""
        
        return prompt
    
    def _parse_reflection(self, reflection_text: str) -> Dict[str, Any]:
        """
        解析反思结果
        
        Args:
            reflection_text: 反思文本
            
        Returns:
            Dict: 反思结果
        """
        # 简单解析（实际应用中可以更复杂）
        should_continue = "should continue: yes" in reflection_text.lower()
        should_revise = "should revise plan: yes" in reflection_text.lower()
        
        return {
            "should_continue": should_continue,
            "should_revise_plan": should_revise,
            "reflection": reflection_text,
            "suggestions": []
        }
    
    def _default_reflection(self, progress: Dict[str, Any]) -> Dict[str, Any]:
        """
        默认反思（降级方案）
        
        Args:
            progress: 进度信息
            
        Returns:
            Dict: 反思结果
        """
        # 如果有失败任务，建议停止
        should_continue = progress['failed'] == 0
        
        return {
            "should_continue": should_continue,
            "should_revise_plan": False,
            "reflection": f"Progress: {progress['completed']}/{progress['total']} tasks completed",
            "suggestions": []
        }
    
    def __repr__(self) -> str:
        return f"<Planner(llm_enabled={self.llm_caller is not None})>"
