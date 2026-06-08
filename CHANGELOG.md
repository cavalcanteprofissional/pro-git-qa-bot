# Changelog — Git Q&A Bot

## Fase 0 — Setup

- [x] 0.1 — PDF do Pro Git (501 págs, 18MB) em `data/corpus/progit.pdf`
- [x] 0.2 — `.env.local` configurado com GEMINI_API_KEY + Langfuse
- [x] 0.3 — Ambiente virtual criado e dependências instaladas (114 pacotes)
- [x] 0.4 — Langfuse instalado e configurado
- [x] 0.5 — `projeto-portfolio.pdf` e `.md` adicionados ao `.gitignore`
- [x] 0.6 — `CHANGELOG.md` criado
- [x] 0.7 — `TODO.md` criado com plano por fases
- [x] 0.8 — `LICENSE` (MIT) adicionado
- [x] 0.9 — Repositório Git inicializado e push para GitHub
- [x] 0.10 — `.env` renomeado para `.env.local` + `load_dotenv` atualizado

## Fase 1 — Pipeline RAG (TODOs 1-3)

- [ ] TODO 1 — `ingest_and_index` implementado
- [ ] TODO 2 — `retrieve` implementado
- [ ] TODO 3 — `answer` implementado

## Fase 2 — Tool + Cache + Routing (TODOs 4-6)

- [x] TODO 4 — `lookup_chapter` implementado (capítulos 1-13 do Pro Git)
- [x] TODO 5 — `SemanticCache.get` implementado (cosine similarity com threshold)
- [x] TODO 6 — `classify_complexity` implementado (heurística cheap/premium)

## Fase 3 — UI + Deploy

- [x] 3.1 — `streamlit_app.py` personalizado (título + slogan)
- [x] 3.2 — Langfuse `@observe()` integrado
- [x] 3.3 — Teste local funcionando (streamlit boots sem erros)
- [ ] 3.4 — Repositório no GitHub (aguardando permissão)
- [ ] 3.5 — Deploy no Streamlit Cloud (após push)

## Fase 4 — README + Documentação

- [ ] 4.1 — Problem statement
- [ ] 4.2 — Diagrama de arquitetura
- [ ] 4.3 — Tabela de custo/latência
- [ ] 4.4 — Design decisions
- [ ] 4.5 — Limitations
- [ ] 4.6 — GIF de demo
- [ ] 4.7 — Revisão rubrica

## Fase 5 — Testes e Polish

- [ ] 5.1 — Smoke tests passando
- [ ] 5.2 — 3 perguntas de teste validadas
- [ ] 5.3 — Tool `lookup_chapter` testada
- [ ] 5.4 — Cache hit-rate e routing verificados

## Fase 6 — Entrega

- [ ] 6.1 — Vídeo demo gravado
- [ ] 6.2 — 3 URLs confirmadas
- [ ] 6.3 — Forms enviado

---

## Bugs encontrados

| Data | Descrição | Status |
|------|-----------|--------|
| — | — | — |
