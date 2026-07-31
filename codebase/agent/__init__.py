"""Agent `/recap` — khung AI cho hackathon (xem spec.md §4).

Export chính:
- recap: build_recap, render (quiz: build_quiz, render)
"""

from . import config, sources, tools, llm
from .recap import build_recap, render as render_recap
from .quiz import build_quiz, render as render_quiz
from .agent import run_agent
from .llm import make_client

__all__ = [
    "config", "sources", "tools", "llm",
    "build_recap", "render_recap",
    "build_quiz", "render_quiz",
    "run_agent", "make_client",
]
