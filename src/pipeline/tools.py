"""Function-calling / tool-use — registro de tools usadas pelo agente.

Reaproveita o LAB-001.
"""

from __future__ import annotations

import json
from typing import Any, Callable


CHAPTERS = {
    1: "Getting Started — About version control, Git history, Git basics, command-line setup, first-time config, getting help.",
    2: "Git Basics — Initializing a repo, staging files, committing, viewing history, undoing things, remotes, tagging, aliases.",
    3: "Git Branching — Branches in a nutshell, basic branch/merge, branch management, workflows, remote branches, rebasing.",
    4: "Git on the Server — Protocols (local, HTTP, SSH, Git), setting up a server, generating SSH keys, Git daemon, smart HTTP, GitWeb, hosting options.",
    5: "Distributed Git — Distributed workflows, contributing to a project, maintaining a project, signed commits, shortlog.",
    6: "GitHub — Account setup, SSH config, contributing to projects (fork/clone/PR), maintaining a project on GitHub, GitHub Pages.",
    7: "Git Tools — Revision selection, interactive staging, stashing, signing, searching, rewriting history, reset/diff, bundling, replace, credential storage.",
    8: "Customizing Git — Git config, gitattributes, git hooks, forced commit policies, environment variables.",
    9: "Git and Other Systems — Git as a client (SVN, Mercurial), migrating to Git from other VCSs.",
    10: "Git Internals — Plumbing and porcelain, Git objects (blob, tree, commit, tag), packfiles, refspecs, transfer protocols, maintenance.",
    11: "Appendix A: Git in Other Environments — Git in GUI (macOS, Windows, VS Code), Git in IntelliJ, Git in Sublime Text, Git in Bash/Zsh, Git in PowerShell.",
    12: "Appendix B: Embedding Git — Git in CLI applications (libgit2, rugged, go-git), JGit (Java), Dulwich (Python).",
    13: "Appendix C: Git Commands — Reference of every Git command organized by category: setup, create, branch/share, inspect, patch/debug, admin, plumbing.",
}


def lookup_chapter(chapter: int) -> str:
    """Retorna o sumário do capítulo N do Pro Git."""
    if chapter not in CHAPTERS:
        return (
            f"Capítulo {chapter} não encontrado. "
            f"Capítulos disponíveis: {', '.join(str(k) for k in sorted(CHAPTERS))}."
        )
    return CHAPTERS[chapter]


TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "lookup_chapter",
            "description": (
                "Retorna o sumário de um capítulo do livro Pro Git. "
                "Use quando o usuário pedir resumo de capítulo, "
                "navegação entre capítulos, ou referência a seções do livro."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "chapter": {
                        "type": "integer",
                        "description": "Número do capítulo (1 a 13)",
                    },
                },
                "required": ["chapter"],
            },
        },
    },
]


TOOL_REGISTRY: dict[str, Callable[..., str]] = {
    "lookup_chapter": lookup_chapter,
}


def run_tool_call(name: str, arguments_json: str) -> str:
    """Executa uma tool call e retorna o resultado como string."""
    if name not in TOOL_REGISTRY:
        return f"ERROR: tool '{name}' nao registrada"
    try:
        kwargs = json.loads(arguments_json)
        return TOOL_REGISTRY[name](**kwargs)
    except Exception as e:
        return f"ERROR ao executar {name}: {e}"
