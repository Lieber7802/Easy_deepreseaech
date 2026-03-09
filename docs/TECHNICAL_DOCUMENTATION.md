# Deep Research Agent 项目技术文档

## 1. 项目简介

Deep Research Agent 是一个基于 **LangGraph** 和 **LangChain** 的多智能体（Multi-Agent）深度研究系统。它能够根据用户输入的复杂研究主题，自动拆解任务、并发执行网络搜索与本地知识库检索（RAG）、汇总信息并生成专业的深度研究报告。

系统采用了现代化的 **Map-Reduce** 架构，支持大规模并行任务执行，并集成了 **RAG（检索增强生成）** 模块，允许用户上传私有文档作为研究素材。

## 2. 系统架构

### 2.1 核心流程 (Core Flow)

系统由以下几个关键节点组成，通过 LangGraph 的状态图（StateGraph）进行编排：

1.  **Supervisor (Lead Researcher)**:
    *   **角色**: 总指挥/主研究员。
    *   **职责**: 接收用户的主题，规划研究大纲，将其拆解为多个并行的子任务（Sub-tasks）。
    *   **实现**: 使用 Prompt Engineering 强制模型生成结构化的 `ConductResearch` 工具调用列表。

2.  **Researcher (Sub-Agents)**:
    *   **角色**: 执行研究员。
    *   **职责**: 针对分配的具体子问题进行深入调研。
    *   **能力**:
        *   **Web Search**: 调用 Tavily / DuckDuckGo API 搜索互联网实时信息。
        *   **Local RAG**: 调用 `search_knowledge_base` 工具检索用户上传的本地文档。
    *   **并发**: 支持配置并发数量（默认为 3），利用 Python `asyncio` 实现真正的并行执行。

3.  **Reviewer (可选)**:
    *   **角色**: 审核员。
    *   **职责**: 检查 Researcher 提交的草稿，提出修改意见或补充搜索的建议。

4.  **Report Generator**:
    *   **角色**: 报告生成器。
    *   **职责**: 汇总所有子任务的研究成果，合成最终的 Markdown 格式深度报告。

### 2.2 RAG 模块 (Retrieval-Augmented Generation)

为了支持私有知识库，系统内置了一个轻量级的 RAG 引擎：

*   **Embedding**: 使用 **ZhipuAI (智谱)** 的 `embedding-3` 模型 (1024 维)。
*   **Vector Store**: 使用 **ChromaDB** 进行本地向量存储与检索。
*   **Document Processing**:
    *   支持 PDF (`PyPDFLoader`)、TXT、Markdown 格式。
    *   使用 `RecursiveCharacterTextSplitter` 进行文档切分 (Chunk Size: 1000, Overlap: 200)。
*   **Tool Integration**: 封装为 `search_knowledge_base` 工具，Agent 可自主决定何时查阅本地资料。

## 3. 技术栈

### 后端 (Backend)
*   **Language**: Python 3.10+
*   **Framework**: FastAPI (提供 RESTful API 和 SSE 流式输出)
*   **Agent Framework**: LangGraph, LangChain
*   **LLM**: 支持 OpenAI 接口兼容模型 (如 GPT-4, DeepSeek, ZhipuGLM)
*   **Vector DB**: ChromaDB
*   **Search API**: Tavily, DuckDuckGo

### 前端 (Frontend)
*   **Framework**: Vue 3 (Composition API)
*   **Build Tool**: Vite
*   **Styling**: CSS3 (Aurora 极光风格动画)
*   **State Management**: 自定义 Composable (`useResearch`)
*   **Markdown Rendering**: markdown-it

## 4. 关键代码结构

```
easy_deepresearch/
├── backend/
│   ├── main.py                 # FastAPI 入口，定义 API 路由
│   ├── service.py              # 业务逻辑层，处理 Agent 运行流
│   ├── src/
│   │   ├── core/
│   │   │   ├── graph.py        # LangGraph 图定义 (Nodes & Edges)
│   │   │   ├── deep_researcher.py # 核心 Agent 逻辑
│   │   │   ├── rag_manager.py  # RAG 引擎实现 (Ingest & Retrieve)
│   │   │   ├── prompts.py      # Prompt 模板
│   │   │   └── utils.py        # 工具函数定义 (Tools)
│   └── .env                    # 环境变量配置
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ResearchForm.vue # 研究表单 (含文件上传)
│   │   │   └── TaskList.vue    # 任务列表组件
│   │   ├── composables/
│   │   │   └── useResearch.ts  # 前端状态管理逻辑
│   │   └── App.vue             # 主应用入口
```

## 5. 功能特性

1.  **并行研究**: 系统能同时启动多个 Researcher 子代理，大幅缩短信息收集时间。
2.  **混合检索**: 智能结合公网搜索（Tavily）和私有知识库（RAG），确保信息全面且准确。
3.  **实时反馈**: 通过 Server-Sent Events (SSE) 技术，前端实时展示每个子任务的状态（规划中 -> 执行中 -> 完成）和详细日志。
4.  **交互式 UI**: 现代化的极光风格界面，支持任务卡片呼吸动画、日志折叠/展开、Markdown 报告渲染。
5.  **灵活配置**: 支持自定义并发数、搜索源配置。

## 6. 部署与运行

### 后端
```bash
cd backend
pip install -r requirements.txt
# 配置 .env 文件 (OPENAI_API_KEY, TAVILY_API_KEY 等)
python main.py
```

### 前端
```bash
cd frontend
npm install
npm run dev
```

## 7. 未来规划
*   支持更多文档格式 (Word, Excel)。
*   引入 Re-ranking (重排序) 模型提升 RAG 精度。
*   支持导出报告为 PDF/Word 格式。
*   增加“人机协同”节点，允许用户在研究中途干预方向。
