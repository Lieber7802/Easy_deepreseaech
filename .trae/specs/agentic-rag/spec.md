# Agentic RAG 优化 Spec

## Why
当前的 `RAGManager` 仍是典型的 Pipeline 模式：输入问题后直接执行 Hybrid Retrieve，再将结果交给大模型。这种模式在深度研究场景中缺乏“评估、反思、纠错、追问”的闭环能力，面对模糊查询、复杂问题或知识缺口时，容易出现低质量召回、错误归因和基于无关内容的幻觉生成。

本次优化目标是将现有 RAG 能力升级为 **Agentic RAG**：把本地知识库检索从单次函数调用，升级为可迭代决策的 **LangGraph RAG 子图**。这样，当 Researcher 需要查阅本地文档时，系统会像“知识库专家”一样，先理解和拆解问题，再检索、评分、反思、重试，并在本地知识不足时主动触发外部补充，而不是被动地一次检索后硬生成答案。

## What Changes
- **将现有 `search_knowledge_base` 升级为 Agentic RAG 子图入口**：Researcher 不再只调用一次检索函数，而是唤起可循环的 RAG Sub-graph。
- **新增预检索阶段 (Pre-Retrieval)**：加入 Query Analysis、Query Rewriting、Query Decomposition，对模糊或复杂查询先做理解、重写和拆解。
- **保留并增强现有 Hybrid Retrieval**：继续使用 Dense + BM25 + RRF 的召回主干，但在其前后增加智能控制节点。
- **新增检索中质量控制 (Active Retrieval)**：加入 Document Grader，对召回的 Parent Chunks 做 Relevant / Irrelevant 评估，并驱动自我纠错。
- **新增反思与回退机制 (Reflect / Retry / Fallback)**：本地检索多轮失败后，发出 Knowledge Gap 信号，自动切换到 Web Search，后续可扩展到 MCP 动态知识注入。
- **新增后检索阶段 (Post-Retrieval)**：在生成草稿后加入 Hallucination Checker，对内容是否被检索证据完整支撑进行 Groundedness 检查。
- **支持多跳追问 (Multi-hop Reasoning)**：允许系统根据第一轮证据识别缺失概念，主动发起第二轮针对性检索。
- **提供平滑演进路径**：优先落地低成本高收益的 Document Grader，再逐步封装完整子图，并最终接入 MCP 动态索引扩展。

## Impact
- Affected specs: 本地知识库问答能力、深度研究检索链路、Researcher 调用本地知识的方式、知识缺口补偿策略。
- Affected code:
  - `backend/src/core/rag_manager.py`
  - `backend/src/core/deep_researcher.py`
  - `backend/src/core/state.py`
  - `backend/src/core/utils.py`
  - `backend/src/core/skills/builtin.py`
  - `backend/src/core/skills/base.py`
  - `backend/src/core/prompts.py`
  - 视接入方式可能影响 `backend/main.py` 或相关 API 暴露层

## ADDED Requirements
### Requirement: Agentic RAG 子图入口
系统 SHALL 将现有本地知识库检索能力封装为可被 Researcher 调用的 LangGraph 子图，而非单次静态函数流水线。

#### Scenario: Researcher 需要查阅本地文档
- **WHEN** Researcher 判定问题与上传文档或本地知识库相关
- **THEN** 系统调用 Agentic RAG 子图入口而不是直接执行一次 `search_knowledge_base`
- **AND** 子图负责完成查询分析、检索、评分、重试与结果返回

### Requirement: 查询理解、重写与拆解
系统 SHALL 在正式检索前具备 Query Analysis、Query Rewriting 与 Query Decomposition 能力，以提高复杂问题的召回质量。

#### Scenario: 查询表达模糊
- **WHEN** 用户或 Researcher 提供的 query 缺乏上下文、关键词不完整或表达模糊
- **THEN** 系统先重写 query，使其更适合 Dense Retrieval 与 BM25 检索

#### Scenario: 查询为复杂多意图问题
- **WHEN** 问题包含多个子目标、多个时间维度或多个证据来源
- **THEN** 系统将其拆解为 2-3 个子查询并发检索
- **AND** 系统在召回阶段合并各子查询结果池

### Requirement: 文档评分驱动的自我纠错
系统 SHALL 在 Hybrid Retrieval 之后对召回文档进行相关性评分，并依据评分结果决定继续生成、重写检索或触发回退。

#### Scenario: 大部分文档相关
- **WHEN** RRF 融合后的大部分文档被判定为 Relevant
- **THEN** 系统进入生成草稿节点

#### Scenario: 大部分文档不相关
- **WHEN** Document Grader 判断召回文档大部分为 Irrelevant
- **THEN** 系统触发反思逻辑并重写查询
- **AND** 系统重新发起本地检索，而不是直接生成答案

### Requirement: 知识缺口感知与外部回退
系统 SHALL 在本地知识库多次检索失败时识别 Knowledge Gap，并主动切换到外部知识源，而不是基于无关本地文档生成内容。

#### Scenario: 本地知识库持续无答案
- **WHEN** 系统经过多轮查询重写与本地检索后，仍无法获得高相关性文档
- **THEN** 系统发出 Knowledge Gap 信号
- **AND** 系统自动触发 Web Search fallback 获取补充信息

#### Scenario: 后续扩展外部知识注入
- **WHEN** Web Search 仍无法满足对结构化或私有外部知识的需求
- **THEN** 系统可扩展接入 MCP 数据源，实现动态拉取外部数据并构建临时索引

### Requirement: 多跳追问
系统 SHALL 支持依据第一轮证据自动识别缺失概念，并发起第二轮特定条件检索。

#### Scenario: 第一轮证据不完整但方向正确
- **WHEN** 第一轮检索已得到部分关键证据，但回答仍依赖额外概念或补充事实
- **THEN** 系统根据阶段性摘要识别待补证概念
- **AND** 系统主动发起第二轮定向检索

### Requirement: 生成后幻觉检测
系统 SHALL 在生成草稿后执行 Groundedness 检查，确保输出内容能被检索得到的 Parent Chunks 支撑。

#### Scenario: 生成内容存在未被证据支撑的断言
- **WHEN** Hallucination Checker 检测到草稿中的结论无法在召回的 Parent Chunks 中找到依据
- **THEN** 系统打回生成阶段
- **AND** 系统要求补检索、重写或重新生成，而不是直接输出

## MODIFIED Requirements
### Requirement: 本地知识检索能力
系统当前的本地知识检索能力由单次 Hybrid Retrieval 升级为可循环、可评分、可回退的 Agentic RAG 流程。原有的 Dense + BM25 + RRF 主链路仍保留，但其角色从“最终答案输入”调整为“Agentic 决策过程中的检索执行节点”。

## REMOVED Requirements
### Requirement: 单次静态知识库检索即返回结果
**Reason**: 单次静态检索无法满足深度研究场景中的质量控制、自主追问和知识缺口处理需求。
**Migration**: 将原有 `search_knowledge_base` 能力保留为底层检索原语，并由 Agentic RAG 子图统一编排调用。
