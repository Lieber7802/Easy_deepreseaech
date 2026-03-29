# Tasks
- [x] Task 1: 设计评估数据模型与事件协议
  - [x] SubTask 1.1: 为请求与运行上下文定义 `run_id`、`experiment_id`、`dataset_id`、`sample_id`、`eval_mode` 等字段。
  - [x] SubTask 1.2: 设计统一评估事件结构，覆盖主流程、RAG、工具调用、SSE 和最终结果。
  - [x] SubTask 1.3: 定义实验汇总结构，支持 classic / agentic / both 三种模式的横向对比。

- [x] Task 2: 实现后端评估采集器
  - [x] SubTask 2.1: 新增 `evaluation/collector.py`，支持结构化写入 jsonl。
  - [x] SubTask 2.2: 新增 `evaluation/schema.py`，统一约束事件与汇总格式。
  - [x] SubTask 2.3: 设计可扩展接口，为 sqlite 或远端分析存储预留能力。

- [x] Task 3: 接入主流程运行指标
  - [x] SubTask 3.1: 在 `main.py` 与 `models.py` 中透传评估上下文字段。
  - [x] SubTask 3.2: 在 `service.py` 中采集任务数、完成率、失败率、工具调用数、最终报告耗时等指标。
  - [x] SubTask 3.3: 将关键评估事件同步写入 collector，并按需透传到 SSE。

- [x] Task 4: 接入经典 Hybrid RAG 指标
  - [x] SubTask 4.1: 在 `rag_manager.py` 中记录 dense/BM25/RRF/parent chunk 等检索统计。
  - [x] SubTask 4.2: 让 `search_knowledge_base` 在不破坏现有返回格式的前提下产出结构化评估数据。
  - [x] SubTask 4.3: 将经典 RAG 指标纳入统一 experiment 汇总。

- [x] Task 5: 接入 Agentic RAG 子图指标
  - [x] SubTask 5.1: 为 QueryAnalysis、Rewrite、Decomposition、DocumentGrader、HallucinationCheck 等节点增加指标采集。
  - [x] SubTask 5.2: 记录 retry 次数、knowledge_gap、fallback 率、groundedness 通过率和总耗时。
  - [x] SubTask 5.3: 保证 Agentic RAG 指标能与 classic RAG 在同一实验框架中对比。

- [x] Task 6: 构建离线基准评估执行器
  - [x] SubTask 6.1: 新增 `evaluation/runner.py`，支持批量读取测试集样本。
  - [x] SubTask 6.2: 支持以 classic / agentic / both 模式回放同一批样本。
  - [x] SubTask 6.3: 设计 `backend/data/eval_datasets/*.jsonl` 样本格式，至少覆盖本地库命中、知识缺口、复杂多跳问题三类。

- [x] Task 7: 生成实验汇总报告
  - [x] SubTask 7.1: 新增 `evaluation/report.py`，计算成功率、平均耗时、grader 通过率、fallback 率、groundedness 通过率等。
  - [x] SubTask 7.2: 输出能直接回答“Agentic RAG 比经典 Hybrid RAG 好多少”的聚合结果。
  - [x] SubTask 7.3: 支持为后续文档与前端展示生成结构化摘要。

- [x] Task 8: 前端与文档对齐
  - [x] SubTask 8.1: 在 SSE 协议中预留 `metrics` / `eval_summary` 事件并更新前端消费逻辑。
  - [x] SubTask 8.2: 更新 README、技术文档和 Agentic RAG 报告中的评估系统章节。
  - [x] SubTask 8.3: 明确说明当前评估能力边界与后续扩展方向。

- [x] Task 9: 验证评估系统正确性
  - [x] SubTask 9.1: 验证在线运行时能持续写出结构化评估事件。
  - [x] SubTask 9.2: 验证离线基准回放可稳定完成并输出实验汇总。
  - [x] SubTask 9.3: 验证 classic 与 agentic 模式的对比结果可复现。
  - [x] SubTask 9.4: 验证新埋点不会破坏现有 Deep Research 主链路和 SSE 输出。

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 1 and Task 2
- Task 4 depends on Task 1 and Task 2
- Task 5 depends on Task 1 and Task 2
- Task 6 depends on Task 1, Task 2, Task 3, Task 4, and Task 5
- Task 7 depends on Task 6
- Task 8 depends on Task 3, Task 7
- Task 9 depends on Task 3, Task 4, Task 5, Task 6, Task 7, and Task 8
