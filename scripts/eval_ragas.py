"""Avaliação RAGAS — golden set de 14 queries.

Uso:
    uv run python scripts/eval_ragas.py
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Aplica compat shim ANTES de importar ragas
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.patches import ragas_compat  # noqa: E402

ragas_compat.apply()

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
load_dotenv(dotenv_path=_ROOT / ".env.local")

from langchain_openai import ChatOpenAI  # noqa: E402
from langchain_community.embeddings import HuggingFaceEmbeddings  # noqa: E402
from datasets import Dataset  # noqa: E402
import ragas  # noqa: E402
from ragas.metrics import (  # noqa: E402
    faithfulness,
    answer_relevancy,
    context_precision,
)
from ragas.embeddings.base import LangchainEmbeddingsWrapper  # noqa: E402
from ragas.llms.base import RunConfig  # noqa: E402

from src.pipeline.rag import build_rag_pipeline  # noqa: E402
from src.observability.trace import log_event  # noqa: E402

RESULTS_FILE = _ROOT / "data" / "eval_results.json"
GOLDEN_SET = _ROOT / "data" / "golden_set.json"
INTERMEDIATE_FILE = _ROOT / "data" / "eval_samples.json"

# Gemini free tier: 20 req/dia para flash-lite
# Delay seguro entre chamadas: 10s + backoff
BASE_DELAY = 10
MAX_RETRIES = 3


def _call_with_backoff(pipeline, question: str) -> dict:
    """Chama pipeline.answer() com exponential backoff para rate limit."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return pipeline.answer(question)
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                wait = (BASE_DELAY + 5) * attempt
                print(f"  Rate limit hit (attempt {attempt}/{MAX_RETRIES}). "
                      f"Waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"Falhou apos {MAX_RETRIES} tentativas para: {question}")


def load_golden() -> list[dict]:
    with open(GOLDEN_SET, encoding="utf-8") as f:
        return json.load(f)


def run_evaluation() -> dict:
    """Executa pipeline sobre golden set e calcula metricas RAGAS."""
    print(f"Carregando golden set de {GOLDEN_SET}...")
    golden = load_golden()
    print(f"  {len(golden)} queries carregadas")

    # Verifica se ja existem amostras intermediarias
    samples = []
    if INTERMEDIATE_FILE.exists():
        with open(INTERMEDIATE_FILE, encoding="utf-8") as f:
            samples = json.load(f)
        print(f"  {len(samples)} amostras ja coletadas (retomando...)")

    if len(samples) < len(golden):
        print("Inicializando pipeline...")
        pipeline = build_rag_pipeline(corpus_dir=str(_ROOT / "data" / "corpus"))
        print(f"  Collection: {pipeline.collection.count()} chunks")

    for i, item in enumerate(golden):
        if i < len(samples):
            continue  # ja processado

        q = item["question"]
        print(f"[{i+1}/{len(golden)}] {q[:60]}...")

        if i > 0 or len(samples) > 0:
            delay = BASE_DELAY
            print(f"  Aguardando {delay}s para rate limit...")
            time.sleep(delay)

        result = _call_with_backoff(pipeline, q)

        hits = pipeline.retrieve(q, k=5)
        contexts = [h["text"] for h in hits]

        samples.append({
            "user_input": q,
            "response": result["answer"],
            "retrieved_contexts": contexts,
            "reference": item["ground_truth"],
        })

        # Salva intermediario a cada query
        with open(INTERMEDIATE_FILE, "w", encoding="utf-8") as f:
            json.dump(samples, f, indent=2, ensure_ascii=False)

        print(f"  response: {result['answer'][:80]}...")
        print(f"  contexts: {len(contexts)} chunks")

    # Monta dataset HuggingFace
    ds = Dataset.from_list(samples)

    # LLM juiz via GROQ (free tier, TPM 6K com max_workers=1 serializado)
    groq_key = os.environ.get("GROQ_API_KEY")
    if groq_key:
        from ragas.llms.base import LangchainLLMWrapper as LLMWrapper
        raw_llm = ChatOpenAI(
            model="qwen/qwen3-32b",
            api_key=groq_key,
            base_url="https://api.groq.com/openai/v1",
            temperature=0.0,
        )
        # Pre-wrap com parser leniente (GROQ pode retornar finish_reason variado)
        llm = LLMWrapper(
            raw_llm,
            run_config=RunConfig(timeout=300, max_retries=5, max_workers=1),
            is_finished_parser=lambda _: True,
        )
    else:
        # Fallback: Gemini (quota limitada a 20 req/dia)
        llm = ChatOpenAI(
            model="gemini-2.5-flash-lite",
            api_key=os.environ["GEMINI_API_KEY"],
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            temperature=0.0,
        )

    # Embeddings locais (mesmo modelo usado no pipeline RAG)
    hf_embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
    )
    embeddings = LangchainEmbeddingsWrapper(hf_embeddings)

    print("\nCalculando metricas RAGAS (faithfulness, answer_relevancy, context_precision)...")
    print("  Isso pode levar alguns minutos (LLM juiz consume cota extra)...")

    try:
        result = ragas.evaluate(
            ds,
            metrics=[faithfulness, answer_relevancy, context_precision],
            llm=llm,
            embeddings=embeddings,
            run_config=RunConfig(timeout=300, max_retries=5, max_workers=1),
        )

        def _mean_score(values: list) -> float | None:
            """Media de valores nao-NaN/None. Retorna None se vazio."""
            clean = [v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
            if not clean:
                return None
            return round(sum(clean) / len(clean), 4)

        scores = {
            "faithfulness": _mean_score(result["faithfulness"]),
            "answer_relevancy": _mean_score(result["answer_relevancy"]),
            "context_precision": _mean_score(result["context_precision"]),
            "num_queries": len(samples),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
    except Exception as e:
        print(f"ERRO no RAGAS evaluate: {e}")
        scores = {
            "faithfulness": None,
            "answer_relevancy": None,
            "context_precision": None,
            "num_queries": len(samples),
            "error": str(e),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

    # Salva resultados finais
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(scores, f, indent=2)

    log_event("ragas_evaluation", **scores)

    if scores.get("faithfulness") is not None:
        print(f"\nResultados salvos em {RESULTS_FILE}")
        print(f"faithfulness={scores['faithfulness']}, "
              f"answer_relevancy={scores['answer_relevancy']}, "
              f"context_precision={scores['context_precision']}")
    else:
        print(f"\nAmostras salvas em {INTERMEDIATE_FILE}. "
              f"RAGAS evaluate falhou (provavelmente rate limit). "
              f"Rode novamente quando a cota resetar.")

    return scores


if __name__ == "__main__":
    run_evaluation()
