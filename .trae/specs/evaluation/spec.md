# Evaluation System Spec

## Why
当前项目已经具备经典 Hybrid RAG、Agentic RAG、多智能体研究图、SSE 事件流和 Skill/MCP 扩展能力，但缺少统一的量化评估系统。因此团队无法回答“Agentic RAG 是否真的优于经典 Hybrid RAG、具体提升了多少、在哪些问题上更优”这类关键问题。

本次变更的目标是建立一套可复现、可对比、可持续演进的评估体系，同时覆盖 **Agentic RAG** 与 **多智能体 Deep Research 主流程**。系统需要同时支持在线埋点、离线基准回放和结果汇总，以便对不同 RAG 模式、不同模型、不同 Prompt 和不同工具组合进行横向比较。

## What Changes
- 新增统一评估系统模块，负责采集、持久化和聚合 Agent、RAG、SSE 运行指标。
- 在请求入口引入评估上下文字段，如 `run_id`、`experiment_id`、`dataset_id`、`sample_id`、`eval_mode`。
- 在 `service.py` 中增加主流程运行级埋点，采集节点事件、任务状态、工具调用和最终结果统计。
- 在 `rag_manager.py` 中增加 RAG 级指标输出，覆盖经典 Hybrid RAG 与 Agentic RAG 子图。
- 新增离线基准评估执行器，支持批量回放样本，对比 classic / agentic / both 模式表现。
- 新增评估报告聚合逻辑，输出结构化指标和可读总结。
- 在前后端事件协议中预留评估事件，如 `metrics` / `eval_summary`，支持可视化展示。
- 为后续 MCP 动态知识注入评估、多跳推理评估和 groundedness 评估扩展预留接口。

## Impact
- Affected specs: 本地知识检索评估能力、Agentic RAG 效果对比能力、多智能体运行质量评估、SSE 事件可观测性。
- Affected code:
  - `backend/models.py`
  - `backend/main.py`
  - `backend/service.py`
  - `backend/src/core/rag_manager.py`
  - `backend/src/core/utils.py`
  - `backend/src/core/configuration.py`
  - `backend/src/core/state.py`
  - `backend/src/core/deep_researcher.py`
  - `backend/src/core/skills/builtin.py`
  - `frontend/src/services/api.ts`
  - `frontend/src/composables/useResearch.ts`
  - `docs/TECHNICAL_DOCUMENTATION.md`
  - `docs/Agentic-RAG-report.md`
- New code:
  - `backend/src/evaluation/collector.py`
  - `backend/src/evaluation/schema.py`
  - `backend/src/evaluation/runner.py`
  - `backend/src/evaluation/report.py`
  - `backend/data/eval_datasets/*.jsonl`

## ADDED Requirements
### Requirement: 统一评估上下文
系统 SHALL 为每一次研究运行与评估回放分配统一的评估上下文，用于在主流程、RAG、SSE 和离线报告之间串联数据。

#### Scenario: 在线研究请求进入系统
- **WHEN** 用户发起一次 `/research/stream` 请求并启用评估模式
- **THEN** 系统生成或接收 `run_id`
- **AND** 透传 `experiment_id`、`dataset_id`、`sample_id`、`eval_mode`
- **AND** 所有后续埋点事件均带有这些字段

### Requirement: 主流程运行指标采集
系统 SHALL 对多智能体主研究流程进行运行级评估，记录任务数、工具调用数、任务完成率、失败率、耗时和最终报告生成情况。

#### Scenario: Deep Research 主流程执行
- **WHEN** Supervisor 拆解任务并驱动多个 Researcher 并发执行
- **THEN** 系统记录任务创建数、完成数、失败数、每任务工具调用数、总耗时和最终报告生成耗时
- **AND** 指标可被后续聚合为实验报告

### Requirement: 经典 Hybrid RAG 指标采集
系统 SHALL 记录经典 Hybrid RAG 的检索级指标，用于与 Agentic RAG 做横向比较。

#### Scenario: 调用 `search_knowledge_base`
- **WHEN** 系统执行经典本地知识检索
- **THEN** 记录 dense 召回数、BM25 召回数、RRF 融合后文档数、parent chunk 数和检索耗时

### Requirement: Agentic RAG 指标采集
系统 SHALL 记录 Agentic RAG 子图的节点级指标，以衡量其“自主纠错”和“质量控制”效果。

#### Scenario: 调用 `agentic_knowledge_base`
- **WHEN** 系统执行 Agentic RAG 子图
- **THEN** 记录 QueryAnalysis 路由结果、rewrite 触发率、decomposition 触发率、grader 通过率、retry 次数、knowledge_gap 触发率、fallback 触发率、hallucination check 结果和总耗时

### Requirement: 结构化评估事件持久化
系统 SHALL 将评估数据以结构化事件形式持久化，以便离线统计和跨实验对比。

#### Scenario: 运行过程中产生指标
- **WHEN** 任意主流程节点、RAG 节点或工具调用产生评估数据
- **THEN** 系统将其写入统一的 collector
- **AND** 首版至少支持 jsonl 持久化
- **AND** 后续可扩展到 sqlite 或其他分析存储

### Requirement: 离线基准集回放
系统 SHALL 提供离线基准集执行入口，用于可复现实验与模式对比。

#### Scenario: 比较 classic 与 agentic 模式
- **WHEN** 研发人员指定一个评估数据集并运行 `evaluation runner`
- **THEN** 系统批量执行样本
- **AND** 分别以 classic / agentic / both 模式回放
- **AND** 输出每组实验的结果与汇总指标

### Requirement: 结果聚合与对比报告
系统 SHALL 能输出用于回答“哪个好、好多少、好在哪”的聚合报告。

#### Scenario: 实验回放完成
- **WHEN** 一个实验批次完成
- **THEN** 系统输出每种模式的成功率、平均耗时、fallback 率、grader 通过率、groundedness 通过率等汇总指标
- **AND** 报告中明确 classic 与 agentic 的差值和优势场景

### Requirement: 前端评估可视化预留
系统 SHALL 为前端提供评估事件或汇总数据接口，以支持实验结果展示。

#### Scenario: 前端订阅研究流
- **WHEN** 后端在运行过程中产出评估指标
- **THEN** SSE 流中可以附带 `metrics` 或 `eval_summary` 事件
- **AND** 前端可以展示首事件延迟、任务完成率、RAG 模式与关键质量指标

## MODIFIED Requirements
### Requirement: RAG 模式切换
现有 `agentic_rag_mode` 不仅用于控制工具暴露范围，还应作为评估维度参与实验统计。系统需要在评估系统中识别 classic / agentic / both 模式，并输出模式对比结果。

### Requirement: Service 事件流
现有 `service.py` 已负责将 LangGraph 事件转换为 SSE 事件。该能力需要扩展为评估事件的统一汇聚入口，确保主流程、RAG 和工具层的指标都能在此被收集与透传。

## REMOVED Requirements
### Requirement: 仅依赖人工主观判断评估 RAG 效果
**Reason**: 主观体验无法支撑模式对比、A/B 实验、回归测试和研发决策。
**Migration**: 使用结构化评估事件、离线数据集回放和聚合报告代替纯人工比较。
