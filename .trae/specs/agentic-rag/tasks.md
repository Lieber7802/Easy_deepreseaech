# Tasks
- [x] Task 1: 为 Agentic RAG 设计状态与 Prompt 基座
  - [x] SubTask 1.1: 在 `state.py` 中补充 RAG 子图所需状态，如原始查询、重写查询、子查询列表、文档评分结果、重试次数、知识缺口标记。
  - [x] SubTask 1.2: 在 `prompts.py` 中新增 Query Analysis、Query Rewriting、Query Decomposition、Document Grader、Hallucination Checker 所需 Prompt。
  - [x] SubTask 1.3: 约定各评分节点的结构化输出格式，避免文本判断导致的路由歧义。

- [x] Task 2: 重构 `rag_manager.py` 为可复用的 Agentic 检索原语
  - [x] SubTask 2.1: 保留现有 Dense + BM25 + RRF 检索主干，并明确其作为子图中的 HybridRetrieve 节点职责。
  - [x] SubTask 2.2: 增加对子查询并发检索与结果池合并的支持。
  - [x] SubTask 2.3: 暴露 Parent Chunks、召回评分上下文和文档元信息，供 Document Grader 与 Hallucination Checker 使用。

- [x] Task 3: 封装 Agentic RAG LangGraph 子图
  - [x] SubTask 3.1: 在 `deep_researcher.py` 或独立模块中实现 QueryAnalysis、RewriteQuery、HybridRetrieve、DocumentGrader、GenerateDraft、HallucinationCheck、WebSearchFallback 等节点。
  - [x] SubTask 3.2: 为子图增加条件边，实现“直接检索 / 先优化再检索 / 文档不相关则重写 / 知识缺口则 fallback”的循环与分支。
  - [x] SubTask 3.3: 为子图加入多轮重试上限与熔断逻辑，防止本地检索重写陷入死循环。
  - [x] SubTask 3.4: 为子图预留多跳追问入口，使系统可根据第一轮摘要触发第二轮定向检索。

- [x] Task 4: 将 Agentic RAG 能力接入现有 Researcher / Skill 体系
  - [x] SubTask 4.1: 将 Agentic RAG 子图封装为新的 Skill 或 Tool 入口，例如 `agentic_knowledge_base`。
  - [x] SubTask 4.2: 调整 Researcher 在处理本地知识问题时优先调用 Agentic RAG，而非单次 `search_knowledge_base`。
  - [x] SubTask 4.3: 保留原有 `search_knowledge_base` 作为底层原语或回退能力，降低切换风险。

- [x] Task 5: 分阶段落地外部知识回退与动态扩展
  - [x] SubTask 5.1: 第一阶段优先上线 Document Grader，以低成本提升检索精度。
  - [x] SubTask 5.2: 第二阶段完成完整 RAG 子图封装，并支持前端或配置层切换传统 RAG 与 Agentic RAG。
  - [x] SubTask 5.3: 第三阶段接入 MCP 数据源，在本地知识不足时支持动态拉取外部数据、建立临时索引后继续推理。

- [x] Task 6: 验证 Agentic RAG 的质量与稳定性
  - [x] SubTask 6.1: 验证查询重写与查询拆解能显著改善模糊或复杂问题的召回质量。
  - [x] SubTask 6.2: 验证文档评分能有效过滤无关 Chunk，并驱动正确的重试或回退路径。
  - [x] SubTask 6.3: 验证多轮本地检索失败时会触发 Knowledge Gap 和 Web Search fallback。
  - [x] SubTask 6.4: 验证 Hallucination Checker 能拦截未被 Parent Chunks 支撑的输出。
  - [x] SubTask 6.5: 验证新方案不会破坏现有 Deep Research 主图、Supervisor 分发与并发研究流程。

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 1 and Task 2
- Task 4 depends on Task 3
- Task 5 depends on Task 3 and Task 4
- Task 6 depends on Task 2, Task 3, Task 4, and Task 5
