import asyncio
import json
import os
import time
import uuid
from typing import Any, Callable, Dict, List, Tuple

from langchain.chat_models import init_chat_model
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.messages import HumanMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from typing_extensions import TypedDict
from zhipuai import ZhipuAI

from src.core.prompts import (
    agentic_rag_document_grader_prompt,
    agentic_rag_hallucination_check_prompt,
    agentic_rag_query_analysis_prompt,
    agentic_rag_query_decomposition_prompt,
    agentic_rag_query_rewrite_prompt,
)
from src.core.state import (
    DocumentGradeResult,
    HallucinationCheckResult,
    QueryAnalysisResult,
    QueryDecompositionResult,
    QueryRewriteResult,
)
from src.evaluation.collector import emit_metric_from_runnable_config


class ZhipuAIEmbeddings(Embeddings):
    def __init__(self, api_key: str, model: str = "embedding-3", dimensions: int = 1024):
        self.client = ZhipuAI(api_key=api_key)
        self.model = model
        self.dimensions = dimensions

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings: List[List[float]] = []
        for text in texts:
            response = self.client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self.dimensions,
            )
            embeddings.append(response.data[0].embedding)
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        response = self.client.embeddings.create(
            model=self.model,
            input=text,
            dimensions=self.dimensions,
        )
        return response.data[0].embedding


class RAGManager:
    def __init__(self, persist_directory: str = "data/chroma_db"):
        self.persist_directory = persist_directory
        self.corpus_path = os.path.join(self.persist_directory, "corpus.jsonl")

        self.api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ZHIPUAI_API_KEY")
        if not self.api_key:
            raise ValueError("API Key not found in environment variables.")

        self.embeddings = ZhipuAIEmbeddings(
            api_key=self.api_key, model="embedding-3", dimensions=1024
        )

        self.vector_store = Chroma(
            persist_directory=self.persist_directory,
            embedding_function=self.embeddings,
            collection_name="deep_research_knowledge",
        )

        # Parent-Child splitters: small chunks for retrieval, big chunks for generation
        self.child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800, chunk_overlap=160
        )
        self.parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=3000, chunk_overlap=300
        )

        # Hybrid retrieval parameters
        self.dense_k = 8
        self.keyword_k = 8
        self.rrf_k = 60  # Reciprocal Rank Fusion parameter
        self.agentic_grader_relevance_ratio = 0.4

        # Build BM25 retriever from persisted corpus if available
        self.bm25: BM25Retriever | None = None
        self._ensure_dirs()
        self._rebuild_bm25_from_corpus()

    def _ensure_dirs(self):
        os.makedirs(self.persist_directory, exist_ok=True)

    def _persist_corpus_append(self, docs: List[Document]) -> None:
        with open(self.corpus_path, "a", encoding="utf-8") as f:
            for d in docs:
                record = {
                    "page_content": d.page_content,
                    "metadata": d.metadata,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _rebuild_bm25_from_corpus(self) -> None:
        if not os.path.exists(self.corpus_path):
            return
        documents: List[Document] = []
        with open(self.corpus_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    documents.append(
                        Document(page_content=data["page_content"], metadata=data.get("metadata", {}))
                    )
                except Exception:
                    continue
        if documents:
            # Build BM25 retriever from all child chunks
            self.bm25 = BM25Retriever.from_documents(documents)

    async def ingest_file(self, file_path: str) -> int:
        if file_path.endswith(".pdf"):
            loader = PyPDFLoader(file_path)
        elif file_path.endswith(".txt") or file_path.endswith(".md"):
            loader = TextLoader(file_path, encoding="utf-8")
        else:
            raise ValueError("Unsupported file format. Please upload PDF, TXT, or MD.")

        raw_docs = loader.load()
        if not raw_docs:
            return 0

        # Derive a document id for this file
        base = os.path.basename(file_path)
        doc_id = f"{base}:{uuid.uuid4().hex[:8]}"

        # Build parent chunks first (big)
        parent_chunks: List[Document] = self.parent_splitter.split_documents(raw_docs)

        child_docs: List[Document] = []
        for p_idx, parent in enumerate(parent_chunks):
            parent_id = f"{doc_id}:p{p_idx}"
            # Split each parent chunk into smaller child chunks
            children = self.child_splitter.split_text(parent.page_content)
            for c_idx, text in enumerate(children):
                chunk_id = f"{parent_id}:c{c_idx}"
                meta = dict(parent.metadata) if isinstance(parent.metadata, dict) else {}
                meta.update(
                    {
                        "source": meta.get("source") or file_path,
                        "doc_id": doc_id,
                        "parent_id": parent_id,
                        "chunk_id": chunk_id,
                        # Store parent text for generation context
                        "parent_content": parent.page_content,
                    }
                )
                child_docs.append(Document(page_content=text, metadata=meta))

        if not child_docs:
            return 0

        # Add child chunks to vector store
        self.vector_store.add_documents(child_docs)
        # Persist to corpus (for BM25 rebuild)
        self._persist_corpus_append(child_docs)
        # Rebuild BM25 to include new docs
        self._rebuild_bm25_from_corpus()
        return len(child_docs)

    async def ingest_external_documents(self, documents: List[Dict[str, Any] | str]) -> int:
        child_docs: List[Document] = []
        if not documents:
            return 0

        doc_id = f"external:{uuid.uuid4().hex[:8]}"
        for idx, item in enumerate(documents):
            if isinstance(item, str):
                text = item
                source = "external_dynamic"
                metadata: Dict[str, Any] = {}
            else:
                text = str(item.get("content", ""))
                source = str(item.get("source", "external_dynamic"))
                metadata = dict(item.get("metadata", {}))
            if not text.strip():
                continue
            parent_id = f"{doc_id}:p{idx}"
            children = self.child_splitter.split_text(text)
            if not children:
                children = [text]
            for c_idx, chunk_text in enumerate(children):
                chunk_id = f"{parent_id}:c{c_idx}"
                meta = dict(metadata)
                meta.update(
                    {
                        "source": source,
                        "doc_id": doc_id,
                        "parent_id": parent_id,
                        "chunk_id": chunk_id,
                        "parent_content": text,
                    }
                )
                child_docs.append(Document(page_content=chunk_text, metadata=meta))

        if not child_docs:
            return 0
        self.vector_store.add_documents(child_docs)
        self._persist_corpus_append(child_docs)
        self._rebuild_bm25_from_corpus()
        return len(child_docs)

    def _rrf_fuse(self, dense: List[Document], keywords: List[Document]) -> List[Document]:
        # Map chunk_id -> document and accumulate RRF scores
        def chunk_key(d: Document) -> str:
            return d.metadata.get("chunk_id") or f"hash:{hash(d.page_content)}"

        scores: Dict[str, float] = {}
        doc_map: Dict[str, Document] = {}

        for rank, d in enumerate(dense, start=1):
            key = chunk_key(d)
            scores[key] = scores.get(key, 0.0) + 1.0 / (self.rrf_k + rank)
            doc_map[key] = d
        for rank, d in enumerate(keywords, start=1):
            key = chunk_key(d)
            scores[key] = scores.get(key, 0.0) + 1.0 / (self.rrf_k + rank)
            doc_map[key] = d

        fused_keys = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
        return [doc_map[k] for k in fused_keys]

    def _rrf_fuse_with_scores(
        self, dense: List[Document], keywords: List[Document]
    ) -> List[Tuple[Document, float]]:
        def chunk_key(d: Document) -> str:
            return d.metadata.get("chunk_id") or f"hash:{hash(d.page_content)}"

        scores: Dict[str, float] = {}
        doc_map: Dict[str, Document] = {}

        for rank, d in enumerate(dense, start=1):
            key = chunk_key(d)
            scores[key] = scores.get(key, 0.0) + 1.0 / (self.rrf_k + rank)
            doc_map[key] = d
        for rank, d in enumerate(keywords, start=1):
            key = chunk_key(d)
            scores[key] = scores.get(key, 0.0) + 1.0 / (self.rrf_k + rank)
            doc_map[key] = d

        fused_keys = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
        return [(doc_map[k], scores[k]) for k in fused_keys]

    def retrieve(self, query: str, k: int = 5) -> List[Document]:
        # Dense retrieval over child chunks
        dense_children = self.vector_store.similarity_search(query, k=self.dense_k)
        # Keyword retrieval (BM25) over child chunks
        keyword_children: List[Document] = []
        if self.bm25 is not None:
            try:
                keyword_children = self.bm25.get_relevant_documents(query)[: self.keyword_k]
            except Exception:
                keyword_children = []

        # RRF fusion of child-level results
        fused_children = self._rrf_fuse(dense_children, keyword_children) if keyword_children else dense_children

        # Elevate to parent-level documents for generation
        parents: Dict[str, Tuple[float, Document]] = {}
        for rank, child in enumerate(fused_children, start=1):
            parent_id = child.metadata.get("parent_id")
            parent_content = child.metadata.get("parent_content")
            if not parent_id or not parent_content:
                # Fallback: treat child as parent
                parent_id = child.metadata.get("chunk_id", f"p:{rank}")
                parent_content = child.page_content
            score = 1.0 / (self.rrf_k + rank)
            if parent_id not in parents or parents[parent_id][0] < score:
                # Compose a parent-level Document
                meta = dict(child.metadata)
                # Remove heavy child-only fields if any
                meta.pop("chunk_id", None)
                parent_doc = Document(page_content=parent_content, metadata=meta)
                parents[parent_id] = (score, parent_doc)

        # Sort parents by score and return top-k
        ordered = sorted(parents.values(), key=lambda t: t[0], reverse=True)
        return [doc for _, doc in ordered[:k]]

    def retrieve_with_scores(self, query: str, k: int = 5) -> List[Tuple[float, Document]]:
        dense_children = self.vector_store.similarity_search(query, k=self.dense_k)
        keyword_children: List[Document] = []
        if self.bm25 is not None:
            try:
                keyword_children = self.bm25.get_relevant_documents(query)[: self.keyword_k]
            except Exception:
                keyword_children = []

        fused_children = (
            self._rrf_fuse_with_scores(dense_children, keyword_children)
            if keyword_children
            else [(doc, 1.0 / (self.rrf_k + rank)) for rank, doc in enumerate(dense_children, start=1)]
        )

        parents: Dict[str, Tuple[float, Document]] = {}
        for child, score in fused_children:
            parent_id = child.metadata.get("parent_id")
            parent_content = child.metadata.get("parent_content")
            if not parent_id or not parent_content:
                parent_id = child.metadata.get("chunk_id", f"p:{hash(child.page_content)}")
                parent_content = child.page_content
            if parent_id not in parents or parents[parent_id][0] < score:
                meta = dict(child.metadata)
                meta.pop("chunk_id", None)
                parents[parent_id] = (score, Document(page_content=parent_content, metadata=meta))

        ordered = sorted(parents.values(), key=lambda t: t[0], reverse=True)
        return ordered[:k]

    def _build_agentic_model(self):
        model_name = os.getenv("AGENTIC_RAG_MODEL") or "openai:glm-4"
        max_tokens = int(os.getenv("AGENTIC_RAG_MODEL_MAX_TOKENS", "1024"))
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ZHIPUAI_API_KEY")
        return init_chat_model(
            model=model_name,
            max_tokens=max_tokens,
            api_key=api_key,
            tags=["langsmith:nostream"],
        )

    async def _analyze_query(self, query: str) -> QueryAnalysisResult:
        try:
            model = self._build_agentic_model().with_structured_output(QueryAnalysisResult)
            prompt = agentic_rag_query_analysis_prompt.format(query=query, date=self._today())
            return await model.ainvoke([HumanMessage(content=prompt)])
        except Exception:
            lower = query.lower()
            local_signals = ["上传", "文档", "文件", "knowledge", "知识库", "报告", "pdf", "txt", "md"]
            complex_signals = ["比较", "对比", "以及", "并且", "and", "vs", "历史", "演进", "影响"]
            route = "local_kb" if any(s in lower for s in local_signals) else "local_kb"
            needs_decomposition = any(s in lower for s in complex_signals) or len(query) > 50
            return QueryAnalysisResult(
                route=route,
                needs_rewrite=len(query.strip()) < 12,
                needs_decomposition=needs_decomposition,
                rationale="Fallback heuristic analysis.",
            )

    async def _rewrite_query(self, query: str) -> str:
        try:
            model = self._build_agentic_model().with_structured_output(QueryRewriteResult)
            prompt = agentic_rag_query_rewrite_prompt.format(query=query)
            result = await model.ainvoke([HumanMessage(content=prompt)])
            return result.rewritten_query.strip() or query
        except Exception:
            return query.strip()

    async def _decompose_query(self, query: str) -> List[str]:
        try:
            model = self._build_agentic_model().with_structured_output(QueryDecompositionResult)
            prompt = agentic_rag_query_decomposition_prompt.format(query=query)
            result = await model.ainvoke([HumanMessage(content=prompt)])
            sub_queries = [q.strip() for q in result.sub_queries if q.strip()]
            return sub_queries[:3] if sub_queries else [query]
        except Exception:
            return [query]

    async def _grade_document(self, query: str, document: str) -> DocumentGradeResult:
        try:
            model = self._build_agentic_model().with_structured_output(DocumentGradeResult)
            prompt = agentic_rag_document_grader_prompt.format(query=query, document=document[:8000])
            return await model.ainvoke([HumanMessage(content=prompt)])
        except Exception:
            tokens = set(query.lower().split())
            overlap = sum(1 for token in tokens if token in document.lower())
            return DocumentGradeResult(relevant=overlap > 0, reason="Fallback lexical overlap.")

    async def _check_hallucination(self, draft: str, evidence: str) -> HallucinationCheckResult:
        try:
            model = self._build_agentic_model().with_structured_output(HallucinationCheckResult)
            prompt = agentic_rag_hallucination_check_prompt.format(
                draft=draft[:12000],
                evidence=evidence[:12000],
            )
            return await model.ainvoke([HumanMessage(content=prompt)])
        except Exception:
            grounded = bool(draft.strip()) and bool(evidence.strip())
            return HallucinationCheckResult(
                grounded=grounded,
                reason="Fallback basic non-empty check.",
            )

    def _today(self) -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")

    def _serialize_doc(self, doc: Document, score: float = 0.0) -> dict[str, Any]:
        return {
            "content": doc.page_content,
            "metadata": dict(doc.metadata),
            "score": score,
        }

    def _build_draft_answer(self, query: str, docs: list[dict[str, Any]]) -> str:
        if not docs:
            return "未在本地知识库中找到足够证据。"
        lines: list[str] = [f"问题：{query}", "", "证据摘要："]
        for idx, item in enumerate(docs, start=1):
            source = os.path.basename(item.get("metadata", {}).get("source", "Unknown"))
            snippet = item.get("content", "").replace("\n", " ").strip()
            lines.append(f"{idx}. [来源: {source}] {snippet[:1200]}")
        lines.append("")
        lines.append("结论：以上内容来自本地知识库证据，建议结合完整来源进一步核验。")
        return "\n".join(lines)

    async def run_agentic_rag(
        self,
        query: str,
        k: int = 5,
        max_retries: int = 2,
        web_fallback: Callable[[str], Any] | None = None,
        external_documents: List[Dict[str, Any] | str] | None = None,
        eval_context: Dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        started_at = time.perf_counter()
        eval_config = (eval_context or {}).get("config")
        eval_component = (eval_context or {}).get("component", "rag_agentic")

        if external_documents:
            try:
                await self.ingest_external_documents(external_documents)
            except Exception:
                pass

        class RuntimeState(TypedDict):
            query: str
            rewritten_query: str
            sub_queries: list[str]
            retrieval_queries: list[str]
            retrieved_docs: list[dict[str, Any]]
            graded_docs: list[dict[str, Any]]
            retry_count: int
            max_retries: int
            knowledge_gap: bool
            draft_answer: str
            final_answer: str
            route: str
            trace: list[str]

        async def query_analysis_node(state: RuntimeState) -> Command:
            node_start = time.perf_counter()
            analyzed = await self._analyze_query(state["query"])
            emit_metric_from_runnable_config(
                config=eval_config,
                event_type="agentic_rag_node",
                component=eval_component,
                payload={
                    "node": "query_analysis",
                    "route": analyzed.route,
                    "needs_rewrite": analyzed.needs_rewrite,
                    "needs_decomposition": analyzed.needs_decomposition,
                    "latency_ms": (time.perf_counter() - node_start) * 1000.0,
                },
            )
            rewritten = state["query"]
            trace = state["trace"] + [f"QueryAnalysis(route={analyzed.route})"]
            if analyzed.route == "web_search":
                return Command(
                    goto="web_search_fallback",
                    update={"route": analyzed.route, "trace": trace},
                )
            if analyzed.needs_rewrite:
                return Command(
                    goto="rewrite_query",
                    update={"route": analyzed.route, "trace": trace},
                )
            if analyzed.needs_decomposition:
                return Command(
                    goto="decompose_query",
                    update={"route": analyzed.route, "rewritten_query": rewritten, "trace": trace},
                )
            return Command(
                goto="hybrid_retrieve",
                update={
                    "route": analyzed.route,
                    "rewritten_query": rewritten,
                    "retrieval_queries": [rewritten],
                    "trace": trace,
                },
            )

        async def rewrite_query_node(state: RuntimeState) -> Command:
            node_start = time.perf_counter()
            base_query = state["rewritten_query"] or state["query"]
            rewritten = await self._rewrite_query(base_query)
            emit_metric_from_runnable_config(
                config=eval_config,
                event_type="agentic_rag_node",
                component=eval_component,
                payload={
                    "node": "rewrite_query",
                    "rewritten_length": len(rewritten),
                    "latency_ms": (time.perf_counter() - node_start) * 1000.0,
                },
            )
            trace = state["trace"] + ["RewriteQuery"]
            return Command(
                goto="decompose_query",
                update={"rewritten_query": rewritten, "trace": trace},
            )

        async def decompose_query_node(state: RuntimeState) -> Command:
            node_start = time.perf_counter()
            base_query = state["rewritten_query"] or state["query"]
            sub_queries = await self._decompose_query(base_query)
            retrieval_queries = sub_queries if sub_queries else [base_query]
            emit_metric_from_runnable_config(
                config=eval_config,
                event_type="agentic_rag_node",
                component=eval_component,
                payload={
                    "node": "decompose_query",
                    "sub_query_count": len(retrieval_queries),
                    "latency_ms": (time.perf_counter() - node_start) * 1000.0,
                },
            )
            trace = state["trace"] + [f"DecomposeQuery(n={len(retrieval_queries)})"]
            return Command(
                goto="hybrid_retrieve",
                update={
                    "sub_queries": sub_queries,
                    "retrieval_queries": retrieval_queries,
                    "trace": trace,
                },
            )

        async def hybrid_retrieve_node(state: RuntimeState) -> Command:
            node_start = time.perf_counter()
            queries = state["retrieval_queries"] or [state["rewritten_query"] or state["query"]]
            merged: Dict[str, dict[str, Any]] = {}
            for q in queries:
                results = self.retrieve_with_scores(q, k=k)
                for score, doc in results:
                    parent_id = doc.metadata.get("parent_id") or doc.metadata.get("chunk_id") or f"p:{hash(doc.page_content)}"
                    current = merged.get(parent_id)
                    serialized = self._serialize_doc(doc, score=score)
                    if current is None or current["score"] < score:
                        merged[parent_id] = serialized
            retrieved_docs = sorted(merged.values(), key=lambda d: d["score"], reverse=True)[:k]
            emit_metric_from_runnable_config(
                config=eval_config,
                event_type="agentic_rag_node",
                component=eval_component,
                payload={
                    "node": "hybrid_retrieve",
                    "query_count": len(queries),
                    "retrieved_docs": len(retrieved_docs),
                    "latency_ms": (time.perf_counter() - node_start) * 1000.0,
                },
            )
            trace = state["trace"] + [f"HybridRetrieve(n={len(retrieved_docs)})"]
            return Command(goto="document_grader", update={"retrieved_docs": retrieved_docs, "trace": trace})

        async def document_grader_node(state: RuntimeState) -> Command:
            node_start = time.perf_counter()
            retrieved_docs = state["retrieved_docs"]
            if not retrieved_docs:
                if state["retry_count"] < state["max_retries"]:
                    return Command(
                        goto="rewrite_query",
                        update={
                            "retry_count": state["retry_count"] + 1,
                            "trace": state["trace"] + ["DocumentGrader(empty->retry)"],
                        },
                    )
                return Command(
                    goto="web_search_fallback",
                    update={"knowledge_gap": True, "trace": state["trace"] + ["DocumentGrader(empty->fallback)"]},
                )

            graded_docs: list[dict[str, Any]] = []
            for doc in retrieved_docs:
                grade = await self._grade_document(state["rewritten_query"] or state["query"], doc["content"])
                if grade.relevant:
                    doc_copy = dict(doc)
                    doc_copy["grade_reason"] = grade.reason
                    graded_docs.append(doc_copy)

            relevance_ratio = len(graded_docs) / max(len(retrieved_docs), 1)
            emit_metric_from_runnable_config(
                config=eval_config,
                event_type="agentic_rag_node",
                component=eval_component,
                payload={
                    "node": "document_grader",
                    "retrieved_count": len(retrieved_docs),
                    "graded_relevant_count": len(graded_docs),
                    "grader_pass_rate": relevance_ratio,
                    "retry_count": state["retry_count"],
                    "latency_ms": (time.perf_counter() - node_start) * 1000.0,
                },
            )
            if relevance_ratio < self.agentic_grader_relevance_ratio:
                if state["retry_count"] < state["max_retries"]:
                    return Command(
                        goto="rewrite_query",
                        update={
                            "retry_count": state["retry_count"] + 1,
                            "trace": state["trace"] + [f"DocumentGrader(low={relevance_ratio:.2f}->retry)"],
                        },
                    )
                return Command(
                    goto="web_search_fallback",
                    update={
                        "knowledge_gap": True,
                        "graded_docs": graded_docs,
                        "trace": state["trace"] + [f"DocumentGrader(low={relevance_ratio:.2f}->fallback)"],
                    },
                )

            return Command(
                goto="generate_draft",
                update={
                    "graded_docs": graded_docs,
                    "trace": state["trace"] + [f"DocumentGrader(pass={relevance_ratio:.2f})"],
                },
            )

        async def generate_draft_node(state: RuntimeState) -> Command:
            node_start = time.perf_counter()
            draft = self._build_draft_answer(state["query"], state["graded_docs"])
            emit_metric_from_runnable_config(
                config=eval_config,
                event_type="agentic_rag_node",
                component=eval_component,
                payload={
                    "node": "generate_draft",
                    "draft_length": len(draft),
                    "latency_ms": (time.perf_counter() - node_start) * 1000.0,
                },
            )
            return Command(
                goto="hallucination_check",
                update={
                    "draft_answer": draft,
                    "trace": state["trace"] + ["GenerateDraft"],
                },
            )

        async def hallucination_check_node(state: RuntimeState) -> Command:
            node_start = time.perf_counter()
            evidence = "\n\n".join(doc["content"] for doc in state["graded_docs"])
            checked = await self._check_hallucination(state["draft_answer"], evidence)
            emit_metric_from_runnable_config(
                config=eval_config,
                event_type="agentic_rag_node",
                component=eval_component,
                payload={
                    "node": "hallucination_check",
                    "grounded": checked.grounded,
                    "retry_count": state["retry_count"],
                    "latency_ms": (time.perf_counter() - node_start) * 1000.0,
                },
            )
            if checked.grounded:
                return Command(
                    goto=END,
                    update={
                        "final_answer": state["draft_answer"],
                        "trace": state["trace"] + ["HallucinationCheck(pass)"],
                    },
                )
            if state["retry_count"] < state["max_retries"]:
                return Command(
                    goto="rewrite_query",
                    update={
                        "retry_count": state["retry_count"] + 1,
                        "trace": state["trace"] + ["HallucinationCheck(fail->retry)"],
                    },
                )
            return Command(
                goto="web_search_fallback",
                update={
                    "knowledge_gap": True,
                    "trace": state["trace"] + ["HallucinationCheck(fail->fallback)"],
                },
            )

        async def web_search_fallback_node(state: RuntimeState) -> Command:
            node_start = time.perf_counter()
            fallback_text = "知识库证据不足，建议启用公网搜索或 MCP 数据源补充。"
            if web_fallback is not None:
                try:
                    result = web_fallback(state["query"])
                    if asyncio.iscoroutine(result):
                        result = await result
                    if isinstance(result, str) and result.strip():
                        fallback_text = result
                except Exception:
                    fallback_text = "知识库证据不足，外部回退检索失败。"
            final_answer = f"{fallback_text}\n\n{state['draft_answer']}".strip()
            emit_metric_from_runnable_config(
                config=eval_config,
                event_type="agentic_rag_node",
                component=eval_component,
                payload={
                    "node": "web_search_fallback",
                    "knowledge_gap": state.get("knowledge_gap", False),
                    "latency_ms": (time.perf_counter() - node_start) * 1000.0,
                },
            )
            return Command(
                goto=END,
                update={
                    "final_answer": final_answer,
                    "trace": state["trace"] + ["WebSearchFallback"],
                },
            )

        builder = StateGraph(RuntimeState)
        builder.add_node("query_analysis", query_analysis_node)
        builder.add_node("rewrite_query", rewrite_query_node)
        builder.add_node("decompose_query", decompose_query_node)
        builder.add_node("hybrid_retrieve", hybrid_retrieve_node)
        builder.add_node("document_grader", document_grader_node)
        builder.add_node("generate_draft", generate_draft_node)
        builder.add_node("hallucination_check", hallucination_check_node)
        builder.add_node("web_search_fallback", web_search_fallback_node)
        builder.add_edge(START, "query_analysis")
        graph = builder.compile()

        result = await graph.ainvoke(
            {
                "query": query,
                "rewritten_query": "",
                "sub_queries": [],
                "retrieval_queries": [],
                "retrieved_docs": [],
                "graded_docs": [],
                "retry_count": 0,
                "max_retries": max_retries,
                "knowledge_gap": False,
                "draft_answer": "",
                "final_answer": "",
                "route": "local_kb",
                "trace": [],
            }
        )
        total_latency_ms = (time.perf_counter() - started_at) * 1000.0
        retry_count = int(result.get("retry_count", 0))
        knowledge_gap = bool(result.get("knowledge_gap", False))
        graded_docs = result.get("graded_docs", []) or []
        retrieved_docs = result.get("retrieved_docs", []) or []
        grader_pass_rate = len(graded_docs) / max(len(retrieved_docs), 1) if retrieved_docs else 0.0
        fallback_rate = 1.0 if any("WebSearchFallback" in t for t in (result.get("trace") or [])) else 0.0
        grounded_pass_rate = 1.0 if any("HallucinationCheck(pass)" in t for t in (result.get("trace") or [])) else 0.0
        result["evaluation"] = {
            "retry_count": retry_count,
            "knowledge_gap": knowledge_gap,
            "grader_pass_rate": grader_pass_rate,
            "fallback_rate": fallback_rate,
            "grounded_pass_rate": grounded_pass_rate,
            "total_latency_ms": total_latency_ms,
        }
        emit_metric_from_runnable_config(
            config=eval_config,
            event_type="agentic_rag_summary",
            component=eval_component,
            payload=result["evaluation"],
        )
        return result


# Global instance
_rag_manager = None


def get_rag_manager():
    global _rag_manager
    if _rag_manager is None:
        os.makedirs("data/chroma_db", exist_ok=True)
        _rag_manager = RAGManager()
    return _rag_manager
