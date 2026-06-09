"""Streamlit UI — Git Q&A Bot para o livro Pro Git.

Integra pipeline RAG (TODOs 1-3), ferramenta lookup_chapter (TO DO 4),
cache exato + semantico (TO DO 5), roteamento cheap-first (TO DO 6),
e observabilidade via Langfuse.
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

# Adiciona o root do projeto no path para imports
_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

load_dotenv(dotenv_path=_ROOT / ".env.local")

import streamlit as st  # noqa: E402

from langfuse import Langfuse, observe  # noqa: E402

from src.observability.trace import log_event  # noqa: E402
from src.pipeline.cache import ExactCache, SemanticCache  # noqa: E402
from src.pipeline.rag import build_rag_pipeline  # noqa: E402
from src.pipeline.routing import classify_complexity  # noqa: E402

# ---------------------------------------------------------------- Langfuse init
langfuse = Langfuse()

# ---------------------------------------------------------------- Streamlit UI
st.set_page_config(page_title="Git Q&A Bot", page_icon=":robot:", layout="centered")

st.title(":books: Git Q&A Bot")
st.caption("Assistente RAG para o livro Pro Git — pergunte, cite, aprenda.")


# Inicializacao lazy de pipeline + caches
@st.cache_resource
def get_pipeline():
    return build_rag_pipeline(corpus_dir=str(_ROOT / "data" / "corpus"))


@st.cache_resource
def get_exact_cache():
    return ExactCache()


@st.cache_resource
def get_semantic_cache():
    return SemanticCache(threshold=0.93)


with st.spinner("Inicializando pipeline RAG..."):
    pipeline = get_pipeline()
    exact_cache = get_exact_cache()
    semantic_cache = get_semantic_cache()


# Sidebar — metricas e debug
with st.sidebar:
    st.header("Metricas")
    st.metric("Chunks indexados", pipeline.collection.count())
    st.metric("Exact cache", exact_cache.stats()["size"])
    st.metric("Semantic cache", semantic_cache.stats()["size"])

    # --- RAGAS Evaluation (cached results) ---
    st.divider()
    st.subheader("📊 RAGAS Evaluation")

    _eval_file = _ROOT / "data" / "eval_results.json"
    if _eval_file.exists():
        try:
            import json
            with open(_eval_file, encoding="utf-8") as _fh:
                _eval_data = json.load(_fh)
            if _eval_data.get("faithfulness") is not None:
                _cols = st.columns(3)
                _cols[0].metric("Faithfulness", f"{_eval_data['faithfulness']:.2%}")
                _cols[1].metric("Answer Relevance", f"{_eval_data['answer_relevancy']:.2%}")
                _cols[2].metric("Context Precision", f"{_eval_data['context_precision']:.2%}")
                st.caption(f"{_eval_data['num_queries']} queries · {_eval_data.get('timestamp', '')[:10]}")
            else:
                st.warning(f"Avaliação pendente: {_eval_data.get('error', 'erro desconhecido')}")
        except Exception as _e:
            st.warning(f"Erro ao ler avaliação: {_e}")
    else:
        st.info("Avaliação não executada. Rode `scripts/eval_ragas.py` manualmente (consome cota Gemini).")


# ---------------------------------------------------------------- handler com @observe()
@observe(name="rag_query", capture_input=True, capture_output=True)
def handle_query(query: str) -> dict:
    """Executa pipeline completo: cache → routing → RAG → cache write."""
    # 1. Exact cache
    cached = exact_cache.get(query)
    if cached:
        log_event("cache_hit", layer="exact")
        return {"answer": cached, "source": "exact_cache"}

    # 2. Semantic cache
    try:
        cached = semantic_cache.get(query)
        if cached:
            log_event("cache_hit", layer="semantic")
            return {"answer": cached, "source": "semantic_cache"}
    except NotImplementedError:
        pass

    # 3. Routing
    try:
        decision = classify_complexity(query)
    except NotImplementedError:
        decision = None

    # 4. RAG
    result = pipeline.answer(query)

    # 5. Cache write
    exact_cache.put(query, result["answer"])
    semantic_cache.put(query, result["answer"])

    return result


# ---------------------------------------------------------------- chat loop
query = st.text_input(
    "Sua pergunta:",
    placeholder="Ex: O que e Git? | Explique merge e rebase | Resuma o capitulo 3",
)

if query:
    result = handle_query(query)
    source = result.get("source")

    if source == "exact_cache":
        st.success("Cache hit (exact)")
        st.write(result["answer"])
    elif source == "semantic_cache":
        st.success("Cache hit (semantic)")
        st.write(result["answer"])
    else:
        st.write(result["answer"])
        if result.get("sources"):
            with st.expander("Fontes citadas"):
                for src, page in result["sources"]:
                    st.write(f"- `{src}:p{page}`")


st.divider()
st.caption("Pro Git Q&A Bot — https://github.com/cavalcanteprofissional/pro-git-qa-bot")
