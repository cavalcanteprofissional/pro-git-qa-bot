"""Streamlit UI — Git Q&A Bot para o livro Pro Git.

Integra pipeline RAG (TODOs 1-3), ferramenta lookup_chapter (TO DO 4),
cache exato + semantico (TO DO 5), roteamento cheap-first (TO DO 6),
e observabilidade via Langfuse.
"""

from __future__ import annotations

import os
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
langfuse = None
if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
    langfuse = Langfuse()

# ---------------------------------------------------------------- Streamlit UI
st.set_page_config(page_title="Git Q&A Bot", page_icon=":robot:", layout="centered")

st.markdown(
    """
<style>
/* Sidebar — métricas menores */
section[data-testid="stSidebar"] [data-testid="stMetricValue"] {
    font-size: 1.0rem !important;
}
section[data-testid="stSidebar"] [data-testid="stMetricLabel"] {
    font-size: 0.75rem !important;
}
section[data-testid="stSidebar"] .stSubheader {
    font-size: 0.85rem !important;
}
</style>
""",
    unsafe_allow_html=True,
)

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


# ── Session state: runtime metrics ──────────────────────────────────────
if "total_requests" not in st.session_state:
    st.session_state.total_requests = 0
    st.session_state.exact_hits = 0
    st.session_state.semantic_hits = 0
    st.session_state.latencies: list[float] = []

# Sidebar — metricas e debug
with st.sidebar:
    st.title("🤖 Git Q&A Bot")
    st.caption("Dashboard de métricas")

    # ── Sistema ──────────────────────────────────────────────────────────
    with st.container(border=True):
        st.subheader("⚙️ Sistema")
        col1, col2 = st.columns(2)
        col1.metric("Chunks indexados", pipeline.collection.count())

        provider = "GROQ" if pipeline._groq else "Gemini"
        col2.metric("Provedor", provider)

        model_label = os.getenv("CHEAP_MODEL", "qwen/qwen3-32b")
        st.metric("Modelo LLM", model_label)

        st.markdown(f"**Busca:** Semântica (vetorial)")
        bm25_ok = "✅ Ativo" if os.getenv("BM25_ENABLED") else "⛔ Inativo"
        st.markdown(f"**Índice BM25:** {bm25_ok}")

    # ── Desempenho ──────────────────────────────────────────────────────
    with st.container(border=True):
        st.subheader("📊 Desempenho")

        s = st.session_state
        total = s.total_requests
        exact_hits = s.exact_hits
        semantic_hits = s.semantic_hits
        latencies = s.latencies

        col1, col2 = st.columns(2)
        col1.metric("Requisições", total)
        p95 = (
            sorted(latencies)[int(len(latencies) * 0.95)]
            if len(latencies) >= 20
            else (max(latencies) if latencies else 0)
        )
        col2.metric("Latência P95 (ms)", f"{p95:.0f}" if p95 else "—")

        exact_rate = exact_hits / total * 100 if total > 0 else 0
        semantic_rate = semantic_hits / total * 100 if total > 0 else 0
        col1.metric("Cache Hit (exact)", f"{exact_rate:.0f}%")
        col2.metric("Cache Hit (semântico)", f"{semantic_rate:.0f}%")

    # ── RAGAS Evaluation ────────────────────────────────────────────────
    with st.container(border=True):
        st.subheader("📊 RAGAS Evaluation")

        _eval_file = _ROOT / "data" / "eval_results.json"
        if _eval_file.exists():
            try:
                import json
                with open(_eval_file, encoding="utf-8") as _fh:
                    _eval_data = json.load(_fh)
                _faith = _eval_data.get("faithfulness")
                _ar = _eval_data.get("answer_relevancy")
                _cp = _eval_data.get("context_precision")

                st.metric("Faithfulness", f"{_faith:.2%}" if _faith is not None else "N/A")
                st.metric("Answer Relevance", f"{_ar:.2%}" if _ar is not None else "N/A")
                st.metric("Context Precision", f"{_cp:.2%}" if _cp is not None else "N/A")

                _meta = f"{_eval_data.get('num_queries', '?')} queries"
                if _ts := _eval_data.get("timestamp", ""):
                    _meta += f" · {_ts[:10]}"
                st.caption(_meta)

                if _faith is None:
                    st.info(_eval_data.get("note", ""))
            except Exception as _e:
                st.warning(f"Erro ao ler avaliação: {_e}")
        else:
            st.info("Avaliação não executada. Rode `scripts/eval_ragas.py` manualmente (consome cota GROQ/Gemini).")


# ---------------------------------------------------------------- handler com @observe()
@observe(name="rag_query", capture_input=True, capture_output=True)
def handle_query(query: str) -> dict:
    """Executa pipeline completo: cache → routing → RAG → cache write."""
    import time as _time
    _t0 = _time.perf_counter()

    s = st.session_state
    s.total_requests += 1

    # 1. Exact cache
    cached = exact_cache.get(query)
    if cached:
        log_event("cache_hit", layer="exact")
        s.exact_hits += 1
        s.latencies.append(round((_time.perf_counter() - _t0) * 1000, 1))
        return {"answer": cached, "source": "exact_cache"}

    # 2. Semantic cache
    try:
        cached = semantic_cache.get(query)
        if cached:
            log_event("cache_hit", layer="semantic")
            s.semantic_hits += 1
            s.latencies.append(round((_time.perf_counter() - _t0) * 1000, 1))
            return {"answer": cached, "source": "semantic_cache"}
    except NotImplementedError:
        pass

    # 3. Routing
    try:
        decision = classify_complexity(query)
    except NotImplementedError:
        decision = None

    # 4. RAG (passa modelo definido pelo routing ou None para cheap/GROQ)
    model_name = decision.model if decision else None
    result = pipeline.answer(query, model=model_name)

    # 5. Cache write
    exact_cache.put(query, result["answer"])
    semantic_cache.put(query, result["answer"])

    s.latencies.append(round((_time.perf_counter() - _t0) * 1000, 1))
    return result


# ---------------------------------------------------------------- sugestões
_SUGGEST_KEYWORDS = [
    "opções", "sugestõe", "sugestão", "opcao", "opção",
    "perguntar", "ideias", "exemplos", "ajuda", "help",
    "options", "suggest", "o que posso", "me dê",
]

_SUGGESTIONS = [
    ("O que é Git?", "🐙"),
    ("Diferença entre merge e rebase", "🔀"),
    ("Como criar um repositório?", "📁"),
    ("Resuma o capítulo 3", "📘"),
    ("O que é um commit?", "💾"),
    ("Como funciona o GitHub?", "🐱"),
    ("O que é staging area?", "📋"),
    ("Como desfazer um commit?", "⏪"),
    ("Explique git clone", "📥"),
    ("O que é .gitignore?", "🚫"),
]


# ---------------------------------------------------------------- chat loop
query = st.text_input(
    "💬 Sua pergunta:",
    placeholder="Pergunte algo sobre Git! Ex: O que é Git? 🐙 | Como fazer merge? 🔀 | Resuma o capítulo 3 📘",
)

# ── Suggestion flow ─────────────────────────────────────────────────────
if "suggestion_query" in st.session_state:
    query = st.session_state.pop("suggestion_query")

# ── Welcome message ─────────────────────────────────────────────────────
if not query or not query.strip():
    st.info(
        "👋 Olá! Sou o assistente do livro **Pro Git**. "
        "Pergunte sobre qualquer tópico de Git "
        "ou digite **"me dê opções"** para ver exemplos."
    )

# ── Query handling ──────────────────────────────────────────────────────
if query and query.strip():
    # Detecta pedido de sugestões
    if any(kw in query.lower() for kw in _SUGGEST_KEYWORDS):
        st.success("💡 **Aqui estão algumas perguntas que posso responder:**")
        cols = st.columns(2)
        for i, (q, emoji) in enumerate(_SUGGESTIONS):
            with cols[i % 2]:
                if st.button(f"{emoji} {q}", key=f"suggest_{i}", use_container_width=True):
                    st.session_state["suggestion_query"] = q
                    st.rerun()
    else:
        result = handle_query(query)
        source = result.get("source")

        if source == "exact_cache":
            st.success("⚡ Resposta do cache (exact match)")
            st.write(result["answer"])
        elif source == "semantic_cache":
            st.success("⚡ Resposta do cache (semantic match)")
            st.write(result["answer"])
        else:
            st.write(result["answer"])
            if result.get("sources"):
                with st.expander("📎 Fontes citadas"):
                    for src, page in result["sources"]:
                        st.write(f"- `{src}:p{page}`")


st.divider()
st.caption("Pro Git Q&A Bot — https://github.com/cavalcanteprofissional/pro-git-qa-bot")
