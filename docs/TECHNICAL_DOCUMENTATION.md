# Deep Research Agent 项目技术文档

## 1. 项目简介

Deep Research Agent 是一个基于 **LangGraph**、**LangChain**、**FastAPI** 和 **Vue 3** 的多智能体深度研究系统。系统的目标不是简单回答问题，而是围绕复杂研究主题，完成任务拆解、并发检索、证据汇总和最终报告生成。

当前版本在原有多智能体研究框架之上，进一步完成了本地知识检索链路的升级：除了传统的 **Hybrid RAG**，还新增了 **Agentic RAG**。这使得系统在处理本地知识库时，能够执行查询分析、查询重写、查询拆解、文档评分、重试回退和 groundedness 校验，而不是只做一次静态检索后直接生成答案。

## 2. 系统总体架构

### 2.1 顶层架构

系统分为四个主要层次：

1. **前端交互层**
   - 负责主题输入、文件上传、任务状态展示、日志流渲染和最终报告展示。
   - 通过 HTTP + SSE 与后端通信。

2. **API / Service 层**
   - `backend/main.py` 提供 `/research/stream`、`/upload`、`/skills` 等接口。
   - `backend/service.py` 负责调用 LangGraph 图，并把执行过程中的事件转成前端可消费的 SSE 消息。

3. **多智能体编排层**
   - 由 `deep_researcher.py` 定义主图、Supervisor 子图和 Researcher 子图。
   - Supervisor 负责拆解复杂研究任务。
   - Researcher 负责执行 Web Search、本地知识库检索、MCP 工具调用和信息压缩。

4. **知识与工具层**
   - Web Search：Tavily / DuckDuckGo / 供应商原生 Web Search
   - 本地知识检索：经典 `search_knowledge_base` 与增强版 `agentic_knowledge_base`
   - Skill Registry：统一注册内置技能和 MCP 映射能力
   - MCP：既可消费外部能力，也可作为能力提供方对外暴露

### 2.2 LangGraph 嵌套图结构

系统核心采用三层嵌套图：

- **主图 Main Graph**
  - `clarify_with_user`
  - `write_research_brief`
  - `research_supervisor`
  - `final_report_generation`

- **Supervisor 子图**
  - `supervisor`
  - `supervisor_tools`

- **Researcher 子图**
  - `researcher`
  - `researcher_tools`
  - `compress_research`

Researcher 在执行过程中会根据语义自主决定调用：
- `tavily_search`
- `duckduckgo_search`
- `search_knowledge_base`
- `agentic_knowledge_base`
- MCP Tool

## 3. 本地知识检索架构

### 3.1 经典 Hybrid RAG

原始本地知识库检索仍然保留，作为底层检索原语存在：

- **向量模型**: Zhipu `embedding-3`，1024 维
- **向量库**: Chroma
- **关键词检索**: BM25Retriever
- **融合方式**: RRF（Reciprocal Rank Fusion）
- **切块策略**:
  - Child Chunk：`chunk_size=800`，`chunk_overlap=160`
  - Parent Chunk：`chunk_size=3000`，`chunk_overlap=300`

该模式由 `search_knowledge_base` 工具直接暴露，适合低延迟、低成本、快速召回的场景。

### 3.2 Agentic RAG

新增的 Agentic RAG 不再把本地知识检索当作单次函数调用，而是把它升级为一个 **LangGraph 子图式执行流程**。它围绕“检索质量”构建闭环，核心阶段如下：

#### 预检索阶段

- **Query Analysis**
  - 判断问题适合本地库、外部搜索，还是无需检索。
  - 决定是否需要重写、是否需要拆解。

- **Query Rewriting**
  - 将模糊、短小或上下文不足的问题改写为更适合 Dense + BM25 的检索表达。

- **Query Decomposition**
  - 将复杂问题拆分为 2-3 个可并发检索的子查询。

#### 检索中阶段

- **Hybrid Retrieve**
  - 对每个查询执行 Dense + BM25 + RRF。
  - 在 Parent Chunk 级别聚合并返回候选文档。

- **Document Grader**
  - 对检索文档进行 Relevant / Irrelevant 评分。
  - 当高质量证据比例不足时触发自我纠错。

- **Reflect / Retry**
  - 检索失败或低相关时触发 query rewrite + retry。
  - 通过 `max_retries` 与 relevance ratio 限制防止死循环。

- **Knowledge Gap**
  - 当本地知识持续无法覆盖问题时，标记知识缺口，转入外部补充路径。

#### 后检索阶段

- **Generate Draft**
  - 基于筛选后的 Parent Chunk 生成草稿。

- **Hallucination Check**
  - 校验草稿中的核心断言能否被 Parent Chunks 支撑。
  - 校验失败则重新进入 rewrite / retry 或 fallback。

- **Web Search Fallback**
  - 本地知识库不足时，自动触发公网搜索补充结果。
  - 当前实现默认用 Tavily fallback。
  - 设计上已为 MCP 动态知识注入预留入口。

## 4. Agentic RAG 的代码实现

### 4.1 状态定义

在 `src/core/state.py` 中，新增了以下结构化输出模型：

- `QueryAnalysisResult`
- `QueryRewriteResult`
- `QueryDecompositionResult`
- `DocumentGradeResult`
- `HallucinationCheckResult`
- `AgenticRAGState`

这些模型的作用是：
- 让路由与条件边基于结构化字段，而不是脆弱的自然语言解析
- 为 LangGraph 子图提供稳定状态字段
- 让 Agentic RAG 各节点的控制逻辑可以被可靠复用

### 4.2 Prompt 模板

在 `src/core/prompts.py` 中新增：

- `agentic_rag_query_analysis_prompt`
- `agentic_rag_query_rewrite_prompt`
- `agentic_rag_query_decomposition_prompt`
- `agentic_rag_document_grader_prompt`
- `agentic_rag_hallucination_check_prompt`

这些 Prompt 被专门设计为结构化输出节点使用，目标是：
- 降低 Query 处理歧义
- 使文档评分与幻觉检测更稳定
- 将“评估、反思、纠错”能力真正嵌入检索链路

### 4.3 RAGManager 升级

`src/core/rag_manager.py` 现在同时承担两类职责：

1. **经典检索引擎**
   - 文档摄入
   - BM25 构建
   - Dense + BM25 + RRF 检索
   - Parent Chunk 聚合

2. **Agentic RAG 子图执行器**
   - `_analyze_query`
   - `_rewrite_query`
   - `_decompose_query`
   - `_grade_document`
   - `_check_hallucination`
   - `run_agentic_rag`

其中 `run_agentic_rag` 会在内部构造子图节点：

- `query_analysis`
- `rewrite_query`
- `decompose_query`
- `hybrid_retrieve`
- `document_grader`
- `generate_draft`
- `hallucination_check`
- `web_search_fallback`

### 4.4 外部动态知识注入

`rag_manager.py` 新增了 `ingest_external_documents`，其作用是：

- 接收运行时传入的外部文本或结构化文档
- 动态切块后写入现有 Chroma 与 BM25 语料
- 为未来通过 MCP 拉取 GitHub、数据库、企业内部系统数据后临时建索引提供能力基础

目前这部分主要作为接口预埋，便于后续扩展。

## 5. Tool / Skill / MCP 三层设计

### 5.1 Tool 层

`src/core/utils.py` 当前提供两类本地知识工具：

- `search_knowledge_base`
  - 经典 Hybrid RAG
  - 简洁、低成本、低延迟

- `agentic_knowledge_base`
  - Agentic RAG 子图入口
  - 支持查询分析、重写、拆解、文档评分、幻觉检测、fallback 和 trace 输出

### 5.2 Skill 层

`src/core/skills/builtin.py` 当前注册以下内置 Skill：

- `tavily_search`
- `search_knowledge_base`
- `agentic_knowledge_base`
- `arxiv_search`

其中 `agentic_knowledge_base` 的接入意义在于：
- Researcher 在工具调用循环中可以直接选择增强版本地知识检索
- 系统可通过配置决定仅暴露经典模式、仅暴露 Agentic 模式或同时暴露两者

### 5.3 配置层

在 `src/core/configuration.py` 中新增：

- `agentic_rag_mode`
  - `both`
  - `classic`
  - `agentic`

该配置会在 `get_all_tools()` 组装工具时生效，用于控制工具暴露范围。

### 5.4 MCP 层

项目支持两种 MCP 使用方式：

1. **作为 MCP Client**
   - 拉取外部 MCP Tool，映射为本地可用能力

2. **作为 MCP Server**
   - 对外提供深度研究与知识库检索能力

需要注意的是：
- 当前 `backend/mcp_server.py` 对外暴露的知识库工具仍以经典检索为主
- Agentic RAG 已在后端内部工具与 Skill 层实现，但尚未单独对外暴露为独立 MCP Tool

## 6. SSE 流式执行

`backend/main.py` 的 `/research/stream` 使用 `StreamingResponse` 输出 SSE 数据流。

`backend/service.py` 使用 `deep_researcher.astream_events(..., version="v2")` 捕获执行事件，并映射为前端事件流：

- `status`
- `todo_list`
- `task_status`
- `tool_call`
- `sources`
- `task_summary_chunk`
- `final_report`
- `done`

这种设计的特点是：
- 内部模型调用不做逐 token 文本流式
- 对外提供“节点级 / 工具级”事件流式
- 更适合多智能体、多工具、多子图场景下的用户体验

## 7. 当前实现的关键限制

虽然 Agentic RAG 已经完成基础实现，但仍有一些工程上明确保留的扩展点：

1. **多跳追问为预留入口**
   - 当前已在任务和子图设计上预留，但尚未构建完整第二轮概念追问闭环

2. **Groundedness 检查是单轮判断**
   - 当前实现可触发重写与 fallback，但还未细化到“逐段 claim 级别核验”

3. **MCP 动态注入为能力预埋**
   - `ingest_external_documents` 已可承接外部数据
   - 但尚未与具体 MCP 数据源形成自动化闭环

4. **Skill Toggle 仍是 mock**
   - `/skills/{name}/toggle` 当前只校验技能存在性
   - 未持久化用户偏好，也未真正动态关闭某个 Skill

## 8. 量化评估系统

当前版本新增了评估系统基础能力，目标是回答：

- Agentic RAG 是否优于经典 Hybrid RAG
- 具体提升了哪些指标
- 提升发生在哪些样本类型上

### 8.1 在线评估埋点

请求层支持评估上下文：

- `run_id`
- `experiment_id`
- `dataset_id`
- `sample_id`
- `eval_mode`
- `evaluation_enabled`

当 `evaluation_enabled=true` 时：

- `service.py` 会记录主流程指标（任务数、完成率、工具调用数、总耗时、首事件延迟）
- `search_knowledge_base` 会记录经典 Hybrid RAG 检索指标
- `agentic_knowledge_base` 与 `run_agentic_rag` 会记录 Agentic 子图指标（grader 通过率、retry、knowledge gap、fallback、groundedness）

事件默认写入：

- `backend/data/evaluations/evaluation_events.jsonl`

### 8.2 评估模块结构

新增模块：

- `src/evaluation/schema.py`：评估事件、上下文与报告结构
- `src/evaluation/collector.py`：统一事件采集与 jsonl 落盘
- `src/evaluation/runner.py`：离线基准集回放执行器
- `src/evaluation/report.py`：聚合 classic / agentic / both 对比报告

### 8.3 离线基准回放

基准样本文件：

- `backend/data/eval_datasets/baseline_eval_samples.jsonl`

运行方式示例：

```bash
cd backend
python -m src.evaluation.runner --dataset data/eval_datasets/baseline_eval_samples.jsonl --mode both --experiment-id exp-v1
```

### 8.4 关键对比指标

- 主流程：总耗时、首事件延迟、任务完成率、工具调用数
- Hybrid RAG：返回文档数、RRF 相关统计
- Agentic RAG：route 分布、rewrite/decomposition 触发率、grader 通过率、retry 次数、fallback 率、groundedness 通过率

### 8.5 边界与后续

- 当前 `eval_summary` 已在 SSE 中预留事件类型
- 事件已可用于后端离线聚合，但前端暂无完整评估可视化面板
- 后续可接入 sqlite / OLAP 存储，支持更长周期实验分析

## 9. 关键代码结构

```text
easy_deepresearch/
├── backend/
│   ├── main.py
│   ├── service.py
│   ├── mcp_server.py
│   ├── src/core/
│   │   ├── configuration.py
│   │   ├── deep_researcher.py
│   │   ├── prompts.py
│   │   ├── rag_manager.py
│   │   ├── state.py
│   │   ├── utils.py
│   │   └── skills/
│   │       ├── base.py
│   │       ├── builtin.py
│   │       └── mcp_client.py
├── frontend/
│   └── src/
│       ├── components/
│       ├── composables/
│       └── services/
└── docs/
    ├── TECHNICAL_DOCUMENTATION.md
    └── Agentic-RAG-report.md
```

## 10. 运行与配置

### 后端

```bash
cd backend
pip install .
python main.py
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

### 关键配置

- `search_api`
- `max_concurrent_research_units`
- `max_researcher_iterations`
- `max_react_tool_calls`
- `agentic_rag_mode`
- `AGENTIC_RAG_MODEL`
- `AGENTIC_RAG_MODEL_MAX_TOKENS`

## 11. 后续演进方向

- 将 Agentic RAG 独立拆分为单独模块文件，降低 `rag_manager.py` 复杂度
- 引入 claim-level groundedness / re-ranking 模型
- 让 MCP Server 对外暴露 `agentic_knowledge_base`
- 将 Skill 开关真正接入配置与前端状态
- 补充 Agentic RAG 端到端回归测试和基准评估集
