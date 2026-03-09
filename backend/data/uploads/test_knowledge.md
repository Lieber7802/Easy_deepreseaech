# Deep Research Agent

Deep Research Agent 是一个基于 LangGraph 的多智能体系统。

## 核心架构
系统采用 Map-Reduce 架构：
1. **Supervisor (Lead Researcher)**: 负责拆解任务，分配给 Researcher。
2. **Researcher**: 执行具体的搜索任务。
3. **Reviewer (可选)**: 审核结果。

## RAG 系统
本项目集成了基于 ChromaDB 和 ZhipuAI 的 RAG 模块。
支持 PDF、TXT、Markdown 文件上传。
向量维度为 1024。

## 技术栈
- Backend: Python, FastAPI, LangChain, LangGraph
- Frontend: Vue 3, TypeScript
- Search: Tavily, DuckDuckGo
- Database: ChromaDB (Vector)
