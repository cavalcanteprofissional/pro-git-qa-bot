"""Compatibility shim for ragas 0.3.x with langchain-community >= 0.4.

ragas 0.3.x imports:
    from langchain_community.chat_models.vertexai import ChatVertexAI
    from langchain_community.llms import VertexAI

In langchain-community >= 0.4 these were moved to standalone
`langchain-google-vertexai`. This shim patches sys.modules to make
the old import paths redirect to the new locations.
"""

from __future__ import annotations

import sys


def apply() -> None:
    """Apply compatibility shims so ragas can import Vertex AI symbols."""
    applied = getattr(sys, "_ragas_compat_applied", False)
    if applied:
        return

    # --- Shim 1: langchain_community.chat_models.vertexai.ChatVertexAI ---
    if "langchain_community.chat_models.vertexai" not in sys.modules:
        import langchain_community.chat_models  # noqa: F401 — ensure parent loaded

        from langchain_google_vertexai import ChatVertexAI  # noqa: E402

        import types
        mod = types.ModuleType("langchain_community.chat_models.vertexai")
        mod.ChatVertexAI = ChatVertexAI
        sys.modules["langchain_community.chat_models.vertexai"] = mod

    # --- Shim 2: langchain_community.llms.VertexAI ---
    if "langchain_community.llms.vertexai" not in sys.modules:
        try:
            import langchain_community.llms  # noqa: F401
        except Exception:
            pass

        from langchain_google_vertexai import VertexAI  # noqa: E402

        import types  # noqa: E402
        mod2 = types.ModuleType("langchain_community.llms.vertexai")
        mod2.VertexAI = VertexAI
        sys.modules["langchain_community.llms.vertexai"] = mod2

    # Also shim the flat import used by some ragas versions
    for attr in ("VertexAI", "ChatVertexAI"):
        for parent in ("langchain_community.llms", "langchain_community.chat_models"):
            if parent not in sys.modules:
                continue
            if not hasattr(sys.modules[parent], attr):
                try:
                    from langchain_google_vertexai import VertexAI as V  # noqa: F811, E402
                    from langchain_google_vertexai import ChatVertexAI as CV  # noqa: F811, E402
                    setattr(sys.modules[parent], attr, locals()[attr])
                except Exception:
                    pass

    sys._ragas_compat_applied = True  # type: ignore[attr-defined]
