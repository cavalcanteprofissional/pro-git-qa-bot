# TODO.md — Projeto Portfólio: Git Q&A Bot

## Dados do Projeto

| Item | Decisão |
|------|---------|
| **Modalidade** | A — Template + corpus próprio |
| **Domínio** | Q&A sobre Livro Técnico (Pro Git) |
| **Provedor LLM** | Gemini (free tier) |
| **Modelo cheap** | `gemini-2.5-flash-lite` |
| **Modelo premium** | `gemini-2.5-pro` |
| **Embedding** | `gemini-embedding-001` |
| **Chunking** | `chunk_size=800`, `overlap=100` |
| **Observabilidade** | Langfuse (banda Excelente) |
| **Trilha** | Basic (target ≥60 em todos critérios) |
| **Tool custom** | `lookup_chapter(chapter: int) -> str` |

---

## Etapas

### Fase 0 — Setup (30 min)

- [ ] **0.1** — Colocar PDF do Pro Git em `data/corpus/`
  - Download: https://git-scm.com/book/en/v2 (ou repo oficial)
  - Nomear como `progit.pdf`
- [ ] **0.2** — Configurar `.env` com `GEMINI_API_KEY`
- [ ] **0.3** — Criar ambiente virtual: `uv venv && source .venv/bin/activate`
- [ ] **0.4** — Instalar dependências: `uv sync`
- [ ] **0.5** — Adicionar dependência Langfuse: `uv pip install langfuse`
- [ ] **0.6** — Configurar Langfuse no `.env` (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST)

### Fase 1 — Pipeline RAG (Aluno A) ~40 min

#### TODO 1 — `src/pipeline/rag.py::ingest_and_index` (20 min)
- [ ] **1.A** — Iterar PDFs com `PdfReader`, extrair texto página a página
- [ ] **1.B** — Aplicar `RecursiveCharacterTextSplitter(chunk_size=800, overlap=100)`
- [ ] **1.C** — Indexar chunks no Chroma com `collection.add(ids=, documents=, metadatas=)`

#### TODO 2 — `src/pipeline/rag.py::retrieve` (5 min)
- [ ] **2** — Implementar `collection.query(query_texts=[query], n_results=k)`
  - Retornar lista de dicts: `{"text", "source", "page", "distance"}`

#### TODO 3 — `src/pipeline/rag.py::answer` (15 min)
- [ ] **3** — Montar contexto → prompt com `PROMPT_TEMPLATE` → chamar LLM
  - Prompt obriga citação `[arquivo:página]`
  - Retornar `{"answer": str, "sources": [(str, int)]}`

### Fase 2 — Tool + Cache + Routing (Aluno B) ~55 min

#### TODO 4 — `src/pipeline/tools.py::lookup_chapter` (30 min)
- [ ] **4.A** — Implementar função `lookup_chapter(chapter: int) -> str`
  - Extrai sumário/estrutura do capítulo N do Pro Git
  - Pode usar PDF indexado ou arquivo auxiliar `data/progit-toc.json`
- [ ] **4.B** — Registrar schema JSON em `TOOLS` e função em `TOOL_REGISTRY`

#### TODO 5 — `src/pipeline/cache.py::SemanticCache.get` (15 min)
- [ ] **5** — Implementar busca por similaridade cosseno:
  - Embedar query → comparar com `self._embeddings`
  - Se `max_similarity >= threshold (0.93)`, retornar `self._answers[idx]`
  - Senão, retornar `None`

#### TODO 6 — `src/pipeline/routing.py::classify_complexity` (10 min)
- [ ] **6** — Heurística para classificar query:
  - `len < 60` + termina com `?` → simple (cheap model)
  - Contém palavras-chave (`explique`, `compare`, `analise`, `diferença`) → complex (premium)
  - Default → simple

### Fase 3 — UI + Deploy ~30 min

- [ ] **3.1** — Personalizar `streamlit_app.py`:
  - Título: "Git Q&A Bot"
  - Slogan: "Assistente RAG para o livro Pro Git — pergunte, cite, aprenda."
- [ ] **3.2** — Adicionar `@observe()` do Langfuse nas chamadas LLM
- [ ] **3.3** — Testar local: `streamlit run src/ui/streamlit_app.py`
- [ ] **3.4** — Subir no GitHub (repo público)
- [ ] **3.5** — Deploy 1-click no Streamlit Community Cloud

### Fase 4 — README + Documentação ~40 min

- [ ] **4.1** — Preencher problem statement (3 linhas)
- [ ] **4.2** — Diagrama de arquitetura (Mermaid)
- [ ] **4.3** — Tabela de custo/latência (rodar bench de 50 queries)
- [ ] **4.4** — Design decisions (3-5 bullets)
- [ ] **4.5** — Limitations (3 bullets honestos)
- [ ] **4.6** — Gerar GIF de demo (10-15s, <5MB)
- [ ] **4.7** — Ver rubrica: garantir que atende banda **Básico** nos 4 critérios

### Fase 5 — Testes e Polish ~20 min

- [ ] **5.1** — Rodar smoke tests: `uv run pytest tests/test_smoke.py -v`
- [ ] **5.2** — 3 perguntas de teste que dependem do corpus:
  - "O que é Git e para que serve?"
  - "Explique a diferença entre merge e rebase"
  - "Como criar um branch no Git?"
- [ ] **5.3** — Verificar tool `lookup_chapter` com "Resuma o capítulo 3"
- [ ] **5.4** — Verificar cache hit-rate e routing funcionando

#### Bug Fix — SemanticCache local embedding (Streamlit Cloud compatibility)

- [ ] **FIX** — Substituir embedding via API (OpenAI + Gemini) por `sentence-transformers/all-MiniLM-L6-v2` local:
  - `SemanticCache._embed` agora usa `SentenceTransformer.encode()` em vez de `OpenAI.embeddings.create()`
  - Elimina dependência de `GEMINI_API_KEY` no cache → funciona no Streamlit Cloud sem secrets extras
  - Latência ~50ms, consistente com o `LocalEmbeddingFunction` do ChromaDB

## Fase 6 — Entrega ~15 min

- [ ] **6.1** — Gravar vídeo demo (≤3 min, ambos aparecem)
- [ ] **6.2** — Confirmar 3 URLs abrindo em janela anônima
- [ ] **6.3** — Preencher Forms com:
  - URL da demo (Streamlit Cloud)
  - URL do repositório (GitHub público)
  - URL do vídeo demo
  - Nomes + emails institucionais da dupla

---

## Rubrica — Banda Alvo: Básico (60-74)

| Critério | Peso | O que entregar para atingir ≥60 |
|----------|:----:|----------------------------------|
| Técnica | 40% | TODOs 1-6 funcionando individualmente, pipeline roda sem crash |
| README | 30% | Problem statement + setup funcional |
| Custo/Latência | 20% | Medir custo por chamada + cache implementado com hit-rate |
| Demo | 10% | URL acessível + 1 fluxo demonstrável sem crash |

---

## Entregas

- [ ] URL pública da demo (Streamlit Cloud)
- [ ] URL do repositório GitHub (público)
- [ ] URL do vídeo demo (≤3 min, Loom/Youtube unlisted)
- [ ] Forms preenchido até **16:45 do Dia 3 (08/06/2026)**
