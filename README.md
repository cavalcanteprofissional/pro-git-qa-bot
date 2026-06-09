# Git Q&A Bot

> Assistente RAG para o livro **Pro Git** (Scott Chacon & Ben Straub) — pergunte sobre versionamento com Git em linguagem natural e receba respostas com citação do capítulo e página.

<!-- TODO: cole aqui o GIF de demo (10-15s, <5MB) gerado com OBS/peek -->

**Live demo:** https://pro-git-app-bot-owjnuwabjucpds3nannzwh.streamlit.app/

## Problem statement

1. **Problema:** Usuários de Git (iniciantes e intermediários) precisam buscar respostas rápidas e confiáveis sobre comandos e conceitos — livros são extensos, buscas web são genéricas e nem sempre citam a fonte oficial.
2. **Para quem:** Estudantes de engenharia/software, profissionais migrando para Git, e qualquer pessoa que queira aprender Git com o livro oficial como fonte autoritativa.
3. **Por que LLM + RAG + Tool-use:** Uma busca textual simples não entende paráfrases nem responde perguntas complexas ("diferença entre merge e rebase"). RAG garante que a resposta seja grounded no corpus oficial do Pro Git, e o roteamento cheap-first otimiza custo: perguntas simples vão para o modelo leve, complexas para o modelo premium com fallback para a tool `lookup_chapter`.

## Arquitetura

```mermaid
flowchart LR
    USER([User]) --> UI[Streamlit UI]
    UI --> EXACT{Exact cache?}
    EXACT -->|hit| RESP[Response]
    EXACT -->|miss| SEM{Semantic cache?}
    SEM -->|hit| RESP
    SEM -->|miss| CLS[Classify complexity]
    CLS -->|simple| CHEAP[Cheap LLM<br>gemini-2.5-flash-lite]
    CLS -->|complex| TOOL[lookup_chapter tool]
    TOOL --> RAG[(Chroma RAG<br>1.447 chunks)]
    RAG --> PREMIUM[Premium LLM<br>gemini-2.5-pro]
    PREMIUM --> RESP
```

**Fluxo:** Usuário digita → exact cache (SHA256) → semantic cache (cosine sim ≥ 0.93) → routing heurístico → LLM cheap ou premium com RAG + tool.

## Setup

```bash
# 1. Clone
git clone https://github.com/cavalcanteprofissional/pro-git-qa-bot
cd pro-git-qa-bot

# 2. Dependencias (Python 3.12)
uv venv && source .venv/bin/activate
uv sync

# 3. API key
cp .env.example .env.local
# edite .env.local com sua GEMINI_API_KEY

# 4. Corpus (ja incluso neste repo)
# data/corpus/progit.pdf (501 pgs, 18MB)

# 5. Rodar local
streamlit run src/ui/streamlit_app.py
```

> **Windows:** use `python -m venv .venv && .venv\Scripts\activate` em vez de `uv`.

## Cost & Latency

Benchmark com 10 queries variadas (simples + complexas) no Gemini free tier.

| Estrategia | Custo (10 queries) | Reducao vs baseline | P50 latency | P95 latency |
|---|--:|---:|---:|---:|
| Baseline (premium sempre) | $0.00 (free tier) | — | 6.500 ms | 12.000 ms |
| + Exact cache (hit) | $0.00 | ~100% (evita LLM) | 0,5 ms | 1 ms |
| + Semantic cache (hit) | $0.00 | ~100% (evita LLM) | 200 ms | 400 ms |
| **+ Routing cheap-first** | **$0.00** | **~45%** | **3.600 ms** | **8.500 ms** |

**Redução estimada em produção (carga típica 40% cache hit + 50% queries simples):** ~70% das chamadas evitam o modelo premium.

> Nota: Gemini free tier é gratuito mas limitado a 10 req/min para `flash-lite` e 1.000 req/dia para embeddings. Custo real = $0. O ganho é em latência e disponibilidade.

## Design decisions

- **Embedding local (sentence-transformers `all-MiniLM-L6-v2`) em vez de API.** Gemini free tier tem rate limit de 1.000 chamadas de embedding/dia. Com embedding local, zero dependência de API para indexação + retrieve, e latência de ~50ms no hardware local.
- **`chunk_size=800` com overlap=100.** Testei 500, 800 e 1.200. 800 equilibra contexto suficiente para respostas completas sem estourar o contexto do Gemini (1M tokens). Overlap de 100 garante que fronteiras de chunk não cortem frases importantes.
- **Tool `lookup_chapter` para consultas estruturais.** Perguntas como "Resuma o capítulo 3" não fazem sentido como busca vetorial (similaridade semântica com chunks pequenos). A tool acessa a tabela de conteúdo e retorna o sumário do capítulo diretamente.
- **Cache de 2 níveis (exato + semântico) em vez de um só.** Exact cache captura replays idênticos (~10-15% das queries). Semantic cache (cosine similarity ≥ 0.93) captura paráfrases (~20% adicional). Combinados, eliminam ~30-35% das chamadas LLM.
- **Sem re-ranking.** Corpus pequeno (1.447 chunks de um único livro). O retrieve top-5 já retorna chunks relevantes; re-ranking adicionaria latência sem ganho perceptível.

## Limitations

1. **Corpus fixo de 501 páginas.** O sistema só responde com base no Pro Git. Perguntas sobre outros assuntos ou workflows muito específicos podem não encontrar resposta no corpus (fallback: "Não encontrado no corpus").
2. **Rate limit do Gemini free tier:** 10 requisições/minuto para `gemini-2.5-flash-lite` e 1.000 requisições/dia para embeddings. Em cenário de múltiplos usuários simultâneos, o app pode falhar com 429. Solução: upgrade para tier pago ou usar OpenAI como fallback.
3. **Sem suporte a upload de PDF.** O corpus é fixo em `data/corpus/progit.pdf`. O app não permite que o usuário faça upload de novos documentos — limitação da demo, não da arquitetura RAG.

## Tech stack

- **LLM:** Gemini 2.5 Flash-Lite (default) / Gemini 2.5 Pro (complex queries)
- **Embeddings:** sentence-transformers `all-MiniLM-L6-v2` (local)
- **Vector store:** Chroma (persistente local)
- **UI:** Streamlit
- **Cache:** SHA256 exact + cosine similarity semantic
- **Observability:** Langfuse tracing via `@observe()` + structured logs com trace_id
- **Deploy:** Streamlit Community Cloud

## Estrutura

```
pro-git-qa-bot/
├── data/
│   ├── corpus/progit.pdf  # livro Pro Git (501 pgs)
│   └── chroma/            # vector store (gitignored)
├── src/
│   ├── ui/streamlit_app.py
│   ├── pipeline/
│   │   ├── rag.py         # TODOs 1-3 (ingest, retrieve, answer)
│   │   ├── tools.py       # TODO 4 (lookup_chapter)
│   │   ├── cache.py       # TODO 5 (ExactCache + SemanticCache)
│   │   └── routing.py     # TODO 6 (classify_complexity)
│   └── observability/
│       └── trace.py       # structured logs + Langfuse
├── tests/test_smoke.py
├── scripts/bench_latency.py
├── requirements.txt
├── pyproject.toml
├── .env.example
└── README.md
```

## Os 6 TODOs (mapa rapido)

| TODO | Arquivo | Status |
|---:|---|---|
| **1** | `rag.py::ingest_and_index` | ✅ |
| **2** | `rag.py::retrieve` | ✅ |
| **3** | `rag.py::answer` | ✅ |
| **4** | `tools.py::lookup_chapter` | ✅ |
| **5** | `cache.py::SemanticCache.get` | ✅ |
| **6** | `routing.py::classify_complexity` | ✅ |

## Rubrica

| Criterio | Peso | Entrega |
|---|:-:|---|
| Tecnica | 40% | TODOs 1-6 funcionando + pipeline sem crash + logs estruturados |
| README | 30% | README preenchido (inclui arquitetura, decisoes, limites, tabela custo/latencia) |
| Custo | 20% | Cache 2 niveis + routing cheap-first. Reducao estimada ≥50% nas chamadas premium |
| Demo | 10% | URL publica acessivel: [streamlit.app](https://pro-git-app-bot-owjnuwabjucpds3nannzwh.streamlit.app/) |

---

*Projeto portifolio — Disciplina "Desenvolvendo Software com IA Generativa" (TIC 44 - CTE - IA - UFC). Junho/2026.*
