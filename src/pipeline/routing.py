"""Model routing cheap-first com fallback.

Reaproveita o notebook 05.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from openai import OpenAI


@dataclass(frozen=True)
class RouteDecision:
    model: str
    complexity: str
    reason: str


COMPLEX_KEYWORDS = [
    "explique", "compare", "analise", "projete", "diferença", "diferença",
    "por que", "como funciona", "detalhe", "exemplo prático",
    "arquitetura", "implemente", "desenhe", "relacione",
    "vantagens e desvantagens", "prós e contras", "quando usar",
    "contraste", "elabore", "discurse", "fundamento",
]


# ------------------------------------------------------------------ TODO 6
def classify_complexity(query: str) -> RouteDecision:
    """Classifica complexidade da query para escolher modelo (cheap vs premium).

    Estrategia heuristica simples. Em producao, evoluiria para classifier treinado.
    """
    cheap_model = os.environ.get("CHEAP_MODEL", "gemini-2.5-flash-lite")
    premium_model = os.environ.get("PREMIUM_MODEL", "gemini-2.5-pro")

    q_lower = query.lower().strip()

    if len(q_lower) < 60 and q_lower.endswith("?"):
        return RouteDecision(
            model=cheap_model,
            complexity="simple",
            reason="Query curta e interrogativa → cheap model",
        )

    for keyword in COMPLEX_KEYWORDS:
        if keyword in q_lower:
            return RouteDecision(
                model=premium_model,
                complexity="complex",
                reason=f"Query contém palavra-chave '{keyword}' → premium model",
            )

    return RouteDecision(
        model=cheap_model,
        complexity="simple",
        reason="Query não classifica como complexa → cheap model (default)",
    )


def make_client() -> OpenAI:
    """Cliente OpenAI-compatible para o provider configurado."""
    if "GEMINI_API_KEY" in os.environ:
        return OpenAI(
            api_key=os.environ["GEMINI_API_KEY"],
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
    return OpenAI()
