"""RAG pipeline — chunk, embed, index, retrieve, generate.

GROQ primário (cheap, free tier 6K TPM / 100K TPD rolling),
Gemini premium (fallback, free tier 20 req/dia) com auto-fallback em 429.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer


class LocalEmbeddingFunction(EmbeddingFunction):
    """Embedding function using sentence-transformers (local, no API calls)."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model = SentenceTransformer(model_name)

    def __call__(self, input: Documents) -> Embeddings:
        return self._model.encode(list(input), show_progress_bar=False).tolist()


def _make_groq_client() -> OpenAI | None:
    """Cliente GROQ (primário cheap, free tier)."""
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        return None
    return OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")


def _make_gemini_client() -> OpenAI | None:
    """Cliente Gemini (premium fallback, free tier 20 req/dia)."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    return OpenAI(
        api_key=key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )


class RAGPipeline:
    """Pipeline RAG end-to-end com Chroma local.

    Usa GROQ como LLM primário (cheap) e Gemini como premium/fallback.
    Auto-fallback para GROQ se Gemini atingir rate limit 429.
    """

    def __init__(
        self,
        corpus_dir: str = "data/corpus",
        persist_dir: str = "data/chroma",
        collection_name: str = "docs",
        embed_model: str | None = None,
    ) -> None:
        self._groq = _make_groq_client()
        self._gemini = _make_gemini_client()
        self._default_client = self._groq or self._gemini
        if not self._default_client:
            raise RuntimeError("Configure GROQ_API_KEY ou GEMINI_API_KEY no .env")

        self.cheap_model = os.environ.get("CHEAP_MODEL", "qwen/qwen3-32b")
        self.premium_model = os.environ.get("PREMIUM_MODEL", "gemini-2.5-pro")
        self.embed_model = embed_model or "all-MiniLM-L6-v2"

        self.embed_fn = LocalEmbeddingFunction(model_name=self.embed_model)

        self.corpus_dir = Path(corpus_dir)
        self.persist_dir = persist_dir
        self.collection_name = collection_name

        chroma = chromadb.PersistentClient(path=persist_dir)
        self.collection = chroma.get_or_create_collection(
            name=collection_name, embedding_function=self.embed_fn
        )

    # ------------------------------------------------------------------ TODO 1
    def ingest_and_index(self) -> int:
        """Le PDFs de corpus_dir, faz chunking e indexa em Chroma.

        Retorna numero de chunks indexados.
        """
        pdfs = list(self.corpus_dir.glob("*.pdf"))
        if not pdfs:
            raise FileNotFoundError(
                f"Nenhum PDF encontrado em {self.corpus_dir}. "
                "Coloque seus documentos em data/corpus/"
            )

        docs: list[dict] = []
        for pdf_path in pdfs:
            reader = PdfReader(str(pdf_path))
            for i, page in enumerate(reader.pages, start=1):
                text = page.extract_text()
                if text and text.strip():
                    docs.append({
                        "text": text.strip(),
                        "source": pdf_path.name,
                        "page": i,
                    })

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=100,
            separators=["\n\n", "\n", ".", " ", ""],
        )
        chunks: list[dict] = []
        for doc in docs:
            texts = splitter.split_text(doc["text"])
            for j, chunk_text in enumerate(texts):
                chunk_id = f"{doc['source']}_p{doc['page']}_c{j}"
                chunks.append({
                    "id": chunk_id,
                    "text": chunk_text,
                    "source": doc["source"],
                    "page": doc["page"],
                })

        if chunks:
            print(f"  Indexing {len(chunks)} chunks with local embeddings...")
            self.collection.add(
                ids=[c["id"] for c in chunks],
                documents=[c["text"] for c in chunks],
                metadatas=[{"source": c["source"], "page": c["page"]} for c in chunks],
            )

        return self.collection.count()

    # ------------------------------------------------------------------ TODO 2
    def retrieve(self, query: str, k: int = 5) -> list[dict]:
        """Busca top-k chunks similares a query."""
        results = self.collection.query(
            query_texts=[query],
            n_results=k,
        )

        hits: list[dict] = []
        if not results["ids"] or not results["ids"][0]:
            return hits

        for i, doc_id in enumerate(results["ids"][0]):
            hits.append({
                "text": results["documents"][0][i],
                "source": results["metadatas"][0][i]["source"],
                "page": results["metadatas"][0][i]["page"],
                "distance": results["distances"][0][i] if results.get("distances") else 0.0,
            })

        return hits

    # ------------------------------------------------------------------ TODO 3
    def answer(self, question: str, k: int = 5, model: str | None = None) -> dict:
        """Pipeline completo: retrieve + augment + generate.

        Args:
            model: Nome do modelo. None usa cheap_model (GROQ).
                   premium_model usa Gemini com fallback GROQ em rate limit 429.
        """
        hits = self.retrieve(question, k=k)

        context_parts = []
        for h in hits:
            context_parts.append(
                f"[{h['source']}:p{h['page']}]\n{h['text']}"
            )
        context = "\n\n".join(context_parts)

        prompt = PROMPT_TEMPLATE.format(context=context, question=question)

        # Seleciona cliente e modelo
        if model == self.premium_model and self._gemini:
            client = self._gemini
            model_name = self.premium_model
        elif self._groq:
            client = self._groq
            model_name = model or self.cheap_model
        else:
            client = self._gemini
            model_name = model if model in ("gemini-2.5-pro", "gemini-2.5-flash-lite") else "gemini-2.5-flash-lite"

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
        except Exception as e:
            err_str = str(e)
            if ("429" in err_str or "RESOURCE_EXHAUSTED" in err_str) and self._groq and client != self._groq:
                # Gemini rate limited → fallback GROQ cheap
                response = self._groq.chat.completions.create(
                    model=self.cheap_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                )
            else:
                raise

        answer_text = response.choices[0].message.content or ""
        answer_text = re.sub(r"<think>.*?</think>\s*", "", answer_text, flags=re.DOTALL).strip()

        sources = [(h["source"], h["page"]) for h in hits]

        return {"answer": answer_text, "sources": sources}


PROMPT_TEMPLATE = """Voce e um assistente tecnico. Responda APENAS com base no contexto abaixo.
Se a informacao nao estiver no contexto, responda educadamente que voce nao sabe e sugira reformular a pergunta.
Sempre cite a fonte usando o formato [arquivo:pagina].

CONTEXTO:
{context}

PERGUNTA: {question}

RESPOSTA:"""


def build_rag_pipeline(corpus_dir: str = "data/corpus") -> RAGPipeline:
    """Factory: cria pipeline e indexa corpus se ainda nao indexado."""
    pipeline = RAGPipeline(corpus_dir=corpus_dir)
    if pipeline.collection.count() == 0:
        pipeline.ingest_and_index()
    return pipeline
