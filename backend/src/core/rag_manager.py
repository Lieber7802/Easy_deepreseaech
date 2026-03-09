import os
import json
import uuid
from typing import List, Dict, Tuple
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever
from zhipuai import ZhipuAI
from langchain_core.embeddings import Embeddings


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


# Global instance
_rag_manager = None


def get_rag_manager():
    global _rag_manager
    if _rag_manager is None:
        os.makedirs("data/chroma_db", exist_ok=True)
        _rag_manager = RAGManager()
    return _rag_manager
