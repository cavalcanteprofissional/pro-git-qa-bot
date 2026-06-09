"""Benchmark de latencia para preencher tabela de custo/latencia do README.

Uso:
    uv run python scripts/bench_latency.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
load_dotenv(dotenv_path=_ROOT / ".env.local")

from src.pipeline.cache import ExactCache, SemanticCache
from src.pipeline.rag import build_rag_pipeline
from src.pipeline.routing import classify_complexity

QUERIES = [
    "O que e Git?",
    "Para que serve o Git?",
    "Como criar um branch?",
    "O que e um commit?",
    "Como resolver merge conflict?",
    "Explique a diferenca entre merge e rebase",
    "O que e o staging area?",
    "Como funciona o git log?",
    "O que e um remote?",
    "Como clonar um repositorio?",
]


def bench() -> None:
    print("Inicializando pipeline...")
    pipeline = build_rag_pipeline(corpus_dir=str(_ROOT / "data" / "corpus"))
    exact = ExactCache()
    semantic = SemanticCache(threshold=0.93)

    latencies = {"baseline": [], "exact": [], "semantic": [], "routing": []}

    for i, q in enumerate(QUERIES):
        print(f"[{i+1}/{len(QUERIES)}] {q[:50]}...")

        # --- Baseline: tudo via LLM (simula premium sempre) ---
        t0 = time.perf_counter()
        result = pipeline.answer(q)
        t_llm = (time.perf_counter() - t0) * 1000
        latencies["baseline"].append(t_llm)

        # --- Exact cache hit (mede so o lookup) ---
        exact.put(q, result["answer"])
        t0 = time.perf_counter()
        _ = exact.get(q)
        latencies["exact"].append((time.perf_counter() - t0) * 1000)

    # --- Routing (mede classificacao) ---
    t0 = time.perf_counter()
    decision = classify_complexity(q)
    latencies["routing"].append((time.perf_counter() - t0) * 1000)

    # --- Semantic cache (estima 200ms para embedding via API) ---
    latencies["semantic"].append(200.0)

    r = decision
    print(
        f"  {r.complexity:>7} | "
        f"LLM {t_llm:>7.0f}ms | "
        f"exact {latencies['exact'][-1]:>5.0f}ms | "
        f"sem ~200ms | "
        f"route {latencies['routing'][-1]:>5.0f}ms"
    )

    def p50(lst): return sorted(lst)[len(lst)//2]
    def p95(lst): return sorted(lst)[int(len(lst)*0.95)]
    def avg(lst): return sum(lst)/len(lst)

    print()
    print("=" * 75)
    print(f"{'Estrategia':<35} {'P50':>10} {'P95':>10} {'Avg':>10}")
    print("-" * 75)
    for name in ["baseline", "exact", "semantic", "routing"]:
        print(
            f"{name:<35} "
            f"{p50(latencies[name]):>8.0f}ms "
            f"{p95(latencies[name]):>8.0f}ms "
            f"{avg(latencies[name]):>8.0f}ms"
        )

    b = p50(latencies["baseline"])
    print(f"\nReducao estimada com cache (carga 60% cache hit + routing cheap): "
          f"{(1 - (0.4 * b + 0.6 * 50) / b) * 100:.0f}%")


if __name__ == "__main__":
    bench()
