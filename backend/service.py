import json
import uuid
import asyncio
import time
from typing import AsyncIterator, Dict, Any, List
from langchain_core.messages import AIMessage, ToolMessage
from src.core.deep_researcher import deep_researcher
from src.core.configuration import Configuration
from src.core.skills.base import SkillRegistry
from src.evaluation.collector import get_collector
from src.evaluation.schema import EvaluationContext
from models import TodoItem

class DeepResearchService:
    def __init__(self):
        self.todo_items: List[TodoItem] = []
        self.topic_to_task_id: Dict[str, int] = {}
        self.tool_call_id_to_task_id: Dict[str, int] = {}
        self.task_counter = 0

    def get_skills(self) -> List[Dict[str, Any]]:
        """Get all available skills."""
        return list(SkillRegistry.list_skills().values())

    def toggle_skill(self, skill_name: str, enabled: bool) -> bool:
        """Toggle a skill on/off (Mock implementation for now)."""
        # In a real app, we would persist this preference or pass it to graph config.
        # For now, we just return True to simulate success.
        skill = SkillRegistry.get_skill(skill_name)
        return skill is not None

    def _create_task(self, topic: str) -> TodoItem:
        self.task_counter += 1
        task = TodoItem(
            id=self.task_counter,
            title=f"研究任务 {self.task_counter}",
            intent=f"研究子话题: {topic}",
            query=topic,
            status="pending"
        )
        self.todo_items.append(task)
        self.topic_to_task_id[topic] = task.id
        return task

    async def run_stream(
        self,
        topic: str,
        search_api: str = "tavily",
        run_id: str | None = None,
        experiment_id: str | None = None,
        dataset_id: str | None = None,
        sample_id: str | None = None,
        eval_mode: str = "online",
        agentic_rag_mode: str = "both",
        evaluation_enabled: bool = False,
    ) -> AsyncIterator[dict]:
        self.todo_items = []
        self.topic_to_task_id = {}
        self.tool_call_id_to_task_id = {}
        self.task_counter = 0

        active_run_id = run_id or str(uuid.uuid4())
        thread_id = str(uuid.uuid4())
        collector = get_collector()
        eval_context = EvaluationContext(
            run_id=active_run_id,
            experiment_id=experiment_id,
            dataset_id=dataset_id,
            sample_id=sample_id,
            eval_mode=eval_mode,
            rag_mode=agentic_rag_mode,
        )

        inputs = {"messages": [{"role": "user", "content": topic}]}
        config = {
            "configurable": {
                "thread_id": thread_id,
                "search_api": search_api,
                "max_researcher_iterations": 5, # 增加迭代次数以防止任务被截断
                "max_concurrent_research_units": 3,
                "run_id": active_run_id,
                "experiment_id": experiment_id,
                "dataset_id": dataset_id,
                "sample_id": sample_id,
                "eval_mode": eval_mode,
                "agentic_rag_mode": agentic_rag_mode,
                "evaluation_enabled": evaluation_enabled,
            }
        }

        run_started_at = time.perf_counter()
        first_event_latency_ms: float | None = None
        metrics = {
            "tasks_created": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "tool_calls": 0,
        }
        has_finished = False

        if evaluation_enabled:
            collector.emit_from_context(
                context=eval_context,
                event_type="run_started",
                component="service",
                payload={
                    "topic": topic,
                    "search_api": search_api,
                    "thread_id": thread_id,
                },
            )

        yield {"type": "status", "message": "初始化研究流程..."}

        # 记录已发送状态的任务，避免重复发送
        sent_status_tasks = set()

        async for event in deep_researcher.astream_events(inputs, config, version="v2"):
            kind = event["event"]
            name = event["name"]
            data = event["data"]
            tags = event.get("tags", [])
            metadata = event.get("metadata", {})
            
            if first_event_latency_ms is None:
                first_event_latency_ms = (time.perf_counter() - run_started_at) * 1000.0

            current_topic = metadata.get("research_topic")
            current_tool_call_id = metadata.get("tool_call_id")
            
            current_task_id = None
            if current_tool_call_id:
                current_task_id = self.tool_call_id_to_task_id.get(current_tool_call_id)
            
            if not current_task_id and current_topic:
                current_task_id = self.topic_to_task_id.get(current_topic)
            
            langgraph_node = metadata.get("langgraph_node")

            # 1. 捕获 Supervisor 的任务分配
            if kind == "on_chat_model_end":
                output = data.get("output")
                if output and isinstance(output, AIMessage) and output.tool_calls:
                    new_tasks = []
                    for tool_call in output.tool_calls:
                        if tool_call["name"] == "ConductResearch":
                            sub_topic = tool_call["args"].get("research_topic")
                            tool_call_id = tool_call.get("id")
                            if sub_topic and sub_topic not in self.topic_to_task_id:
                                task = self._create_task(sub_topic)
                                new_tasks.append(task)
                                if tool_call_id:
                                    self.tool_call_id_to_task_id[tool_call_id] = task.id
                    
                    if new_tasks:
                        metrics["tasks_created"] = len(self.todo_items)
                        if evaluation_enabled:
                            collector.emit_from_context(
                                context=eval_context,
                                event_type="todo_tasks_created",
                                component="service",
                                payload={
                                    "tasks_created": len(self.todo_items),
                                    "latest_created_count": len(new_tasks),
                                },
                            )
                        yield {
                            "type": "todo_list",
                            "tasks": [t.dict() for t in self.todo_items],
                            "step": 0
                        }

            # 2. 捕获 Researcher 开始
            if kind == "on_chain_start" and name == "researcher" and current_task_id:
                for t in self.todo_items:
                    if t.id == current_task_id:
                        t.status = "in_progress"
                        sent_status_tasks.add(current_task_id) # 记录已发送状态
                yield {
                    "type": "task_status",
                    "task_id": current_task_id,
                    "status": "in_progress",
                    "title": f"研究任务 {current_task_id}",
                    "intent": f"正在研究: {current_topic}"
                }

            # 3. 捕获 Tool Calls (包括搜索)
            if kind == "on_tool_start" and current_task_id:
                 metrics["tool_calls"] += 1
                 if evaluation_enabled:
                    collector.emit_from_context(
                        context=eval_context,
                        event_type="tool_invoked",
                        component="service",
                        payload={
                            "tool": name,
                            "task_id": current_task_id,
                        },
                    )
                 yield {
                    "type": "tool_call",
                    "tool": name,
                    "task_id": current_task_id,
                    "parameters": data.get("input")
                 }

            # 4. 捕获 Tool Outputs (包括搜索结果)
            if kind == "on_tool_end" and current_task_id:
                output = data.get("output")
                # 如果是 Web Search 工具，提取内容作为 sources
                if output and isinstance(output, str):
                    # 尝试判断是否为搜索结果
                    if "http" in output or "Source" in output or "Snippet" in output:
                        yield {
                            "type": "sources",
                            "task_id": current_task_id,
                            "latest_sources": output,
                            "backend": "search"
                        }
                
                yield {
                    "type": "tool_call",
                    "tool": name,
                    "task_id": current_task_id,
                    "result": str(output)[:1000] # 截断防止过大
                }

            # 5. 捕获压缩结果 (Summary)
            if kind == "on_chain_end" and name == "compress_research" and current_task_id:
                 output = data.get("output")
                 if output and isinstance(output, dict) and "compressed_research" in output:
                     summary = output["compressed_research"]
                     for t in self.todo_items:
                        if t.id == current_task_id:
                            t.summary = summary
                            t.status = "completed"
                    
                     yield {
                        "type": "task_summary_chunk",
                        "task_id": current_task_id,
                        "content": summary
                     }
                     yield {
                        "type": "task_status",
                        "task_id": current_task_id,
                        "status": "completed"
                     }
                     metrics["tasks_completed"] += 1

            # 6. 捕获 supervisor_tools 结束，用于处理异常情况下的任务状态更新
            if kind == "on_chain_end" and name == "supervisor_tools":
                output = data.get("output")
                messages = []
                if output:
                    if hasattr(output, "update"): # Command object
                        messages = output.update.get("supervisor_messages", [])
                    elif isinstance(output, dict):
                        if "supervisor_messages" in output:
                            messages = output["supervisor_messages"]
                        elif "update" in output and isinstance(output["update"], dict):
                             messages = output["update"].get("supervisor_messages", [])
                        # LangGraph 可能把 Command 序列化为 {"goto": ..., "update": ...}
                
                for msg in messages:
                    # 注意：从 Command 中获取的 messages 可能是 ToolMessage 对象
                    if hasattr(msg, "tool_call_id"): # Duck typing for ToolMessage
                        task_id = self.tool_call_id_to_task_id.get(msg.tool_call_id)
                        if task_id:
                            # 找到对应的任务
                            for t in self.todo_items:
                                if t.id == task_id:
                                    # 如果尚未发送 "in_progress" 状态，先发送一次
                                    if task_id not in sent_status_tasks:
                                        t.status = "in_progress"
                                        yield {
                                            "type": "task_status",
                                            "task_id": task_id,
                                            "status": "in_progress",
                                            "title": t.title,
                                            "intent": t.intent
                                        }
                                        sent_status_tasks.add(task_id)

                                    if t.status != "completed":
                                        # 如果内容包含错误，标记为失败
                                        if "Error" in str(msg.content) or "failed" in str(msg.content):
                                            t.status = "failed"
                                            t.summary = str(msg.content)[:500] + "..." # 截断摘要防止过长
                                            metrics["tasks_failed"] += 1
                                        else:
                                            # 正常完成（可能是从 ToolMessage 里恢复的）
                                            t.status = "completed"
                                            t.summary = str(msg.content)[:500] + "..." # 截断摘要防止过长
                                            metrics["tasks_completed"] += 1
                                        
                                        yield {
                                            "type": "task_status",
                                            "task_id": task_id,
                                            "status": t.status,
                                            "summary": t.summary
                                        }

            # 7. 捕获最终报告
            if kind == "on_chain_end" and name == "final_report_generation":
                output = data.get("output")
                if output and isinstance(output, dict) and "final_report" in output:
                    report = output["final_report"]
                    total_latency_ms = (time.perf_counter() - run_started_at) * 1000.0
                    completed_count = sum(1 for t in self.todo_items if t.status == "completed")
                    failed_count = sum(1 for t in self.todo_items if t.status == "failed")
                    if evaluation_enabled:
                        collector.emit_from_context(
                            context=eval_context,
                            event_type="run_finished",
                            component="service",
                            payload={
                                "status": "completed",
                                "total_latency_ms": total_latency_ms,
                                "first_event_latency_ms": first_event_latency_ms or 0.0,
                                "tasks_created": len(self.todo_items),
                                "tasks_completed": completed_count,
                                "tasks_failed": failed_count,
                                "tool_calls": metrics["tool_calls"],
                                "report_length": len(report),
                            },
                        )
                        yield {
                            "type": "metrics",
                            "run_id": active_run_id,
                            "metrics": {
                                "total_latency_ms": total_latency_ms,
                                "first_event_latency_ms": first_event_latency_ms or 0.0,
                                "tasks_created": len(self.todo_items),
                                "tasks_completed": completed_count,
                                "tasks_failed": failed_count,
                                "tool_calls": metrics["tool_calls"],
                            },
                        }
                        yield {
                            "type": "eval_summary",
                            "run_id": active_run_id,
                            "summary": {
                                "rag_mode": agentic_rag_mode,
                                "tasks_created": len(self.todo_items),
                                "tasks_completed": completed_count,
                                "tasks_failed": failed_count,
                                "tool_calls": metrics["tool_calls"],
                            },
                        }
                    yield {
                        "type": "final_report",
                        "report": report
                    }
                    yield {"type": "done"}
                    has_finished = True
                    return
        if evaluation_enabled and not has_finished:
            total_latency_ms = (time.perf_counter() - run_started_at) * 1000.0
            collector.emit_from_context(
                context=eval_context,
                event_type="run_finished",
                component="service",
                payload={
                    "status": "failed",
                    "total_latency_ms": total_latency_ms,
                    "first_event_latency_ms": first_event_latency_ms or 0.0,
                    "tasks_created": len(self.todo_items),
                    "tasks_completed": sum(1 for t in self.todo_items if t.status == "completed"),
                    "tasks_failed": sum(1 for t in self.todo_items if t.status == "failed"),
                    "tool_calls": metrics["tool_calls"],
                },
            )
